import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from quality_gates import languages
from quality_gates import quality_check as qc


def branches(name, count):
    body = "".join(f"    if x == {i}:\n        return {i}\n" for i in range(count))
    return f"def {name}(x):\n{body}    return -1\n"


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            qc.main(argv)
        except SystemExit as stop:
            return stop.code, out.getvalue(), err.getvalue()
    raise AssertionError("main did not exit")


class InTempDir(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        before = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, before)

    def write(self, path, text):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")


class TestMissingPath(unittest.TestCase):
    def test_a_path_that_does_not_exist_exits_2_with_the_path_named(self):
        rc, _, err = run_main(["/no/such/path/ever"])
        self.assertEqual(rc, 2)
        self.assertEqual(err, "ERROR: path not found: /no/such/path/ever\n")


class TestNoPythonFiles(InTempDir):
    def test_an_empty_folder_exits_2(self):
        Path("empty").mkdir()
        rc, _, err = run_main(["empty"])
        self.assertEqual(rc, 2)
        self.assertEqual(err, "No Python files found.\n")

    def test_a_file_that_is_not_python_exits_2(self):
        self.write("notes.txt", "text content")
        self.assertEqual(run_main(["notes.txt"])[0], 2)


class TestCleanCode(InTempDir):
    def setUp(self):
        super().setUp()
        self.write("mod.py", branches("simple", 0))

    def test_all_ok_exits_0(self):
        rc, out, _ = run_main(["mod.py"])
        self.assertEqual(rc, 0)
        self.assertIn("Clean", out)

    def test_text_output_contains_summary(self):
        _, out, _ = run_main(["mod.py"])
        self.assertIn("SUMMARY", out)
        self.assertIn("Files analysed", out)

    def test_json_lists_every_function_with_no_rank(self):
        _, out, _ = run_main(["mod.py", "--format", "json"])
        self.assertEqual(json.loads(out), [{
            "file": "mod.py", "name": "simple", "fullname": "simple", "type": "Function",
            "complexity": 1, "line": 1, "above_threshold": False,
        }])


class TestFlaggedCode(InTempDir):
    def gate(self, cc, *extra):
        self.write("mod.py", branches("fn", cc - 1))
        return run_main(["mod.py", *extra])

    def test_flagged_exits_1(self):
        rc, out, _ = self.gate(10)
        self.assertEqual(rc, 1)
        self.assertIn("FLAGGED", out)

    def test_default_threshold_passes_cc_8_the_agent_ceiling(self):
        self.assertEqual(self.gate(8)[0], 0)

    def test_default_threshold_flags_cc_9(self):
        self.assertEqual(self.gate(9)[0], 1)

    def test_a_flagged_row_shows_the_cc_and_name_without_a_letter_grade(self):
        _, out, _ = self.gate(12)
        self.assertIn("  CC= 12  mod.py:1  fn\n", out)
        self.assertNotIn("[C]", out)

    def test_json_format_exits_0_even_when_a_function_is_flagged(self):
        rc, out, _ = self.gate(20, "--format", "json")
        self.assertEqual(rc, 0)
        self.assertIsInstance(json.loads(out), list)

    def test_a_custom_threshold_of_10_passes_a_cc_9_function_the_default_would_flag(self):
        self.assertEqual(self.gate(9, "--threshold", "10")[0], 0)


class TestNames(InTempDir):
    def test_a_class_gets_no_score(self):
        self.write("mod.py", "class K:\n    def m(self):\n        pass\n")
        _, out, _ = run_main(["mod.py", "--format", "json"])
        self.assertEqual([r["fullname"] for r in json.loads(out)], ["K.m"])

    def test_closures_and_nested_class_methods_are_reported_by_their_dotted_name(self):
        self.write("mod.py", "def outer():\n    def inner():\n        pass\n\n\nclass K:\n    class Inner:\n        def deep(self):\n            pass\n")
        _, out, _ = run_main(["mod.py", "--format", "json"])
        self.assertEqual({r["fullname"] for r in json.loads(out)}, {"outer", "outer.inner", "K.Inner.deep"})


class TestSyntaxErrorInFile(InTempDir):
    def test_a_file_radon_cannot_parse_is_skipped_and_the_run_passes(self):
        self.write("bad.py", "def broken(:\n")
        self.write("good.py", branches("g", 0))
        rc, out, _ = run_main([".", "--format", "json"])
        self.assertEqual(rc, 0)
        self.assertEqual([r["name"] for r in json.loads(out)], ["g"])


class TestRadonNotInstalled(InTempDir):
    def test_missing_radon_exits_2_with_the_install_instruction(self):
        self.write("mod.py", branches("f", 0))
        with patch.dict(sys.modules, {"radon": None, "radon.visitors": None}):
            rc, _, err = run_main(["mod.py"])
        self.assertEqual(rc, 2)
        self.assertEqual(err, "ERROR: radon is not installed.\n  Install with: pip3 install radon\n")


class TestSkippedFolders(InTempDir):
    def setUp(self):
        super().setUp()
        self.write("src/build/gen.py", branches("gen", 0))
        self.write("src/real.py", branches("real", 0))

    def test_a_build_folder_is_skipped_and_named_after_the_text_report(self):
        rc, out, _ = run_main(["src"])
        self.assertEqual(rc, 0)
        self.assertTrue(out.endswith("Skipped 1 folder(s): src/build\n"))

    def test_json_keeps_its_bare_list_and_names_the_skipped_folder_on_stderr(self):
        _, out, err = run_main(["src", "--format", "json"])
        self.assertEqual([r["name"] for r in json.loads(out)], ["real"])
        self.assertEqual(err, "Skipped 1 folder(s): src/build\n")

    def test_a_scan_with_nothing_skipped_prints_no_skipped_line(self):
        _, out, _ = run_main(["src/real.py"])
        self.assertNotIn("Skipped", out)

    def test_the_pycache_folder_is_skipped(self):
        self.write("src/__pycache__/cached.py", branches("cached", 0))
        _, out, _ = run_main(["src", "--format", "json"])
        self.assertEqual([r["name"] for r in json.loads(out)], ["real"])


class TestDirectoryWalk(InTempDir):
    def test_analyses_all_py_files_in_dir(self):
        for i in range(3):
            self.write(f"pkg/mod{i}.py", branches(f"f{i}", 0))
        rc, out, _ = run_main(["pkg", "--format", "json"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(json.loads(out)), 3)


class HelpTest(unittest.TestCase):
    def flat_help(self):
        code, out, _ = run_main(["--help"])
        self.assertEqual(code, 0)
        return " ".join(out.split())

    def test_help_lists_every_suffix_of_every_cc_check_language(self):
        flat = self.flat_help()
        for name in languages.CC_CHECK_LANGUAGES:
            for suffix in languages.LANGUAGES[name].suffixes:
                with self.subTest(suffix):
                    self.assertRegex(flat, re.escape(suffix) + r"\b")

    def test_the_lang_help_names_each_checker_with_the_suffixes_it_counts(self):
        flat = self.flat_help()
        for name in languages.CC_CHECK_LANGUAGES:
            language = languages.LANGUAGES[name]
            with self.subTest(name):
                self.assertIn(f"{name} counts {language.suffix_text} with {language.counter}", flat)

    def test_the_description_names_the_python_and_typescript_checkers(self):
        self.assertIn("Cyclomatic complexity reporter for Python and TypeScript code", self.flat_help())


if __name__ == "__main__":
    unittest.main()
