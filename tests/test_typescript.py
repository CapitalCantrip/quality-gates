import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from quality_gates import crap, istanbul, lizard_scan
from quality_gates import quality_check as qc

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = "tests/fixtures/typescript"
COVERAGE = f"{FIXTURES}/coverage-final.json"
SAMPLE = f"{FIXTURES}/sample.ts"


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

    def coverage(self, start, fallback_end):
        return istanbul.function_coverage(self.files, SAMPLE, start, fallback_end)

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
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
            istanbul.load("no/such/coverage.json")
        self.assertEqual(stop.exception.code, 2)


class LizardScanTest(InRepoRoot):
    def test_typescript_tsx_and_javascript_files_are_all_read(self):
        names = {(Path(f["file"]).name, f["name"]) for f in lizard_scan.scan([FIXTURES], "typescript")}
        self.assertIn(("component.tsx", "V"), names)
        self.assertIn(("sample.ts", "pick"), names)

    def test_switch_cases_count_toward_complexity(self):
        untested = [f for f in lizard_scan.scan([SAMPLE], "typescript") if f["name"] == "untested"]
        self.assertEqual(untested[0]["cc"], 3)

    def test_repeated_names_in_a_file_get_their_order_as_a_suffix(self):
        functions = [
            {"file": "a.ts", "name": "(anonymous)", "start": 9},
            {"file": "a.ts", "name": "(anonymous)", "start": 2},
            {"file": "b.ts", "name": "(anonymous)", "start": 1},
            {"file": "a.ts", "name": "render", "start": 5},
        ]
        labels = {(f["file"], f["start"]): f["label"] for f in lizard_scan.with_labels(functions)}
        self.assertEqual(labels, {
            ("a.ts", 2): "(anonymous)", ("a.ts", 9): "(anonymous)#2",
            ("b.ts", 1): "(anonymous)", ("a.ts", 5): "render",
        })

    def test_node_modules_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            vendored = Path(tmp) / "node_modules" / "lib"
            vendored.mkdir(parents=True)
            (vendored / "x.js").write_text("function x(a) { return a ? 1 : 2; }\n", encoding="utf-8")
            self.assertEqual(lizard_scan.scan([tmp], "typescript"), [])


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
