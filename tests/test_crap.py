import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from quality_gates import crap


def call(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            crap.main(argv)
        except SystemExit as stop:
            return stop.code, out.getvalue(), err.getvalue()
    raise AssertionError("main did not exit")


def result(name, grade, score=1.0):
    return crap.FunctionResult("mod.py", name, 1, 2, 1.0, score, grade)


def lizard_row(name, cc, start, end, path="Sources/App.swift"):
    return f"5,{cc},30,1,10,{name}@{start}-{end}@{path},{path},{name},{name}(),{start},{end}"


def completed(stdout, returncode=0):
    return CompletedProcess([], returncode, stdout=stdout, stderr="")


def exit_code(fn, *args):
    with redirect_stderr(io.StringIO()):
        try:
            fn(*args)
        except SystemExit as stop:
            return stop.code
    raise AssertionError(f"{fn.__name__} did not exit")


class CrapScoreTest(unittest.TestCase):
    def test_a_fully_covered_function_scores_its_cc(self):
        self.assertEqual(crap.crap_score(5, 1.0), 5)

    def test_an_uncovered_function_scores_cc_squared_plus_cc(self):
        self.assertEqual(crap.crap_score(5, 0.0), 30)

    def test_coverage_above_one_is_clamped_so_the_score_never_drops_below_cc(self):
        self.assertEqual(crap.crap_score(5, 1.5), 5)

    def test_negative_coverage_is_clamped_to_the_uncovered_score(self):
        self.assertEqual(crap.crap_score(5, -0.5), 30)

    def test_a_score_equal_to_a_threshold_does_not_cross_it(self):
        self.assertEqual(crap.crap_grade(8, 5, 8), "WARN")
        self.assertEqual(crap.crap_grade(5, 5, 8), "ok")
        self.assertEqual(crap.crap_grade(8.01, 5, 8), "FAIL")


class PythonCoverageTest(unittest.TestCase):
    def test_branch_map_counts_taken_and_total_branches_per_source_line(self):
        bmap = crap._build_branch_map([[3, 4], [3, 6], [9, 10]], [[3, 8], [9, 12]])
        self.assertEqual(bmap, {3: [2, 3], 9: [1, 2]})

    def test_branch_coverage_is_preferred_over_line_coverage(self):
        entry = crap._parse_file_coverage({
            "executed_lines": [1, 2, 3, 4],
            "missing_lines": [],
            "executed_branches": [[2, 3]],
            "missing_branches": [[2, 4]],
        })
        self.assertEqual(crap.function_coverage_python({"m.py": entry}, "m.py", 1, 4), 0.5)

    def test_line_coverage_is_used_when_the_function_has_no_branches(self):
        entry = crap._parse_file_coverage({
            "executed_lines": [1, 2, 10],
            "missing_lines": [3, 4],
            "executed_branches": [[10, 11]],
            "missing_branches": [],
        })
        self.assertEqual(crap.function_coverage_python({"m.py": entry}, "m.py", 1, 4), 0.5)

    def test_a_file_missing_from_coverage_has_no_coverage(self):
        self.assertIsNone(crap.function_coverage_python({}, "m.py", 1, 4))

    def test_a_function_with_no_tracked_lines_has_no_coverage(self):
        entry = crap._parse_file_coverage({"executed_lines": [20], "missing_lines": []})
        self.assertIsNone(crap.function_coverage_python({"m.py": entry}, "m.py", 1, 4))


class PythonGateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.module = self.dir / "mod.py"
        self.module.write_text(
            "def f(x):\n    if x == 1:\n        return 1\n    if x == 2:\n        return 2\n    return 3\n\n\n"
            "class K:\n    def m(self, x):\n        if x == 1:\n            return 1\n"
            "        if x == 2:\n            return 2\n        return 3\n"
        )
        self.coverage = self.dir / "coverage.json"

    def write_coverage(self, executed, missing, **branches):
        fd = {"executed_lines": executed, "missing_lines": missing, **branches}
        self.coverage.write_text(json.dumps({"files": {str(self.module): fd}}))
        future = self.module.stat().st_mtime + 10
        os.utime(self.coverage, (future, future))

    def gate(self, *extra):
        return call(["--lang", "python", str(self.module), "--coverage-json", str(self.coverage), *extra])

    def test_full_coverage_passes_and_names_methods_by_their_class(self):
        self.write_coverage(list(range(1, 16)), [])
        code, out, _ = self.gate("--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["pass"])
        self.assertEqual({f["name"] for f in payload["functions"]}, {"f", "K.m"})
        self.assertEqual({f["coverage_source"] for f in payload["functions"]}, {"coverage-json"})

    def test_line_coverage_alone_warns_that_branch_data_is_missing(self):
        self.write_coverage(list(range(1, 16)), [])
        _, _, err = self.gate()
        self.assertIn("no branch data", err)

    def test_an_uncovered_function_fails(self):
        self.write_coverage([9, 10], [1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15])
        code, out, _ = self.gate("--no-color")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)

    def test_a_function_outside_the_coverage_file_is_scored_as_uncovered_with_unknown_coverage(self):
        self.coverage.write_text(json.dumps({"files": {}}))
        code, out, _ = self.gate("--json")
        self.assertEqual(code, 1)
        functions = json.loads(out)["functions"]
        self.assertEqual({f["coverage"] for f in functions}, {None})
        self.assertEqual({f["coverage_source"] for f in functions}, {None})
        self.assertEqual({f["crap"] for f in functions}, {12.0})

    def test_without_a_coverage_source_scores_are_worst_case(self):
        code, _, err = call(["--lang", "python", str(self.module)])
        self.assertEqual(code, 1)
        self.assertIn("worst-case", err)

    def test_min_cc_skips_simpler_functions(self):
        self.write_coverage([], list(range(1, 16)))
        code, _, err = self.gate("--min-cc", "4")
        self.assertEqual(code, 2)
        self.assertIn("no functions analysed", err)

    def test_allow_empty_turns_an_empty_scan_into_a_pass(self):
        self.write_coverage([], list(range(1, 16)))
        code, _, _ = self.gate("--min-cc", "4", "--allow-empty")
        self.assertEqual(code, 0)

    def test_a_missing_coverage_file_is_a_tool_error(self):
        code, _, err = self.gate()
        self.assertEqual(code, 2)
        self.assertIn("cannot open coverage file", err)

    def test_malformed_coverage_json_is_a_tool_error(self):
        self.coverage.write_text("{not json")
        code, _, err = self.gate()
        self.assertEqual(code, 2)
        self.assertIn("bad coverage JSON", err)

    def test_coverage_older_than_the_source_warns(self):
        self.write_coverage(list(range(1, 16)), [])
        past = self.module.stat().st_mtime - 10
        os.utime(self.coverage, (past, past))
        code, _, err = self.gate()
        self.assertEqual(code, 0)
        self.assertIn("stale", err)

    def test_strict_freshness_makes_stale_coverage_a_tool_error(self):
        self.write_coverage(list(range(1, 16)), [])
        past = self.module.stat().st_mtime - 10
        os.utime(self.coverage, (past, past))
        code, _, _ = self.gate("--strict-freshness")
        self.assertEqual(code, 2)


class RadonTest(unittest.TestCase):
    def test_a_missing_radon_is_a_tool_error(self):
        with patch.object(crap.importlib.util, "find_spec", return_value=None):
            self.assertEqual(exit_code(crap.cc_python, ["src"]), 2)

    def test_a_failed_radon_run_is_a_tool_error(self):
        with patch.object(crap, "run", return_value=completed("", 1)):
            self.assertEqual(exit_code(crap.cc_python, ["src"]), 2)

    def test_unparseable_radon_output_is_a_tool_error(self):
        with patch.object(crap, "run", return_value=completed("{not json")):
            self.assertEqual(exit_code(crap.cc_python, ["src"]), 2)

    def test_empty_radon_output_means_no_functions(self):
        with patch.object(crap, "run", return_value=completed("  \n")):
            self.assertEqual(crap.cc_python(["src"]), {})


class CoverageSourceTest(unittest.TestCase):
    def source(self, coverage_json=None, xcresult=None, no_coverage=False):
        return crap._coverage_source(Namespace(coverage_json=coverage_json, xcresult=xcresult, no_coverage=no_coverage))

    def test_each_coverage_flag_is_reported_by_its_own_tag(self):
        self.assertEqual(self.source(coverage_json="c.json"), "coverage-json")
        self.assertEqual(self.source(xcresult="r.xcresult"), "xcresult")
        self.assertEqual(self.source(no_coverage=True), "assumed-zero")

    def test_no_coverage_flag_has_no_tag(self):
        self.assertIsNone(self.source())


class ArgumentTest(unittest.TestCase):
    def test_warn_must_be_below_the_threshold(self):
        code, _, err = call(["--lang", "python", ".", "--warn", "8"])
        self.assertEqual(code, 2)
        self.assertIn("--warn", err)

    def test_xcresult_is_refused_for_python(self):
        code, _, err = call(["--lang", "python", ".", "--xcresult", "x.xcresult"])
        self.assertEqual(code, 2)
        self.assertIn("Swift-only", err)

    def test_coverage_json_is_refused_for_swift(self):
        code, _, err = call(["--lang", "swift", ".", "--coverage-json", "c.json"])
        self.assertEqual(code, 2)
        self.assertIn("Python-only", err)

    def test_a_missing_source_path_is_a_tool_error(self):
        code, _, err = call(["--lang", "python", "/no/such/path", "--no-coverage"])
        self.assertEqual(code, 2)
        self.assertIn("path not found", err)

    def test_update_needs_a_baseline(self):
        code, _, err = call(["--lang", "python", ".", "--coverage-json", "c.json", "--update"])
        self.assertEqual(code, 2)
        self.assertIn("--update needs --baseline", err)

    def test_help_lists_the_exit_codes(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            crap.main(["--help"])
        self.assertIn("Exit codes", out.getvalue())


class TableTest(unittest.TestCase):
    def table(self, results, top):
        out = io.StringIO()
        with redirect_stdout(out):
            crap.print_table(results, no_color=True, top=top)
        return out.getvalue()

    def test_top_caps_ok_and_warn_rows_but_every_fail_row_is_shown(self):
        results = [result(f"bad{i}", "FAIL", 20) for i in range(3)]
        results += [result(f"fine{i}", "ok") for i in range(5)]
        out = self.table(results, top=2)
        for i in range(3):
            self.assertIn(f"bad{i}", out)
        self.assertIn("fine1", out)
        self.assertNotIn("fine2", out)
        self.assertIn("3 more ok/WARN", out)

    def test_top_zero_shows_every_row(self):
        out = self.table([result(f"fine{i}", "ok") for i in range(5)], top=0)
        self.assertIn("fine4", out)
        self.assertNotIn("more ok/WARN", out)

    def test_long_labels_are_truncated_to_fifty_characters(self):
        out = self.table([result("x" * 80, "ok")], top=0)
        row = out.splitlines()[-1]
        self.assertTrue(row.endswith("…"))
        self.assertNotIn("x" * 50, row)


class SwiftCoverageTest(unittest.TestCase):
    def test_lizard_rows_are_read_by_column_and_malformed_rows_are_dropped(self):
        stdout = "\n".join([lizard_row("load", 4, 10, 30), "too,short", lizard_row("bad", "x", 1, 2)])
        with patch.object(crap, "run", return_value=completed(stdout)):
            functions = crap.cc_swift(["Sources"])
        self.assertEqual(functions, [{"file": "Sources/App.swift", "name": "load", "cc": 4, "start": 10, "end": 30}])

    def test_lizard_exit_1_is_not_a_failure(self):
        with patch.object(crap, "run", return_value=completed(lizard_row("load", 4, 10, 30), 1)):
            self.assertEqual(len(crap.cc_swift(["Sources"])), 1)

    def test_a_missing_lizard_is_a_tool_error(self):
        with patch.object(crap, "run", side_effect=FileNotFoundError), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stop:
                crap.cc_swift(["Sources"])
        self.assertEqual(stop.exception.code, 2)

    def test_a_lizard_crash_is_a_tool_error(self):
        with patch.object(crap, "run", return_value=completed("", 2)):
            self.assertEqual(exit_code(crap.cc_swift, ["Sources"]), 2)

    def test_empty_lizard_output_means_no_functions(self):
        with patch.object(crap, "run", return_value=completed("")):
            self.assertEqual(crap.cc_swift(["Sources"]), [])

    def test_unparseable_xccov_output_is_a_tool_error(self):
        with patch.object(crap, "run", return_value=completed("{not json")):
            self.assertEqual(exit_code(crap.coverage_swift, "r.xcresult"), 2)

    def test_an_overloaded_function_is_matched_by_its_line(self):
        funcs = crap._extract_file_funcs({"functions": [
            {"name": "load(_:)", "lineNumber": 10, "lineCoverage": 1.0},
            {"name": "load(_:into:)", "lineNumber": 20, "lineCoverage": 0.25},
        ]})
        cov_map = {"App.swift": funcs}
        self.assertEqual(crap.function_coverage_swift(cov_map, "Sources/App.swift", "load", 20), 0.25)

    def test_a_name_without_a_matching_line_takes_the_first_occurrence(self):
        funcs = crap._extract_file_funcs({"functions": [
            {"name": "load(_:)", "lineNumber": 10, "lineCoverage": 1.0},
            {"name": "load(_:into:)", "lineNumber": 20, "lineCoverage": 0.25},
        ]})
        self.assertEqual(crap.function_coverage_swift({"App": funcs}, "App.swift", "load", 99), 1.0)

    def test_a_class_qualified_xccov_name_matches_lizards_bare_method_name(self):
        funcs = crap._extract_file_funcs({"functions": [
            {"name": "Store.load(_:)", "lineNumber": 10, "lineCoverage": 0.5},
        ]})
        self.assertEqual(crap.function_coverage_swift({"App.swift": funcs}, "App.swift", "load", 10), 0.5)

    def test_xccov_coverage_is_clamped_to_the_unit_interval(self):
        funcs = crap._extract_file_funcs({"functions": [{"name": "f()", "lineNumber": 1, "lineCoverage": 1.7}]})
        self.assertEqual(funcs["f"], 1.0)

    def test_xccov_report_is_indexed_by_path_file_name_and_stem(self):
        report = {"targets": [{"files": [{"path": "/src/App.swift", "functions": [
            {"name": "load()", "lineNumber": 3, "lineCoverage": 0.5},
        ]}]}]}
        with patch.object(crap, "run", return_value=completed(json.dumps(report))):
            cov_map = crap.coverage_swift("r.xcresult")
        self.assertEqual({"/src/App.swift", "App.swift", "App"}, set(cov_map))

    def test_a_failed_xccov_is_a_tool_error(self):
        with patch.object(crap, "run", return_value=completed("", 1)), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stop:
                crap.coverage_swift("r.xcresult")
        self.assertEqual(stop.exception.code, 2)

    def test_swift_scores_join_lizard_complexity_with_xccov_coverage(self):
        report = {"targets": [{"files": [{"path": "Sources/App.swift", "functions": [
            {"name": "load()", "lineNumber": 10, "lineCoverage": 1.0},
        ]}]}]}
        outputs = [completed(lizard_row("load", 4, 10, 30)), completed(json.dumps(report))]
        with patch.object(crap, "run", side_effect=outputs):
            results = crap.analyse_swift(["Sources"], "r.xcresult", False, 2, 5, 8)
        self.assertEqual([(r.name, r.coverage, r.crap) for r in results], [("load", 1.0, 4)])

    def swift_scores(self, xcresult, no_coverage, min_cc=2):
        rows = "\n".join([lizard_row("load", 4, 10, 30), lizard_row("tiny", 1, 40, 41)])
        with patch.object(crap, "run", return_value=completed(rows)):
            return crap.analyse_swift(["Sources"], xcresult, no_coverage, min_cc, 5, 8)

    def test_swift_functions_below_min_cc_are_skipped(self):
        self.assertEqual([r.name for r in self.swift_scores(None, True)], ["load"])

    def test_swift_without_coverage_scores_worst_case(self):
        self.assertEqual([(r.coverage, r.crap) for r in self.swift_scores(None, True)], [(0.0, 20)])

    def test_swift_without_any_coverage_data_scores_worst_case_with_unknown_coverage(self):
        self.assertEqual([(r.coverage, r.crap) for r in self.swift_scores(None, False)], [(None, 20)])


if __name__ == "__main__":
    unittest.main()
