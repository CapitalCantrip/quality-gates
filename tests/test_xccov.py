import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from quality_gates import xccov
from quality_gates.complexity_scan import Function
from quality_gates.errors import ToolError


def completed(stdout, returncode=0):
    return CompletedProcess([], returncode, stdout=stdout, stderr="")


def indexed(path, funcs):
    return {str(Path(path).resolve()): funcs}


def xccov_file(path, name, line, figure):
    return {"path": path, "functions": [{"name": f"{name}()", "lineNumber": line, "lineCoverage": figure}]}


def read_report(*files):
    report = {"targets": [{"files": list(files)}]}
    with patch.object(xccov, "run", return_value=completed(json.dumps(report))):
        return xccov.read("r.xcresult")


def function(file, name, line):
    return Function(file, name, 2, line, line + 1, name)


class SwiftCoverageTest(unittest.TestCase):
    def test_unparseable_xccov_output_is_a_tool_error(self):
        with patch.object(xccov, "run", return_value=completed("{not json")):
            with self.assertRaises(ToolError):
                xccov.load("r.xcresult")

    def test_xccov_output_nested_too_deeply_to_parse_is_a_tool_error(self):
        with patch.object(xccov, "run", return_value=completed("[" * 200000)):
            with self.assertRaises(ToolError) as raised:
                xccov.load("r.xcresult")
        self.assertTrue(str(raised.exception).startswith("could not parse xccov output: "))

    def test_xccov_output_with_a_number_the_parser_refuses_is_a_tool_error(self):
        with patch.object(xccov, "run", return_value=completed("1")):
            with patch("quality_gates.xccov.json.loads", side_effect=ValueError("Exceeds the limit")):
                with self.assertRaises(ToolError) as raised:
                    xccov.load("r.xcresult")
        self.assertEqual(str(raised.exception), "could not parse xccov output: Exceeds the limit")

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
        cov_map = indexed("App.swift", funcs)
        self.assertEqual(xccov.function_coverage(cov_map, "App.swift", "load", 20), 0.25)

    def test_a_name_without_a_matching_line_takes_the_first_occurrence(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "load(_:)", "lineNumber": 10, "lineCoverage": 1.0},
            {"name": "load(_:into:)", "lineNumber": 20, "lineCoverage": 0.25},
        ]})
        self.assertEqual(xccov.function_coverage(indexed("App.swift", funcs), "App.swift", "load", 99), 1.0)

    def test_a_class_qualified_xccov_name_matches_lizards_bare_method_name(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "Store.load(_:)", "lineNumber": 10, "lineCoverage": 0.5},
        ]})
        self.assertEqual(xccov.function_coverage(indexed("App.swift", funcs), "App.swift", "load", 10), 0.5)

    def test_xccov_coverage_is_clamped_to_the_unit_interval(self):
        funcs = xccov._extract_file_funcs({"functions": [{"name": "f()", "lineNumber": 1, "lineCoverage": 1.7}]})
        self.assertEqual(funcs["f"], 1.0)

    def test_a_null_line_coverage_gives_that_function_unknown_coverage_and_its_neighbour_a_figure(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "broken()", "lineNumber": 10, "lineCoverage": None},
            {"name": "fine()", "lineNumber": 20, "lineCoverage": 0.5},
        ]})
        cov_map = indexed("App.swift", funcs)
        self.assertIsNone(xccov.function_coverage(cov_map, "App.swift", "broken", 10))
        self.assertEqual(xccov.function_coverage(cov_map, "App.swift", "fine", 20), 0.5)

    def test_a_missing_line_coverage_gives_unknown_coverage_not_zero(self):
        funcs = xccov._extract_file_funcs({"functions": [{"name": "broken()", "lineNumber": 10}]})
        self.assertIsNone(xccov.function_coverage(indexed("App.swift", funcs), "App.swift", "broken", 10))

    def test_a_line_coverage_that_is_not_a_number_gives_unknown_coverage(self):
        for name, figure in {"text": "0.5", "list": [0.5], "flag": True, "not a number": float("nan")}.items():
            with self.subTest(name):
                funcs = xccov._extract_file_funcs({"functions": [{"name": "f()", "lineNumber": 1, "lineCoverage": figure}]})
                self.assertIsNone(xccov.function_coverage(indexed("App.swift", funcs), "App.swift", "f", 1))

    def test_a_line_coverage_too_large_for_a_float_gives_unknown_coverage(self):
        for name, figure in {"huge integer": 10 ** 400, "huge negative integer": -10 ** 400, "infinity": float("inf")}.items():
            with self.subTest(name):
                funcs = xccov._extract_file_funcs({"functions": [{"name": "f()", "lineNumber": 1, "lineCoverage": figure}]})
                self.assertIsNone(xccov.function_coverage(indexed("App.swift", funcs), "App.swift", "f", 1))

    def test_an_overload_with_unknown_coverage_does_not_borrow_its_sibling_by_name(self):
        funcs = xccov._extract_file_funcs({"functions": [
            {"name": "load(_:)", "lineNumber": 10, "lineCoverage": 1.0},
            {"name": "load(_:into:)", "lineNumber": 20, "lineCoverage": None},
        ]})
        self.assertIsNone(xccov.function_coverage(indexed("App.swift", funcs), "App.swift", "load", 20))

    def test_a_present_line_coverage_of_zero_is_still_a_figure(self):
        funcs = xccov._extract_file_funcs({"functions": [{"name": "f()", "lineNumber": 1, "lineCoverage": 0}]})
        self.assertEqual(xccov.function_coverage(indexed("App.swift", funcs), "App.swift", "f", 1), 0.0)

    def test_two_same_named_files_in_different_folders_are_scored_from_their_own_entries(self):
        coverage_of = read_report(
            xccov_file("/abs/Sources/A/Model.swift", "f", 3, 1.0),
            xccov_file("/abs/Sources/B/Model.swift", "f", 3, 0.0),
        )
        self.assertEqual(coverage_of(function("/abs/Sources/A/Model.swift", "f", 3)), 1.0)
        self.assertEqual(coverage_of(function("/abs/Sources/B/Model.swift", "f", 3)), 0.0)

    def test_a_relative_lizard_path_matches_the_same_file_in_an_absolute_xccov_path(self):
        absolute = str(Path("Sources/App.swift").resolve())
        coverage_of = read_report(xccov_file(absolute, "f", 3, 0.5))
        self.assertEqual(coverage_of(function("Sources/App.swift", "f", 3)), 0.5)

    def test_a_scanned_file_absent_from_the_report_has_unknown_coverage(self):
        coverage_of = read_report(xccov_file("/abs/Sources/A/Model.swift", "f", 3, 1.0))
        self.assertIsNone(coverage_of(function("/abs/Sources/B/Model.swift", "f", 3)))

    def test_a_scanned_file_with_the_name_and_stem_of_a_report_file_has_unknown_coverage(self):
        coverage_of = read_report(xccov_file("/ci/Sources/Model.swift", "f", 3, 1.0))
        self.assertIsNone(coverage_of(function("/checkout/Sources/Model.swift", "f", 3)))
        self.assertIsNone(coverage_of(function("Model", "f", 3)))

    def test_a_report_path_through_a_symlink_matches_the_real_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp).resolve() / "real"
            real.mkdir()
            (Path(tmp) / "link").symlink_to(real)
            coverage_of = read_report(xccov_file(str(Path(tmp) / "link" / "App.swift"), "f", 3, 0.5))
            self.assertEqual(coverage_of(function(str(real / "App.swift"), "f", 3)), 0.5)

    def test_a_report_file_without_a_path_is_not_matched_by_its_name(self):
        coverage_of = read_report({"name": "App.swift", "functions": [
            {"name": "f()", "lineNumber": 3, "lineCoverage": 1.0},
        ]})
        self.assertIsNone(coverage_of(function("App.swift", "f", 3)))

    def test_a_function_path_that_cannot_be_resolved_is_a_tool_error(self):
        coverage_of = read_report(xccov_file("/abs/App.swift", "f", 3, 1.0))
        with self.assertRaises(ToolError) as raised:
            coverage_of(function("/abs/Ap\u0000p.swift", "f", 3))
        self.assertTrue(str(raised.exception).startswith("cannot resolve path "))

    def test_a_report_path_that_cannot_be_resolved_is_a_tool_error(self):
        with self.assertRaises(ToolError) as raised:
            read_report(xccov_file("/abs/Ap\u0000p.swift", "f", 3, 1.0))
        self.assertTrue(str(raised.exception).startswith("cannot resolve path "))


if __name__ == "__main__":
    unittest.main()
