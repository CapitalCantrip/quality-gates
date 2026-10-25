import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from quality_gates.errors import ToolError, run_gate


class RunGateTest(unittest.TestCase):
    def test_the_exit_code_a_gate_returns_is_passed_through(self):
        self.assertEqual(run_gate(lambda argv, root: 1, ["x"], None, "[t] "), 1)

    def test_a_tool_error_is_printed_after_the_tag_and_becomes_exit_code_2(self):
        def gate(argv, root):
            raise ToolError("path not found: x")

        err = io.StringIO()
        with redirect_stderr(err):
            code = run_gate(gate, [], None, "[t] ")
        self.assertEqual((code, err.getvalue()), (2, "[t] path not found: x\n"))

    def test_an_error_that_is_not_a_tool_error_is_not_caught(self):
        def gate(argv, root):
            raise ValueError("bug")

        with self.assertRaises(ValueError):
            run_gate(gate, [], None, "[t] ")


ASCII_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONIOENCODING": ""}


class AsciiLocaleTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.module = Path(tmp.name) / "mod.py"
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
