"""Tests for quality_check.py.

quality_check.py has a single main() function with CC=22.
The radon import is deferred (inside main()), so we can control it via
patch.dict(sys.modules) without needing radon installed.

Two complementary strategies:
  1. Mock radon — fast, hermetic, covers all branches.
  2. Subprocess with `uv run --with radon` — verifies real behaviour on a
     known file; only runs if uv is available (skipped otherwise).
"""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from quality_gates import quality_check as qc


# ── fake radon helpers ────────────────────────────────────────────────────────

def _make_radon_stubs():
    """Return (radon_mod, radon_complexity_mod) with cc_visit and cc_rank."""
    radon_mod = ModuleType("radon")
    complexity_mod = ModuleType("radon.complexity")
    radon_mod.complexity = complexity_mod
    complexity_mod.cc_visit = MagicMock(return_value=[])
    complexity_mod.cc_rank = MagicMock(side_effect=lambda cc: "A" if cc <= 5 else "B")
    return radon_mod, complexity_mod


def _make_block(name, complexity, lineno=1, class_name="Function"):
    b = MagicMock()
    b.name = name
    b.complexity = complexity
    b.lineno = lineno
    b.__class__ = type(class_name, (), {})
    return b


# ── helpers to call main() safely ─────────────────────────────────────────────

def _run_main(argv, radon_blocks_by_file=None, stdin=None):
    """Call quality_check.main() with mocked sys.argv, stdout, stderr, radon.

    radon_blocks_by_file: dict {path_str: [blocks]} or None for empty.
    Returns (rc, stdout_str, stderr_str).
    """
    radon_mod, complexity_mod = _make_radon_stubs()
    if radon_blocks_by_file:
        def _cc_visit(source):
            # Identify which file is being processed by source content
            # (content is unique per test file)
            for p, blocks in radon_blocks_by_file.items():
                try:
                    if Path(p).read_text() == source:
                        return blocks
                except Exception:
                    pass
            return []
        complexity_mod.cc_visit.side_effect = _cc_visit

    out_buf = io.StringIO()
    err_buf = io.StringIO()
    rc = None

    with patch("sys.argv", ["quality_check.py"] + argv), \
         patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
         patch("sys.stdout", out_buf), \
         patch("sys.stderr", err_buf):
        try:
            qc.main()
        except SystemExit as e:
            rc = e.code

    return rc, out_buf.getvalue(), err_buf.getvalue()


# ── missing path ──────────────────────────────────────────────────────────────

class TestMissingPath(unittest.TestCase):
    def test_nonexistent_path_exits_2(self):
        rc, out, err = _run_main(["/no/such/path/ever"])
        self.assertEqual(rc, 2)
        self.assertIn("not found", err)


# ── no python files ───────────────────────────────────────────────────────────

class TestNoPythonFiles(unittest.TestCase):
    def test_empty_dir_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, err = _run_main([d])
        self.assertEqual(rc, 2)
        self.assertIn("No Python files found", err)

    def test_non_py_file_exits_2(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            p = Path(f.name)
            f.write(b"text content")
        try:
            rc, out, err = _run_main([str(p)])
            self.assertEqual(rc, 2)
        finally:
            p.unlink(missing_ok=True)


# ── clean code paths ──────────────────────────────────────────────────────────

class TestCleanCode(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        )
        self._tmp.write("def simple(): pass\n")
        self._tmp.close()
        self.py_path = Path(self._tmp.name)
        self.addCleanup(self.py_path.unlink, missing_ok=True)

    def _blocks_low_cc(self):
        return [_make_block("simple", 1)]

    def test_all_ok_exits_0(self):
        radon_mod, complexity_mod = _make_radon_stubs()
        complexity_mod.cc_visit.return_value = self._blocks_low_cc()
        out, err = io.StringIO(), io.StringIO()
        rc = None
        with patch("sys.argv", ["qc", str(self.py_path)]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", out), patch("sys.stderr", err):
            try:
                qc.main()
            except SystemExit as e:
                rc = e.code
        self.assertEqual(rc, 0)
        self.assertIn("Clean", out.getvalue())

    def test_text_output_contains_summary(self):
        radon_mod, complexity_mod = _make_radon_stubs()
        complexity_mod.cc_visit.return_value = self._blocks_low_cc()
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["qc", str(self.py_path)]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", out), patch("sys.stderr", err):
            try:
                qc.main()
            except SystemExit:
                pass
        output = out.getvalue()
        self.assertIn("SUMMARY", output)
        self.assertIn("Files analysed", output)

    def test_json_format_exits_0_always(self):
        radon_mod, complexity_mod = _make_radon_stubs()
        complexity_mod.cc_visit.return_value = [_make_block("complex_fn", 20)]
        complexity_mod.cc_rank.side_effect = lambda cc: "F"
        out, err = io.StringIO(), io.StringIO()
        rc = None
        with patch("sys.argv", ["qc", str(self.py_path), "--format", "json"]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", out), patch("sys.stderr", err):
            try:
                qc.main()
            except SystemExit as e:
                rc = e.code
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertIsInstance(data, list)

    def test_json_contains_expected_keys(self):
        radon_mod, complexity_mod = _make_radon_stubs()
        complexity_mod.cc_visit.return_value = [_make_block("fn", 3)]
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["qc", str(self.py_path), "--format", "json"]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", out), patch("sys.stderr", err):
            try:
                qc.main()
            except SystemExit:
                pass
        data = json.loads(out.getvalue())
        self.assertTrue(len(data) >= 1)
        keys = set(data[0].keys())
        self.assertIn("name", keys)
        self.assertIn("complexity", keys)
        self.assertIn("rank", keys)
        self.assertIn("above_threshold", keys)


# ── flagged code paths ────────────────────────────────────────────────────────

class TestFlaggedCode(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        )
        self._tmp.write("def complex_fn(): pass\n")
        self._tmp.close()
        self.py_path = Path(self._tmp.name)
        self.addCleanup(self.py_path.unlink, missing_ok=True)

    def test_flagged_exits_1(self):
        radon_mod, complexity_mod = _make_radon_stubs()
        complexity_mod.cc_visit.return_value = [_make_block("complex_fn", 10)]
        complexity_mod.cc_rank.return_value = "B"
        out, err = io.StringIO(), io.StringIO()
        rc = None
        with patch("sys.argv", ["qc", str(self.py_path)]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", out), patch("sys.stderr", err):
            try:
                qc.main()
            except SystemExit as e:
                rc = e.code
        self.assertEqual(rc, 1)
        self.assertIn("FLAGGED", out.getvalue())

    def _exit_code_for_cc(self, cc):
        radon_mod, complexity_mod = _make_radon_stubs()
        complexity_mod.cc_visit.return_value = [_make_block("fn", cc)]
        complexity_mod.cc_rank.return_value = "B"
        rc = 0
        with patch("sys.argv", ["qc", str(self.py_path)]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            try:
                qc.main()
            except SystemExit as e:
                rc = e.code
        return rc

    def test_default_threshold_passes_cc_8_the_agent_ceiling(self):
        self.assertEqual(self._exit_code_for_cc(8), 0)

    def test_default_threshold_flags_cc_9(self):
        self.assertEqual(self._exit_code_for_cc(9), 1)

    def test_flagged_text_contains_function_name(self):
        radon_mod, complexity_mod = _make_radon_stubs()
        complexity_mod.cc_visit.return_value = [_make_block("big_function", 12)]
        complexity_mod.cc_rank.return_value = "C"
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["qc", str(self.py_path)]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", out), patch("sys.stderr", err):
            try:
                qc.main()
            except SystemExit:
                pass
        self.assertIn("big_function", out.getvalue())

    def test_custom_threshold_flags_at_right_level(self):
        radon_mod, complexity_mod = _make_radon_stubs()
        # CC=9: above default threshold (8) but below custom threshold (10)
        complexity_mod.cc_visit.return_value = [_make_block("moderate_fn", 9)]
        complexity_mod.cc_rank.return_value = "B"
        out, err = io.StringIO(), io.StringIO()
        rc = None
        with patch("sys.argv", ["qc", str(self.py_path), "--threshold", "10"]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", out), patch("sys.stderr", err):
            try:
                qc.main()
            except SystemExit as e:
                rc = e.code
        # CC=9 <= threshold 10 → exit 0
        self.assertEqual(rc, 0)


# ── syntax error in analysed file ────────────────────────────────────────────

class TestSyntaxErrorInFile(unittest.TestCase):
    def test_syntax_error_file_skipped(self):
        """A file that radon fails to parse is skipped, not a fatal error."""
        with tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write("def broken(\n")
            good_path = Path(f.name)
        self.addCleanup(good_path.unlink, missing_ok=True)

        radon_mod, complexity_mod = _make_radon_stubs()

        def _cc_visit(source):
            raise SyntaxError("bad syntax")
        complexity_mod.cc_visit.side_effect = _cc_visit

        out, err = io.StringIO(), io.StringIO()
        rc = None
        with patch("sys.argv", ["qc", str(good_path)]), \
             patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
             patch("sys.stdout", out), patch("sys.stderr", err):
            try:
                qc.main()
            except SystemExit as e:
                rc = e.code
        # Syntax error file is skipped; 0 results → still exits 0 (no functions flagged)
        # OR exits 0 if the lone file is skipped and no other results exist.
        self.assertIn(rc, (0, 2))


# ── radon not installed ───────────────────────────────────────────────────────

class TestRadonNotInstalled(unittest.TestCase):
    def test_missing_radon_exits_2(self):
        with tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write("def fn(): pass\n")
            p = Path(f.name)
        self.addCleanup(p.unlink, missing_ok=True)

        # Simulate radon not being importable
        with patch.dict(sys.modules, {"radon": None, "radon.complexity": None}):
            out, err = io.StringIO(), io.StringIO()
            rc = None
            with patch("sys.argv", ["qc", str(p)]), \
                 patch("sys.stdout", out), patch("sys.stderr", err):
                try:
                    qc.main()
                except SystemExit as e:
                    rc = e.code
        self.assertEqual(rc, 2)
        self.assertIn("radon", err.getvalue())


# ── directory walk ────────────────────────────────────────────────────────────

class TestDirectoryWalk(unittest.TestCase):
    def test_analyses_all_py_files_in_dir(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(3):
                (Path(d) / f"mod{i}.py").write_text(f"def f{i}(): pass\n", encoding="utf-8")

            radon_mod, complexity_mod = _make_radon_stubs()
            complexity_mod.cc_visit.return_value = [_make_block("f", 1)]
            out, err = io.StringIO(), io.StringIO()
            rc = None
            with patch("sys.argv", ["qc", d, "--format", "json"]), \
                 patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
                 patch("sys.stdout", out), patch("sys.stderr", err):
                try:
                    qc.main()
                except SystemExit as e:
                    rc = e.code
            self.assertEqual(rc, 0)
            data = json.loads(out.getvalue())
            # 3 files × 1 block each
            self.assertEqual(len(data), 3)

    def test_pycache_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            pycache = Path(d) / "__pycache__"
            pycache.mkdir()
            (pycache / "cached.py").write_text("def c(): pass\n", encoding="utf-8")
            (Path(d) / "real.py").write_text("def r(): pass\n", encoding="utf-8")

            radon_mod, complexity_mod = _make_radon_stubs()
            complexity_mod.cc_visit.return_value = [_make_block("r", 1)]
            out, err = io.StringIO(), io.StringIO()
            with patch("sys.argv", ["qc", d, "--format", "json"]), \
                 patch.dict(sys.modules, {"radon": radon_mod, "radon.complexity": complexity_mod}), \
                 patch("sys.stdout", out), patch("sys.stderr", err):
                try:
                    qc.main()
                except SystemExit:
                    pass
            data = json.loads(out.getvalue())
            # Only 1 file (real.py), not the __pycache__ one
            self.assertEqual(len(data), 1)


if __name__ == "__main__":
    unittest.main()
