import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ASCII_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONIOENCODING": ""}


class AsciiLocaleTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.module = Path(tmp.name) / "mod.py"
        subprocess.run(["git", "init", "-q", tmp.name], check=True)
        self.module.write_text("def f(x):\n    if x:\n        return 1\n    return 2\n", encoding="utf-8")

    def run_module(self, module, *argv):
        env = {**os.environ, **ASCII_LOCALE}
        return subprocess.run(
            [sys.executable, "-m", module, *argv],
            capture_output=True, env=env, cwd=self.module.parent,
        )

    def test_crap_prints_its_table_and_notices_under_an_ascii_locale(self):
        done = self.run_module("quality_gates.crap", "--lang", "python", str(self.module))
        self.assertNotIn(b"Traceback", done.stderr)
        self.assertEqual(done.returncode, 0)
        self.assertIn("─".encode("utf-8"), done.stdout)
        self.assertIn("⚠️".encode("utf-8"), done.stdout)
        self.assertIn("—".encode("utf-8"), done.stderr)

    def test_cc_check_prints_its_report_under_an_ascii_locale(self):
        done = self.run_module("quality_gates.quality_check", str(self.module))
        self.assertNotIn(b"Traceback", done.stderr)
        self.assertEqual(done.returncode, 0)
        self.assertIn("✓".encode("utf-8"), done.stdout)


if __name__ == "__main__":
    unittest.main()
