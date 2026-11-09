import json
import unittest

from gate_pins import CRAP, NEW, OLD, project

MODULE = (
    "def f(a):\n    if a:\n        return 1\n    return 2\n\n\n"
    "def g(a, b, c):\n    if a:\n        return 1\n    if b:\n        return 2\n"
    "    if c:\n        return 3\n    return 4\n"
)
OTHER = "def h(a):\n    if a:\n        return 1\n    return 2\n"
COVERED_LINES = [1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13, 14]
F_ONLY_LINES = [1, 2, 3, 4]
G_LINES = [7, 8, 9, 10, 11, 12, 13, 14]
FLAGS = ("--lang", "python", "--no-color")
COVERAGE = ("--coverage-json", "cov.json")
NO_BRANCHES = (
    "[crap] ⚠️  no branch data in coverage file — using line coverage only.\n"
    "  For more accurate scores add [run] branch=True to .coveragerc.\n"
)
STALE = "[crap] ⚠️  coverage file may be stale: cov.json is older than the newest source file\n"
HEADER = (
    "GRADE          CRAP    CC   COV     FUNCTION\n"
    "─────────────────────────────────────────────────────────────────────────────────\n"
)
ALL_OK = (
    HEADER +
    "✅ ok             4.0    4  100.0%  m.py:7  g\n"
    "✅ ok             2.0    2  100.0%  m.py:1  f\n\n"
    "  2 function(s) · 2 ok · 0 warn · 0 fail\n"
    "  Max CRAP: 4.0  ·  Mean CRAP: 3.0\n"
    "  Thresholds: warn > 5.0  fail > 8.0\n"
)
ONE_FAIL = (
    HEADER +
    "❌ FAIL          20.0    4    0.0%  m.py:7  g\n"
    "✅ ok             2.0    2  100.0%  m.py:1  f\n\n"
    "  2 function(s) · 1 ok · 0 warn · 1 fail\n"
    "  Max CRAP: 20.0  ·  Mean CRAP: 11.0\n"
    "  Thresholds: warn > 5.0  fail > 8.0\n"
)
FAIL_AND_UNMEASURED = (
    HEADER +
    "❌ FAIL          20.0    4    0.0%  m.py:7  g\n"
    "❔ UNMEASURED       —    2      ?  o.py:1  h\n"
    "✅ ok             2.0    2  100.0%  m.py:1  f\n\n"
    "  3 function(s) · 1 ok · 0 warn · 1 fail\n"
    "  1 unmeasured in 1 file(s): o.py\n"
    "  Max CRAP: 20.0  ·  Mean CRAP: 11.0\n"
    "  Thresholds: warn > 5.0  fail > 8.0\n"
)
ONLY_UNMEASURED = (
    HEADER +
    "❔ UNMEASURED       —    2      ?  o.py:1  h\n\n"
    "  1 function(s) · 0 ok · 0 warn · 0 fail\n"
    "  1 unmeasured in 1 file(s): o.py\n"
    "  Thresholds: warn > 5.0  fail > 8.0\n"
)
UNMATCHED_REPORT = (
    "[crap] no scored function got a figure from the coverage report; it may have been made elsewhere "
    "or hold no figures for the scanned files\n"
)
UNMEASURED_ADVICE = (
    "\nUnmeasured functions fail the gate. Measure their files or take them out of the scan; "
    "the baseline keeps any entry they already have and records none for them.\n"
)
BEHIND_LINE = "\nThe baseline is behind. Run again with --update and commit crap.json.\n"
UPDATE_REFUSAL = "--update only lowers the baseline. It will not record a new or worse function.\n"
NOT_A_REPO = (
    "[crap] not inside a git repository: quality-gates looks at the files git would commit, "
    "so run it inside the project's repository, or run `git init` there first\n"
)
WORST_CASE_NOTICE = "[crap] No coverage source given — computing worst-case scores (0% coverage assumed).\n\n"
CONFLICTED = "<<<<<<< ours\n{}\n=======\n{\"x\": 1}\n>>>>>>> theirs\n"
NO_FOLDER = "[Errno 2] No such file or directory: 'nodir/b.json'\n"
BAD_JSON = "bad baseline crap.json: Expecting value: line 1 column 1 (char 0)\n"
NOT_AN_OBJECT = "bad baseline crap.json: must be an object, got list\n"
NULL_VALUE = "bad baseline crap.json: value for m.py::g must be a number, got NoneType\n"
TEXT_VALUE = "bad baseline crap.json: value for m.py::g must be a number, got str\n"
NAN_VALUE = "bad baseline crap.json: value for m.py::g must be a number, got NaN\n"
LOCKED = "[Errno 13] Permission denied: 'locked/b.json'\n"
UNRESOLVABLE = "[crap] cannot resolve path 'loop1': Symlink loop from '<ROOT>/loop1'\n"


def report(m_lines):
    files = {"m.py": {"executed_lines": m_lines, "missing_lines": [n for n in COVERED_LINES if n not in m_lines]}}
    return json.dumps({"files": files})


class PinTest(unittest.TestCase):

    def assertRan(self, ran, code, out, err=""):
        self.assertEqual(ran.triple(), (code, out, err))

    def measured(self, covered, extra=None):
        made = project(self, {"m.py": MODULE, "o.py": OTHER, **(extra or {})})
        made.write("cov.json", report(covered))
        made.date("m.py", OLD)
        made.date("o.py", OLD)
        made.date("cov.json", NEW)
        return made

    def covered(self):
        return self.measured(COVERED_LINES)

    def uncovered(self):
        return self.measured(F_ONLY_LINES)

    def go(self, made, *args):
        return made.run(CRAP, *FLAGS, *args)


class ReportTest(PinTest):

    def test_fully_covered_functions_print_the_table_and_exit_0(self):
        made = self.covered()
        self.assertRan(self.go(made, "m.py", *COVERAGE), 0, ALL_OK, NO_BRANCHES)

    def test_an_uncovered_function_over_the_threshold_prints_fail_and_exits_1(self):
        made = self.uncovered()
        self.assertRan(self.go(made, "m.py", *COVERAGE), 1, ONE_FAIL, NO_BRANCHES)

    def test_the_table_is_coloured_when_colour_is_not_switched_off(self):
        made = self.uncovered()
        ran = made.run(CRAP, "--lang", "python", "m.py", *COVERAGE)
        self.assertEqual(ran.code, 1)
        self.assertIn("\x1b[31m❌ FAIL      \x1b[0m    20.0    4    0.0%  m.py:7  g\n", ran.out)
        self.assertIn("\x1b[32m✅ ok        \x1b[0m     2.0    2  100.0%  m.py:1  f\n", ran.out)

    def test_a_function_without_a_coverage_figure_is_unmeasured_and_fails_the_gate_with_exit_1(self):
        made = self.uncovered()
        self.assertRan(self.go(made, ".", *COVERAGE), 1, FAIL_AND_UNMEASURED, NO_BRANCHES)

    def test_a_report_that_gives_no_scored_function_a_figure_warns_on_stderr_and_exits_1(self):
        made = self.uncovered()
        self.assertRan(self.go(made, "o.py", *COVERAGE), 1, ONLY_UNMEASURED, NO_BRANCHES + UNMATCHED_REPORT)

    def test_no_coverage_source_warns_on_stderr_and_assumes_zero_coverage(self):
        made = self.covered()
        expected = (
            HEADER +
            "❌ FAIL          20.0    4    0.0%  m.py:7  g\n"
            "⚠️  WARN           6.0    2    0.0%  m.py:1  f\n\n"
            "  2 function(s) · 0 ok · 1 warn · 1 fail\n"
            "  Max CRAP: 20.0  ·  Mean CRAP: 13.0\n"
            "  Thresholds: warn > 5.0  fail > 8.0\n"
        )
        self.assertRan(self.go(made, "m.py"), 1, expected, WORST_CASE_NOTICE)

    def test_the_no_coverage_flag_assumes_zero_coverage_without_the_stderr_notice(self):
        made = self.covered()
        ran = self.go(made, "m.py", "--no-coverage")
        self.assertEqual((ran.code, ran.err), (1, ""))
        self.assertIn("❌ FAIL          20.0    4    0.0%  m.py:7  g\n", ran.out)

    def test_the_json_format_prints_the_payload_to_stdout_and_exits_1_on_a_failure(self):
        made = self.uncovered()
        expected = json.dumps({
            "threshold": 8.0, "warn": 5.0, "pass": False, "coverage_source": "coverage-json",
            "functions": [
                {"file": "m.py", "name": "g", "line": 7, "cc": 4, "coverage": 0.0, "crap": 20.0,
                 "grade": "FAIL", "coverage_source": "coverage-json"},
                {"file": "m.py", "name": "f", "line": 1, "cc": 2, "coverage": 1.0, "crap": 2.0,
                 "grade": "ok", "coverage_source": "coverage-json"},
            ],
            "unmeasured": [], "skipped": [],
        }, indent=2) + "\n"
        self.assertRan(made.run(CRAP, "--lang", "python", "m.py", *COVERAGE, "--json"), 1, expected, NO_BRANCHES)


class CouldNotRunTest(PinTest):

    def test_a_coverage_report_that_does_not_exist_cannot_run_and_exits_2(self):
        made = self.covered()
        expected = "[crap] cannot open coverage file: [Errno 2] No such file or directory: 'nope.json'\n"
        self.assertRan(self.go(made, "m.py", "--coverage-json", "nope.json"), 2, "", expected)

    def test_an_empty_coverage_report_path_cannot_run_and_exits_2(self):
        made = self.covered()
        expected = "[crap] --coverage-json was given an empty path\n"
        self.assertRan(self.go(made, "m.py", "--coverage-json", ""), 2, "", expected)

    def test_an_empty_baseline_path_cannot_run_and_exits_2(self):
        made = self.covered()
        expected = "[crap] --baseline was given an empty path\n"
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", ""), 2, "", expected)

    def test_a_path_that_does_not_exist_cannot_run_and_exits_2(self):
        made = self.covered()
        self.assertRan(self.go(made, "nothing", "--no-coverage"), 2, "", "[crap] path not found: nothing\n")

    def test_a_folder_with_no_python_functions_cannot_run_and_exits_2(self):
        made = self.covered()
        made.write("sub/x.txt", "x")
        expected = (
            "[crap] no functions analysed in: sub\n"
            "  Check that the paths contain source files for the chosen --lang.\n"
            "  Use --allow-empty to suppress this error.\n"
        )
        self.assertRan(self.go(made, "sub", "--no-coverage"), 2, "", expected)

    def test_a_directory_that_is_not_a_git_repository_cannot_run_and_exits_2(self):
        made = project(self, {"m.py": MODULE}, repo=False)
        self.assertRan(self.go(made, "."), 2, "", WORST_CASE_NOTICE + NOT_A_REPO)

    def test_a_baseline_without_coverage_cannot_run_and_exits_2(self):
        made = self.covered()
        expected = "[crap] --baseline needs coverage data. Worst-case scores are a ranking, not a gate (ADR-001).\n"
        self.assertRan(self.go(made, "m.py", "--no-coverage", "--baseline", "crap.json"), 2, "", expected)

    def test_a_missing_baseline_prints_the_table_then_cannot_run_and_exits_2(self):
        made = self.uncovered()
        expected = ONE_FAIL + "No baseline at crap.json. Run with --update to create one.\n"
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json"), 2, expected, NO_BRANCHES)


class StaleReportTest(PinTest):

    def stale(self):
        made = self.uncovered()
        made.date("m.py", NEW)
        made.date("cov.json", OLD)
        return made

    def test_a_report_older_than_the_newest_source_warns_on_stderr_and_still_scores(self):
        made = self.stale()
        self.assertRan(self.go(made, "m.py", *COVERAGE), 1, ONE_FAIL, NO_BRANCHES + STALE)

    def test_a_stale_report_with_strict_freshness_cannot_run_and_exits_2_with_nothing_on_stdout(self):
        made = self.stale()
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--strict-freshness"), 2, "", NO_BRANCHES + STALE)

    def test_a_report_newer_than_every_source_gives_no_stale_warning(self):
        made = self.covered()
        self.assertEqual(self.go(made, "m.py", *COVERAGE, "--strict-freshness").err, NO_BRANCHES)


class BaselineTest(PinTest):

    def baselined(self, made, text):
        made.write("crap.json", text)
        return made

    def test_a_function_at_its_baseline_passes_with_the_ratchet_line_and_exits_0(self):
        made = self.baselined(self.uncovered(), '{\n  "m.py::g": 20.0\n}\n')
        expected = ONE_FAIL + "ratchet: 1 baselined function(s) over the threshold, none new or worse\n"
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json"), 0, expected, NO_BRANCHES)

    def test_a_new_failing_function_fails_as_new_and_exits_1(self):
        made = self.baselined(self.uncovered(), "{}\n")
        expected = ONE_FAIL + "FAIL m.py::g: 20.0, new\n"
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json"), 1, expected, NO_BRANCHES)

    def test_a_function_worse_than_its_baseline_fails_with_the_allowance_and_exits_1(self):
        made = self.baselined(self.uncovered(), '{\n  "m.py::g": 12.5\n}\n')
        expected = ONE_FAIL + "FAIL m.py::g: 20.0, baseline allows 12.5\n"
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json"), 1, expected, NO_BRANCHES)

    def test_a_function_that_dropped_below_the_threshold_is_reported_paid_and_exits_1(self):
        made = self.baselined(self.covered(), '{\n  "m.py::g": 20.0\n}\n')
        expected = ALL_OK + "PAID m.py::g: now at or below the threshold, baseline still says 20.0\n" + BEHIND_LINE
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json"), 1, expected, NO_BRANCHES)

    def test_an_unmeasured_function_fails_the_baseline_gate_with_the_advice_and_exits_1(self):
        made = self.baselined(self.uncovered(), '{\n  "m.py::g": 20.0,\n  "o.py::h": 7.0\n}\n')
        expected = FAIL_AND_UNMEASURED + "UNMEASURED o.py::h: no coverage figure\n" + UNMEASURED_ADVICE
        self.assertRan(self.go(made, "m.py", "o.py", *COVERAGE, "--baseline", "crap.json"), 1, expected, NO_BRANCHES)


class UpdateTest(PinTest):

    def test_update_creates_a_missing_baseline_from_the_failing_functions_byte_for_byte(self):
        made = self.uncovered()
        expected = ONE_FAIL + "baseline: 1 function(s) over the threshold\n"
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json", "--update"), 0, expected, NO_BRANCHES)
        self.assertEqual(made.read("crap.json"), b'{\n  "m.py::g": 20.0\n}\n')

    def test_update_lowers_a_paid_function_out_of_the_baseline_byte_for_byte(self):
        made = self.covered()
        made.write("crap.json", '{\n  "m.py::g": 20.0\n}\n')
        expected = ALL_OK + "baseline: 0 function(s) over the threshold\n"
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json", "--update"), 0, expected, NO_BRANCHES)
        self.assertEqual(made.read("crap.json"), b"{}\n")

    def test_update_refuses_a_new_failing_function_and_leaves_the_baseline_untouched(self):
        made = self.uncovered()
        made.write("crap.json", "{}\n")
        expected = ONE_FAIL + "FAIL m.py::g: 20.0, new\n" + UPDATE_REFUSAL
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json", "--update"), 1, expected, NO_BRANCHES)
        self.assertEqual(made.read("crap.json"), b"{}\n")

    def test_update_keeps_the_entry_of_an_unmeasured_function_and_exits_1_with_the_advice(self):
        made = self.uncovered()
        made.write("crap.json", '{\n  "m.py::g": 20.0,\n  "o.py::h": 7.0\n}\n')
        expected = FAIL_AND_UNMEASURED + "baseline: 2 function(s) over the threshold\nUNMEASURED o.py::h: no coverage figure\n" + UNMEASURED_ADVICE
        self.assertRan(self.go(made, "m.py", "o.py", *COVERAGE, "--baseline", "crap.json", "--update"), 1, expected, NO_BRANCHES)
        self.assertEqual(made.read("crap.json"), b'{\n  "m.py::g": 20.0,\n  "o.py::h": 7.0\n}\n')

    def test_update_with_an_empty_baseline_path_exits_2_and_writes_nothing(self):
        made = self.covered()
        expected = "[crap] --baseline was given an empty path\n"
        self.assertRan(self.go(made, "m.py", *COVERAGE, "--baseline", "", "--update"), 2, "", expected)

    def test_update_in_a_directory_that_is_not_a_git_repository_exits_2_and_writes_nothing(self):
        made = project(self, {"m.py": MODULE}, repo=False)
        made.write("cov.json", report(COVERED_LINES))
        ran = self.go(made, ".", *COVERAGE, "--baseline", "crap.json", "--update")
        self.assertEqual((ran.code, ran.out, ran.err.endswith(NOT_A_REPO)), (2, "", True))
        self.assertFalse(made.exists("crap.json"))


class BaselineFileTest(PinTest):

    def failing(self, baseline):
        made = self.uncovered()
        made.write("crap.json", baseline)
        return made

    def test_update_into_a_folder_that_does_not_exist_prints_the_table_and_the_os_error_and_exits_2(self):
        made = self.uncovered()
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "nodir/b.json", "--update")
        self.assertRan(ran, 2, ONE_FAIL + NO_FOLDER, NO_BRANCHES)

    def test_a_baseline_with_merge_conflict_markers_prints_the_table_then_cannot_run_and_exits_2(self):
        made = self.failing(CONFLICTED)
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json")
        self.assertRan(ran, 2, ONE_FAIL + BAD_JSON, NO_BRANCHES)

    def test_update_over_a_baseline_with_merge_conflict_markers_cannot_run_and_leaves_it_untouched(self):
        made = self.failing(CONFLICTED)
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json", "--update")
        self.assertRan(ran, 2, ONE_FAIL + BAD_JSON, NO_BRANCHES)
        self.assertEqual(made.read("crap.json"), CONFLICTED.encode("utf-8"))

    def test_a_baseline_that_is_not_a_json_object_prints_the_table_then_cannot_run_and_exits_2(self):
        made = self.failing("[]\n")
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json")
        self.assertRan(ran, 2, ONE_FAIL + NOT_AN_OBJECT, NO_BRANCHES)

    def test_update_over_a_baseline_that_is_not_a_json_object_cannot_run_and_leaves_it_untouched(self):
        made = self.failing("[]\n")
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json", "--update")
        self.assertRan(ran, 2, ONE_FAIL + NOT_AN_OBJECT, NO_BRANCHES)
        self.assertEqual(made.read("crap.json"), b"[]\n")

    def test_a_path_that_cannot_be_resolved_while_keying_prints_the_tagged_error_on_stderr_and_exits_2(self):
        made = self.failing("{}\n")
        ran = made.run_unresolvable(CRAP, *FLAGS, "m.py", *COVERAGE, "--baseline", "crap.json")
        self.assertRan(ran, 2, ONE_FAIL, NO_BRANCHES + UNRESOLVABLE)

    def test_update_with_a_path_that_cannot_be_resolved_prints_the_tagged_error_and_leaves_the_baseline(self):
        made = self.failing("{}\n")
        ran = made.run_unresolvable(CRAP, *FLAGS, "m.py", *COVERAGE, "--baseline", "crap.json", "--update")
        self.assertRan(ran, 2, ONE_FAIL, NO_BRANCHES + UNRESOLVABLE)
        self.assertEqual(made.read("crap.json"), b"{}\n")

    def test_a_baseline_value_of_null_prints_the_table_then_cannot_run_and_exits_2(self):
        made = self.failing('{"m.py::g": null}\n')
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json")
        self.assertRan(ran, 2, ONE_FAIL + NULL_VALUE, NO_BRANCHES)

    def test_update_over_a_baseline_value_of_null_cannot_run_and_leaves_it_untouched(self):
        made = self.failing('{"m.py::g": null}\n')
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json", "--update")
        self.assertRan(ran, 2, ONE_FAIL + NULL_VALUE, NO_BRANCHES)
        self.assertEqual(made.read("crap.json"), b'{"m.py::g": null}\n')

    def test_a_baseline_value_that_is_a_string_prints_the_table_then_cannot_run_and_exits_2(self):
        made = self.failing('{"m.py::g": "10"}\n')
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json")
        self.assertRan(ran, 2, ONE_FAIL + TEXT_VALUE, NO_BRANCHES)

    def test_update_over_a_baseline_value_that_is_a_string_cannot_run_and_leaves_it_untouched(self):
        made = self.failing('{"m.py::g": "10"}\n')
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json", "--update")
        self.assertRan(ran, 2, ONE_FAIL + TEXT_VALUE, NO_BRANCHES)
        self.assertEqual(made.read("crap.json"), b'{"m.py::g": "10"}\n')

    def test_a_baseline_value_of_nan_prints_the_table_then_cannot_run_and_exits_2(self):
        made = self.failing('{"m.py::g": NaN}\n')
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "crap.json")
        self.assertRan(ran, 2, ONE_FAIL + NAN_VALUE, NO_BRANCHES)

    def test_a_baseline_in_a_folder_that_cannot_be_searched_prints_the_table_then_cannot_run_and_exits_2(self):
        made = self.uncovered()
        made.lock("locked")
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "locked/b.json")
        self.assertRan(ran, 2, ONE_FAIL + LOCKED, NO_BRANCHES)

    def test_update_into_a_folder_that_cannot_be_searched_cannot_run_and_exits_2(self):
        made = self.uncovered()
        made.lock("locked")
        ran = self.go(made, "m.py", *COVERAGE, "--baseline", "locked/b.json", "--update")
        self.assertRan(ran, 2, ONE_FAIL + LOCKED, NO_BRANCHES)


if __name__ == "__main__":
    unittest.main()
