import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from quality_gates import crap, istanbul
from quality_gates.errors import ToolError
from quality_gates import quality_check as qc

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = "tests/fixtures/typescript"
COVERAGE = f"{FIXTURES}/coverage-final.json"
SAMPLE = f"{FIXTURES}/sample.ts"
SAME_LINE = f"{FIXTURES}/same_line.js"
SAME_LINE_COVERAGE = f"{FIXTURES}/coverage-same-line.json"
SAME_LINE_TYPED = f"{FIXTURES}/same_line_typed.ts"
SAME_LINE_TYPED_COVERAGE = f"{FIXTURES}/coverage-same-line-typed.json"


def run_main(main, argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main(argv, root=ROOT)
        except SystemExit as stop:
            return stop.code, out.getvalue(), err.getvalue()
    raise AssertionError("main did not exit")


class InRepoRoot(unittest.TestCase):
    def setUp(self):
        before = os.getcwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, before)


class IstanbulCoverageTest(InRepoRoot):
    def setUp(self):
        super().setUp()
        self.files = istanbul.load(COVERAGE)

    def coverage(self, start, lizard_end):
        return istanbul.function_coverage(self.files, SAMPLE, start, lizard_end)

    def test_a_function_with_branches_scores_its_branch_arms(self):
        self.assertEqual(self.coverage(1, 10), 0.875)

    def test_the_range_comes_from_istanbul_not_lizards_overrunning_end_line(self):
        self.assertEqual(istanbul.function_range(self.files[str(ROOT / SAMPLE)], 1, 10), (1, 8))

    def test_a_method_scores_the_branches_in_its_own_lines(self):
        self.assertEqual(self.coverage(12, 15), 0.5)

    def test_a_const_arrow_function_is_matched_by_its_declaration_line(self):
        self.assertEqual(self.coverage(18, 19), 1.0)

    def test_an_untested_function_scores_zero(self):
        self.assertEqual(self.coverage(21, 27), 0.0)

    def test_a_function_without_branches_scores_its_statements(self):
        files = {"/p/a.ts": {
            "fnMap": {"0": {"decl": {"start": {"line": 1}}, "loc": {"start": {"line": 1}, "end": {"line": 4}}}},
            "statementMap": {"0": {"start": {"line": 2}}, "1": {"start": {"line": 3}}, "2": {"start": {"line": 9}}},
            "s": {"0": 1, "1": 0, "2": 1},
            "branchMap": {}, "b": {},
        }}
        self.assertEqual(istanbul.function_coverage(files, "/p/a.ts", 1, 4), 0.5)

    def test_without_a_matching_fnmap_entry_lizards_range_is_used(self):
        self.assertEqual(istanbul.function_range({"fnMap": {}}, 3, 7), (3, 7))

    def test_a_file_missing_from_the_report_has_unknown_coverage(self):
        self.assertIsNone(istanbul.function_coverage(self.files, "src/other.ts", 1, 5))

    def test_absolute_and_relative_report_keys_both_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "c.json"
            report.write_text(json.dumps({str(ROOT / SAMPLE): {"fnMap": {}}}), encoding="utf-8")
            self.assertIn(str(ROOT / SAMPLE), istanbul.load(str(report)))
        self.assertIn(str(ROOT / SAMPLE), self.files)

    def test_an_unreadable_report_is_a_tool_error(self):
        with self.assertRaises(ToolError):
            istanbul.load("no/such/coverage.json")

    def test_crap_names_a_report_that_is_not_utf8_under_its_own_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "coverage-final.json"
            report.write_bytes(b"\xff\xfe\x00binary")
            code, _, err = run_main(crap.main, ["--lang", "typescript", SAMPLE, "--istanbul-json", str(report)])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("[crap] bad Istanbul coverage JSON: "))
        self.assertNotIn("Traceback", err)

    def test_crap_names_an_unreadable_report_under_its_own_tag(self):
        code, _, err = run_main(crap.main, ["--lang", "typescript", SAMPLE, "--istanbul-json", "no/such.json"])
        self.assertEqual(code, 2)
        self.assertEqual(err, "[crap] cannot open Istanbul coverage file: [Errno 2] No such file or directory: 'no/such.json'\n")


def span_entry(line, last):
    return {
        "decl": {"start": {"line": line}},
        "loc": {"start": {"line": line}, "end": {"line": last}},
    }


class SameLineFunctionsTest(InRepoRoot):
    def setUp(self):
        super().setUp()
        report = istanbul.load(SAME_LINE_COVERAGE)
        self.entry = report[str(ROOT / SAME_LINE)]

    def span(self, start, end):
        return istanbul.function_range(self.entry, start, end)

    def test_a_callback_sharing_its_holders_line_is_scored_over_its_own_lines(self):
        self.assertEqual(self.span(3, 3), (3, 3))

    def test_the_holder_that_wraps_onto_a_second_line_keeps_both_lines(self):
        self.assertEqual(self.span(3, 4), (3, 4))

    def test_the_issues_one_line_callback_and_its_holder_are_both_scored_over_that_line(self):
        self.assertEqual(self.span(1, 1), (1, 1))

    def test_the_second_of_two_functions_on_one_line_is_matched_to_its_own_entry(self):
        self.assertEqual(self.span(6, 11), (6, 11))

    def test_the_first_of_two_functions_on_one_line_is_matched_to_its_own_entry(self):
        self.assertEqual(self.span(6, 6), (6, 6))

    def test_with_no_entry_ending_on_lizards_end_line_the_narrowest_entry_containing_it_is_used(self):
        entry = {"fnMap": {"0": span_entry(1, 9), "1": span_entry(1, 5), "2": span_entry(1, 7)}}
        self.assertEqual(istanbul.function_range(entry, 1, 4), (1, 5))

    def test_with_no_entry_containing_lizards_end_line_the_entry_on_that_line_that_ends_last_is_used(self):
        entry = {"fnMap": {"0": span_entry(1, 3), "1": span_entry(1, 8), "2": span_entry(1, 5)}}
        self.assertEqual(istanbul.function_range(entry, 1, 10), (1, 8))

    def test_a_typed_function_whose_lizard_end_overruns_into_an_interface_keeps_its_own_end_line(self):
        entry = istanbul.load(SAME_LINE_TYPED_COVERAGE)[str(ROOT / SAME_LINE_TYPED)]
        self.assertEqual(istanbul.function_range(entry, 1, 8), (1, 6))

    def test_crap_scores_a_typed_function_declared_after_another_on_one_line_over_its_own_lines(self):
        code, out, _ = run_main(crap.main, [
            "--lang", "typescript", SAME_LINE_TYPED, "--istanbul-json", SAME_LINE_TYPED_COVERAGE, "--json",
        ])
        scores = {f["name"]: (f["cc"], f["coverage"]) for f in json.loads(out)["functions"]}
        self.assertEqual(code, 0)
        self.assertEqual(scores, {"a1": (2, 0.5), "a2": (2, 0.75)})

    def test_an_entry_starting_on_another_line_is_never_matched(self):
        entry = {"fnMap": {"0": span_entry(2, 4)}}
        self.assertEqual(istanbul.function_range(entry, 1, 4), (1, 4))

    def test_crap_scores_each_function_on_a_shared_line_over_its_own_lines(self):
        code, out, _ = run_main(crap.main, [
            "--lang", "typescript", SAME_LINE, "--istanbul-json", SAME_LINE_COVERAGE, "--json", "--min-cc", "1",
        ])
        scores = {(f["line"], f["name"]): (f["cc"], f["coverage"]) for f in json.loads(out)["functions"]}
        self.assertEqual(code, 0)
        self.assertEqual(scores, {
            (1, "doubled"): (1, 0.5),
            (1, "(anonymous)"): (2, 0.5),
            (3, "bounded"): (1, 0.75),
            (3, "(anonymous)#2"): (2, 0.5),
            (4, "(anonymous)#3"): (2, 1.0),
            (6, "first"): (2, 0.5),
            (6, "second"): (2, 0.75),
        })


class CrapTypescriptTest(InRepoRoot):
    def test_scores_join_lizard_complexity_with_istanbul_coverage(self):
        code, out, _ = run_main(crap.main, [
            "--lang", "typescript", SAMPLE, "--istanbul-json", COVERAGE, "--json",
        ])
        scores = {f["name"]: (f["cc"], f["coverage"]) for f in json.loads(out)["functions"]}
        self.assertEqual(scores["grade"], (5, 0.875))
        self.assertEqual(scores["untested"], (3, 0.0))
        self.assertEqual(code, 1)

    def test_istanbul_json_is_refused_for_python(self):
        code, _, err = run_main(crap.main, ["--lang", "python", ".", "--istanbul-json", COVERAGE])
        self.assertEqual(code, 2)
        self.assertIn("TypeScript-only", err)

    def test_coverage_json_is_refused_for_typescript(self):
        code, _, _ = run_main(crap.main, ["--lang", "typescript", SAMPLE, "--coverage-json", COVERAGE])
        self.assertEqual(code, 2)

    def test_the_baseline_records_each_repeated_name_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.ts"
            body = "  if (a) { return 1; } if (b) { return 2; } if (c) { return 3; } if (d) { return 4; } return 5;\n"
            src.write_text(
                f"const p = [function (a, b, c, d) {{\n{body}}}, function (a, b, c, d) {{\n{body}}}];\n",
                encoding="utf-8",
            )
            report = Path(tmp) / "coverage-final.json"
            report.write_text(json.dumps({str(src): {"fnMap": {}, "statementMap": {}, "s": {}, "branchMap": {}, "b": {}}}), encoding="utf-8")
            baseline = Path(tmp) / "crap-baseline.json"
            argv = ["--lang", "typescript", str(src), "--istanbul-json", str(report), "--baseline", str(baseline), "--update"]
            run_main(crap.main, argv)
            keys = set(json.loads(baseline.read_text(encoding="utf-8")))
        self.assertEqual({k.split("::")[1] for k in keys}, {"p", "p#2"})


class CcCheckTypescriptTest(InRepoRoot):
    def test_python_stays_the_default_language(self):
        self.assertEqual(qc.build_parser().parse_args(["x"]).lang, "python")

    def test_a_typescript_function_above_the_threshold_fails(self):
        code, out, _ = run_main(qc.main, ["--lang", "typescript", SAMPLE, "--threshold", "4"])
        self.assertEqual(code, 1)
        self.assertIn("grade", out)

    def test_typescript_at_or_below_the_threshold_passes(self):
        code, _, _ = run_main(qc.main, ["--lang", "typescript", FIXTURES])
        self.assertEqual(code, 0)

    def test_a_baseline_holds_typescript_debt(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "cc-baseline.json"
            argv = ["--lang", "typescript", SAMPLE, "--threshold", "4", "--baseline", str(baseline)]
            run_main(qc.main, argv + ["--update"])
            code, _, _ = run_main(qc.main, argv)
            keys = list(json.loads(baseline.read_text(encoding="utf-8")))
        self.assertEqual(code, 0)
        self.assertEqual(keys, [f"{SAMPLE}::grade"])

    def test_a_tree_with_no_typescript_files_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, _ = run_main(qc.main, ["--lang", "typescript", tmp])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
