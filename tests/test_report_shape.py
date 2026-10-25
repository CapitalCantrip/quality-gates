import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import patch

from quality_gates import coverage_json, istanbul, xccov
from quality_gates.errors import ToolError

ISTANBUL_STATEMENT = {"statementMap": {"0": {"start": {"line": 1}}}, "s": {"0": 1}}


class ReportFile(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.report = Path(tmp.name) / "report.json"

    def written(self, document):
        self.report.write_text(json.dumps(document), encoding="utf-8")
        return str(self.report)

    def assertRefused(self, label, load, document):
        with self.assertRaises(ToolError) as raised:
            load(document)
        self.assertTrue(str(raised.exception).startswith(f"bad {label}: "), str(raised.exception))


class CoverageJsonShapeTest(ReportFile):
    def load(self, document):
        return coverage_json.load(self.written(document))

    def test_a_document_that_is_not_an_object_is_refused(self):
        self.assertRefused("coverage JSON", self.load, [])

    def test_a_files_map_that_is_not_an_object_is_refused(self):
        self.assertRefused("coverage JSON", self.load, {"files": []})

    def test_a_file_entry_that_is_not_an_object_is_refused(self):
        self.assertRefused("coverage JSON", self.load, {"files": {"a.py": []}})

    def test_a_line_list_that_is_not_a_list_of_line_numbers_is_refused(self):
        for lines in (None, 5, [[1]]):
            with self.subTest(lines=lines):
                self.assertRefused("coverage JSON", self.load, {"files": {"a.py": {"executed_lines": lines}}})

    def test_a_branch_that_is_not_a_pair_of_lines_is_refused(self):
        self.assertRefused("coverage JSON", self.load, {"files": {"a.py": {"missing_branches": [3]}}})

    def test_a_document_without_files_loads_with_no_figures(self):
        self.assertEqual(self.load({}), {})


class IstanbulShapeTest(ReportFile):
    def load(self, document):
        return istanbul.load(self.written(document))

    def coverage(self, entry):
        coverage_of = istanbul.read(self.written({"/abs/a.ts": entry}))
        return coverage_of(SimpleNamespace(file="/abs/a.ts", start=1, end=2))

    def test_a_document_that_is_not_an_object_is_refused(self):
        self.assertRefused("Istanbul coverage JSON", self.load, [])

    def test_a_file_entry_that_is_not_an_object_is_refused(self):
        self.assertRefused("Istanbul coverage JSON", self.load, {"a.ts": []})

    def test_a_function_record_of_the_wrong_shape_is_refused(self):
        entry = {**ISTANBUL_STATEMENT, "fnMap": {"0": {"decl": None}}}
        self.assertRefused("Istanbul coverage JSON", self.coverage, entry)

    def test_a_statement_record_of_the_wrong_shape_is_refused(self):
        self.assertRefused("Istanbul coverage JSON", self.coverage, {"statementMap": {"0": []}})

    def test_an_entry_without_statements_has_no_figure(self):
        self.assertIsNone(self.coverage({}))


def xccov_output(document):
    stdout = json.dumps(document).encode("utf-8")
    return patch.object(xccov, "run", return_value=CompletedProcess([], 0, stdout=stdout, stderr=b""))


def xccov_function(**fields):
    return {"targets": [{"files": [{"path": "/abs/a.swift", "functions": [{"lineNumber": 3, "lineCoverage": 1.0, **fields}]}]}]}


class XccovShapeTest(unittest.TestCase):
    def load(self, document):
        with xccov_output(document):
            return xccov.load("r.xcresult")

    def assertRefused(self, document):
        with self.assertRaises(ToolError) as raised:
            self.load(document)
        self.assertTrue(str(raised.exception).startswith("bad xccov output: "), str(raised.exception))

    def test_a_document_that_is_not_an_object_is_refused(self):
        self.assertRefused([])

    def test_a_target_list_or_target_of_the_wrong_shape_is_refused(self):
        for targets in ({}, [[]], [{"files": {}}], [{"files": [[]]}]):
            with self.subTest(targets=targets):
                self.assertRefused({"targets": targets})

    def test_a_file_path_that_is_not_text_is_refused(self):
        self.assertRefused({"targets": [{"files": [{"path": 123, "functions": []}]}]})

    def test_a_function_list_or_record_of_the_wrong_shape_is_refused(self):
        for functions in ({}, [None]):
            with self.subTest(functions=functions):
                self.assertRefused({"targets": [{"files": [{"path": "/abs/a.swift", "functions": functions}]}]})

    def test_a_function_name_that_is_not_text_is_refused(self):
        for name in (None, 7):
            with self.subTest(name=name):
                self.assertRefused(xccov_function(name=name))

    def test_a_function_with_a_null_figure_still_loads_with_no_figure(self):
        loaded = self.load(xccov_function(name="f()", lineCoverage=None))
        self.assertEqual(list(loaded.values()), [{("f", 3): None, "f": None}])


if __name__ == "__main__":
    unittest.main()
