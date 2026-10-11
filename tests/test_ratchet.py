import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from quality_gates import crap
from quality_gates import quality_check as qc
from quality_gates import ratchet


def branchy(name, branches, indent=""):
    body = "".join(f"{indent}    if x == {n}:\n{indent}        return {n}\n" for n in range(branches))
    return f"{indent}def {name}(x):\n{body}{indent}    return -1\n"


def call(entry, argv, root):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            entry(argv, root=root)
        except SystemExit as stop:
            return stop.code, out.getvalue() + err.getvalue()
    raise AssertionError("main did not exit")


class KeyTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        before = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, before)
        (self.root / "shared" / "Shop").mkdir(parents=True)
        (self.root / "src").mkdir()
        (self.root / "shared" / "Shop" / "shop.py").write_text("x = 1\n")
        (self.root / "src" / "mod.py").write_text("x = 1\n")
        os.symlink(self.root / "shared" / "Shop", self.root / "src" / "Shop")

    def test_a_file_behind_a_symlinked_folder_is_keyed_by_its_real_path(self):
        self.assertEqual(ratchet.key(self.root, "src/Shop/shop.py", "f"), "shared/Shop/shop.py::f")

    def test_an_absolute_file_behind_a_symlinked_folder_is_keyed_by_its_real_path(self):
        file = str(self.root / "src" / "Shop" / "shop.py")
        self.assertEqual(ratchet.key(self.root, file, "f"), "shared/Shop/shop.py::f")

    def test_a_file_behind_a_link_to_a_folder_outside_the_repo_is_keyed_with_a_parent_step(self):
        outside = tempfile.TemporaryDirectory(dir=self.root.parent)
        self.addCleanup(outside.cleanup)
        (Path(outside.name) / "o.py").write_text("x = 1\n")
        os.symlink(outside.name, self.root / "src" / "Out")
        expected = f"../{Path(outside.name).name}/o.py::f"
        self.assertEqual(ratchet.key(self.root, "src/Out/o.py", "f"), expected)

    def test_an_ordinary_files_key_is_its_path_from_the_root(self):
        self.assertEqual(ratchet.key(self.root, "src/mod.py", "f"), "src/mod.py::f")

    def test_an_ordinary_absolute_files_key_is_its_path_from_the_root(self):
        self.assertEqual(ratchet.key(self.root, str(self.root / "src" / "mod.py"), "f"), "src/mod.py::f")

    def test_a_relative_file_with_dot_segments_is_keyed_without_them(self):
        self.assertEqual(ratchet.key(self.root, "./src/../src/mod.py", "f"), "src/mod.py::f")

    def test_a_scanned_path_that_is_itself_a_link_is_keyed_by_its_real_path(self):
        os.symlink(self.root / "shared", self.root / "alias")
        self.assertEqual(ratchet.key(self.root, "alias/Shop/shop.py", "f"), "shared/Shop/shop.py::f")

    def test_a_file_reached_through_a_link_and_a_dot_dot_step_is_keyed_by_where_the_step_really_lands(self):
        (self.root / "shared" / "up.py").write_text("x = 1\n")
        self.assertEqual(ratchet.key(self.root, "src/Shop/../up.py", "f"), "shared/up.py::f")

    def test_one_file_reached_by_three_spellings_gets_one_key(self):
        spellings = ("src/Shop/shop.py", "shared/Shop/shop.py", str(self.root / "src" / "Shop" / ".." / "Shop" / "shop.py"))
        self.assertEqual({ratchet.key(self.root, s, "f") for s in spellings}, {"shared/Shop/shop.py::f"})

    def test_a_logical_working_directory_does_not_change_the_key(self):
        alias = self.root.parent / (self.root.name + "-alias")
        os.symlink(self.root, alias)
        self.addCleanup(os.unlink, alias)
        self.assertEqual(ratchet.key(alias, str(alias / "src" / "Shop" / "shop.py"), "f"), "shared/Shop/shop.py::f")


class CcCheckRatchetTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "pkg").mkdir()
        self.module = self.root / "pkg" / "mod.py"
        self.file = self.root / "cc-baseline.json"

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, *functions):
        self.module.write_text("\n\n".join(functions))

    def gate(self, *extra):
        argv = [str(self.root / "pkg"), "--threshold", "3", "--baseline", str(self.file), *extra]
        return call(qc.main, argv, self.root)

    def baseline(self):
        return json.loads(self.file.read_text())

    def test_the_check_refuses_to_run_without_a_baseline_file(self):
        self.put(branchy("f", 5))
        code, out = self.gate()
        self.assertEqual(code, 2)
        self.assertIn("--update", out)
        self.assertFalse(self.file.exists())

    def test_update_without_a_baseline_flag_is_a_usage_error(self):
        self.put(branchy("f", 5))
        code, _ = call(qc.main, [str(self.root), "--update"], self.root)
        self.assertEqual(code, 2)

    def test_the_first_update_records_only_functions_over_the_threshold(self):
        self.put(branchy("f", 5), branchy("g", 1))
        self.assertEqual(self.gate("--update")[0], 0)
        self.assertEqual(self.baseline(), {"pkg/mod.py::f": 6})
        self.assertEqual(self.gate()[0], 0)

    def test_baseline_keys_are_relative_to_the_repo_root_so_the_file_is_portable(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        for name in self.baseline():
            self.assertFalse(name.startswith("/"), name)
            self.assertNotIn(self.tmp.name, name)

    def test_a_function_behind_a_symlinked_folder_shows_its_link_path_and_is_baselined_by_its_real_path(self):
        (self.root / "pkg" / "real").mkdir()
        (self.root / "pkg" / "real" / "inner.py").write_text(branchy("g", 5))
        os.symlink(self.root / "pkg" / "real", self.root / "pkg" / "app")
        app = str(self.root / "pkg" / "app")
        _, shown = call(qc.main, [app, "--threshold", "3", "--format", "json"], self.root)
        call(qc.main, [app, "--threshold", "3", "--baseline", str(self.file), "--update"], self.root)
        self.assertEqual(([r["file"] for r in json.loads(shown)], self.baseline()), ([f"{app}/inner.py"], {"pkg/real/inner.py::g": 6}))

    def test_argument_order_does_not_change_which_keys_a_baseline_holds(self):
        (self.root / "pkg" / "real").mkdir()
        (self.root / "pkg" / "real" / "inner.py").write_text(branchy("g", 5))
        os.symlink(self.root / "pkg" / "real", self.root / "pkg" / "app")
        base = ["--threshold", "3", "--baseline", str(self.file)]
        self.assertEqual(call(qc.main, [str(self.root / "pkg"), *base, "--update"], self.root)[0], 0)
        before = self.baseline()
        code, out = call(qc.main, [str(self.root / "pkg" / "app"), str(self.root / "pkg"), *base], self.root)
        self.assertEqual((code, before), (0, {"pkg/real/inner.py::g": 6}))

    def test_a_method_is_keyed_by_its_class(self):
        self.put("class A:\n" + branchy("m", 5, indent="    "))
        self.gate("--update")
        self.assertIn("pkg/mod.py::A.m", self.baseline())

    def test_a_new_function_over_the_threshold_fails_the_check(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        self.put(branchy("f", 5), branchy("g", 4))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("FAIL pkg/mod.py::g: 5, new", out)

    def test_a_baselined_function_whose_score_rose_fails_the_check(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        self.put(branchy("f", 6))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("FAIL pkg/mod.py::f: 7, baseline allows 6", out)

    def test_a_renamed_function_counts_as_new(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        self.put(branchy("renamed", 5))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("pkg/mod.py::renamed: 6, new", out)

    def test_a_moved_function_counts_as_new(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        self.module.rename(self.root / "pkg" / "other.py")
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("pkg/other.py::f: 6, new", out)

    def test_a_score_that_fell_fails_until_update_records_it(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        self.put(branchy("f", 4))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("PAID pkg/mod.py::f: now 5, baseline still says 6", out)
        self.assertEqual(self.gate("--update")[0], 0)
        self.assertEqual(self.baseline(), {"pkg/mod.py::f": 5})
        self.assertEqual(self.gate()[0], 0)

    def test_a_function_that_drops_to_the_threshold_fails_until_update_removes_it(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        self.put(branchy("f", 2))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("at or below the threshold", out)
        self.gate("--update")
        self.assertEqual(self.baseline(), {})
        self.assertEqual(self.gate()[0], 0)

    def test_update_never_raises_a_score(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        self.put(branchy("f", 6))
        code, _ = self.gate("--update")
        self.assertEqual(code, 1)
        self.assertEqual(self.baseline(), {"pkg/mod.py::f": 6})

    def test_update_never_adds_a_new_function(self):
        self.put(branchy("f", 5))
        self.gate("--update")
        self.put(branchy("f", 5), branchy("g", 4))
        code, _ = self.gate("--update")
        self.assertEqual(code, 1)
        self.assertEqual(self.baseline(), {"pkg/mod.py::f": 6})

    def test_several_paths_are_checked_in_one_run(self):
        (self.root / "a.py").write_text(branchy("a", 5))
        (self.root / "b.py").write_text(branchy("b", 5))
        argv = [str(self.root / "a.py"), str(self.root / "b.py"), "--threshold", "3", "--format", "json"]
        code, out = call(qc.main, argv, self.root)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(r["name"] for r in json.loads(out)), ["a", "b"])

    def test_a_missing_path_among_several_is_an_error(self):
        (self.root / "a.py").write_text(branchy("a", 1))
        code, _ = call(qc.main, [str(self.root / "a.py"), str(self.root / "nope")], self.root)
        self.assertEqual(code, 2)


class CrapRatchetTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.module = self.root / "mod.py"
        self.coverage = self.root / "coverage.json"
        self.file = self.root / "crap-baseline.json"

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, *functions):
        text = "\n\n".join(functions)
        self.module.write_text(text)
        lines = list(range(1, text.count("\n") + 2))
        files = {str(self.module): {"executed_lines": [], "missing_lines": lines}}
        self.coverage.write_text(json.dumps({"files": files}))

    def gate(self, *extra):
        argv = ["--lang", "python", str(self.module), "--coverage-json", str(self.coverage),
                "--baseline", str(self.file), *extra]
        return call(crap.main, argv, self.root)

    def baseline(self):
        return json.loads(self.file.read_text())

    def test_crap_refuses_a_baseline_without_coverage(self):
        self.put(branchy("f", 2))
        argv = ["--lang", "python", str(self.module), "--no-coverage", "--baseline", str(self.file)]
        code, out = call(crap.main, argv, self.root)
        self.assertEqual(code, 2)
        self.assertIn("needs coverage", out)

    def test_crap_records_failing_functions_and_fails_on_a_new_one(self):
        self.put(branchy("f", 2))
        self.assertEqual(self.gate("--update")[0], 0)
        self.assertEqual(self.baseline(), {"mod.py::f": 12.0})
        self.assertEqual(self.gate()[0], 0)
        self.put(branchy("f", 2), branchy("g", 2))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("FAIL mod.py::g: 12.0, new", out)

    def test_crap_fails_when_a_baselined_score_rises(self):
        self.put(branchy("f", 2))
        self.gate("--update")
        self.put(branchy("f", 3))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("baseline allows 12.0", out)


if __name__ == "__main__":
    unittest.main()
