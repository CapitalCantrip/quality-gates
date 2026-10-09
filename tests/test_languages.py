import argparse
import os
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from quality_gates import complexity_scan, crap, languages, xccov
from quality_gates import quality_check as qc
from quality_gates.complexity_scan import Function

ROOT = Path(__file__).resolve().parents[1]
PYTHON_REPORT = "tests/fixtures/python/coverage-report.json"
PYTHON_SAMPLE = "tests/fixtures/python/sample.py"
SWIFT_REPORT = ROOT / "tests/fixtures/swift/xccov-report.json"
TYPESCRIPT_REPORT = "tests/fixtures/typescript/coverage-final.json"
TYPESCRIPT_SAMPLE = "tests/fixtures/typescript/sample.ts"


def reader(lang):
    return languages.LANGUAGES[lang].coverage[0].read


class LanguageRecordTest(unittest.TestCase):
    def test_every_language_crap_accepts_has_a_counting_tool_suffixes_and_a_coverage_reader(self):
        for name, language in languages.LANGUAGES.items():
            with self.subTest(name):
                self.assertEqual(crap.build_parser().parse_args(["--lang", name]).lang, name)
                self.assertTrue(language.label)
                self.assertIn(language.counter, complexity_scan.COUNTING_TOOLS)
                self.assertTrue(language.suffixes)
                self.assertTrue(language.coverage)
                if language.counter == languages.LIZARD:
                    self.assertTrue(language.lizard_languages)
                for coverage in language.coverage:
                    self.assertTrue(coverage.flag.startswith("--"))
                    self.assertTrue(coverage.flag[len("--"):])
                    self.assertTrue(coverage.source)
                    self.assertTrue(coverage.help)
                    self.assertTrue(callable(coverage.read))

    def test_every_language_says_where_its_coverage_comes_from(self):
        for name, language in languages.LANGUAGES.items():
            with self.subTest(name):
                self.assertTrue(language.coverage_from)

    def test_a_language_lists_its_suffixes_in_declaration_order_for_help(self):
        self.assertEqual(languages.LANGUAGES["typescript"].suffix_text, ".ts .tsx .js .jsx .cjs .mjs")

    def test_every_language_cc_check_accepts_has_a_nothing_found_message(self):
        self.assertEqual(languages.CC_CHECK_LANGUAGES, ["python", "typescript"])
        for name, language in languages.LANGUAGES.items():
            with self.subTest(name):
                self.assertEqual(name in languages.CC_CHECK_LANGUAGES, language.cc_check)
                if language.cc_check:
                    self.assertEqual(qc.build_parser().parse_args(["--lang", name, "x"]).lang, name)
                    self.assertTrue(language.cc_check_nothing_found)

    def test_no_two_languages_share_a_coverage_flag(self):
        flags = [coverage.flag for coverage in languages.COVERAGE_FORMATS]
        self.assertEqual(sorted(flags), sorted(set(flags)))

    def test_coverage_flags_are_offered_in_language_order(self):
        flags = [coverage.flag for coverage in languages.COVERAGE_FORMATS]
        self.assertEqual(flags, ["--coverage-json", "--xcresult", "--istanbul-json"])

    def test_each_coverage_format_names_its_own_json_source_tag(self):
        sources = {coverage.flag: coverage.source for coverage in languages.COVERAGE_FORMATS}
        self.assertEqual(sources, {
            "--coverage-json": "coverage-json", "--xcresult": "xcresult", "--istanbul-json": "istanbul-json",
        })

    def test_each_coverage_format_stores_its_report_where_argparse_would_by_default(self):
        for coverage in languages.COVERAGE_FORMATS:
            with self.subTest(coverage.flag):
                self.assertEqual(argparse.ArgumentParser().add_argument(coverage.flag).dest, coverage.dest)


class CoverageReaderTest(unittest.TestCase):
    def setUp(self):
        before = os.getcwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, before)

    def xccov(self):
        stdout = SWIFT_REPORT.read_text(encoding="utf-8")
        return patch.object(xccov, "run", return_value=CompletedProcess([], 0, stdout=stdout, stderr=""))

    def test_python_coverage_is_the_branch_coverage_within_the_functions_lines(self):
        coverage_of = reader("python")(PYTHON_REPORT)
        self.assertEqual(coverage_of(Function(PYTHON_SAMPLE, "grade", 2, 1, 4, "grade")), 0.5)

    def test_swift_coverage_is_matched_by_the_name_before_its_label_and_the_start_line(self):
        with self.xccov():
            coverage_of = reader("swift")("App.xcresult")
        self.assertEqual(coverage_of(Function("Sources/Store.swift", "load#2", 3, 20, 30, "load")), 0.25)

    def test_typescript_coverage_is_the_branch_coverage_within_istanbuls_function_range(self):
        coverage_of = reader("typescript")(TYPESCRIPT_REPORT)
        self.assertEqual(coverage_of(Function(TYPESCRIPT_SAMPLE, "grade", 5, 1, 10, "grade")), 0.875)

    def test_a_function_in_a_file_the_report_does_not_cover_has_unknown_coverage(self):
        with self.xccov():
            readers = {
                "python": reader("python")(PYTHON_REPORT),
                "swift": reader("swift")("App.xcresult"),
                "typescript": reader("typescript")(TYPESCRIPT_REPORT),
            }
        for lang, coverage_of in readers.items():
            with self.subTest(lang):
                self.assertIsNone(coverage_of(Function("elsewhere/Other.x", "f", 2, 1, 4, "f")))


if __name__ == "__main__":
    unittest.main()
