import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from quality_gates import comment_debt, complexity_scan

UNREADABLE_FILES = ("broken.py", "latin.py", "folder.py", "locked.py")
UNREADABLE_BY_SCAN = ("broken.py", "latin.py", "locked.py")
GATES = {
    "comment-debt": ["quality_gates.comment_debt"],
    "cc-check": ["quality_gates.quality_check", "."],
    "crap": ["quality_gates.crap", "--lang", "python", "--no-coverage", "--allow-empty", "."],
}
GATE_EXITS = {0, 1, 2}
RUNS_AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


def git(root, *argv):
    subprocess.run(["git", *argv], cwd=root, check=True, capture_output=True)


def run_gate(root, module_and_args):
    module, *args = module_and_args
    return subprocess.run([sys.executable, "-m", module, *args], cwd=root, capture_output=True, text=True)


@unittest.skipIf(RUNS_AS_ROOT, "root opens a file without read permission")
class EveryGateOnFilesItCannotReadTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        git(self.root, "init", "-q")
        (self.root / "good.py").write_text("def ok():\n    return 1\n")
        git(self.root, "add", "good.py")
        (self.root / "comment-debt.json").write_text("{}\n")
        (self.root / "broken.py").write_text("def f(:\n")
        (self.root / "latin.py").write_bytes(b'x = "\xff"\n')
        (self.root / "folder").mkdir()
        (self.root / "folder.py").symlink_to(self.root / "folder")
        locked = self.root / "locked.py"
        locked.write_text("# hidden\n")
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o644)

    def test_no_gate_prints_a_traceback_or_exits_outside_its_documented_codes(self):
        for gate, module_and_args in GATES.items():
            with self.subTest(gate=gate):
                done = run_gate(self.root, module_and_args)
                self.assertNotIn("Traceback", done.stdout + done.stderr)
                self.assertIn(done.returncode, GATE_EXITS)

    def test_comment_debt_names_each_file_it_cannot_read_as_unmeasured_and_fails(self):
        done = run_gate(self.root, GATES["comment-debt"])
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        for name in UNREADABLE_FILES:
            self.assertIn(f"UNMEASURED {name}: {comment_debt.UNREAD}\n", done.stdout)

    def test_cc_check_names_each_python_file_it_cannot_read_as_unmeasured_and_fails(self):
        done = run_gate(self.root, GATES["cc-check"])
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        for name in UNREADABLE_BY_SCAN:
            self.assertIn(f"UNMEASURED {name}: {complexity_scan.UNREAD}\n", done.stdout)

    def test_cc_check_does_not_end_its_report_with_clean_when_a_file_is_unmeasured(self):
        done = run_gate(self.root, GATES["cc-check"])
        self.assertNotIn("Clean. Exit 0.", done.stdout)
        self.assertIn("Unmeasured:         3", done.stdout)

    def test_crap_names_each_python_file_it_cannot_read_as_unmeasured_and_fails(self):
        done = run_gate(self.root, GATES["crap"])
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        for name in UNREADABLE_BY_SCAN:
            self.assertIn(f"UNMEASURED {name}: {complexity_scan.UNREAD}\n", done.stdout)

    def test_crap_json_lists_each_unreadable_python_file_under_unmeasured_and_fails(self):
        done = run_gate(self.root, [*GATES["crap"][:-1], "--json", "."])
        report = json.loads(done.stdout)
        self.assertEqual((done.returncode, report["pass"]), (1, False))
        self.assertEqual(report["unmeasured"], list(UNREADABLE_BY_SCAN))

    def test_crap_does_not_call_a_scan_of_only_unreadable_files_empty(self):
        done = run_gate(self.root, ["quality_gates.crap", "--lang", "python", "--no-coverage", "broken.py"])
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertNotIn("no functions analysed", done.stdout + done.stderr)

    def test_the_crap_summary_counts_and_names_the_files_it_could_not_read(self):
        done = run_gate(self.root, GATES["crap"])
        self.assertIn("  3 file(s) could not be read: broken.py, latin.py, locked.py", done.stdout)


if __name__ == "__main__":
    unittest.main()
