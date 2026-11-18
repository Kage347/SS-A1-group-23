"""Exercise cd when the shell loses access to its current directory."""

import argparse
import os
from pathlib import Path
import stat
import tempfile
import unittest

from task3_reference import open_shell


class PermissionTests(unittest.TestCase):
    def setUp(self):
        fixture = tempfile.TemporaryDirectory(prefix="s3-permissions-", dir="/tmp")
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name).resolve()
        self.start = self.root / "start"
        self.home = self.root / "home"
        self.start.mkdir()
        self.home.mkdir()
        # Restore access from the harness before removing the fixture, even on failure.
        self.addCleanup(self.start.chmod, 0o700)

    def lock_current_directory(self, shell):
        messages, _ = shell.command("/bin/chmod 000 .")
        self.assertEqual(messages, [])
        self.assertEqual(stat.S_IMODE(self.start.stat().st_mode), 0)

    def assert_location(self, shell, path):
        self.assertEqual(shell.command("/bin/pwd"), ([str(path)], f"[{path} s3]$ "))

    def assert_history_unavailable(self, shell, path):
        expected = (["cd: previous directory unavailable"], f"[{path} s3]$ ")
        self.assertEqual(shell.command("cd -"), expected)
        self.assert_location(shell, path)

    def test_bare_cd_escapes_to_home(self):
        with open_shell(self.binary, self.start, self.home, self.root) as (shell, _):
            self.lock_current_directory(shell)
            messages, _ = shell.command("cd")
            self.assert_location(shell, self.home)
            self.assertEqual(messages, [])
            self.assert_history_unavailable(shell, self.home)

    def test_absolute_cd_discards_unrelated_history(self):
        with open_shell(self.binary, self.root, self.home, self.root) as (shell, _):
            shell.command("cd start")  # The previous directory is now the fixture root.
            self.lock_current_directory(shell)
            messages, _ = shell.command(f"cd {self.home}")
            self.assert_location(shell, self.home)
            self.assertEqual(messages, [])
            self.assert_history_unavailable(shell, self.home)

    def test_failed_move_keeps_previous_directory(self):
        with open_shell(self.binary, self.root, self.home, self.root) as (shell, _):
            shell.command("cd start")
            self.lock_current_directory(shell)
            messages, _ = shell.command(f"cd {self.root / 'missing'}")
            self.assertEqual(messages, ["cd: No such file or directory"])
            shell.command("cd -")
            self.assert_location(shell, self.root)
            self.assert_history_unavailable(shell, self.root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("run as an ordinary user so mode 000 denies directory access")
    PermissionTests.binary = args.binary.resolve()
    unittest.main(argv=[__file__], verbosity=2)
