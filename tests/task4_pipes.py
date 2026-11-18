"""Black-box Task 4 checks. Run: python3 tests/task4_pipes.py ./s3.

Uses the sibling Task 3 Terminal reader. All subprocesses run in isolated process
groups; timeout/final cleanup kills the entire group, including pipeline children.
"""

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import pty
import resource
import shutil
import signal
import subprocess
import tempfile
import termios

from task3_reference import Terminal


PHRASES = b"burn quietly\nstill water\nbright embers burn\nclouds drift\nburn bright\n"
SORTED = b"".join(sorted(PHRASES.splitlines(keepends=True)))
RECOVERED = b"__S3_PIPELINE_RECOVERED_37A6__\n"


def check(condition, label):
    if not condition:
        raise AssertionError(label)


def equal(actual, expected, label):
    check(actual == expected, f"{label}: expected {expected!r}, got {actual!r}")


def cleanup(process):
    # Also try after the shell exits, because forgotten children can remain.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if process.poll() is None:
        process.wait(timeout=2)


class Suite:
    def __init__(self, binary, root, timeout):
        self.binary, self.root, self.timeout = binary, root, timeout
        self.env = dict(os.environ, LC_ALL="C", PATH=os.defpath, HOME=str(root / "home"))
        self.env.pop("OLDPWD", None)

    def fixture(self, name):
        directory = self.root / name
        (directory / "txt").mkdir(parents=True)
        (directory / "txt/phrases.txt").write_bytes(PHRASES)
        return directory

    def script(self, directory, commands, fd_limit=None):
        def limit_fds():
            _, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            resource.setrlimit(resource.RLIMIT_NOFILE, (fd_limit, hard))

        source = "\n".join([*commands, "echo " + RECOVERED.decode().strip(), "exit", ""]).encode()
        process = subprocess.Popen([str(self.binary)], cwd=directory, env=self.env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True,
                                   preexec_fn=limit_fds if fd_limit is not None else None)
        try:
            try:
                output, errors = process.communicate(source, timeout=self.timeout)
            except subprocess.TimeoutExpired as exc:
                cleanup(process)
                output, errors = process.communicate(timeout=2)
                raise AssertionError(f"timeout: {commands!r}; stdout={output[-1000:]!r}; "
                                     f"stderr={errors[-1000:]!r}") from exc
            equal(process.returncode, 0, "shell exit status")
            check(RECOVERED in output, "normal command loop did not recover")
            return output.replace(f"[{directory} s3]$ ".encode(), b""), errors
        finally:
            cleanup(process)

    @contextmanager
    def terminal(self, directory):
        master, slave = pty.openpty()
        settings = termios.tcgetattr(slave)
        settings[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, settings)
        try:
            process = subprocess.Popen([str(self.binary)], cwd=directory, env=self.env,
                                       stdin=slave, stdout=slave, stderr=slave,
                                       start_new_session=True)
        except BaseException:
            os.close(master)
            raise
        finally:
            os.close(slave)
        try:
            terminal = Terminal(master, process)
            yield terminal, terminal.read_prompt()
        finally:
            cleanup(process)
            os.close(master)

    def lecturer_examples(self):
        directory = self.fixture("lecturer")
        output, errors = self.script(directory, [
            "cat txt/phrases.txt | sort > txt/phrases_sorted.txt",
            "tr a-z A-Z < txt/phrases.txt | grep BURN | sort | wc -l",
        ])
        equal((directory / "txt/phrases_sorted.txt").read_bytes(), SORTED, "literal two-stage example")
        equal(output.removesuffix(RECOVERED).strip(), b"3", "literal four-stage example")
        equal(errors, b"", "lecturer-example diagnostics")

    def eleven_stages(self):
        directory = self.fixture("eleven")
        stages = ["cat txt/phrases.txt"] + ["cat"] * 9 + ["sort > result.txt"]
        self.script(directory, [" | ".join(stages)])
        equal((directory / "result.txt").read_bytes(), SORTED, "eleven-stage bytes")

    def midpoint_redirection(self):
        directory = self.fixture("midpoint")
        target = directory / "middle.txt"
        target.write_bytes(b"stale contents\n")
        self.script(directory, ["cat txt/phrases.txt | sort > middle.txt | wc -l > count.txt"])
        equal(target.read_bytes(), SORTED, "midpoint truncation")
        equal((directory / "count.txt").read_bytes().strip(), b"0", "midpoint downstream EOF")
        self.script(directory, ["cat txt/phrases.txt | sort >> middle.txt | wc -l > append-count.txt"])
        equal(target.read_bytes(), SORTED + SORTED, "midpoint append")
        equal((directory / "append-count.txt").read_bytes().strip(), b"0", "append downstream EOF")

    def large_transfer(self):
        directory = self.fixture("large")
        size = 6 * 1024 * 1024
        pattern = b"pipeline transfer 0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\n"
        data = (pattern * ((size + len(pattern) - 1) // len(pattern)))[:size]
        (directory / "large.bin").write_bytes(data)
        self.script(directory, [
            "cat large.bin | cat | cat | cat > copy.bin",
            "cat large.bin | cat | wc -c > count.txt",
        ])
        check((directory / "copy.bin").read_bytes() == data, "6 MiB exact byte transfer")
        equal((directory / "count.txt").read_bytes().strip(), str(size).encode(), "6 MiB wc -c")

    def early_exit(self):
        directory = self.fixture("early-exit")
        output, errors = self.script(directory, ["yes | head -n 1"])
        equal(errors, b"", "early reader exit diagnostics")
        equal(output, b"y\n" + RECOVERED, "yes | head -n 1 prints directly and recovers")

    def failed_stage(self):
        directory = self.fixture("failed-stage")
        (directory / "large.txt").write_bytes(b"upstream data\n" * 100000)
        missing = "s3-no-such-middle-37a6"
        _, errors = self.script(directory, [
            f"cat large.txt | {missing} | wc -c > missing.txt",
            "cat txt/phrases.txt | cat > . | wc -c > failed-open.txt",
        ])
        check(missing.encode() in errors, "unknown-executable diagnostic must name the command")
        check(b"open:" in errors, "failed redirection must report its open error")
        for name in ("missing.txt", "failed-open.txt"):
            equal((directory / name).read_bytes().strip(), b"0", "downstream EOF after failed stage")

    def malformed(self):
        directory = self.fixture("malformed")
        target = directory / "sentinel.txt"
        cases = [
            ("| echo bad > leading.txt", b"empty"),
            ("echo bad > sentinel.txt |", b"empty"),
            ("cat txt/phrases.txt > sentinel.txt | | cat > empty.txt", b"empty"),
            ("cat txt/phrases.txt > sentinel.txt | cat >", b"redirection"),
        ]
        for command, kind in cases:
            target.write_bytes(b"KEEP THIS FILE\n")
            _, errors = self.script(directory, [command])
            check(kind in errors.lower(), f"diagnostic must identify {kind.decode()} syntax")
            equal(target.read_bytes(), b"KEEP THIS FILE\n", "reject whole syntax before truncating")
            for name in ("leading.txt", "empty.txt"):
                check(not (directory / name).exists(), "malformed pipeline created an output file")

    def resource_failure(self):
        directory = self.fixture("resource-failure")
        # stdio 0,1,2 plus history 3 leaves only 4,5: the second pipe must fail.
        _, errors = self.script(directory, [
            "sleep 15 | cat | cat",
            "cat txt/phrases.txt | sort > recovered.txt",
        ], fd_limit=6)
        check(b"pipe" in errors.lower(), "pipe allocation failure must be diagnosed")
        equal((directory / "recovered.txt").read_bytes(), SORTED,
              "two-stage pipeline still works after resource failure")

    def cwd_and_prompt(self):
        directory = self.fixture("interactive")
        work = directory / "work"
        work.mkdir()
        with self.terminal(directory) as (terminal, startup):
            equal(startup, ([], f"[{directory} s3]$ "), "initial prompt")
            equal(terminal.command("cd work"), ([], f"[{work} s3]$ "), "parent cd")
            equal(terminal.command("pwd | cat"), ([str(work)], f"[{work} s3]$ "), "pipeline cwd")
            equal(terminal.command("cat < ../txt/phrases.txt | sort > after-cd.txt"),
                  ([], f"[{work} s3]$ "), "prompt after relative redirection")
            equal((work / "after-cd.txt").read_bytes(), SORTED, "output in changed directory")
            check(not (directory / "after-cd.txt").exists(), "output appeared in former directory")
            messages, prompt = terminal.command("cat | | cat")
            check(any("empty" in line.lower() for line in messages), "PTY empty-stage diagnostic")
            equal(prompt, f"[{work} s3]$ ", "prompt after syntax error")
            equal(terminal.command("cd .."), ([], f"[{directory} s3]$ "), "cd after pipeline error")
            equal(terminal.exit(), 0, "interactive exit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--timeout", type=float, default=6.0, help="noninteractive session timeout")
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(f"not executable: {binary}")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    missing = [name for name in ("cat", "sort", "tr", "grep", "wc", "yes", "head", "echo", "pwd", "sleep")
               if shutil.which(name, path=os.defpath) is None]
    if missing:
        parser.error("missing system utilities: " + ", ".join(missing))
    failed = []
    with tempfile.TemporaryDirectory(prefix="s3-pipes-tests-", dir="/tmp") as fixture:
        root = Path(fixture).resolve()
        (root / "home").mkdir()
        suite = Suite(binary, root, args.timeout)
        cases = [suite.lecturer_examples, suite.eleven_stages, suite.midpoint_redirection,
                 suite.large_transfer, suite.early_exit, suite.failed_stage,
                 suite.malformed, suite.resource_failure, suite.cwd_and_prompt]
        for case in cases:
            try:
                case()
                print("PASS", case.__name__)
            except (AssertionError, OSError, subprocess.SubprocessError) as exc:
                failed.append(case.__name__)
                print("FAIL", case.__name__, "-", exc)
    print(f"{len(cases)-len(failed)}/{len(cases)} pipeline groups passed.")
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
