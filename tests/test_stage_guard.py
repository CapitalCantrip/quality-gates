import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "src" / "quality_gates" / "hooks" / "stage_guard.py"
spec = importlib.util.spec_from_file_location("stage_guard", HOOK)
stage_guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_guard)


def verdict(command):
    stderr = io.StringIO()
    payload = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
    return stage_guard.main(payload, stderr), stderr.getvalue()


class BulkStagingIsBlocked(unittest.TestCase):
    def assertBlocked(self, command):
        code, message = verdict(command)
        self.assertEqual(code, 2, command)
        self.assertIn("Stage the files this change touched, by name", message)

    def test_git_add_all_in_every_spelling_is_blocked(self):
        for command in ["git add -A", "git add --all", "git add .", "git add ./", "git add -u",
                        "git add --update", "git add :/", "git add :.", "git add *", "git add -Av", "git stage -A"]:
            self.assertBlocked(command)

    def test_git_commit_all_in_every_spelling_is_blocked(self):
        for command in ["git commit -a", "git commit --all -m done", "git commit -am done",
                        'git commit -a -m "fix"']:
            self.assertBlocked(command)

    def test_a_bulk_stage_hidden_in_a_chain_is_blocked(self):
        for command in ["cd src && git add -A", "make test; git add .", "true || git commit -am x",
                        "echo $(git add -A)", "git status\ngit add ."]:
            self.assertBlocked(command)

    def test_git_options_before_the_subcommand_do_not_hide_it(self):
        for command in ["git -C ../other add -A", "git -c core.x=y add .", "/usr/bin/git add -A",
                        "git --no-pager commit -a"]:
            self.assertBlocked(command)

    def test_the_message_names_the_command_that_was_blocked(self):
        _, message = verdict("cd src && git add -A")
        self.assertIn("`git add -A`", message)


class NamedStagingIsAllowed(unittest.TestCase):
    def assertAllowed(self, command):
        self.assertEqual(verdict(command), (0, ""), command)

    def test_staging_named_files_is_allowed(self):
        for command in ["git add src/a.py tests/test_a.py", "git add ./src/a.py", "git add -p src/a.py",
                        "git add -- src/a.py", "git stage README.md"]:
            self.assertAllowed(command)

    def test_a_commit_of_what_is_already_staged_is_allowed(self):
        for command in ["git commit -m 'add all the things'", 'git commit -m "-a is blocked"',
                        "git commit --amend --no-edit", "git commit -ma", "git commit -F msg.txt -- a.py"]:
            self.assertAllowed(command)

    def test_a_heredoc_commit_message_mentioning_bulk_staging_is_allowed(self):
        self.assertAllowed('git commit -m "$(cat <<\'EOF\'\nStop using git add -A\n\nBody\nEOF\n)"')

    def test_commands_that_only_mention_git_add_are_allowed(self):
        for command in ["echo 'git add -A'", "grep -r 'git add .' docs", "ls -A", "git status -u"]:
            self.assertAllowed(command)

    def test_input_that_is_not_a_bash_call_is_allowed(self):
        self.assertEqual(stage_guard.main(io.StringIO("not json"), io.StringIO()), 0)
        self.assertEqual(stage_guard.main(io.StringIO('{"tool_input": {}}'), io.StringIO()), 0)
        self.assertEqual(stage_guard.main(io.StringIO("[1]"), io.StringIO()), 0)

    def test_an_unbalanced_quote_does_not_crash_the_guard(self):
        self.assertEqual(verdict("git add -A 'oops")[0], 2)
        self.assertEqual(verdict("echo 'oops")[0], 0)


class TheShippedScriptRunsOnItsOwn(unittest.TestCase):
    def test_run_as_a_script_it_exits_2_on_git_add_all(self):
        payload = json.dumps({"tool_input": {"command": "git add -A"}})
        result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("stage guard", result.stderr)


if __name__ == "__main__":
    unittest.main()
