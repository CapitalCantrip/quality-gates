import io
import unittest
from contextlib import redirect_stderr

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


if __name__ == "__main__":
    unittest.main()
