import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from quality_gates import languages_table

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / "docs" / "languages-by-gates.md"
HEADER = "| Language | comment-debt | cc-check | crap | Components installed for it |"
EVERY_LANGUAGE = "core, design-helpers, session-helpers"
PYTHON_ROW = "| Python | scores | scores | scores | core, no-comments, complexity-python, crap, design-helpers, session-helpers |"
SWIFT_ROW = "| Swift | — | — | scores | core, complexity-swift, crap, design-helpers, session-helpers |"
RUST_ROW = "| Rust | — | — | — | core, complexity-rust, design-helpers, session-helpers |"
SHELL_ROW = f"| Shell | — | — | — | {EVERY_LANGUAGE} |"


class Rendered(unittest.TestCase):
    def test_each_registered_language_gets_a_row_saying_which_gates_score_it_and_what_is_installed(self):
        lines = languages_table.render().splitlines()
        self.assertIn(HEADER, lines)
        for row in (PYTHON_ROW, SWIFT_ROW, RUST_ROW, SHELL_ROW):
            with self.subTest(row):
                self.assertIn(row, lines)

    def test_a_component_for_no_language_in_particular_is_installed_for_every_language(self):
        rows = [line for line in languages_table.render().splitlines()
                if line.startswith("| ") and not line.startswith(("| ---", "| Language"))]
        self.assertEqual(len(rows), 5)
        for row in rows:
            installed = row.rstrip(" |").rsplit(" | ", 1)[1].split(", ")
            with self.subTest(row):
                self.assertTrue(set(EVERY_LANGUAGE.split(", ")) <= set(installed), row)

    def test_the_rows_follow_the_registry_order(self):
        rows = [line.split(" | ")[0] for line in languages_table.render().splitlines()
                if line.startswith("| ") and not line.startswith("| ---")]
        self.assertEqual(rows, ["| Language", "| Python", "| Swift", "| TypeScript", "| Rust", "| Shell"])

    def test_the_page_says_how_it_is_made(self):
        self.assertIn("python -m quality_gates.languages_table", languages_table.render())


class Checked(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name).resolve() / "quality-gates"
        (self.repo / "docs" / "adr" / "archive").mkdir(parents=True)
        (self.repo / "docs" / "adr" / "archive" / "ADR-011-code-structure.md").write_text("# ADR-011\n", encoding="utf-8")
        self.path = self.repo / "docs" / "languages-by-gates.md"

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = languages_table.main(list(argv), repo=self.repo)
        return code, out.getvalue()

    def test_the_shipped_table_matches_the_gate_tables(self):
        self.assertEqual(languages_table.check(SHIPPED), [])

    def test_the_command_writes_into_the_checkout_that_holds_the_package(self):
        self.assertEqual(languages_table.REPO, ROOT)

    def test_a_missing_table_fails_the_check(self):
        self.assertEqual(languages_table.check(self.path),
                         [f"{self.path}: missing; run python -m quality_gates.languages_table"])

    def test_a_table_edited_by_hand_fails_the_check(self):
        self.path.write_text(languages_table.render().replace(SHELL_ROW, "| Shell | scores | — | — | none |"),
                             encoding="utf-8")
        self.assertEqual(languages_table.check(self.path),
                         [f"{self.path}: differs from the gate tables; run python -m quality_gates.languages_table"])

    def test_writing_the_table_makes_the_check_pass(self):
        self.assertEqual(self.run_main(), (0, "Wrote docs/languages-by-gates.md\n"))
        self.assertEqual(languages_table.check(self.path), [])

    def test_the_default_page_lands_in_the_checkout_whatever_folder_the_command_runs_in(self):
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        with tempfile.TemporaryDirectory() as elsewhere:
            os.chdir(elsewhere)
            self.assertEqual(self.run_main()[0], 0)
            os.chdir(here)
            self.assertEqual(list(Path(elsewhere).iterdir()), [])
        self.assertEqual(languages_table.check(self.path), [])

    def test_a_copy_of_the_package_outside_a_quality_gates_checkout_refuses_to_write_and_says_why(self):
        (self.repo / "docs" / "adr" / "archive" / "ADR-011-code-structure.md").unlink()
        code, out = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("only inside the quality-gates checkout", out)
        self.assertFalse(self.path.exists())

    def test_a_path_outside_the_checkout_is_refused(self):
        outside = self.repo.parent / "consumer" / "languages-by-gates.md"
        for flag in (str(outside), "../consumer/languages-by-gates.md"):
            with self.subTest(flag):
                code, out = self.run_main("--path", flag)
                self.assertEqual(code, 2)
                self.assertIn(f"{flag} is outside the quality-gates checkout", out)
        self.assertFalse(outside.parent.exists())

    def test_the_check_flag_exits_1_and_names_the_drift(self):
        self.assertEqual(self.run_main("--check"),
                         (1, "docs/languages-by-gates.md: missing; run python -m quality_gates.languages_table\n"))

    def test_a_missing_component_list_exits_3_with_one_plain_line_naming_the_file_for_check_and_write(self):
        missing = self.repo / "missing.json"
        for argv in (["--check"], []):
            with self.subTest(argv=argv):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = languages_table.main(argv, repo=self.repo, components_path=missing)
                self.assertEqual((code, out.getvalue(), err.getvalue()),
                                 (3, "", f"python -m quality_gates.languages_table: {missing}: not found\n"))
        self.assertFalse(self.path.exists())

    def test_the_check_flag_exits_0_when_the_table_matches(self):
        self.path.write_text(languages_table.render(), encoding="utf-8")
        self.assertEqual(self.run_main("--check"), (0, "The languages-by-gates table matches the gate tables.\n"))


if __name__ == "__main__":
    unittest.main()
