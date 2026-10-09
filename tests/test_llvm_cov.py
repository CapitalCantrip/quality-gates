import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from quality_gates import crap, languages
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


CODE, EXPANSION, SKIPPED = 0, 1, 2


def region(line_start, line_end, count, kind=CODE):
    return [line_start, 5, line_end, 30, count, 0, 0, kind]


def record(filename, *regions):
    return {"name": "f", "count": regions[0][4], "filenames": [filename], "regions": list(regions)}


def export_of(*records):
    return {"type": "llvm.coverage.json.export", "version": "3.0.1",
            "data": [{"files": [], "functions": list(records)}]}


class InRepoRoot(unittest.TestCase):
    def setUp(self):
        before = os.getcwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, before)


LLVM_COV_REPORT_SHOW_FUNCTIONS = [
    (GRADE, "grade", 5, 13, 8 / 9),
    (GRADE, "clamp", 15, 17, 3 / 3),
    (GRADE, "clamp", 19, 27, 7 / 9),
    (GRADE, "describe", 30, 37, 5 / 8),
    (GRADE, "largest", 39, 48, 10 / 10),
    (GRADE, "label", 51, 53, 3 / 3),
    (GRADE, "summary", 50, 58, 8 / 9),
    (GRADE, "weighted", 60, 68, 5 / 6),
    (GRADE, "penalty", 71, 76, 0 / 6),
    (GRADE, "tally", 70, 84, 14 / 15),
    (GRADE, "mode", 86, 95, 5 / 6),
    (GRADE, "scaled", 97, 107, 5 / 6),
    (GRADES_STORE, "add", 6, 16, 9 / 11),
    (GRADES_STORE, "passing", 18, 22, 5 / 5),
    (LEDGER_STORE, "add", 6, 15, 0 / 10),
]


class FixtureCoverageTest(InRepoRoot):
    def setUp(self):
        super().setUp()
        self.coverage_of = llvm_cov_reader()(EXPORT)

    def test_each_function_gets_the_lines_figure_llvm_cov_report_show_functions_prints_for_it(self):
        for file, name, start, end, coverage in LLVM_COV_REPORT_SHOW_FUNCTIONS:
            with self.subTest(f"{file}:{start}"):
                self.assertAlmostEqual(self.coverage_of(function(file, name, start, end)), coverage)

    def test_a_closure_and_a_nested_function_that_never_ran_do_not_count_against_the_function_holding_them(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "tally", 70, 84)), 14 / 15)

    def test_lines_compiled_out_by_an_if_config_are_not_counted(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "mode", 86, 95)), 5 / 6)

    def test_a_closure_default_argument_in_a_signature_over_several_lines_is_not_taken_for_the_function(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "scaled", 97, 107)), 5 / 6)

    def test_an_attribute_line_above_the_declaration_does_not_move_the_match(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "describe", 29, 37)), 5 / 8)

    def test_a_signature_over_several_lines_matches_the_body_that_opens_below_it(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADE, "weighted", 60, 68)), 5 / 6)

    def test_two_files_with_the_same_name_are_each_scored_from_their_own_entry(self):
        self.assertAlmostEqual(self.coverage_of(function(GRADES_STORE, "add", 6, 16)), 9 / 11)
        self.assertEqual(self.coverage_of(function(LEDGER_STORE, "add", 6, 15)), 0.0)

    def test_a_file_absent_from_the_report_whose_name_is_unique_in_the_report_has_unknown_coverage(self):
        self.assertIsNone(self.coverage_of(function(f"{SOURCES}/Untested/Grade.swift", "grade", 5, 13)))

    def test_a_file_sharing_only_its_name_with_two_report_files_has_unknown_coverage(self):
        self.assertIsNone(self.coverage_of(function("elsewhere/Store.swift", "add", 6, 16)))

    def test_a_function_in_a_file_the_report_does_not_cover_has_unknown_coverage(self):
        self.assertIsNone(self.coverage_of(function(f"{SOURCES}/Grades/Other.swift", "grade", 5, 13)))

    def test_lines_with_no_function_body_in_the_report_have_unknown_coverage(self):
        self.assertIsNone(self.coverage_of(function(GRADE, "Grade", 1, 3)))


def write_json(tmp, document):
    path = Path(tmp) / "export.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


class SameCheckoutMatchingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.tested = self.source("Sources/Core/Models/Item.swift")
        self.untested = self.source("Sources/Extra/Models/Item.swift")
        self.coverage_of = llvm_cov_reader()(write_json(tmp.name, export_of(record(str(self.tested), region(1, 2, 1)))))

    def source(self, relative):
        path = self.root / relative
        path.parent.mkdir(parents=True)
        path.write_text("func f() {\n}\n", encoding="utf-8")
        return path

    def test_a_file_in_this_checkout_is_matched_by_its_exact_path(self):
        self.assertEqual(self.coverage_of(function(str(self.tested), "f", 1, 2)), 1.0)

    def test_a_file_in_an_untested_target_sharing_folder_and_name_with_a_tested_file_has_unknown_coverage(self):
        self.assertIsNone(self.coverage_of(function(str(self.untested), "f", 1, 2)))


class ExportCoverageTest(unittest.TestCase):
    def coverage(self, report, start=1, end=9, filepath=BUILT_AT):
        with tempfile.TemporaryDirectory() as tmp:
            coverage_of = llvm_cov_reader()(write_json(tmp, report))
        return coverage_of(function(filepath, "f", start, end))

    def test_a_file_the_report_names_by_its_exact_path_is_matched(self):
        report = export_of(record(BUILT_AT, region(1, 2, 1)))
        self.assertEqual(self.coverage(report, 1, 2, BUILT_AT), 1.0)

    def test_a_file_sharing_its_folder_and_name_with_one_report_file_is_matched(self):
        report = export_of(record(BUILT_AT, region(1, 2, 1)))
        self.assertEqual(self.coverage(report, 1, 2, "/checkout/App/Main.swift"), 1.0)

    def test_a_file_sharing_its_folder_and_name_equally_with_two_report_files_has_unknown_coverage(self):
        report = export_of(record(BUILT_AT, region(1, 2, 1)), record("/other/App/Main.swift", region(1, 2, 1)))
        self.assertIsNone(self.coverage(report, 1, 2, "/checkout/App/Main.swift"))

    def test_a_closure_that_never_ran_does_not_count_against_the_function_that_holds_it(self):
        report = export_of(record(BUILT_AT, region(1, 6, 1)), record(BUILT_AT, region(3, 5, 0)))
        self.assertEqual(self.coverage(report, 1, 6), 1.0)

    def test_a_region_that_never_ran_inside_the_function_counts_against_it(self):
        report = export_of(record(BUILT_AT, region(1, 6, 1), region(3, 4, 0)))
        self.assertAlmostEqual(self.coverage(report, 1, 6), 5 / 6)

    def test_lines_between_two_inner_regions_take_the_count_of_the_region_around_them(self):
        report = export_of(record(BUILT_AT, region(1, 6, 1), region(2, 3, 0), [5, 10, 5, 20, 1, 0, 0, CODE]))
        self.assertAlmostEqual(self.coverage(report, 1, 6), 5 / 6)

    def test_regions_covering_the_same_span_add_their_counts(self):
        report = export_of(record(BUILT_AT, region(1, 4, 1), region(2, 3, 0), region(2, 3, 1)))
        self.assertEqual(self.coverage(report, 1, 4), 1.0)

    def test_regions_in_a_file_a_macro_expands_into_are_not_counted_in_the_function(self):
        expanded = {"name": "f", "count": 1, "filenames": ["/build/Pkg/Macros/Expanded.swift", BUILT_AT],
                    "regions": [[1, 5, 3, 30, 1, 1, 0, CODE], [2, 5, 2, 20, 1, 1, 0, EXPANSION],
                                [10, 1, 12, 2, 0, 0, 0, CODE]]}
        self.assertEqual(self.coverage(export_of(expanded), 1, 3), 1.0)

    def test_a_zero_length_region_takes_the_count_of_the_region_around_it(self):
        report = export_of(record(BUILT_AT, region(1, 4, 0), [2, 5, 2, 5, 7, 0, 0, CODE], region(3, 3, 1)))
        self.assertAlmostEqual(self.coverage(report, 1, 4), 1 / 4)

    def test_a_zero_length_region_at_the_end_of_a_function_leaves_its_line_uncounted(self):
        report = export_of(record(BUILT_AT, region(1, 4, 0), region(3, 3, 1), [4, 1, 4, 1, 0, 0, 0, CODE]))
        self.assertAlmostEqual(self.coverage(report, 1, 4), 1 / 3)

    def test_a_zero_length_skipped_region_inside_a_function_leaves_only_its_own_line_uncounted(self):
        report = export_of(record(BUILT_AT, region(1, 5, 0), [2, 5, 2, 5, 0, 0, 0, SKIPPED], region(4, 4, 1)))
        self.assertAlmostEqual(self.coverage(report, 1, 5), 1 / 4)

    def test_a_function_listed_more_than_once_is_scored_once_from_the_merged_lines(self):
        ran = record(BUILT_AT, region(1, 3, 1))
        idle = record(BUILT_AT, region(1, 3, 0))
        self.assertEqual(self.coverage(export_of(idle, ran, idle), 1, 3), 1.0)

    def test_a_line_inside_a_skipped_region_is_not_counted(self):
        report = export_of(record(BUILT_AT, region(1, 5, 1), [3, 1, 3, 40, 0, 0, 0, SKIPPED]))
        self.assertEqual(self.coverage(report, 1, 5), 1.0)

    def test_the_outermost_body_starting_first_inside_the_function_is_the_match(self):
        report = export_of(record(BUILT_AT, region(3, 3, 0)), record(BUILT_AT, region(2, 5, 1), region(3, 4, 0)))
        self.assertAlmostEqual(self.coverage(report, 1, 5), 3 / 4)

    def test_a_function_whose_only_region_was_compiled_out_has_unknown_coverage(self):
        report = export_of(record(BUILT_AT, region(1, 3, 0, kind=SKIPPED)))
        self.assertIsNone(self.coverage(report, 1, 3))

    def test_a_closure_that_opens_before_the_body_is_not_taken_for_the_function(self):
        report = export_of(record(BUILT_AT, region(2, 3, 0)), record(BUILT_AT, region(4, 6, 1)))
        self.assertEqual(self.coverage(report, 1, 6), 1.0)

    def test_a_record_with_a_short_region_is_a_tool_error(self):
        self.assertMalformed(export_of({"name": "f", "filenames": [BUILT_AT], "regions": [[1, 5, 3]]}))

    def test_a_record_with_no_regions_key_is_a_tool_error(self):
        self.assertMalformed(export_of({"name": "f", "filenames": [BUILT_AT]}))

    def test_a_record_whose_regions_are_not_a_list_is_a_tool_error(self):
        self.assertMalformed(export_of({"name": "f", "filenames": [BUILT_AT], "regions": 7}))

    def test_a_data_item_that_is_not_an_object_is_a_tool_error(self):
        self.assertMalformed({"type": "llvm.coverage.json.export", "data": [[]]})

    def assertMalformed(self, report):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError) as raised:
                llvm_cov_reader()(write_json(tmp, report))
        self.assertTrue(str(raised.exception).startswith("bad llvm-cov export record: "))

    def test_a_summary_only_export_with_no_function_records_is_a_tool_error(self):
        summary_only = {"type": "llvm.coverage.json.export", "version": "3.0.1",
                        "data": [{"files": [{"filename": BUILT_AT, "summary": {}}], "totals": {}}]}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError) as raised:
                llvm_cov_reader()(write_json(tmp, summary_only))
        self.assertIn("-summary-only", str(raised.exception))

    def test_a_report_with_no_data_gives_every_function_unknown_coverage(self):
        self.assertIsNone(self.coverage(export_of()))

    def test_an_unreadable_export_is_a_tool_error(self):
        with self.assertRaises(ToolError) as raised:
            llvm_cov_reader()("no/such/export.json")
        self.assertTrue(str(raised.exception).startswith("cannot open llvm-cov export: "))

    def test_malformed_export_json_is_a_tool_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ToolError) as raised:
                llvm_cov_reader()(str(path))
        self.assertTrue(str(raised.exception).startswith("bad llvm-cov export JSON: "))

    def test_json_that_is_not_an_llvm_cov_export_is_a_tool_error(self):
        not_exports = {
            "list": [],
            "istanbul": {"/src/a.ts": {"path": "/src/a.ts", "statementMap": {}, "s": {}}},
            "data not a list": {"type": "llvm.coverage.json.export", "data": {}},
        }
        for name, document in not_exports.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ToolError) as raised:
                    llvm_cov_reader()(write_json(tmp, document))
                self.assertTrue(str(raised.exception).startswith("not an llvm-cov export: "))


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

    def test_crap_exits_2_on_json_that_is_not_an_llvm_cov_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_crap(["--lang", "swift", SOURCES, "--llvm-cov-json", write_json(tmp, [])])
        self.assertEqual(code, 2)
        self.assertIn("not an llvm-cov export: ", err)

    def test_crap_exits_2_on_an_export_with_a_malformed_function_record(self):
        broken = export_of({"name": "f", "filenames": [BUILT_AT], "regions": [[1, 5, 3]]})
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_crap(["--lang", "swift", SOURCES, "--llvm-cov-json", write_json(tmp, broken)])
        self.assertEqual(code, 2)
        self.assertIn("bad llvm-cov export record: ", err)

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
        self.assertIn('--llvm-cov-json "$(swift test --show-codecov-path)"', text)


if __name__ == "__main__":
    unittest.main()
