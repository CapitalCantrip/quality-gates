import ast
import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from quality_gates import qg, status

DISPATCHER_SOURCE = ROOT / "src" / "quality_gates" / "qg.py"
DISPATCHER_NAMES = {"COMMANDS", "DESCRIPTION", "build_parser", "main"}


def run(entry, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = entry(argv)
        except SystemExit as stop:
            code = stop.code
    return code, out.getvalue(), err.getvalue()


class QgDispatcherTest(unittest.TestCase):
    def test_every_registered_subcommand_is_reached_through_qg_with_its_own_arguments(self):
        for name, module in qg.COMMANDS.items():
            with self.subTest(name), mock.patch.object(module, "main", return_value=7) as entry:
                self.assertEqual(qg.main([name, "--json", "extra"]), 7)
                entry.assert_called_once_with(["--json", "extra"])

    def test_the_installed_qg_command_runs_the_dispatcher(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('qg = "quality_gates.qg:main"', pyproject)

    def test_the_dispatcher_holds_only_the_command_mapping_and_help(self):
        tree = ast.parse(DISPATCHER_SOURCE.read_text(encoding="utf-8"))
        names = set()
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.FunctionDef):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names.update(target.id for target in node.targets)
            else:
                self.fail(f"unexpected statement at line {node.lineno}")
        self.assertEqual(names, DISPATCHER_NAMES)

    def test_the_dispatcher_imports_only_argparse_and_the_commands_it_maps(self):
        tree = ast.parse(DISPATCHER_SOURCE.read_text(encoding="utf-8"))
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        expected = {"argparse", "sys"} | {module.__name__ for module in qg.COMMANDS.values()}
        self.assertEqual(imported, expected)

    def test_qg_help_lists_every_subcommand(self):
        code, out, _ = run(qg.main, ["--help"])
        self.assertEqual(code, 0)
        for name, module in qg.COMMANDS.items():
            self.assertRegex(out, rf"\n    {name}\s+{module.SUMMARY}\n")

    def test_qg_with_no_subcommand_stops_with_usage_and_exit_2(self):
        code, _, err = run(qg.main, [])
        self.assertEqual(code, 2)
        self.assertEqual(err, "usage: qg [-h] {status} ...\nqg: error: the following arguments are required: command\n")

    def test_an_unknown_subcommand_stops_with_exit_2(self):
        code, _, err = run(qg.main, ["bogus"])
        self.assertEqual(code, 2)
        self.assertIn("invalid choice: 'bogus'", err)

    def test_a_flag_before_the_subcommand_stops_with_usage_and_exit_2(self):
        code, out, err = run(qg.main, ["--json", "status"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("unrecognized arguments: --json", err)

    def test_qg_status_help_shows_the_status_options(self):
        code, out, _ = run(qg.main, ["status", "--help"])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("usage: qg status [-h] [--json]\n"))

    def test_qg_status_prints_what_the_status_module_prints_for_the_folder_it_runs_in(self):
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            for flags in ([], ["--json"]):
                with self.subTest(flags=flags):
                    self.assertEqual(run(qg.main, ["status", *flags]), run(status.main, flags))
            os.chdir(here)


if __name__ == "__main__":
    unittest.main()
