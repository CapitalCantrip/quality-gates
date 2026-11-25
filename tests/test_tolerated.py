import ast
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from quality_gates import project_files, qg, tolerated

ROOT = Path(__file__).resolve().parent.parent
MODULE_SOURCE = ROOT / "src" / "quality_gates" / "tolerated.py"
ALLOWED_IMPORTS = {"argparse", "os", "sys", "dataclasses.dataclass", "quality_gates.project_files",
                   "quality_gates.ratchet",
                   "quality_gates.errors.TOOL_ERROR_EXIT",
                   "quality_gates.errors.ToolError"}


def git(root, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                   capture_output=True)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = qg.main(argv)
        except SystemExit as stop:
            code = stop.code
    return code, out.getvalue(), err.getvalue()


class QgTolerated(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        git(self.root, "init", "-q", "-b", "main")
        (self.root / "cc-baseline.json").write_text('{"a.py::old": 11}\n', encoding="utf-8")
        git(self.root, "add", "cc-baseline.json")
        git(self.root, "commit", "-q", "-m", "baseline")
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        os.chdir(self.root)

    def test_against_main_with_a_committed_baseline_it_says_the_tolerated_list_did_not_grow_and_exits_0(self):
        self.assertEqual(run(["tolerated", "--against", "main"]), (0, "the tolerated list did not grow\n", ""))

    def test_a_ref_that_names_no_commit_did_not_run_and_exits_2_naming_the_ref(self):
        code, out, err = run(["tolerated", "--against", "origin/main"])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, f"qg tolerated: {project_files.NOT_A_COMMIT.format('origin/main')}\n")

    def test_without_git_on_the_path_it_did_not_run_and_exits_2_with_one_line(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.root / "no-bin")}):
            code, out, err = run(["tolerated", "--against", "main"])
        self.assertEqual((code, out, err), (2, "", f"qg tolerated: {project_files.NO_GIT}\n"))

    def test_the_ref_is_required(self):
        code, _, err = run(["tolerated"])
        self.assertEqual(code, 2)
        self.assertIn("--against", err)

    def test_an_unchanged_tree_has_no_growth_against_a_ref(self):
        self.assertEqual(tolerated.growth(self.root, "main"), ())

    def test_qg_help_lists_the_tolerated_subcommand(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn(f" tolerated {tolerated.SUMMARY} ", " ".join(out.split()))


def choice(exclude=(), comment_gate_exclude=()):
    return project_files.choice_text(project_files.Choice(languages=("python",), exclude=tuple(exclude),
                                                          comment_gate_exclude=tuple(comment_gate_exclude)))


GROWTH_LABELS = ("tolerated-growth", "loosening")


class ToleratedListGrowth(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        git(self.root, "init", "-q", "-b", "main")
        self.write("a.py", "x = 1\n")
        self.write("cc-baseline.json", '{"a.py::old": 11}\n')
        self.write("quality-gates.json", choice())
        git(self.root, "add", "a.py", "cc-baseline.json", "quality-gates.json")
        git(self.root, "commit", "-q", "-m", "main")
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        os.chdir(self.root)
        self.labels("")

    def write(self, name, text):
        (self.root / name).parent.mkdir(parents=True, exist_ok=True)
        (self.root / name).write_text(text, encoding="utf-8")

    def labels(self, text):
        patch = mock.patch.dict(os.environ, {tolerated.LABELS_VARIABLE: text})
        patch.start()
        self.addCleanup(patch.stop)

    def check(self):
        return run(["tolerated", "--against", "main"])

    def assertGrew(self, *grown):
        code, out, err = self.check()
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(len(out.splitlines()), 1)
        self.assertTrue(out.startswith(f"the tolerated list grew by {len(grown)}: "), out)
        for item in grown:
            self.assertIn(item, out)
        self.assertIn("tolerated-growth", out)
        return out

    def assertDidNotGrow(self):
        self.assertEqual(self.check(), (0, "the tolerated list did not grow\n", ""))

    def route_1(self):
        (self.root / "cc-baseline.json").unlink()
        self.write("cc-baseline.json", '{"a.py::new": 13, "a.py::old": 11}\n')

    def route_2(self):
        self.write("cc-baseline.json", '{"a.py::old": 11, "a.py::new": 13}\n')

    def route_3(self):
        self.write("quality-gates.json", choice(exclude=["src/"]))

    def test_route_1_a_baseline_deleted_and_recreated_with_a_new_entry_fails_without_the_label(self):
        self.route_1()
        self.assertGrew("cc-baseline.json a.py::new 13 (new)")

    def test_route_2_an_entry_typed_into_the_baseline_by_hand_fails_without_the_label(self):
        self.route_2()
        self.assertGrew("cc-baseline.json a.py::new 13 (new)")

    def test_route_3_a_folder_added_to_the_top_level_exclude_fails_without_the_label(self):
        self.route_3()
        self.assertGrew("quality-gates.json exclude src/ (new)")

    def test_each_route_passes_with_either_builder_label_and_still_prints_one_line_giving_the_growth(self):
        routes = {self.route_1: "cc-baseline.json a.py::new 13 (new)", self.route_2: "cc-baseline.json a.py::new 13 (new)",
                  self.route_3: "quality-gates.json exclude src/ (new)"}
        for route, grown in routes.items():
            for label in GROWTH_LABELS:
                with self.subTest(route=route.__name__, label=label):
                    self.labels(f"bug,{label}")
                    route()
                    code, out, err = self.check()
                    self.assertEqual((code, err), (0, ""))
                    self.assertEqual(out, f"the tolerated list grew by 1: {grown}; "
                                          f"the builder's `{label}` label allows it\n")
                    git(self.root, "checkout", "-q", "--", ".")

    def test_a_label_that_only_resembles_a_builder_label_does_not_pass(self):
        for text in ("tolerated-growth-x", "Loosening", "not loosening", "tolerated"):
            with self.subTest(text):
                self.labels(text)
                self.route_2()
                self.assertEqual(self.check()[0], 1)

    def test_a_raised_entry_is_growth(self):
        self.write("cc-baseline.json", '{"a.py::old": 12}\n')
        self.assertGrew("cc-baseline.json a.py::old 11 -> 12")

    def test_lowering_or_removing_entries_or_deleting_the_baseline_is_not_growth(self):
        for text in ('{"a.py::old": 10}\n', "{}\n", None):
            with self.subTest(text):
                if text is None:
                    (self.root / "cc-baseline.json").unlink()
                else:
                    self.write("cc-baseline.json", text)
                self.assertDidNotGrow()

    def test_removing_or_narrowing_an_exclude_prefix_is_not_growth(self):
        self.write("quality-gates.json", choice(exclude=["src/"], comment_gate_exclude=["gen/"]))
        git(self.root, "commit", "-q", "-am", "excludes")
        for exclude, comment_gate in (([], []), (["src/gen/"], ["gen/old/"]), (["src"], ["gen"])):
            with self.subTest(exclude=exclude, comment_gate=comment_gate):
                self.write("quality-gates.json", choice(exclude=exclude, comment_gate_exclude=comment_gate))
                self.assertDidNotGrow()

    def test_a_prefix_that_now_covers_more_is_growth(self):
        self.write("quality-gates.json", choice(exclude=["src/gen/"]))
        git(self.root, "commit", "-q", "-am", "excludes")
        self.write("quality-gates.json", choice(exclude=["src/"]))
        self.assertGrew("quality-gates.json exclude src/ (new)")

    def test_a_folder_added_to_the_comment_gate_exclude_is_growth(self):
        self.write("quality-gates.json", choice(comment_gate_exclude=["gen/"]))
        self.assertGrew("quality-gates.json settings.no-comments.exclude gen/ (new)")

    def test_moving_a_prefix_from_the_top_level_exclude_to_the_comment_gate_exclude_is_not_growth(self):
        self.write("quality-gates.json", choice(exclude=["gen/"]))
        git(self.root, "commit", "-q", "-am", "excludes")
        self.write("quality-gates.json", choice(comment_gate_exclude=["gen/"]))
        self.assertDidNotGrow()

    def test_a_folder_the_top_level_exclude_gains_is_growth_even_when_the_comment_gate_already_skipped_it(self):
        self.write("quality-gates.json", choice(comment_gate_exclude=["gen/"]))
        git(self.root, "commit", "-q", "-am", "excludes")
        self.write("quality-gates.json", choice(exclude=["gen/"]))
        self.assertGrew("quality-gates.json exclude gen/ (new)")

    def test_both_growths_in_one_change_are_counted_on_the_one_line(self):
        self.route_2()
        self.route_3()
        self.assertGrew("cc-baseline.json a.py::new 13 (new)", "quality-gates.json exclude src/ (new)")

    def test_a_baseline_for_a_gate_the_ref_has_no_baseline_for_is_not_growth(self):
        for name in ("crap-baseline.json", "comment-debt.json", "silencer-baseline.json"):
            with self.subTest(name):
                self.write(name, '{"a.py::f": 40}\n')
                self.assertDidNotGrow()

    def test_on_first_adoption_a_ref_with_no_baselines_and_no_choice_file_has_no_growth(self):
        git(self.root, "rm", "-q", "cc-baseline.json", "quality-gates.json")
        git(self.root, "commit", "-q", "-m", "before adoption")
        self.write("cc-baseline.json", '{"a.py::old": 11}\n')
        self.write("crap-baseline.json", '{"a.py::old": 132}\n')
        self.write("quality-gates.json", choice(exclude=["vendor/"]))
        self.assertDidNotGrow()

    def test_a_new_entry_in_the_silencer_baseline_is_growth_like_any_baseline(self):
        self.write("silencer-baseline.json", '{"a.py": 1}\n')
        git(self.root, "add", "silencer-baseline.json")
        git(self.root, "commit", "-q", "-m", "silencers")
        self.write("silencer-baseline.json", '{"a.py": 1, "b.py": 2}\n')
        self.assertGrew("silencer-baseline.json b.py 2 (new)")

    def test_a_baseline_at_the_ref_that_cannot_be_read_did_not_run_and_names_the_ref(self):
        self.write("cc-baseline.json", "[]\n")
        git(self.root, "commit", "-q", "-am", "broken")
        self.write("cc-baseline.json", '{"a.py::old": 11}\n')
        code, out, err = self.check()
        self.assertEqual((code, out), (2, ""))
        self.assertIn("main:cc-baseline.json", err)

    def test_growth_is_returned_as_findings_naming_where_and_what_grew(self):
        self.route_2()
        self.assertEqual([str(grown) for grown in tolerated.growth(self.root, "main")],
                         ["cc-baseline.json a.py::new 13 (new)"])


class TheCiStepPassesTheLabels(unittest.TestCase):
    def test_the_step_setup_prints_passes_the_pull_requests_labels_in_the_variable_qg_tolerated_reads(self):
        passed = "QG_PR_LABELS: ${{ join(github.event.pull_request.labels.*.name, ',') }}"
        self.assertEqual(tolerated.LABELS_VARIABLE, "QG_PR_LABELS")
        self.assertIn(passed, [line.strip() for line in project_files.TOLERATED_STEP])

    def test_the_paste_note_says_the_trigger_must_rerun_the_check_when_a_label_is_added_or_removed(self):
        note = " ".join(project_files.tolerated_step_notes(Path(tempfile.mkdtemp()))[0].split())
        self.assertIn("types: [opened, synchronize, reopened, labeled, unlabeled]", note)


class ToleratedParsesNothingOfItsOwn(unittest.TestCase):
    def test_the_tolerated_module_imports_no_git_runner_and_no_json_reader(self):
        tree = ast.parse(MODULE_SOURCE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        self.assertLessEqual(imported, ALLOWED_IMPORTS)


if __name__ == "__main__":
    unittest.main()
