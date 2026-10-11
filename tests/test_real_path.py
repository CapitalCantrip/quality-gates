import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from quality_gates import coverage_json, istanbul, ratchet
from quality_gates.real_path import real_path


class InCaseInsensitiveTree(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / "shared" / "Shop").mkdir(parents=True)
        (self.root / "shared" / "Shop" / "shop.py").write_text("x = 1\n")
        if not (self.root / "shared" / "shop").exists():
            self.skipTest("this volume is case sensitive")
        (self.root / "pa").mkdir()
        (self.root / "pb").mkdir()
        os.symlink(self.root / "shared" / "Shop", self.root / "pa" / "x")
        os.symlink(self.root / "shared" / "shop", self.root / "pb" / "x")
        self.true_case = str(self.root / "shared" / "Shop" / "shop.py")


class NoTrueCaseLookupTest(InCaseInsensitiveTree):
    def test_a_platform_with_no_true_case_lookup_keeps_the_link_spelling(self):
        with patch("quality_gates.real_path.GET_PATH", None):
            self.assertEqual(
                real_path(str(self.root / "pb" / "x" / "shop.py")),
                str(self.root / "shared" / "shop" / "shop.py"),
            )


class TrueCasePathTest(InCaseInsensitiveTree):
    def test_a_link_spelled_in_the_wrong_case_resolves_to_the_case_on_disk(self):
        self.assertEqual(real_path(str(self.root / "pb" / "x" / "shop.py")), self.true_case)

    def test_a_path_typed_in_the_wrong_case_resolves_to_the_case_on_disk(self):
        self.assertEqual(real_path(str(self.root / "SHARED" / "shop" / "SHOP.py")), self.true_case)


class TrueCaseKeyTest(InCaseInsensitiveTree):
    def test_two_links_spelling_a_folder_in_different_case_give_the_file_one_key(self):
        keys = {ratchet.key(self.root, str(self.root / link / "x" / "shop.py"), "f") for link in ("pa", "pb")}
        self.assertEqual(keys, {"shared/Shop/shop.py::f"})


class TrueCaseCoverageTest(InCaseInsensitiveTree):
    def test_a_coverage_json_figure_is_found_through_a_link_spelled_in_the_wrong_case(self):
        report = self.root / "coverage.json"
        report.write_text(json.dumps({"files": {self.true_case: {"executed_lines": [1, 2], "missing_lines": [3, 4]}}}))
        files = coverage_json.load(str(report))
        found = coverage_json.function_coverage(files, str(self.root / "pb" / "x" / "shop.py"), 1, 4)
        self.assertEqual(found, 0.5)

    def test_an_istanbul_figure_is_found_through_a_link_spelled_in_the_wrong_case(self):
        entry = {"statementMap": {"0": {"start": {"line": 1}}}, "s": {"0": 1}}
        report = self.root / "coverage-final.json"
        report.write_text(json.dumps({self.true_case: entry}))
        files = istanbul.load(str(report))
        found = istanbul.function_coverage(files, str(self.root / "pb" / "x" / "shop.py"), 1, 2)
        self.assertEqual(found, 1.0)


class CoverageLookupCostTest(unittest.TestCase):
    def test_a_file_with_three_functions_has_its_real_path_read_once(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder).resolve() / "mod.py"
            file.write_text("x = 1\n")
            report = Path(folder) / "coverage.json"
            report.write_text(json.dumps({"files": {str(file): {"executed_lines": [1], "missing_lines": []}}}))
            lookup = coverage_json.read(str(report))
            with patch("quality_gates.coverage_json.real_path", wraps=real_path) as spy:
                for start in (1, 2, 3):
                    lookup(SimpleNamespace(file=str(file), start=start, end=start))
            self.assertEqual(spy.call_count, 1)


class FallbackTest(unittest.TestCase):
    def test_a_path_whose_true_case_cannot_be_read_keeps_the_resolved_path(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder).resolve() / "mod.py"
            file.write_text("x = 1\n")
            with patch("os.open", side_effect=OSError("no")):
                self.assertEqual(real_path(str(file)), str(file))

    def test_a_platform_with_no_true_case_lookup_keeps_the_resolved_path(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder).resolve() / "mod.py"
            file.write_text("x = 1\n")
            with patch("quality_gates.real_path.GET_PATH", None):
                self.assertEqual(real_path(str(file)), str(file))

    def test_a_path_that_does_not_exist_keeps_the_resolved_path(self):
        self.assertEqual(real_path("/nowhere/Mod.py"), "/nowhere/Mod.py")


if __name__ == "__main__":
    unittest.main()
