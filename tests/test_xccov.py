import json
import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from quality_gates import xccov
from quality_gates.errors import ToolError


def completed(stdout, returncode=0):
    return CompletedProcess([], returncode, stdout=stdout, stderr="")


class SwiftCoverageTest(unittest.TestCase):
    def test_unparseable_xccov_output_is_a_tool_error(self):
        with patch.object(xccov, "run", return_value=completed("{not json")):
            with self.assertRaises(ToolError):
                xccov.load("r.xcresult")

    def test_a_failed_xccov_is_a_tool_error(self):
        with patch.object(xccov, "run", return_value=CompletedProcess([], 1, stdout="", stderr="no bundle")):
            with self.assertRaises(ToolError) as raised:
                xccov.load("r.xcresult")
        self.assertEqual(str(raised.exception), "xcrun xccov failed:\nno bundle")

    def test_an_overloaded_function_is_matched_by_its_line(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "load(_:)", "lineNumber": 10, "lineCoverage": 1.0},
            {"name": "load(_:into:)", "lineNumber": 20, "lineCoverage": 0.25},
        ]})
        cov_map = {"App.swift": funcs}
        self.assertEqual(xccov.function_coverage(cov_map, "Sources/App.swift", "load", 20), 0.25)

    def test_a_name_without_a_matching_line_takes_the_first_occurrence(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "load(_:)", "lineNumber": 10, "lineCoverage": 1.0},
            {"name": "load(_:into:)", "lineNumber": 20, "lineCoverage": 0.25},
        ]})
        self.assertEqual(xccov.function_coverage({"App": funcs}, "App.swift", "load", 99), 1.0)

    def test_a_class_qualified_xccov_name_matches_lizards_bare_method_name(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "Store.load(_:)", "lineNumber": 10, "lineCoverage": 0.5},
        ]})
        self.assertEqual(xccov.function_coverage({"App.swift": funcs}, "App.swift", "load", 10), 0.5)

    def test_xccov_coverage_is_clamped_to_the_unit_interval(self):
        funcs = xccov._extract_file_funcs({"functions": [{"name": "f()", "lineNumber": 1, "lineCoverage": 1.7}]})
        self.assertEqual(funcs["f"], 1.0)

    def test_a_null_line_coverage_gives_that_function_unknown_coverage_and_its_neighbour_a_figure(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "broken()", "lineNumber": 10, "lineCoverage": None},
            {"name": "fine()", "lineNumber": 20, "lineCoverage": 0.5},
        ]})
        cov_map = {"App.swift": funcs}
        self.assertIsNone(xccov.function_coverage(cov_map, "App.swift", "broken", 10))
        self.assertEqual(xccov.function_coverage(cov_map, "App.swift", "fine", 20), 0.5)

    def test_a_missing_line_coverage_gives_unknown_coverage_not_zero(self):
        funcs = xccov._extract_file_funcs({"functions": [{"name": "broken()", "lineNumber": 10}]})
        self.assertIsNone(xccov.function_coverage({"App.swift": funcs}, "App.swift", "broken", 10))

    def test_a_line_coverage_that_is_not_a_number_gives_unknown_coverage(self):
        for name, figure in {"text": "0.5", "list": [0.5], "flag": True, "not a number": float("nan")}.items():
            with self.subTest(name):
                funcs = xccov._extract_file_funcs({"functions": [{"name": "f()", "lineNumber": 1, "lineCoverage": figure}]})
                self.assertIsNone(xccov.function_coverage({"App.swift": funcs}, "App.swift", "f", 1))

    def test_an_overload_with_unknown_coverage_does_not_borrow_its_sibling_by_name(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "load(_:)", "lineNumber": 10, "lineCoverage": 1.0},
            {"name": "load(_:into:)", "lineNumber": 20, "lineCoverage": None},
        ]})
        self.assertIsNone(xccov.function_coverage({"App.swift": funcs}, "App.swift", "load", 20))

    def test_a_present_line_coverage_of_zero_is_still_a_figure(self):
        funcs = xccov._extract_file_funcs({"functions": [{"name": "f()", "lineNumber": 1, "lineCoverage": 0}]})
        self.assertEqual(xccov.function_coverage({"App.swift": funcs}, "App.swift", "f", 1), 0.0)

    def test_xccov_report_is_indexed_by_path_file_name_and_stem(self):
        report = {"targets": [{"files": [{"path": "/src/App.swift", "functions": [
            {"name": "load()", "lineNumber": 3, "lineCoverage": 0.5},
        ]}]}]}
        with patch.object(xccov, "run", return_value=completed(json.dumps(report))):
            cov_map = xccov.load("r.xcresult")
        self.assertEqual({"/src/App.swift", "App.swift", "App"}, set(cov_map))


if __name__ == "__main__":
    unittest.main()
