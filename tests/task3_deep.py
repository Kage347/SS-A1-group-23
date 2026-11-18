"""Check the displayed pathname and actual directory across the system path limit."""

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from task3_reference import open_shell


@contextmanager
def deep_directory(root):
    limit = os.pathconf(root, "PC_PATH_MAX")
    if limit <= 0:
        raise RuntimeError("This test needs a filesystem with a reported path limit")
    component = "x" * min(200, os.pathconf(root, "PC_NAME_MAX"))
    original = os.open(".", os.O_RDONLY)
    try:
        os.chdir(root)
        path = root
        # Build the expected physical name from a resolved root and plain components.
        while len(os.fsencode(path)) < limit:
            os.mkdir(component)
            os.chdir(component)
            path = path / component
        Path("level").write_text("5\n")
        Path("../level").write_text("4\n")
        yield path
    finally:
        os.fchdir(original)
        os.close(original)


def run(binary):
    with tempfile.TemporaryDirectory(prefix="s3-deep-", dir="/tmp") as temporary:
        root = Path(temporary).resolve()
        with deep_directory(root) as deep, open_shell(binary, ".", root, root) as (shell, startup):
            steps = [(None, deep, "5"), ("cd ..", deep.parent, "4"), ("cd -", deep, "5")]
            passed = True
            for command, path, level in steps:
                messages, prompt = startup if command is None else shell.command(command)
                # The marker identifies the directory even when the prompt is wrong.
                marker, next_prompt = shell.command("/bin/cat level")
                expected = f"[{path} s3]$ "
                prompts_match = prompt == expected and next_prompt == expected
                print(f"{command or 'startup'}: marker {marker}, expected {level}, "
                      f"full prompts match: {prompts_match}")
                if messages and messages != [str(path)]:
                    print(f"  shell output: {messages}")
                    passed = False
                if marker != [level] or not prompts_match:
                    passed = False
            return shell.exit() == 0 and passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.binary.resolve()) else 1)
