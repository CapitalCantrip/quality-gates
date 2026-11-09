import unittest

from gate_pins import COMMENT_DEBT, project

TWO_COMMENTS = "x = 1\n# why\ny = 2  # more\n"
CLEAN = "x = 1\n"
NEW_POLICY_LINE = (
    "\nNew comments are not allowed (no-code-comments policy). Move the knowledge to a test, "
    "a named constant, an ADR or an issue — see the quality-gates README for where each kind goes.\n"
)
BEHIND_LINE = (
    "\nThe baseline is behind. Run `comment-debt --update` "
    "and commit comment-debt.json so the paid debt cannot come back.\n"
)
UPDATE_REFUSAL = "--update only lowers the baseline. It will not record new comments.\n"
NOT_A_REPO = (
    "comment-debt: not inside a git repository: quality-gates looks at the files git would commit, "
    "so run it inside the project's repository, or run `git init` there first\n"
)
CONFLICTED = "<<<<<<< ours\n{}\n=======\n{\"x\": 1}\n>>>>>>> theirs\n"
NO_FOLDER = "[Errno 2] No such file or directory: 'nodir/b.json'\n"
BAD_JSON = "bad baseline <ROOT>/comment-debt.json: Expecting value: line 1 column 1 (char 0)\n"
NOT_AN_OBJECT = "bad baseline <ROOT>/comment-debt.json: must be an object, got list\n"
NULL_VALUE = "bad baseline <ROOT>/comment-debt.json: value for a.py must be a number, got NoneType\n"
TEXT_VALUE = "bad baseline <ROOT>/comment-debt.json: value for a.py must be a number, got str\n"
LOCKED = "[Errno 13] Permission denied: 'locked/b.json'\n"


class PinTest(unittest.TestCase):

    def assertRan(self, ran, code, out, err=""):
        self.assertEqual(ran.triple(), (code, out, err))

    def baselined(self, files, baseline):
        made = project(self, files)
        made.write("comment-debt.json", baseline)
        return made


class CheckTest(PinTest):

    def test_a_tree_at_its_baseline_passes_with_the_totals_and_exit_0(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, '{\n  "a.py": 2\n}\n')
        self.assertRan(made.run(COMMENT_DEBT), 0, "comment debt: 2 lines in 1 files, none new\n")

    def test_a_clean_tree_with_an_empty_baseline_passes_with_zero_totals(self):
        made = self.baselined({"a.py": CLEAN}, "{}\n")
        self.assertRan(made.run(COMMENT_DEBT), 0, "comment debt: 0 lines in 0 files, none new\n")

    def test_a_new_comment_fails_with_the_line_numbers_of_every_comment_line_and_exit_1(self):
        made = self.baselined({"a.py": TWO_COMMENTS + "# new\n"}, '{\n  "a.py": 2\n}\n')
        expected = "FAIL a.py: 3 comment lines, baseline allows 2 — lines 2, 3, 4\n" + NEW_POLICY_LINE
        self.assertRan(made.run(COMMENT_DEBT), 1, expected)

    def test_a_file_missing_from_the_baseline_fails_with_an_allowance_of_0(self):
        made = self.baselined({"a.py": CLEAN, "b.py": "# why\n"}, "{}\n")
        expected = "FAIL b.py: 1 comment lines, baseline allows 0 — lines 1\n" + NEW_POLICY_LINE
        self.assertRan(made.run(COMMENT_DEBT), 1, expected)

    def test_failing_files_are_listed_in_path_order_before_the_policy_line(self):
        made = self.baselined({"b.py": "# one\n", "a.py": "# two\n# three\n"}, "{}\n")
        expected = (
            "FAIL a.py: 2 comment lines, baseline allows 0 — lines 1, 2\n"
            "FAIL b.py: 1 comment lines, baseline allows 0 — lines 1\n"
        ) + NEW_POLICY_LINE
        self.assertRan(made.run(COMMENT_DEBT), 1, expected)

    def test_a_file_below_its_baseline_is_reported_paid_with_the_update_advice_and_exit_1(self):
        made = self.baselined({"a.py": CLEAN}, '{\n  "a.py": 2\n}\n')
        expected = "PAID a.py: 0 lines, baseline still says 2\n" + BEHIND_LINE
        self.assertRan(made.run(COMMENT_DEBT), 1, expected)

    def test_a_baselined_file_that_is_no_longer_tracked_is_reported_gone_and_exit_1(self):
        made = self.baselined({"a.py": TWO_COMMENTS, "b.py": CLEAN}, '{\n  "a.py": 2\n}\n')
        made.untrack("a.py")
        expected = "GONE a.py: in the baseline but no longer tracked\n" + BEHIND_LINE
        self.assertRan(made.run(COMMENT_DEBT), 1, expected)

    def test_paid_lines_come_before_gone_lines_under_one_behind_notice(self):
        made = self.baselined(
            {"a.py": CLEAN, "b.py": CLEAN, "z.py": CLEAN},
            '{\n  "a.py": 1,\n  "b.py": 1,\n  "gone.py": 1\n}\n',
        )
        expected = (
            "PAID a.py: 0 lines, baseline still says 1\n"
            "PAID b.py: 0 lines, baseline still says 1\n"
            "GONE gone.py: in the baseline but no longer tracked\n"
        ) + BEHIND_LINE
        self.assertRan(made.run(COMMENT_DEBT), 1, expected)

    def test_a_missing_baseline_cannot_run_and_exits_2_naming_the_file(self):
        made = project(self, {"a.py": CLEAN})
        expected = "No baseline at <ROOT>/comment-debt.json. Run with --update to create one.\n"
        self.assertRan(made.run(COMMENT_DEBT), 2, expected)

    def test_a_named_baseline_that_is_missing_cannot_run_and_exits_2_naming_that_file(self):
        made = project(self, {"a.py": CLEAN})
        expected = "No baseline at other.json. Run with --update to create one.\n"
        self.assertRan(made.run(COMMENT_DEBT, "--baseline", "other.json"), 2, expected)

    def test_a_missing_baseline_is_reported_before_a_file_python_cannot_read_is_measured(self):
        made = project(self, {"a.py": CLEAN, "bad.py": "def f(:\n"})
        expected = "No baseline at <ROOT>/comment-debt.json. Run with --update to create one.\n"
        self.assertRan(made.run(COMMENT_DEBT), 2, expected)

    def test_a_directory_that_is_not_a_git_repository_cannot_run_and_exits_2(self):
        made = project(self, {"a.py": CLEAN}, repo=False)
        self.assertRan(made.run(COMMENT_DEBT), 2, NOT_A_REPO)

    def test_an_empty_baseline_path_cannot_run_and_exits_2(self):
        made = project(self, {"a.py": CLEAN})
        self.assertRan(made.run(COMMENT_DEBT, "--baseline", ""), 2, "--baseline was given an empty path\n")

    def test_a_whitespace_baseline_path_cannot_run_and_exits_2(self):
        made = project(self, {"a.py": CLEAN})
        self.assertRan(made.run(COMMENT_DEBT, "--baseline", "  "), 2, "--baseline was given an empty path\n")

    def test_an_empty_baseline_path_is_refused_before_the_repository_is_looked_for(self):
        made = project(self, {"a.py": CLEAN}, repo=False)
        self.assertRan(made.run(COMMENT_DEBT, "--baseline", ""), 2, "--baseline was given an empty path\n")


class UpdateTest(PinTest):

    def test_update_creates_a_missing_baseline_from_the_tree_byte_for_byte(self):
        made = project(self, {"a.py": TWO_COMMENTS, "b.py": CLEAN})
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 0, "baseline: 2 lines in 1 files\n")
        self.assertEqual(made.read("comment-debt.json"), b'{\n  "a.py": 2\n}\n')

    def test_update_creates_an_empty_baseline_for_a_clean_tree_byte_for_byte(self):
        made = project(self, {"a.py": CLEAN})
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 0, "baseline: 0 lines in 0 files\n")
        self.assertEqual(made.read("comment-debt.json"), b"{}\n")

    def test_update_lowers_a_paid_file_and_drops_a_gone_one_byte_for_byte(self):
        made = self.baselined(
            {"a.py": "# one\n", "b.py": CLEAN, "c.py": CLEAN},
            '{\n  "a.py": 3,\n  "b.py": 2,\n  "gone.py": 4\n}\n',
        )
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 0, "baseline: 1 lines in 1 files\n")
        self.assertEqual(made.read("comment-debt.json"), b'{\n  "a.py": 1\n}\n')

    def test_update_sorts_the_paths_it_writes(self):
        made = project(self, {"b.py": "# one\n", "a.py": "# two\n"})
        made.run(COMMENT_DEBT, "--update")
        self.assertEqual(made.read("comment-debt.json"), b'{\n  "a.py": 1,\n  "b.py": 1\n}\n')

    def test_update_refuses_a_new_comment_with_the_fail_line_and_leaves_the_baseline_untouched(self):
        original = '{\n  "a.py": 2\n}\n'
        made = self.baselined({"a.py": TWO_COMMENTS + "# new\n"}, original)
        expected = "FAIL a.py: 3 comment lines, baseline allows 2 — lines 2, 3, 4\n" + NEW_POLICY_LINE + UPDATE_REFUSAL
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 1, expected)
        self.assertEqual(made.read("comment-debt.json"), original.encode("utf-8"))

    def test_update_writes_to_the_baseline_named_on_the_command_line(self):
        made = project(self, {"a.py": TWO_COMMENTS})
        self.assertRan(made.run(COMMENT_DEBT, "--update", "--baseline", "other.json"), 0, "baseline: 2 lines in 1 files\n")
        self.assertEqual(made.read("other.json"), b'{\n  "a.py": 2\n}\n')
        self.assertFalse(made.exists("comment-debt.json"))

    def test_update_in_a_directory_that_is_not_a_git_repository_exits_2_and_writes_nothing(self):
        made = project(self, {"a.py": CLEAN}, repo=False)
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 2, NOT_A_REPO)
        self.assertFalse(made.exists("comment-debt.json"))

    def test_update_with_an_empty_baseline_path_exits_2_and_writes_nothing(self):
        made = project(self, {"a.py": CLEAN})
        self.assertRan(made.run(COMMENT_DEBT, "--update", "--baseline", ""), 2, "--baseline was given an empty path\n")
        self.assertFalse(made.exists("comment-debt.json"))


class BaselineFileTest(PinTest):

    def test_update_into_a_folder_that_does_not_exist_cannot_run_and_exits_2_naming_the_file(self):
        made = project(self, {"a.py": TWO_COMMENTS})
        self.assertRan(made.run(COMMENT_DEBT, "--update", "--baseline", "nodir/b.json"), 2, NO_FOLDER)

    def test_a_baseline_with_merge_conflict_markers_cannot_run_and_exits_2_naming_the_file(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, CONFLICTED)
        self.assertRan(made.run(COMMENT_DEBT), 2, BAD_JSON)

    def test_update_over_a_baseline_with_merge_conflict_markers_cannot_run_and_leaves_it_untouched(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, CONFLICTED)
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 2, BAD_JSON)
        self.assertEqual(made.read("comment-debt.json"), CONFLICTED.encode("utf-8"))

    def test_a_baseline_that_is_not_a_json_object_cannot_run_and_exits_2_naming_the_file(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, "[]\n")
        self.assertRan(made.run(COMMENT_DEBT), 2, NOT_AN_OBJECT)

    def test_update_over_a_baseline_that_is_not_a_json_object_cannot_run_and_leaves_it_untouched(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, "[]\n")
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 2, NOT_AN_OBJECT)
        self.assertEqual(made.read("comment-debt.json"), b"[]\n")

    def test_a_baseline_value_of_null_cannot_run_and_exits_2_naming_the_file(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, '{"a.py": null}\n')
        self.assertRan(made.run(COMMENT_DEBT), 2, NULL_VALUE)

    def test_update_over_a_baseline_value_of_null_cannot_run_and_leaves_it_untouched(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, '{"a.py": null}\n')
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 2, NULL_VALUE)
        self.assertEqual(made.read("comment-debt.json"), b'{"a.py": null}\n')

    def test_a_baseline_value_that_is_a_string_cannot_run_and_exits_2_naming_the_file(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, '{"a.py": "10"}\n')
        self.assertRan(made.run(COMMENT_DEBT), 2, TEXT_VALUE)

    def test_update_over_a_baseline_value_that_is_a_string_cannot_run_and_leaves_it_untouched(self):
        made = self.baselined({"a.py": TWO_COMMENTS}, '{"a.py": "10"}\n')
        self.assertRan(made.run(COMMENT_DEBT, "--update"), 2, TEXT_VALUE)
        self.assertEqual(made.read("comment-debt.json"), b'{"a.py": "10"}\n')

    def test_a_baseline_in_a_folder_that_cannot_be_searched_cannot_run_and_exits_2_naming_the_file(self):
        made = project(self, {"a.py": TWO_COMMENTS})
        made.lock("locked")
        self.assertRan(made.run(COMMENT_DEBT, "--baseline", "locked/b.json"), 2, LOCKED)

    def test_update_into_a_folder_that_cannot_be_searched_cannot_run_and_exits_2_naming_the_file(self):
        made = project(self, {"a.py": TWO_COMMENTS})
        made.lock("locked")
        self.assertRan(made.run(COMMENT_DEBT, "--update", "--baseline", "locked/b.json"), 2, LOCKED)


if __name__ == "__main__":
    unittest.main()
