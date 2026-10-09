import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from quality_gates import crap, languages, llvm_cov
from quality_gates.complexity_scan import Function
from quality_gates.errors import ToolError

ROOT = Path(__file__).resolve().parents[1]
EXPORT = "tests/fixtures/swift/llvm-cov-export.json"
SOURCES = "tests/fixtures/swift/package/Sources"
GRADE = f"{SOURCES}/Grades/Grade.swift"
GRADES_STORE = f"{SOURCES}/Grades/Store.swift"
LEDGER_STORE = f"{SOURCES}/Ledger/Store.swift"
BUILT_AT = "/build/Pkg/Sources/App/Main.swift"


def llvm_cov_reader():
    formats = {coverage.flag: coverage for coverage in languages.LANGUAGES["swift"].coverage}
    return formats["--llvm-cov-json"].read


def function(file, name, start, end):
    return Function(file, name, 2, start, end, name)


def segment(line, count, has_count=True, entry=True, gap=False):
    return [line, 1, count, has_count, entry, gap]


def export_of(*exports):
    return {"type": "llvm.coverage.json.export", "version": "3.0.1", "data": list(exports)}


def one_export(filename, segments, bodies):
    return {
        "files": [{"filename": filename, "segments": segments}],
        "functions": [
            {"name": f"f{i}", "filenames": [filename], "regions": [[start, 10, end, 2, 1, 0, 0, 0]]}
            for i, (start, end) in enumerate(bodies)
        ],
    }


class InRepoRoot(unittest.TestCase):
    def setUp(self):
        before = os.getcwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, before)


class FixtureCoverageTest(InRepoRoot):
    def setUp(self):
        super().setUp()
        self.coverage_of = llvm_cov_reader()(EXPORT)

    def test_each_function_gets_the_line_coverage_llvm_cov_reports_for_it(self):
        expected = [
            (GRADE, "grade", 5, 13, 8 / 9),
            (GRADE, "clamp", 15, 17, 1.0),
            (GRADE, "clamp", 19, 27, 7 / 9),
            (GRADE, "largest", 39, 48, 1.0),
            (GRADES_STORE, "add", 6, 16, 9 / 11),
            (GRADES_STORE, "passing", 18, 22, 1.0),
            (LEDGER_STORE, "add", 6, 15, 0.0),
        ]
        for file, name, start, end, coverage in expected:
            with self.subTest(f"{file}:{start}"):
                self.assertAlmostEqual(self.coverage_of(function(file, name, start, end)), coverage)

    def test_an_attribute_line_above_the_declaration_does_not_move_the_match(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "describe", 30, 37)), 5 / 8)

    def test_a_signature_over_several_lines_matches_the_body_that_opens_below_it(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "weighted", 60, 67)), 5 / 6)

    def test_a_nested_function_is_scored_on_its_own_lines_and_counted_in_its_outer_function(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "label", 51, 53)), 1.0)
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "summary", 50, 58)), 8 / 9)

    def test_two_files_with_the_same_name_are_each_scored_from_their_own_entry(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADES_STORE, "add", 6, 16)), 9 / 11)
        self.assertEqual(self.coverage_of(function(LEDGER_STORE, "add", 6, 15)), 0.0)

    def test_a_file_matched_by_its_name_alone_has_unknown_coverage_when_the_report_has_two_of_that_name(self):
        self.assertIsNone(self.coverage_of(function("elsewhere/Store.swift", "add", 6, 16)))

    def test_a_function_in_a_file_the_report_does_not_cover_has_unknown_coverage(self):
        self.assertIsNone(self.coverage_of(function(f"{SOURCES}/Grades/Other.swift", "grade", 5, 13)))

    def test_lines_with_no_function_body_in_the_report_have_unknown_coverage(self):
        self.assertIsNone(self.coverage_of(function(GRADE, "Grade", 1, 3)))


class ExportCoverageTest(unittest.TestCase):
    def coverage(self, report, start=1, end=9, filepath="/checkout/Sources/App/Main.swift"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            coverage_of = llvm_cov_reader()(str(path))
        return coverage_of(function(filepath, "f", start, end))

    def test_a_closure_that_never_ran_counts_against_the_function_that_holds_it(self):
        segments = [segment(1, 1), segment(3, 0), segment(5, 1, entry=False), segment(6, 0, has_count=False, entry=False)]
        report = export_of(one_export(BUILT_AT, segments, [(1, 6), (3, 5)]))
        self.assertAlmostEqual(self.coverage(report, 1, 6), 4 / 6)

    def test_a_function_listed_more_than_once_is_scored_once_from_the_merged_lines(self):
        ran = [segment(1, 1), segment(3, 0, has_count=False, entry=False)]
        idle = [segment(1, 0), segment(3, 0, has_count=False, entry=False)]
        report = export_of(one_export(BUILT_AT, ran, [(1, 3), (1, 3)]), one_export(BUILT_AT, idle, [(1, 3)]))
        self.assertEqual(self.coverage(report, 1, 3), 1.0)

    def test_a_line_inside_a_skipped_region_is_not_counted(self):
        segments = [segment(1, 1), segment(2, 0), segment(3, 0, has_count=False), segment(4, 1, entry=False),
                    segment(5, 0, has_count=False, entry=False)]
        report = export_of(one_export(BUILT_AT, segments, [(1, 5)]))
        self.assertEqual(self.coverage(report, 1, 5), 1.0)

    def test_the_outermost_body_starting_first_inside_the_function_is_the_match(self):
        segments = [segment(2, 0), segment(3, 1), segment(4, 0, entry=False), segment(5, 0, has_count=False, entry=False)]
        report = export_of(one_export(BUILT_AT, segments, [(3, 3), (2, 5)]))
        self.assertAlmostEqual(self.coverage(report, 1, 5), 2 / 4)

    def test_a_body_with_no_executable_line_has_unknown_coverage(self):
        segments = [segment(5, 1), segment(6, 0, has_count=False, entry=False)]
        report = export_of(one_export(BUILT_AT, segments, [(1, 3), (5, 6)]))
        self.assertIsNone(self.coverage(report, 1, 3))

    def test_a_report_with_no_data_gives_every_function_unknown_coverage(self):
        self.assertIsNone(self.coverage(export_of()))

    def test_an_unreadable_export_is_a_tool_error(self):
        with self.assertRaises(ToolError) as raised:
            llvm_cov.load("no/such/export.json")
        self.assertTrue(str(raised.exception).startswith("cannot open llvm-cov export: "))

    def test_malformed_export_json_is_a_tool_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ToolError) as raised:
                llvm_cov.load(str(path))
        self.assertTrue(str(raised.exception).startswith("bad llvm-cov export JSON: "))


def run_crap(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            crap.main(argv, root=ROOT)
        except SystemExit as stop:
            return stop.code, out.getvalue(), err.getvalue()
    raise AssertionError("crap did not exit")


class CrapSwiftPMTest(InRepoRoot):
    def test_crap_scores_a_swiftpm_package_from_its_llvm_cov_export(self):
        code, out, _ = run_crap(["--lang", "swift", SOURCES, "--llvm-cov-json", EXPORT, "--json"])
        payload = json.loads(out)
        rows = {(Path(f["file"]).parent.name, f["name"]): (f["cc"], round(f["coverage"], 4), f["grade"])
                for f in payload["functions"]}
        self.assertEqual(rows[("Grades", "add")], (3, 0.8182, "ok"))
        self.assertEqual(rows[("Ledger", "add")], (4, 0.0, "FAIL"))
        self.assertEqual(rows[("Grades", "describe")], (4, 0.625, "ok"))
        self.assertEqual(payload["coverage_source"], "llvm-cov-json")
        self.assertEqual({f["coverage_source"] for f in payload["functions"]}, {"llvm-cov-json"})
        self.assertFalse(payload["pass"])
        self.assertEqual(code, 1)

    def test_llvm_cov_json_is_refused_for_python(self):
        code, _, err = run_crap(["--lang", "python", "src", "--llvm-cov-json", EXPORT])
        self.assertEqual(code, 2)
        self.assertIn("--llvm-cov-json is Swift-only", err)

    def test_llvm_cov_json_and_xcresult_cannot_be_given_together(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                crap.build_parser().parse_args(["--lang", "swift", "--xcresult", "a", "--llvm-cov-json", "b"])

    def test_help_says_how_a_swiftpm_package_gets_coverage(self):
        text = crap.build_parser().format_help()
        self.assertIn("swift test --enable-code-coverage", text)
        self.assertIn("--llvm-cov-json $(swift test --show-codecov-path)", text)


if __name__ == "__main__":
    unittest.main()
