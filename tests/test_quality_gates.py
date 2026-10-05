import io
import os
import unittest
from pathlib import Path

from quality_gates import comment_debt, quality_check, skills_sync

REPO = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ["src", "tests"]


class QualityGates(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(REPO)

    def tearDown(self):
        os.chdir(self.cwd)

    def exit_code(self, main, argv):
        with self.assertRaises(SystemExit) as stop:
            main(argv)
        return stop.exception.code

    def test_no_file_has_more_comment_lines_than_its_baseline(self):
        self.assertEqual(comment_debt.main([], root=REPO, out=io.StringIO()), 0)

    def test_no_function_is_more_complex_than_the_baseline_allows(self):
        argv = SOURCE_DIRS + ["--baseline", "cc-baseline.json"]
        self.assertEqual(self.exit_code(quality_check.main, argv), 0)

    def test_the_skills_stage_guard_and_asking_rule_match_the_pinned_version(self):
        self.assertEqual(self.exit_code(skills_sync.main, ["--check"]), 0)
