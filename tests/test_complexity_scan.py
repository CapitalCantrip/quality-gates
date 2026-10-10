import os
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from quality_gates import complexity_scan
from quality_gates.errors import ToolError

ROOT = Path(__file__).resolve().parents[1]
NESTED = (Path(__file__).parent / "fixtures/python/nested.py").read_text(encoding="utf-8")
TS_FIXTURES = "tests/fixtures/typescript"

CLASS_IN_FUNCTION = """\
def f(x):
    if x:
        pass

    class K:
        def m(self, y):
            if y and x:
                return 1
            return 2

    return K
"""

DEEP_CLASSES = """\
def f(x):
    class K:
        def m(self, y):
            if y:
                def clos(z):
                    if z:
                        return 1
                    return 2

                class L:
                    def n(self, w):
                        if w:
                            return 1
                        return 2

                    class M:
                        def o(self, v):
                            return 1 if v else 2

                return L
            return 0

        class J:
            def p(self, u):
                return 1 if u else 2

    return K
"""


CLASS_IN_METHOD = """\
class Top:
    def meth(self, x):
        class N:
            def inner(self, y):
                return 1 if y else 2

        return N
"""


def completed(stdout, returncode=0, stderr=""):
    return CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class InTempDir(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        before = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, before)

    def write(self, path, text="def f(x):\n    return x\n"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")


class PythonScanTest(InTempDir):
    def functions(self, path="mod.py"):
        return {fn.name: fn for fn in complexity_scan.scan([path], "python").functions}

    def test_each_function_carries_its_file_name_cc_and_line_range(self):
        self.write("mod.py", NESTED)
        deep = self.functions()["K.Inner.deep"]
        self.assertEqual((deep.file, deep.cc, deep.start, deep.end), ("mod.py", 2, 14, 17))

    def test_closures_and_nested_class_methods_are_named_from_the_outside_in(self):
        self.write("mod.py", NESTED)
        self.assertEqual(set(self.functions()), {"outer", "outer.inner", "K.m", "K.Inner.deep", "outer#2"})

    def test_a_closure_is_scored_on_its_own_and_not_folded_into_its_outer_function(self):
        self.write("mod.py", NESTED)
        functions = self.functions()
        self.assertEqual((functions["outer"].cc, functions["outer.inner"].cc), (1, 2))

    def test_a_method_of_a_class_defined_inside_a_function_is_scored_under_the_function_class_method_name(self):
        self.write("mod.py", CLASS_IN_FUNCTION)
        method = self.functions()["f.K.m"]
        self.assertEqual((method.file, method.cc, method.start, method.end), ("mod.py", 3, 6, 9))

    def test_a_function_holding_a_class_keeps_its_own_complexity_and_nothing_is_listed_twice(self):
        self.write("mod.py", CLASS_IN_FUNCTION)
        listed = complexity_scan.scan(["mod.py"], "python").functions
        self.assertEqual(sorted((fn.name, fn.cc) for fn in listed), [("f", 2), ("f.K.m", 3)])

    def test_classes_and_closures_are_scored_at_every_depth_inside_a_function(self):
        self.write("mod.py", DEEP_CLASSES)
        self.assertEqual(
            set(self.functions()),
            {"f", "f.K.m", "f.K.m.clos", "f.K.m.L.n", "f.K.m.L.M.o", "f.K.J.p"},
        )

    def test_a_function_holding_deep_classes_keeps_its_own_complexity(self):
        self.write("mod.py", DEEP_CLASSES)
        functions = self.functions()
        self.assertEqual((functions["f"].cc, functions["f.K.m"].cc), (1, 2))

    def test_a_class_defined_in_a_method_of_a_top_level_class_is_scored_under_the_full_path(self):
        self.write("mod.py", CLASS_IN_METHOD)
        self.assertEqual(set(self.functions()), {"Top.meth", "Top.meth.N.inner"})

    def test_a_class_defined_under_an_if_inside_a_function_is_scored(self):
        self.write("mod.py", "def f(x):\n    if x:\n        class K:\n            def m(self):\n                return 1\n")
        self.assertEqual(set(self.functions()), {"f", "f.K.m"})

    def test_a_class_defined_in_an_async_function_is_scored(self):
        self.write("mod.py", "async def f():\n    class K:\n        def m(self):\n            return 1\n")
        self.assertEqual(set(self.functions()), {"f", "f.K.m"})

    def test_a_repeated_name_in_a_file_gets_its_order_as_a_suffix(self):
        self.write("mod.py", "def f():\n    pass\n\n\ndef f():\n    pass\n")
        self.assertEqual(set(self.functions()), {"f", "f#2"})

    def test_a_file_radon_cannot_parse_is_skipped(self):
        self.write("src/bad.py", "def broken(:\n")
        self.write("src/good.py")
        self.assertEqual(set(self.functions("src")), {"f"})

    def test_the_files_scanned_are_returned_even_when_they_hold_no_functions(self):
        self.write("src/constants.py", "LIMIT = 3\n")
        found = complexity_scan.scan(["src"], "python")
        self.assertEqual((found.files, found.functions), (["src/constants.py"], []))

    def test_a_missing_radon_raises_a_tool_error(self):
        self.write("mod.py")
        with patch.dict(sys.modules, {"radon": None, "radon.visitors": None}):
            with self.assertRaises(ToolError):
                complexity_scan.scan(["mod.py"], "python")


class SkipListTest(InTempDir):
    def test_every_skip_list_folder_is_skipped_and_named(self):
        for folder in complexity_scan.SKIPPED_FOLDERS:
            self.write(f"{folder}/x.py")
        found = complexity_scan.scan(["."], "python")
        self.assertEqual(found.functions, [])
        self.assertEqual(found.skipped, sorted(complexity_scan.SKIPPED_FOLDERS))

    def test_a_typescript_project_inside_a_build_folder_is_scanned_when_given_by_its_full_path(self):
        self.write("build/proj/a.ts", "function a(x) { return x ? 1 : 2; }\n")
        found = complexity_scan.scan([os.path.abspath("build/proj")], "typescript")
        self.assertEqual([fn.name for fn in found.functions], ["a"])
        self.assertEqual(found.skipped, [])

    def test_a_hidden_folder_not_on_the_skip_list_is_scanned(self):
        self.write(".claude/hooks/hook.py")
        self.assertEqual([fn.file for fn in complexity_scan.scan(["."], "python").functions], [".claude/hooks/hook.py"])

    def test_a_skip_list_folder_nested_in_another_is_not_named(self):
        self.write("venv/lib/build/x.py")
        self.assertEqual(complexity_scan.scan(["."], "python").skipped, ["venv"])

    def test_a_skip_list_name_deep_inside_a_scanned_path_is_skipped(self):
        self.write("src/pkg/dist/x.py")
        self.write("src/pkg/y.py")
        found = complexity_scan.scan(["src"], "python")
        self.assertEqual(([fn.file for fn in found.functions], found.skipped), (["src/pkg/y.py"], ["src/pkg/dist"]))

    def test_a_swift_file_under_swiftpms_build_folder_is_not_scanned_and_the_folder_is_named(self):
        self.write(".build/debug/test_entry_point.swift", "func entry(a: Int) -> Int { return a > 0 ? 1 : 2 }\n")
        self.write("Sources/App.swift", "func load(a: Int) -> Int { return a > 0 ? 1 : 2 }\n")
        found = complexity_scan.scan(["."], "swift")
        self.assertEqual(([fn.file for fn in found.functions], found.skipped), (["Sources/App.swift"], [".build"]))

    def test_swiftpms_build_folder_is_skipped_for_every_language(self):
        self.write(".build/checkouts/dep/x.py")
        self.write(".build/checkouts/dep/x.ts", "function x(a) { return a ? 1 : 2; }\n")
        for lang in ("python", "typescript"):
            found = complexity_scan.scan(["."], lang)
            self.assertEqual((found.functions, found.skipped), ([], [".build"]))

    def test_a_worktrees_folder_outside_claude_is_scanned(self):
        self.write("tools/worktrees/x.py")
        self.assertEqual(len(complexity_scan.scan(["."], "python").functions), 1)

    def test_a_scan_with_no_skip_list_folders_names_none(self):
        self.write("mod.py")
        self.assertEqual(complexity_scan.scan(["."], "python").skipped, [])

    def test_lizard_skips_the_same_folders(self):
        for folder in complexity_scan.SKIPPED_FOLDERS:
            self.write(f"{folder}/x.ts", "function x(a) { return a ? 1 : 2; }\n")
        self.write(".claude/hooks/h.ts", "function h(a) { return a ? 1 : 2; }\n")
        found = complexity_scan.scan(["."], "typescript")
        self.assertEqual([fn.file for fn in found.functions], [".claude/hooks/h.ts"])
        self.assertEqual(found.skipped, sorted(complexity_scan.SKIPPED_FOLDERS))


class SymlinkedFolderTest(InTempDir):
    def link(self, target, name):
        Path(name).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(os.path.abspath(target), name)

    def files(self, *paths, lang="python"):
        return sorted(fn.file for fn in complexity_scan.scan(list(paths), lang).functions)

    def test_a_function_in_a_symlinked_source_folder_is_scanned(self):
        self.write("Sources/A/a.py")
        self.write("shared/Shop/shop.py")
        self.link("shared/Shop", "Sources/Shop")
        self.assertEqual(self.files("Sources"), ["Sources/A/a.py", "Sources/Shop/shop.py"])

    def test_a_symlinked_folder_keeps_the_link_path_in_the_file_name(self):
        self.write("shared/Shop/shop.py")
        self.link("shared/Shop", "Sources/Shop")
        self.assertEqual(self.files("Sources"), ["Sources/Shop/shop.py"])

    def test_a_symlinked_folder_of_swift_files_is_scanned_by_lizard(self):
        self.write("shared/Shop/Shop.swift", "func shop(a: Int) -> Int { return a > 0 ? 1 : 2 }\n")
        self.link("shared/Shop", "Sources/Shop")
        self.assertEqual(self.files("Sources", lang="swift"), ["Sources/Shop/Shop.swift"])

    def test_a_symlink_loop_terminates_and_scans_each_file_once(self):
        self.write("src/mod.py")
        self.link("src", "src/up")
        found = complexity_scan.scan(["src"], "python")
        self.assertEqual([fn.file for fn in found.functions], ["src/mod.py"])

    def test_the_folder_a_loop_link_repeats_is_named_as_skipped(self):
        self.write("src/mod.py")
        self.link("src", "src/up")
        self.assertEqual(complexity_scan.scan(["src"], "python").skipped, ["src/up"])

    def test_a_link_to_the_scanned_path_itself_is_not_walked_again(self):
        self.write("proj/a/mod.py")
        self.link("proj", "proj/a/back")
        self.assertEqual(self.files("proj"), ["proj/a/mod.py"])

    def test_two_links_to_the_same_folder_scan_its_files_once(self):
        self.write("shared/Shop/shop.py")
        self.link("shared/Shop", "src/ShopA")
        self.link("shared/Shop", "src/ShopB")
        found = complexity_scan.scan(["src"], "python")
        self.assertEqual(([fn.file for fn in found.functions], found.skipped), (["src/ShopA/shop.py"], ["src/ShopB"]))

    def test_a_real_folder_is_walked_before_a_link_to_it_whatever_their_names(self):
        self.write("src/Zeta/z.py")
        self.link("src/Zeta", "src/Alpha")
        found = complexity_scan.scan(["src"], "python")
        self.assertEqual(([fn.file for fn in found.functions], found.skipped), (["src/Zeta/z.py"], ["src/Alpha"]))

    def test_a_folder_reached_through_two_scanned_paths_is_scanned_once(self):
        self.write("shared/Shop/shop.py")
        self.link("shared/Shop", "one/Shop")
        self.link("shared/Shop", "two/Shop")
        found = complexity_scan.scan(["one", "two"], "python")
        self.assertEqual(([fn.file for fn in found.functions], found.skipped), (["one/Shop/shop.py"], ["two/Shop"]))

    def test_a_scanned_path_inside_another_scanned_path_is_not_scanned_twice(self):
        self.write("src/pkg/a.py")
        found = complexity_scan.scan(["src", "src/pkg"], "python")
        self.assertEqual(([fn.name for fn in found.functions], found.skipped), (["f"], ["src/pkg"]))

    def test_a_symlink_named_on_the_skip_list_is_skipped_and_named(self):
        self.write("elsewhere/x.py")
        self.link("elsewhere", "src/build")
        found = complexity_scan.scan(["src"], "python")
        self.assertEqual((found.functions, found.skipped), ([], ["src/build"]))

    def test_a_symlink_to_a_folder_that_does_not_exist_is_ignored(self):
        self.write("src/mod.py")
        os.symlink(os.path.abspath("gone"), "src/dangling")
        self.assertEqual(self.files("src"), ["src/mod.py"])

    def test_a_scanned_path_that_is_itself_a_symlink_to_a_folder_is_scanned(self):
        self.write("real/mod.py")
        self.link("real", "alias")
        self.assertEqual(self.files("alias"), ["alias/mod.py"])


class LizardRunTest(InTempDir):
    def setUp(self):
        super().setUp()
        self.write("App.swift", "func load() {}\n")

    def test_lizard_exit_1_is_not_a_failure(self):
        row = '5,4,30,1,10,"load@10-30@App.swift","App.swift","load","load()",10,30'
        found = complexity_scan.scan(["App.swift"], "swift", runner=lambda *a, **k: completed(row, 1))
        self.assertEqual([(fn.name, fn.cc, fn.start, fn.end) for fn in found.functions], [("load", 4, 10, 30)])

    def test_malformed_lizard_rows_are_dropped(self):
        rows = "too,short\n" + '5,x,30,1,10,"bad@1-2@A.swift","A.swift","bad","bad()",1,2'
        found = complexity_scan.scan(["App.swift"], "swift", runner=lambda *a, **k: completed(rows))
        self.assertEqual(found.functions, [])

    def test_a_crashing_lizard_raises_a_tool_error(self):
        with self.assertRaises(ToolError) as raised:
            complexity_scan.scan(["App.swift"], "swift", runner=lambda *a, **k: completed("", 2, "boom"))
        self.assertEqual(str(raised.exception), "lizard failed:\nboom")

    def test_lizard_reads_only_the_walked_files_of_its_language(self):
        self.write("notes.txt", "text")
        self.write("build/Gen.swift", "func gen() {}\n")
        given = []
        runner = lambda cmd, **k: given.append(Path(cmd[-1]).read_text()) or completed("")
        complexity_scan.scan(["."], "swift", runner=runner)
        self.assertEqual(given, ["App.swift\n"])

    def test_lizard_does_not_run_when_no_file_is_in_its_language(self):
        runner = lambda *a, **k: self.fail("lizard ran")
        self.assertEqual(complexity_scan.scan(["App.swift"], "typescript", runner=runner).functions, [])


class LizardScanTest(unittest.TestCase):
    def setUp(self):
        before = os.getcwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, before)

    def names(self, file):
        found = complexity_scan.scan([TS_FIXTURES], "typescript").functions
        return [(fn.name, fn.start) for fn in found if Path(fn.file).name == file]

    def test_typescript_names_stay_as_lizard_gives_them(self):
        self.assertEqual(self.names("sample.ts"), [
            ("grade", 1), ("total", 12), ("(anonymous)", 13), ("pick", 18), ("(anonymous)#2", 19), ("untested", 21),
        ])

    def test_a_typescript_method_is_named_without_its_class(self):
        self.assertIn(("g", 6), self.names("typed_then_class.ts"))

    def test_typescript_tsx_and_javascript_files_are_all_read(self):
        self.assertTrue(self.names("component.tsx"))
        self.assertTrue(self.names("sample.ts"))

    def test_switch_cases_count_toward_complexity(self):
        found = complexity_scan.scan([f"{TS_FIXTURES}/sample.ts"], "typescript").functions
        self.assertEqual([fn.cc for fn in found if fn.name == "untested"], [3])

    def test_a_missing_lizard_raises_a_tool_error(self):
        with patch.object(complexity_scan.importlib.util, "find_spec", return_value=None):
            with self.assertRaises(ToolError):
                complexity_scan.scan(["."], "typescript")

    def test_a_path_that_does_not_exist_raises_a_tool_error(self):
        with self.assertRaises(ToolError) as raised:
            complexity_scan.scan(["no/such/path"], "python")
        self.assertEqual(str(raised.exception), "path not found: no/such/path")


if __name__ == "__main__":
    unittest.main()
