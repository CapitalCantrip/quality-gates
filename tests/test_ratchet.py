import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import fields
from pathlib import Path
from unittest import mock

from quality_gates import complexity_scan, crap
from quality_gates import comment_debt as cd
from quality_gates import quality_check as qc
from quality_gates import ratchet
from quality_gates.errors import ToolError, Untagged


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
        self.assertEqual(ratchet.location(self.root, "src/Shop/shop.py", "f").key, "shared/Shop/shop.py::f")

    def test_an_absolute_file_behind_a_symlinked_folder_is_keyed_by_its_real_path(self):
        file = str(self.root / "src" / "Shop" / "shop.py")
        self.assertEqual(ratchet.location(self.root, file, "f").key, "shared/Shop/shop.py::f")

    def test_a_file_behind_a_link_to_a_folder_outside_the_repo_is_keyed_with_a_parent_step(self):
        outside = tempfile.TemporaryDirectory(dir=self.root.parent)
        self.addCleanup(outside.cleanup)
        (Path(outside.name) / "o.py").write_text("x = 1\n")
        os.symlink(outside.name, self.root / "src" / "Out")
        expected = f"../{Path(outside.name).name}/o.py::f"
        self.assertEqual(ratchet.location(self.root, "src/Out/o.py", "f").key, expected)

    def test_an_ordinary_files_key_is_its_path_from_the_root(self):
        self.assertEqual(ratchet.location(self.root, "src/mod.py", "f").key, "src/mod.py::f")

    def test_an_ordinary_absolute_files_key_is_its_path_from_the_root(self):
        self.assertEqual(ratchet.location(self.root, str(self.root / "src" / "mod.py"), "f").key, "src/mod.py::f")

    def test_a_relative_file_with_dot_segments_is_keyed_without_them(self):
        self.assertEqual(ratchet.location(self.root, "./src/../src/mod.py", "f").key, "src/mod.py::f")

    def test_a_scanned_path_that_is_itself_a_link_is_keyed_by_its_real_path(self):
        os.symlink(self.root / "shared", self.root / "alias")
        self.assertEqual(ratchet.location(self.root, "alias/Shop/shop.py", "f").key, "shared/Shop/shop.py::f")

    def test_a_file_reached_through_a_link_and_a_dot_dot_step_is_keyed_by_where_the_step_really_lands(self):
        (self.root / "shared" / "up.py").write_text("x = 1\n")
        self.assertEqual(ratchet.location(self.root, "src/Shop/../up.py", "f").key, "shared/up.py::f")

    def test_one_file_reached_by_three_spellings_gets_one_key(self):
        spellings = ("src/Shop/shop.py", "shared/Shop/shop.py", str(self.root / "src" / "Shop" / ".." / "Shop" / "shop.py"))
        self.assertEqual({ratchet.location(self.root, s, "f").key for s in spellings}, {"shared/Shop/shop.py::f"})

    def test_a_logical_working_directory_does_not_change_the_key(self):
        alias = self.root.parent / (self.root.name + "-alias")
        os.symlink(self.root, alias)
        self.addCleanup(os.unlink, alias)
        self.assertEqual(ratchet.location(alias, str(alias / "src" / "Shop" / "shop.py"), "f").key, "shared/Shop/shop.py::f")


class ResultTest(unittest.TestCase):

    def test_the_result_holds_exactly_the_five_outcomes_adr_011_names(self):
        names = [outcome.name for outcome in ratchet.Outcome]
        self.assertEqual(names, ["PASSED", "FAILED", "BEHIND", "UNMEASURED", "DID_NOT_RUN"])

    def test_the_result_carries_no_display_text(self):
        shown = "SHOWN-NEVER-STORED"
        found = [ratchet.Finding(ratchet.Location("a.py", "f"), 3, "complexity", shown)]
        result = ratchet.judge(found, {"a.py::f": 4, "b.py::g": 2})
        self.assertNotIn(shown, repr(result))
        self.assertEqual([f.name for f in fields(result)], ["verdicts"])
        self.assertEqual([f.name for f in fields(result.verdicts[0])], ["location", "outcome", "now", "allowed"])

    def test_each_location_gets_one_outcome_from_its_finding_and_the_baseline(self):
        found = [
            finding("new.py", 5), finding("same.py", 4), finding("better.py", 2),
            finding("dark.py", None), finding("worse.py", 9),
        ]
        baseline = {"same.py::f": 4, "better.py::f": 3, "gone.py::f": 6, "worse.py::f": 8, "dark.py::f": 7}
        outcomes = {v.location.key: v.outcome for v in ratchet.judge(found, baseline).verdicts}
        self.assertEqual(outcomes, {
            "better.py::f": ratchet.Outcome.BEHIND,
            "dark.py::f": ratchet.Outcome.UNMEASURED,
            "gone.py::f": ratchet.Outcome.BEHIND,
            "new.py::f": ratchet.Outcome.FAILED,
            "same.py::f": ratchet.Outcome.PASSED,
            "worse.py::f": ratchet.Outcome.FAILED,
        })

    def test_two_findings_at_one_location_are_judged_by_the_higher_number(self):
        result = ratchet.judge([finding("a.py", 7), finding("a.py", 5)], {"a.py::f": 6})
        self.assertEqual([(v.outcome, v.now) for v in result.verdicts], [(ratchet.Outcome.FAILED, 7)])

    def test_a_location_without_a_function_keys_the_baseline_by_its_file_alone(self):
        result = ratchet.judge([ratchet.Finding(ratchet.Location("a.py"), 2, "comment", "")], {"a.py": 3})
        expected = [(ratchet.Location("a.py"), ratchet.Outcome.BEHIND)]
        self.assertEqual([(v.location, v.outcome) for v in result.verdicts], expected)


def finding(file, number):
    return ratchet.Finding(ratchet.Location(file, "f"), number, "complexity", "")


class SettleTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "baseline.json"

    def test_a_check_without_a_baseline_file_did_not_run_and_exits_2(self):
        out = io.StringIO()
        result = ratchet.enforce(lambda: [finding("a.py", 5)], self.file, False, out)
        self.assertEqual([v.outcome for v in result.verdicts], [ratchet.Outcome.DID_NOT_RUN])
        self.assertEqual(ratchet.exit_code(result), 2)
        self.assertEqual(out.getvalue(), f"No baseline at {self.file}. Run with --update to create one.\n")

    def test_a_check_without_a_baseline_file_never_asks_the_gate_to_find(self):
        def find():
            raise AssertionError("the gate was asked to find")

        with self.assertRaises(ToolError):
            ratchet.settle(find, self.file, updating=False)

    def test_update_writes_the_lowered_baseline_and_then_every_location_has_passed(self):
        self.file.write_text('{"a.py::f": 6, "b.py::f": 4}')
        result = ratchet.settle(lambda: [finding("a.py", 5)], self.file, updating=True)
        self.assertEqual(self.file.read_text(), '{\n  "a.py::f": 5\n}\n')
        self.assertEqual([(v.location.key, v.outcome) for v in result.verdicts], [("a.py::f", ratchet.Outcome.PASSED)])

    def test_update_refuses_a_failed_location_and_writes_nothing(self):
        self.file.write_text('{"a.py::f": 4}')
        result = ratchet.settle(lambda: [finding("a.py", 5)], self.file, updating=True)
        self.assertEqual(self.file.read_text(), '{"a.py::f": 4}')
        self.assertEqual(ratchet.exit_code(result), 1)

    def test_update_keeps_the_entry_of_an_unmeasured_location_and_adds_none_for_a_new_one(self):
        self.file.write_text('{"a.py::f": 9}')
        result = ratchet.settle(lambda: [finding("a.py", None), finding("b.py", None)], self.file, updating=True)
        self.assertEqual(json.loads(self.file.read_text()), {"a.py::f": 9})
        self.assertEqual(ratchet.exit_code(result), 1)


class SharedKeyTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "baseline.json"
        self.file.write_text("{}")
        self.found = [finding("a.py", 9), finding("a.py", None)]

    def test_a_failing_score_and_an_unmeasured_figure_at_one_location_both_fail_the_check(self):
        out = io.StringIO()
        self.assertEqual(ratchet.exit_code(ratchet.enforce(lambda: self.found, self.file, False, out)), 1)
        self.assertIn("FAIL a.py::f: 9, new", out.getvalue())
        self.assertIn("UNMEASURED a.py::f", out.getvalue())

    def test_update_refuses_a_failing_score_even_when_its_location_is_also_unmeasured(self):
        out = io.StringIO()
        self.assertEqual(ratchet.exit_code(ratchet.enforce(lambda: self.found, self.file, True, out)), 1)
        self.assertEqual(self.file.read_text(), "{}")
        self.assertIn("--update only lowers the baseline", out.getvalue())


class CcCheckFindsTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "mod.py").write_text("class A:\n" + branchy("m", 5, indent="    ") + branchy("f", 5))

    def located(self):
        found = complexity_scan.scan([str(self.root / "mod.py")], "python", root=self.root)
        return [f.location for f in qc.findings(found.functions, 3, self.root)]

    def test_the_same_code_gives_the_same_locations_on_two_runs(self):
        first = self.located()
        self.assertEqual(first, [ratchet.Location("mod.py", "A.m"), ratchet.Location("mod.py", "f")])
        self.assertEqual(self.located(), first)

    def test_cc_check_exits_with_the_code_the_ratchet_decides(self):
        file = self.root / "cc.json"
        argv = [str(self.root / "mod.py"), "--threshold", "3"]
        with mock.patch.object(ratchet, "exit_code", return_value=5):
            plain, _ = call(qc.main, argv, self.root)
            updated, _ = call(qc.main, [*argv, "--baseline", str(file), "--update"], self.root)
        self.assertEqual((plain, updated), (5, 5))
        self.assertEqual(json.loads(file.read_text()), {"mod.py::A.m": 6, "mod.py::f": 6})


class CrapFindsTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "mod.py").write_text("class A:\n" + branchy("m", 5, indent="    ") + branchy("f", 5))

    def located(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = crap.gate(["--lang", "python", str(self.root / "mod.py"), "--no-coverage"], self.root)
        return [v.location for v in result.verdicts]

    def test_the_same_code_gives_the_same_locations_on_two_runs(self):
        first = self.located()
        self.assertEqual(first, [ratchet.Location("mod.py", "A.m"), ratchet.Location("mod.py", "f")])
        self.assertEqual(self.located(), first)

    def test_each_finding_shows_what_its_fail_or_unmeasured_line_names(self):
        results = [
            crap.FunctionResult("mod.py", "f", 3, 6, 0.0, 42.0, "FAIL"),
            crap.FunctionResult("mod.py", "A.m", 9, 4, None, None, crap.UNMEASURED),
        ]
        shown = [f.display for f in crap.findings(results, self.root)]
        self.assertEqual(shown, ["FAIL  CRAP=42.0  mod.py:3  f", "UNMEASURED  CRAP=—  mod.py:9  A.m"])


class CommentDebtFindsTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "pkg").mkdir()
        (self.root / "pkg" / "b.py").write_text("x = 1  # b\n")
        (self.root / "a.py").write_text("# a\nx = 1\n")
        subprocess.run(["git", "-C", str(self.root), "add", "a.py", "pkg/b.py"], check=True)

    def located(self):
        return [f.location for f in cd.findings(self.root, [])]

    def test_the_same_code_gives_the_same_locations_on_two_runs(self):
        first = self.located()
        self.assertEqual(first, [ratchet.Location("a.py"), ratchet.Location("pkg/b.py")])
        self.assertEqual(self.located(), first)


class PaidDebtLeavesTheBaselineTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.file = self.root / "baseline.json"
        self.module = self.root / "mod.py"

    def baseline(self):
        return json.loads(self.file.read_text())

    def test_a_location_whose_count_reached_zero_or_vanished_owes_nothing(self):
        result = ratchet.judge([finding("zero.py", 0), finding("kept.py", 2)], {"zero.py::f": 3, "gone.py::f": 4, "kept.py::f": 2})
        owed = {v.location.key: ratchet.owes(v) for v in result.verdicts}
        self.assertEqual(owed, {"gone.py::f": False, "kept.py::f": True, "zero.py::f": False})
        self.assertEqual(ratchet.lowered(result), {"kept.py::f": 2})

    def test_cc_check_update_drops_a_function_paid_down_to_the_threshold(self):
        argv = [str(self.module), "--threshold", "3", "--baseline", str(self.file)]
        self.module.write_text(branchy("f", 5))
        call(qc.main, [*argv, "--update"], self.root)
        self.module.write_text(branchy("f", 1))
        self.assertEqual(call(qc.main, [*argv, "--update"], self.root)[0], 0)
        self.assertEqual(self.baseline(), {})

    def test_crap_update_drops_a_function_paid_down_below_the_threshold(self):
        coverage = self.root / "coverage.json"
        argv = ["--lang", "python", str(self.module), "--coverage-json", str(coverage), "--baseline", str(self.file)]
        self.module.write_text(branchy("f", 2))
        lines = list(range(1, branchy("f", 2).count("\n") + 1))
        coverage.write_text(json.dumps({"files": {str(self.module): {"executed_lines": [], "missing_lines": lines}}}))
        call(crap.main, [*argv, "--update"], self.root)
        coverage.write_text(json.dumps({"files": {str(self.module): {"executed_lines": lines, "missing_lines": []}}}))
        self.assertEqual(call(crap.main, [*argv, "--update"], self.root)[0], 0)
        self.assertEqual(self.baseline(), {})

    def test_comment_debt_update_drops_a_file_paid_down_to_zero_comment_lines(self):
        self.module.write_text("# one\nx = 1\n")
        subprocess.run(["git", "-C", str(self.root), "add", "mod.py"], check=True)
        cd.main(["--update"], root=self.root, baseline=self.file, out=io.StringIO())
        self.module.write_text("x = 1\n")
        self.assertEqual(cd.main(["--update"], root=self.root, baseline=self.file, out=io.StringIO()), 0)
        self.assertEqual(self.baseline(), {})


class CcCheckRatchetTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
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
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
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

    def unmeasured_gate(self, *extra):
        other = self.root / "other.py"
        other.write_text(branchy("g", 2))
        argv = ["--lang", "python", str(self.module), str(other), "--coverage-json", str(self.coverage),
                "--baseline", str(self.file), *extra]
        return call(crap.main, argv, self.root)

    def test_update_records_measured_functions_adds_no_entry_for_an_unmeasured_one_and_fails_naming_it(self):
        self.put(branchy("f", 2))
        code, out = self.unmeasured_gate("--update")
        self.assertEqual(code, 1)
        self.assertEqual(self.baseline(), {"mod.py::f": 12.0})
        self.assertIn("UNMEASURED other.py::g", out)

    def test_an_entry_for_a_function_that_becomes_unmeasured_is_kept_and_not_reported_as_paid(self):
        self.put(branchy("f", 2))
        self.gate("--update")
        self.coverage.write_text(json.dumps({"files": {}}))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("UNMEASURED mod.py::f", out)
        self.assertNotIn("PAID", out)
        self.assertEqual(self.gate("--update")[0], 1)
        self.assertEqual(self.baseline(), {"mod.py::f": 12.0})

    def test_update_still_lowers_measured_entries_while_another_function_is_unmeasured(self):
        self.put(branchy("f", 3))
        self.gate("--update")
        self.put(branchy("f", 2))
        self.assertEqual(self.unmeasured_gate("--update")[0], 1)
        self.assertEqual(self.baseline(), {"mod.py::f": 12.0})

    def test_a_check_with_only_baselined_measured_functions_still_passes(self):
        self.put(branchy("f", 2))
        self.gate("--update")
        code, out = self.gate()
        self.assertEqual(code, 0)
        self.assertNotIn("UNMEASURED", out)


class EmptyBaselineFlagTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.module = self.root / "mod.py"
        self.module.write_text(branchy("f", 2))
        self.coverage = self.root / "coverage.json"
        self.coverage.write_text(json.dumps({"files": {}}))

    def test_crap_refuses_an_empty_or_whitespace_only_baseline_naming_the_flag(self):
        for value in ("", "  "):
            with self.subTest(value=value):
                argv = ["--lang", "python", str(self.module), "--coverage-json", str(self.coverage), "--baseline", value]
                code, out = call(crap.main, argv, self.root)
                self.assertEqual(code, 2)
                self.assertIn("[crap] --baseline was given an empty path", out)

    def test_cc_check_refuses_an_empty_or_whitespace_only_baseline_naming_the_flag(self):
        for value in ("", "  "):
            with self.subTest(value=value):
                code, out = call(qc.main, [str(self.module), "--baseline", value], self.root)
                self.assertEqual(code, 2)
                self.assertIn("ERROR: --baseline was given an empty path", out)


class RunGateTest(unittest.TestCase):
    def test_the_exit_code_of_the_result_a_gate_returns_is_passed_through(self):
        failed = ratchet.Result((ratchet.Verdict(ratchet.Location("a.py"), ratchet.Outcome.FAILED),))
        self.assertEqual(ratchet.run_gate(lambda argv, root: failed, ["x"], None, "[t] "), 1)

    def test_a_tool_error_is_printed_after_the_tag_and_becomes_exit_code_2(self):
        def gate(argv, root):
            raise ToolError("path not found: x")

        err = io.StringIO()
        with redirect_stderr(err):
            code = ratchet.run_gate(gate, [], None, "[t] ")
        self.assertEqual((code, err.getvalue()), (2, "[t] path not found: x\n"))

    def test_an_untagged_tool_error_is_printed_without_the_tag(self):
        def gate(argv, root):
            raise Untagged("No Python files found.")

        err = io.StringIO()
        with redirect_stderr(err):
            code = ratchet.run_gate(gate, [], None, "[t] ")
        self.assertEqual((code, err.getvalue()), (2, "No Python files found.\n"))

    def test_an_error_that_is_not_a_tool_error_is_not_caught(self):
        def gate(argv, root):
            raise ValueError("bug")

        with self.assertRaises(ValueError):
            ratchet.run_gate(gate, [], None, "[t] ")


NOT_A_REPO = (
    "not inside a git repository: quality-gates looks at the files git would commit, "
    "so run it inside the project's repository, or run `git init` there first"
)
STALE_MTIME = 1_000_000_000


class CouldNotRunTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.module = self.root / "m.py"
        self.module.write_text(branchy("f", 3))
        self.missing = self.root / "missing.json"
        self.report = self.root / "cov.json"
        self.report.write_text('{"files": {}}')

    def repo(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "m.py"], check=True)

    def working_in_the_folder(self):
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        os.chdir(self.root)

    def tried(self, run):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = run()
        outcomes = [v.outcome for v in result.verdicts]
        return outcomes, ratchet.exit_code(result), (out.getvalue(), err.getvalue())

    def assertDidNotRun(self, run, message):
        outcomes, code, streams = self.tried(run)
        self.assertEqual((outcomes, code), ([ratchet.Outcome.DID_NOT_RUN], 2))
        self.assertTrue(any(shown.endswith(message) for shown in streams), streams)

    def cc_check(self, *argv):
        return lambda: ratchet.result_of(qc.gate, list(argv), None, qc.ERROR_TAG)

    def crap(self, *argv):
        return lambda: ratchet.result_of(crap.gate, ["--lang", "python", *argv], None, crap.TAG)

    def comment_debt(self, *argv):
        return lambda: cd.result_of(list(argv), None, None, sys.stdout)

    def test_a_missing_baseline_did_not_run_in_cc_check(self):
        self.repo()
        self.assertDidNotRun(
            self.cc_check(str(self.module), "--baseline", str(self.missing)),
            f"No baseline at {self.missing}. Run with --update to create one.\n",
        )

    def test_a_missing_baseline_did_not_run_in_crap(self):
        self.repo()
        self.assertDidNotRun(
            self.crap(str(self.module), "--coverage-json", str(self.report), "--baseline", str(self.missing)),
            f"No baseline at {self.missing}. Run with --update to create one.\n",
        )

    def test_a_missing_baseline_did_not_run_in_comment_debt(self):
        self.repo()
        self.working_in_the_folder()
        self.assertDidNotRun(
            self.comment_debt("--baseline", str(self.missing)),
            f"No baseline at {self.missing}. Run with --update to create one.\n",
        )

    def test_an_empty_baseline_path_did_not_run_in_comment_debt(self):
        self.assertDidNotRun(self.comment_debt("--baseline", ""), "--baseline was given an empty path\n")

    def test_a_directory_that_is_not_a_git_repository_did_not_run_in_cc_check(self):
        self.working_in_the_folder()
        self.assertDidNotRun(self.cc_check("m.py"), f"ERROR: {NOT_A_REPO}\n")

    def test_a_directory_that_is_not_a_git_repository_did_not_run_in_crap(self):
        self.working_in_the_folder()
        self.assertDidNotRun(self.crap("m.py", "--no-coverage"), f"[crap] {NOT_A_REPO}\n")

    def test_a_directory_that_is_not_a_git_repository_did_not_run_in_comment_debt(self):
        self.working_in_the_folder()
        self.assertDidNotRun(self.comment_debt(), f"comment-debt: {NOT_A_REPO}\n")

    def test_a_missing_coverage_report_did_not_run_in_crap(self):
        self.repo()
        self.assertDidNotRun(
            self.crap(str(self.module), "--coverage-json", str(self.missing)),
            f"[crap] cannot open coverage file: [Errno 2] No such file or directory: '{self.missing}'\n",
        )

    def test_a_stale_coverage_report_with_strict_freshness_did_not_run_in_crap(self):
        self.repo()
        os.utime(self.report, (STALE_MTIME, STALE_MTIME))
        self.assertDidNotRun(
            self.crap(str(self.module), "--coverage-json", str(self.report), "--strict-freshness"),
            "[crap] ⚠️  coverage file may be stale: cov.json is older than the newest source file\n",
        )

    def test_nothing_to_scan_did_not_run_in_cc_check(self):
        self.repo()
        (self.root / "empty").mkdir()
        self.assertDidNotRun(self.cc_check(str(self.root / "empty")), "No Python files found.\n")

    def test_nothing_to_scan_did_not_run_in_crap(self):
        self.repo()
        (self.root / "empty").mkdir()
        self.assertDidNotRun(
            self.crap(str(self.root / "empty"), "--no-coverage"),
            "  Use --allow-empty to suppress this error.\n",
        )


if __name__ == "__main__":
    unittest.main()
