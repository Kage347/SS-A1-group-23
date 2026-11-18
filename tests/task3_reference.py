"""Run interactive acceptance checks against a compiled s3 reference binary."""

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import termios
import time


class Terminal:
    def __init__(self, master, process):
        self.master = master
        self.process = process

    def read_prompt(self):
        # With echo disabled, the transcript is program output followed by its prompt.
        output = bytearray()
        deadline = time.monotonic() + 5
        while not output.endswith(b" s3]$ "):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.master], [], [], remaining)[0]:
                raise AssertionError(f"Timed out waiting for prompt: {bytes(output)!r}")
            chunk = os.read(self.master, 8192)
            if not chunk:
                raise AssertionError(f"Shell ended before prompt: {bytes(output)!r}")
            output.extend(chunk)
        text = output.decode(errors="replace").replace("\r\n", "\n")
        messages, _, prompt = text.rpartition("\n")
        return messages.splitlines(), prompt

    def command(self, command):
        os.write(self.master, (command + "\n").encode())
        return self.read_prompt()

    def exit(self):
        os.write(self.master, b"exit\n")
        return self.process.wait(timeout=5)


@contextmanager
def open_shell(binary, cwd, home, bin_dir):
    environment = dict(os.environ, LC_ALL="C", PATH=str(bin_dir) + ":" + os.defpath)
    environment.pop("OLDPWD", None)
    if home is None:
        environment.pop("HOME", None)
    else:
        environment["HOME"] = str(home)

    master, slave = pty.openpty()
    try:
        settings = termios.tcgetattr(slave)
        settings[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, settings)
        with subprocess.Popen([binary], cwd=cwd, env=environment,
                              stdin=slave, stdout=slave, stderr=slave) as process:
            terminal = Terminal(master, process)
            try:
                yield terminal, terminal.read_prompt()
            finally:
                if process.poll() is None:
                    process.kill()
    finally:
        os.close(slave)
        os.close(master)


class Checks:
    def __init__(self):
        self.count = 0

    def equal(self, label, actual, expected):
        if actual != expected:
            raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")
        self.count += 1

    def location(self, shell, expected, label):
        self.equal(label, shell.command("/bin/pwd"), ([str(expected)], f"[{expected} s3]$ "))

    def move(self, shell, command, expected, label, error=False):
        messages, prompt = shell.command(command)
        # cd - may optionally print its destination; it is not an error message.
        diagnostic = any(line for line in messages if line != str(expected))
        self.equal(label + " diagnostic", diagnostic, error)
        self.equal(label + " prompt", prompt, f"[{expected} s3]$ ")
        self.location(shell, expected, label + " actual cwd")


def check_directory_changes(shell, startup, root, home, checks):
    a = root / "A"
    b = a / "B"
    checks.equal("startup", startup, ([], f"[{root} s3]$ "))
    checks.location(shell, root, "initial pwd")
    checks.move(shell, "cd -", root, "first-use history")
    checks.move(shell, "cd A", a, "relative A")
    checks.move(shell, "cd B", b, "relative B")
    checks.move(shell, "cd missing", b, "missing directory", error=True)
    checks.move(shell, "cd -", a, "toggle after failure")
    checks.move(shell, "cd -", b, "second toggle")

    shell.command("/bin/echo moved > result.txt")
    results = {file.relative_to(root): file.read_bytes() for file in root.rglob("result.txt")}
    checks.equal("relative redirection after cd", results, {Path("A/B/result.txt"): b"moved\n"})

    checks.move(shell, "cd .", b, "dot")
    checks.move(shell, "cd ..", a, "parent")
    checks.move(shell, "cd /", Path("/"), "root")
    checks.move(shell, "cd", home, "bare cd")
    checks.move(shell, f"cd {b}", b, "absolute path")
    checks.move(shell, "cd A B", b, "excess operands", error=True)
    checks.move(shell, "cd result.txt", b, "file operand", error=True)
    checks.move(shell, "cd -", home, "history after two failures")


def check_existing_commands(shell, home, checks):
    checks.equal("blank command", shell.command("   "), ([], f"[{home} s3]$ "))
    for command, expected in [
        ("/bin/echo one two", ["one two"]),
        ("cdprobe", ["external command"]),
    ]:
        messages, _ = shell.command(command)
        checks.equal(command, messages, expected)
    messages, _ = shell.command("s3-no-such-command")
    checks.equal("unknown command diagnostic", bool(messages), True)
    messages, _ = shell.command("/bin/echo recovered")
    checks.equal("recovery after unknown command", messages, ["recovered"])

    for command, name, expected in [
        ("/bin/echo first > file", "file", b"first\n"),
        ("/bin/echo second > file", "file", b"second\n"),
        ("/bin/echo third >> file", "file", b"second\nthird\n"),
        ("/bin/echo new >> new", "new", b"new\n"),
    ]:
        shell.command(command)
        checks.equal(command, (home / name).read_bytes(), expected)

    messages, _ = shell.command("/bin/cat < file")
    checks.equal("input redirection", messages, ["second", "third"])
    for command in ("/bin/cat < missing", "/bin/echo x >", "/bin/echo x > ."):
        messages, _ = shell.command(command)
        checks.equal(command + " diagnostic", bool(messages), True)
    checks.location(shell, home, "recovery after redirection errors")
    checks.equal("exit status", shell.exit(), 0)


def run(binary, root):
    checks = Checks()
    home = root / "test-home"
    home.mkdir()
    (root / "A" / "B").mkdir(parents=True)

    bin_dir = root / "bin"
    bin_dir.mkdir()
    probe = bin_dir / "cdprobe"
    probe.write_text("#!/bin/sh\necho 'external command'\n")
    probe.chmod(0o755)

    with open_shell(binary, root, home, bin_dir) as (shell, startup):
        check_directory_changes(shell, startup, root, home, checks)
        check_existing_commands(shell, home, checks)

    for value, label in [(None, "unset HOME"), ("", "empty HOME")]:
        with open_shell(binary, root, value, bin_dir) as (shell, _):
            checks.move(shell, "cd A", root / "A", label + " setup")
            checks.move(shell, "cd", root / "A", label, error=True)
            checks.move(shell, "cd -", root, label + " retained history")
            shell.exit()

    deep = root
    while len(str(deep)) <= 300:
        deep = deep / ("x" * 60)
        deep.mkdir()
    with open_shell(binary, deep, home, bin_dir) as (shell, _):
        checks.location(shell, deep, "long startup cwd")
        checks.move(shell, "cd ..", deep.parent, "leave long cwd")
        checks.move(shell, "cd -", deep, "restore long cwd")
        shell.exit()
    print(f"All {checks.count} assertions passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="path to the compiled s3 reference binary")
    args = parser.parse_args()
    # A simple path lets the fixture exercise the starter shell's space-only tokenizer.
    with tempfile.TemporaryDirectory(prefix="s3-cd-", dir="/tmp") as fixture:
        run(args.binary.resolve(), Path(fixture).resolve())
