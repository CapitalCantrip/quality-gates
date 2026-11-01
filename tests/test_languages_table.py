import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from quality_gates import languages_table

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / "docs" / "languages-by-gates.md"
HEADER = "| Language | comment-debt | cc-check | crap | Components installed for it |"
PYTHON_ROW = "| Python | scores | scores | scores | no-comments, complexity-python, crap |"
SWIFT_ROW = "| Swift | — | — | scores | complexity-swift, crap |"
RUST_ROW = "| Rust | — | — | — | complexity-rust |"
SHELL_ROW = "| Shell | — | — | — | none |"


class Rendered(unittest.TestCase):
    def test_each_registered_language_gets_a_row_saying_which_gates_score_it_and_what_is_installed(self):
        lines = languages_table.render().splitlines()
        self.assertIn(HEADER, lines)
        for row in (PYTHON_ROW, SWIFT_ROW, RUST_ROW, SHELL_ROW):
            with self.subTest(row):
                self.assertIn(row, lines)

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
        self.path = Path(tmp.name) / "languages-by-gates.md"

    def test_the_shipped_table_matches_the_gate_tables(self):
        self.assertEqual(languages_table.check(SHIPPED), [])

    def test_a_missing_table_fails_the_check(self):
        self.assertEqual(languages_table.check(self.path),
                         [f"{self.path}: missing; run python -m quality_gates.languages_table"])

    def test_a_table_edited_by_hand_fails_the_check(self):
        self.path.write_text(languages_table.render().replace(SHELL_ROW, "| Shell | scores | — | — | none |"),
                             encoding="utf-8")
        self.assertEqual(languages_table.check(self.path),
                         [f"{self.path}: differs from the gate tables; run python -m quality_gates.languages_table"])

    def test_writing_the_table_makes_the_check_pass(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(languages_table.main(["--path", str(self.path)]), 0)
        self.assertEqual(languages_table.check(self.path), [])

    def test_the_check_flag_exits_1_and_names_the_drift(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = languages_table.main(["--path", str(self.path), "--check"])
        self.assertEqual((code, out.getvalue()),
                         (1, f"{self.path}: missing; run python -m quality_gates.languages_table\n"))

    def test_the_check_flag_exits_0_when_the_table_matches(self):
        self.path.write_text(languages_table.render(), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = languages_table.main(["--path", str(self.path), "--check"])
        self.assertEqual((code, out.getvalue()), (0, "The languages-by-gates table matches the gate tables.\n"))


if __name__ == "__main__":
    unittest.main()
