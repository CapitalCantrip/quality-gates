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

from quality_gates import complexity_scan, crap
from quality_gates import xccov as xccov_reader


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


def tagged(err):
    return [line for line in err.splitlines() if line.startswith("[crap] ")]


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


class ScoreTest(unittest.TestCase):
    def test_score_applies_the_coverage_lookup_skips_functions_below_min_cc_and_ranks_worst_first(self):
        functions = [
            complexity_scan.Function("a.py", "simple", 1, 1, 2, "simple"),
            complexity_scan.Function("a.py", "half", 4, 3, 9, "half"),
            complexity_scan.Function("a.py", "unknown", 4, 10, 20, "unknown"),
        ]
        coverage = {"half": 0.5, "unknown": None}
        results = crap.score(functions, lambda fn: coverage[fn.name], crap.Limits(min_cc=2, warn=5, threshold=8))
        self.assertEqual(
            [(r.name, r.coverage, r.crap, r.grade) for r in results],
            [("unknown", None, 20.0, "FAIL"), ("half", 0.5, 6.0, "WARN")],
        )


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

    def test_allow_empty_prints_the_empty_scan_message_with_the_crap_tag(self):
        self.write_coverage([], list(range(1, 16)))
        _, _, err = self.gate("--min-cc", "4", "--allow-empty")
        self.assertIn(f"[crap] no functions analysed in: {self.module}\n", err)

    def test_an_empty_scan_without_allow_empty_is_a_tool_error_with_the_crap_tag(self):
        self.write_coverage([], list(range(1, 16)))
        code, _, err = self.gate("--min-cc", "4")
        self.assertEqual(code, 2)
        self.assertIn(f"[crap] no functions analysed in: {self.module}\n", err)

    def test_a_missing_coverage_file_is_a_tool_error(self):
        code, _, err = self.gate()
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("[crap] cannot open coverage file: [Errno 2]"))

    def test_malformed_coverage_json_is_a_tool_error(self):
        self.coverage.write_text("{not json")
        code, _, err = self.gate()
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("[crap] bad coverage JSON: Expecting property name"))

    def test_coverage_older_than_the_source_warns(self):
        self.write_coverage(list(range(1, 16)), [])
        past = self.module.stat().st_mtime - 10
        os.utime(self.coverage, (past, past))
        code, _, err = self.gate()
        self.assertEqual(code, 0)
        self.assertIn("stale", err)

    def test_the_stale_coverage_warning_is_printed_with_the_crap_tag(self):
        self.write_coverage(list(range(1, 16)), [])
        past = self.module.stat().st_mtime - 10
        os.utime(self.coverage, (past, past))
        _, _, err = self.gate()
        self.assertTrue(any("coverage file may be stale: coverage.json" in line for line in tagged(err)))

    def test_strict_freshness_makes_stale_coverage_a_tool_error(self):
        self.write_coverage(list(range(1, 16)), [])
        past = self.module.stat().st_mtime - 10
        os.utime(self.coverage, (past, past))
        code, _, _ = self.gate("--strict-freshness")
        self.assertEqual(code, 2)

    def test_strict_freshness_reports_the_stale_coverage_with_the_crap_tag(self):
        self.write_coverage(list(range(1, 16)), [])
        past = self.module.stat().st_mtime - 10
        os.utime(self.coverage, (past, past))
        _, _, err = self.gate("--strict-freshness")
        self.assertTrue(any("coverage file may be stale: coverage.json" in line for line in tagged(err)))


class CoverageSourceTest(unittest.TestCase):
    def source(self, coverage_json=None, xcresult=None, istanbul_json=None, no_coverage=False):
        return crap._coverage_source(crap._given_report(Namespace(
            coverage_json=coverage_json, xcresult=xcresult, istanbul_json=istanbul_json, no_coverage=no_coverage,
        )))

    def test_each_coverage_flag_is_reported_by_its_own_tag(self):
        self.assertEqual(self.source(coverage_json="c.json"), "coverage-json")
        self.assertEqual(self.source(xcresult="r.xcresult"), "xcresult")
        self.assertEqual(self.source(istanbul_json="coverage-final.json"), "istanbul-json")
        self.assertEqual(self.source(no_coverage=True), "assumed-zero")

    def test_no_coverage_flag_at_all_is_reported_as_assumed_zero(self):
        self.assertEqual(self.source(), "assumed-zero")

    def test_a_gate_run_with_no_coverage_flag_at_all_tags_its_json_assumed_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "mod.py"
            module.write_text("def f(x):\n    if x:\n        return 1\n    return 2\n")
            _, out, _ = call(["--lang", "python", str(module), "--json"])
        payload = json.loads(out)
        self.assertEqual(payload["coverage_source"], "assumed-zero")
        self.assertEqual({f["coverage_source"] for f in payload["functions"]}, {"assumed-zero"})


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
        self.assertEqual(err, "[crap] path not found: /no/such/path\n")

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


class SwiftGateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sources = tmp.name
        Path(tmp.name, "App.swift").write_text("func load() {}\n", encoding="utf-8")

    def gate(self, rows, *extra, xccov=None):
        lizard = patch.object(complexity_scan, "run", return_value=completed("\n".join(rows)))
        xcrun = patch.object(xccov_reader, "run", return_value=completed(json.dumps(xccov or {})))
        with lizard, xcrun:
            code, out, _ = call(["--lang", "swift", self.sources, "--json", *extra])
        return code, json.loads(out)["functions"]

    def test_swift_scores_join_lizard_complexity_with_xccov_coverage(self):
        report = {"targets": [{"files": [{"path": "Sources/App.swift", "functions": [
            {"name": "load()", "lineNumber": 10, "lineCoverage": 1.0},
        ]}]}]}
        code, functions = self.gate([lizard_row("load", 4, 10, 30)], "--xcresult", "r.xcresult", xccov=report)
        self.assertEqual([(f["name"], f["coverage"], f["crap"]) for f in functions], [("load", 1.0, 4)])

    def test_a_repeated_swift_name_still_finds_its_coverage_by_line(self):
        report = {"targets": [{"files": [{"path": "Sources/App.swift", "functions": [
            {"name": "load()", "lineNumber": 10, "lineCoverage": 1.0},
            {"name": "load(_:)", "lineNumber": 40, "lineCoverage": 0.5},
        ]}]}]}
        rows = [lizard_row("load", 4, 10, 30), lizard_row("load", 4, 40, 50)]
        _, functions = self.gate(rows, "--xcresult", "r.xcresult", xccov=report)
        self.assertEqual({f["name"]: f["coverage"] for f in functions}, {"load": 1.0, "load#2": 0.5})

    def test_swift_functions_below_min_cc_are_skipped(self):
        _, functions = self.gate([lizard_row("load", 4, 10, 30), lizard_row("tiny", 1, 40, 41)], "--no-coverage")
        self.assertEqual([f["name"] for f in functions], ["load"])

    def test_swift_without_coverage_scores_worst_case(self):
        _, functions = self.gate([lizard_row("load", 4, 10, 30)], "--no-coverage")
        self.assertEqual([(f["coverage"], f["crap"]) for f in functions], [(0.0, 20)])


if __name__ == "__main__":
    unittest.main()
