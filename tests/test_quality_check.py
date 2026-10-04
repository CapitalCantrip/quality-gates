import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from quality_gates import quality_check as qc


def radon_stub(blocks=(), rank="A"):
    radon_mod = ModuleType("radon")
    complexity_mod = ModuleType("radon.complexity")
    radon_mod.complexity = complexity_mod
    complexity_mod.cc_visit = MagicMock(return_value=list(blocks))
    complexity_mod.cc_rank = MagicMock(return_value=rank)
    return {"radon": radon_mod, "radon.complexity": complexity_mod}


def block(name, complexity, lineno=1):
    b = MagicMock()
    b.name = name
    b.fullname = name
    b.complexity = complexity
    b.lineno = lineno
    b.__class__ = type("Function", (), {})
    return b


def run_main(argv, modules=None):
    out, err = io.StringIO(), io.StringIO()
    with patch.dict(sys.modules, modules or radon_stub()), redirect_stdout(out), redirect_stderr(err):
        try:
            qc.main(argv)
        except SystemExit as stop:
            return stop.code, out.getvalue(), err.getvalue()
    raise AssertionError("main did not exit")


class PythonFileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.py_path = Path(tmp.name) / "mod.py"
        self.py_path.write_text("def fn(): pass\n", encoding="utf-8")

    def gate(self, *blocks, rank="A", extra=()):
        return run_main([str(self.py_path), *extra], radon_stub(blocks, rank))


class TestMissingPath(unittest.TestCase):
    def test_nonexistent_path_exits_2(self):
        rc, _, err = run_main(["/no/such/path/ever"])
        self.assertEqual(rc, 2)
        self.assertIn("not found", err)


class TestNoPythonFiles(unittest.TestCase):
    def test_empty_dir_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = run_main([d])
        self.assertEqual(rc, 2)
        self.assertIn("No Python files found", err)

    def test_non_py_file_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            text = Path(d) / "notes.txt"
            text.write_text("text content", encoding="utf-8")
            rc, _, _ = run_main([str(text)])
        self.assertEqual(rc, 2)


class TestCleanCode(PythonFileTest):
    def test_all_ok_exits_0(self):
        rc, out, _ = self.gate(block("simple", 1))
        self.assertEqual(rc, 0)
        self.assertIn("Clean", out)

    def test_text_output_contains_summary(self):
        _, out, _ = self.gate(block("simple", 1))
        self.assertIn("SUMMARY", out)
        self.assertIn("Files analysed", out)

    def test_json_format_exits_0_even_when_a_function_is_flagged(self):
        rc, out, _ = self.gate(block("complex_fn", 20), rank="F", extra=["--format", "json"])
        self.assertEqual(rc, 0)
        self.assertIsInstance(json.loads(out), list)

    def test_json_contains_expected_keys(self):
        _, out, _ = self.gate(block("fn", 3), extra=["--format", "json"])
        data = json.loads(out)
        self.assertGreaterEqual(len(data), 1)
        self.assertLessEqual({"name", "complexity", "rank", "above_threshold"}, set(data[0]))


class TestFlaggedCode(PythonFileTest):
    def test_flagged_exits_1(self):
        rc, out, _ = self.gate(block("complex_fn", 10), rank="B")
        self.assertEqual(rc, 1)
        self.assertIn("FLAGGED", out)

    def test_default_threshold_passes_cc_8_the_agent_ceiling(self):
        self.assertEqual(self.gate(block("fn", 8))[0], 0)

    def test_default_threshold_flags_cc_9(self):
        self.assertEqual(self.gate(block("fn", 9))[0], 1)

    def test_flagged_text_contains_function_name(self):
        _, out, _ = self.gate(block("big_function", 12), rank="C")
        self.assertIn("big_function", out)

    def test_a_custom_threshold_of_10_passes_a_cc_9_function_the_default_would_flag(self):
        rc, _, _ = self.gate(block("moderate_fn", 9), extra=["--threshold", "10"])
        self.assertEqual(rc, 0)


class TestSyntaxErrorInFile(PythonFileTest):
    def test_a_file_radon_cannot_parse_is_skipped_and_the_run_passes(self):
        modules = radon_stub()
        modules["radon.complexity"].cc_visit.side_effect = SyntaxError("bad syntax")
        rc, _, _ = run_main([str(self.py_path)], modules)
        self.assertEqual(rc, 0)


class TestRadonNotInstalled(PythonFileTest):
    def test_missing_radon_exits_2(self):
        rc, _, err = run_main([str(self.py_path)], {"radon": None, "radon.complexity": None})
        self.assertEqual(rc, 2)
        self.assertIn("radon", err)


class TestDirectoryWalk(unittest.TestCase):
    def test_analyses_all_py_files_in_dir(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(3):
                (Path(d) / f"mod{i}.py").write_text(f"def f{i}(): pass\n", encoding="utf-8")
            rc, out, _ = run_main([d, "--format", "json"], radon_stub([block("f", 1)]))
        self.assertEqual(rc, 0)
        self.assertEqual(len(json.loads(out)), 3)

    def test_pycache_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            pycache = Path(d) / "__pycache__"
            pycache.mkdir()
            (pycache / "cached.py").write_text("def c(): pass\n", encoding="utf-8")
            (Path(d) / "real.py").write_text("def r(): pass\n", encoding="utf-8")
            _, out, _ = run_main([d, "--format", "json"], radon_stub([block("r", 1)]))
        self.assertEqual([r["name"] for r in json.loads(out)], ["r"])


if __name__ == "__main__":
    unittest.main()
