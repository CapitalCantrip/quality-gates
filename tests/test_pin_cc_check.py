import unittest

from gate_pins import CC_CHECK, project

BRANCHY = "def f(a):\n    if a:\n        return 1\n    return 2\n"
SUMMARY_ONE = "  Files analysed:     1\n  Functions checked:  1\n"
CLEAN_REPORT = (
    "\n=== Cyclomatic Complexity Report (threshold: CC > 8) ===\n\n"
    "  All functions at or below threshold. ✓\n\n"
    "SUMMARY:\n" + SUMMARY_ONE +
    "  Above threshold:    0\n  At/below threshold: 1\n\n  → Clean. Exit 0.\n"
)
FLAGGED_ONE = (
    "\n=== Cyclomatic Complexity Report (threshold: CC > 1) ===\n\n"
    "FLAGGED — 1 function(s) above threshold:\n\n"
    "  CC=  2  b.py:1  f\n\n"
    "SUMMARY:\n" + SUMMARY_ONE +
    "  Above threshold:    1\n  At/below threshold: 0\n\n  → Refactoring needed. Exit 1.\n"
)
FLAGGED_TWO = (
    "\n=== Cyclomatic Complexity Report (threshold: CC > 1) ===\n\n"
    "FLAGGED — 2 function(s) above threshold:\n\n"
    "  CC=  2  b.py:1  f\n  CC=  2  c.py:1  f\n\n"
    "SUMMARY:\n  Files analysed:     2\n  Functions checked:  2\n"
    "  Above threshold:    2\n  At/below threshold: 0\n\n  → Refactoring needed. Exit 1.\n"
)
NOT_A_REPO = (
    "ERROR: not inside a git repository: quality-gates looks at the files git would commit, "
    "so run it inside the project's repository, or run `git init` there first\n"
)
BEHIND_LINE = "\nThe baseline is behind. Run again with --update and commit cc.json.\n"
UPDATE_REFUSAL = "--update only lowers the baseline. It will not record a new or worse function.\n"
LOW = ("--threshold", "1")
CONFLICTED = "<<<<<<< ours\n{}\n=======\n{\"x\": 1}\n>>>>>>> theirs\n"
NO_FOLDER = "[Errno 2] No such file or directory: 'nodir/b.json'\n"
BAD_JSON = "bad baseline cc.json: Expecting value: line 1 column 1 (char 0)\n"
NOT_AN_OBJECT = "bad baseline cc.json: must be an object, got list\n"
UNRESOLVABLE = "ERROR: cannot resolve path 'loop1': Symlink loop from '<ROOT>/loop1'\n"


class PinTest(unittest.TestCase):

    def assertRan(self, ran, code, out, err=""):
        self.assertEqual(ran.triple(), (code, out, err))

    def two_functions(self, baseline=None):
        made = project(self, {"b.py": BRANCHY, "c.py": BRANCHY})
        if baseline is not None:
            made.write("cc.json", baseline)
        return made


class ReportTest(PinTest):

    def test_a_clean_tree_prints_the_clean_report_and_exits_0(self):
        made = project(self, {"b.py": BRANCHY})
        self.assertRan(made.run(CC_CHECK, "b.py"), 0, CLEAN_REPORT)

    def test_a_function_above_the_threshold_prints_the_flagged_report_and_exits_1(self):
        made = project(self, {"b.py": BRANCHY})
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py"), 1, FLAGGED_ONE)

    def test_flagged_functions_of_equal_score_are_listed_in_file_order(self):
        made = self.two_functions()
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "c.py"), 1, FLAGGED_TWO)

    def test_the_json_format_prints_every_function_to_stdout_and_exits_0(self):
        made = project(self, {"b.py": BRANCHY})
        expected = (
            '[\n  {\n    "file": "b.py",\n    "name": "f",\n    "fullname": "f",\n'
            '    "type": "Function",\n    "complexity": 2,\n    "line": 1,\n'
            '    "above_threshold": true\n  }\n]\n'
        )
        self.assertRan(made.run(CC_CHECK, *LOW, "--format", "json", "b.py"), 0, expected)


class CouldNotRunTest(PinTest):

    def test_a_path_that_does_not_exist_cannot_run_and_exits_2(self):
        made = project(self, {"b.py": BRANCHY})
        self.assertRan(made.run(CC_CHECK, "nothing"), 2, "", "ERROR: path not found: nothing\n")

    def test_a_folder_with_no_python_files_cannot_run_and_exits_2(self):
        made = project(self, {"sub/x.txt": "x"})
        self.assertRan(made.run(CC_CHECK, "sub"), 2, "", "No Python files found.\n")

    def test_a_directory_that_is_not_a_git_repository_cannot_run_and_exits_2(self):
        made = project(self, {"b.py": BRANCHY}, repo=False)
        self.assertRan(made.run(CC_CHECK, "."), 2, "", NOT_A_REPO)

    def test_an_empty_baseline_path_cannot_run_and_exits_2(self):
        made = project(self, {"b.py": BRANCHY})
        self.assertRan(made.run(CC_CHECK, "b.py", "--baseline", ""), 2, "", "ERROR: --baseline was given an empty path\n")

    def test_a_missing_baseline_prints_the_report_then_cannot_run_and_exits_2(self):
        made = project(self, {"b.py": BRANCHY})
        expected = CLEAN_REPORT + "No baseline at cc.json. Run with --update to create one.\n"
        self.assertRan(made.run(CC_CHECK, "b.py", "--baseline", "cc.json"), 2, expected)

    def test_update_without_a_baseline_flag_cannot_run_and_exits_2_with_the_usage_error(self):
        made = project(self, {"b.py": BRANCHY})
        ran = made.run(CC_CHECK, "b.py", "--update")
        self.assertEqual((ran.code, ran.out), (2, ""))
        self.assertTrue(ran.err.startswith("usage: "))
        self.assertTrue(ran.err.endswith(": error: --update needs --baseline\n"))


class BaselineTest(PinTest):

    def test_a_function_at_its_baseline_passes_with_the_ratchet_line_and_exits_0(self):
        made = project(self, {"b.py": BRANCHY})
        made.write("cc.json", '{\n  "b.py::f": 2\n}\n')
        expected = FLAGGED_ONE + "ratchet: 1 baselined function(s) over the threshold, none new or worse\n"
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "--baseline", "cc.json"), 0, expected)

    def test_a_new_function_over_the_threshold_fails_as_new_and_exits_1(self):
        made = self.two_functions('{\n  "b.py::f": 2\n}\n')
        expected = FLAGGED_TWO + "FAIL c.py::f: 2, new\n"
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "c.py", "--baseline", "cc.json"), 1, expected)

    def test_a_function_worse_than_its_baseline_fails_with_the_allowance_and_exits_1(self):
        made = self.two_functions('{\n  "b.py::f": 1,\n  "c.py::f": 2\n}\n')
        expected = FLAGGED_TWO + "FAIL b.py::f: 2, baseline allows 1\n"
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "c.py", "--baseline", "cc.json"), 1, expected)

    def test_a_function_better_than_its_baseline_is_reported_paid_with_the_update_advice_and_exits_1(self):
        made = self.two_functions('{\n  "b.py::f": 5,\n  "c.py::f": 2\n}\n')
        expected = FLAGGED_TWO + "PAID b.py::f: now 2, baseline still says 5\n" + BEHIND_LINE
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "c.py", "--baseline", "cc.json"), 1, expected)

    def test_a_function_that_dropped_below_the_threshold_is_reported_paid_as_at_or_below_and_exits_1(self):
        made = project(self, {"b.py": BRANCHY})
        made.write("cc.json", '{\n  "b.py::f": 2\n}\n')
        expected = CLEAN_REPORT + "PAID b.py::f: now at or below the threshold, baseline still says 2\n" + BEHIND_LINE
        self.assertRan(made.run(CC_CHECK, "b.py", "--baseline", "cc.json"), 1, expected)

    def test_a_new_function_is_reported_before_any_paid_one_and_the_paid_one_is_not_mentioned(self):
        made = self.two_functions('{\n  "b.py::f": 5\n}\n')
        expected = FLAGGED_TWO + "FAIL c.py::f: 2, new\n"
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "c.py", "--baseline", "cc.json"), 1, expected)

    def test_the_json_format_sends_the_ratchet_line_to_stderr(self):
        made = project(self, {"b.py": BRANCHY})
        made.write("cc.json", '{\n  "b.py::f": 2\n}\n')
        ran = made.run(CC_CHECK, *LOW, "--format", "json", "b.py", "--baseline", "cc.json")
        self.assertEqual(ran.code, 0)
        self.assertTrue(ran.out.startswith("[\n  {\n"))
        self.assertEqual(ran.err, "ratchet: 1 baselined function(s) over the threshold, none new or worse\n")


class UpdateTest(PinTest):

    def test_update_creates_a_missing_baseline_from_the_tree_byte_for_byte(self):
        made = project(self, {"b.py": BRANCHY})
        expected = FLAGGED_ONE + "baseline: 1 function(s) over the threshold\n"
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "--baseline", "cc.json", "--update"), 0, expected)
        self.assertEqual(made.read("cc.json"), b'{\n  "b.py::f": 2\n}\n')

    def test_update_lowers_a_paid_function_and_drops_one_no_longer_over_the_threshold_byte_for_byte(self):
        made = self.two_functions('{\n  "b.py::f": 5,\n  "c.py::f": 2,\n  "gone.py::g": 9\n}\n')
        expected = FLAGGED_TWO + "baseline: 2 function(s) over the threshold\n"
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "c.py", "--baseline", "cc.json", "--update"), 0, expected)
        self.assertEqual(made.read("cc.json"), b'{\n  "b.py::f": 2,\n  "c.py::f": 2\n}\n')

    def test_update_refuses_a_new_function_with_the_fail_line_and_leaves_the_baseline_untouched(self):
        original = '{\n  "b.py::f": 2\n}\n'
        made = self.two_functions(original)
        expected = FLAGGED_TWO + "FAIL c.py::f: 2, new\n" + UPDATE_REFUSAL
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "c.py", "--baseline", "cc.json", "--update"), 1, expected)
        self.assertEqual(made.read("cc.json"), original.encode("utf-8"))

    def test_update_with_an_empty_baseline_path_exits_2_and_writes_nothing(self):
        made = project(self, {"b.py": BRANCHY})
        ran = made.run(CC_CHECK, "b.py", "--baseline", "", "--update")
        self.assertEqual(ran.triple(), (2, "", "ERROR: --baseline was given an empty path\n"))

    def test_update_in_a_directory_that_is_not_a_git_repository_exits_2_and_writes_nothing(self):
        made = project(self, {"b.py": BRANCHY}, repo=False)
        self.assertRan(made.run(CC_CHECK, ".", "--baseline", "cc.json", "--update"), 2, "", NOT_A_REPO)
        self.assertFalse(made.exists("cc.json"))


class BaselineFileTest(PinTest):

    def flagged(self, baseline):
        made = project(self, {"b.py": BRANCHY})
        made.write("cc.json", baseline)
        return made

    def test_update_into_a_folder_that_does_not_exist_prints_the_report_and_the_os_error_and_exits_2(self):
        made = project(self, {"b.py": BRANCHY})
        ran = made.run(CC_CHECK, *LOW, "b.py", "--baseline", "nodir/b.json", "--update")
        self.assertRan(ran, 2, FLAGGED_ONE + NO_FOLDER)

    def test_a_baseline_with_merge_conflict_markers_prints_the_report_then_cannot_run_and_exits_2(self):
        made = self.flagged(CONFLICTED)
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "--baseline", "cc.json"), 2, FLAGGED_ONE + BAD_JSON)

    def test_update_over_a_baseline_with_merge_conflict_markers_cannot_run_and_leaves_it_untouched(self):
        made = self.flagged(CONFLICTED)
        ran = made.run(CC_CHECK, *LOW, "b.py", "--baseline", "cc.json", "--update")
        self.assertRan(ran, 2, FLAGGED_ONE + BAD_JSON)
        self.assertEqual(made.read("cc.json"), CONFLICTED.encode("utf-8"))

    def test_a_baseline_that_is_not_a_json_object_prints_the_report_then_cannot_run_and_exits_2(self):
        made = self.flagged("[]\n")
        self.assertRan(made.run(CC_CHECK, *LOW, "b.py", "--baseline", "cc.json"), 2, FLAGGED_ONE + NOT_AN_OBJECT)

    def test_update_over_a_baseline_that_is_not_a_json_object_cannot_run_and_leaves_it_untouched(self):
        made = self.flagged("[]\n")
        ran = made.run(CC_CHECK, *LOW, "b.py", "--baseline", "cc.json", "--update")
        self.assertRan(ran, 2, FLAGGED_ONE + NOT_AN_OBJECT)
        self.assertEqual(made.read("cc.json"), b"[]\n")

    def test_a_path_that_cannot_be_resolved_while_keying_prints_the_tagged_error_on_stderr_and_exits_2(self):
        made = self.flagged("{}\n")
        ran = made.run_unresolvable(CC_CHECK, *LOW, "b.py", "--baseline", "cc.json")
        self.assertRan(ran, 2, FLAGGED_ONE, UNRESOLVABLE)

    def test_update_with_a_path_that_cannot_be_resolved_prints_the_tagged_error_and_leaves_the_baseline(self):
        made = self.flagged("{}\n")
        ran = made.run_unresolvable(CC_CHECK, *LOW, "b.py", "--baseline", "cc.json", "--update")
        self.assertRan(ran, 2, FLAGGED_ONE, UNRESOLVABLE)
        self.assertEqual(made.read("cc.json"), b"{}\n")


if __name__ == "__main__":
    unittest.main()
