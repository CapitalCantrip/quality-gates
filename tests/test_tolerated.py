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
ALLOWED_IMPORTS = {"argparse", "sys", "quality_gates.project_files", "quality_gates.ratchet",
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

    def test_the_skeleton_finds_no_growth_for_the_tree_against_a_ref(self):
        self.assertEqual(tolerated.growth(self.root, "main"), ())

    def test_qg_help_lists_the_tolerated_subcommand(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn(f" tolerated {tolerated.SUMMARY} ", " ".join(out.split()))


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
