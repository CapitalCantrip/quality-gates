import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import skills_sync, upstream


def run(argv, source, hooks):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), self_exit() as code:
        skills_sync.main(argv, source, hooks)
    return code[0], out.getvalue()


@contextlib.contextmanager
def self_exit():
    code = [None]
    try:
        yield code
    except SystemExit as stop:
        code[0] = stop.code


class SkillsSync(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "shipped"
        self.dest = self.tmp / "repo" / ".claude" / "skills"
        self.write(self.source / "cc-python" / "SKILL.md", "cc python v1")
        self.write(self.source / "crap" / "SKILL.md", "crap v1")
        self.write(self.source / "crap" / "reference.md", "crap ref")
        self.hooks = self.tmp / "shipped-hooks"
        self.write(self.hooks / "stage_guard.py", "guard")
        self.repo = self.tmp / "repo"
        self.write(self.repo / "CLAUDE.md", "# Repo\n")

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def sync(self):
        return run(["--dest", str(self.dest)], self.source, self.hooks)

    def check(self):
        return run(["--dest", str(self.dest), "--check"], self.source, self.hooks)

    def test_sync_copies_every_shipped_skill_with_its_files(self):
        code, _ = self.sync()
        self.assertEqual(code, 0)
        self.assertEqual((self.dest / "crap" / "reference.md").read_text(), "crap ref")
        self.assertEqual((self.dest / "cc-python" / "SKILL.md").read_text(), "cc python v1")

    def test_check_passes_right_after_a_sync(self):
        self.sync()
        self.assertEqual(self.check()[0], 0)

    def test_check_fails_when_a_skill_has_not_been_copied(self):
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("cc-python/SKILL.md: missing", out)

    def test_check_fails_when_a_copy_was_edited_by_hand(self):
        self.sync()
        self.write(self.dest / "crap" / "SKILL.md", "crap edited")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("crap/SKILL.md: differs", out)

    def test_check_fails_when_the_pinned_version_ships_a_newer_skill(self):
        self.sync()
        self.write(self.source / "crap" / "SKILL.md", "crap v2")
        self.assertEqual(self.check()[0], 1)

    def test_a_file_the_new_version_dropped_fails_the_check_and_sync_removes_it(self):
        self.sync()
        (self.source / "crap" / "reference.md").unlink()
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("crap/reference.md: not shipped", out)
        self.sync()
        self.assertFalse((self.dest / "crap" / "reference.md").exists())

    def test_sync_leaves_the_repos_own_skills_alone(self):
        self.write(self.dest / "cos" / "SKILL.md", "the repo's own skill")
        self.sync()
        self.assertEqual((self.dest / "cos" / "SKILL.md").read_text(), "the repo's own skill")
        self.assertEqual(self.check()[0], 0)

    def test_sync_installs_the_stage_guard_and_the_asking_line_beside_the_skills(self):
        code, out = self.sync()
        self.assertEqual(code, 0)
        self.assertEqual((self.repo / ".claude" / "hooks" / "stage_guard.py").read_text(), "guard")
        self.assertIn("stage_guard.py", (self.repo / ".claude" / "settings.json").read_text())
        self.assertIn("**Asking the builder:**", (self.repo / "CLAUDE.md").read_text())
        self.assertIn("asking-rule line in CLAUDE.md", out)

    def test_check_fails_when_claude_md_has_lost_the_asking_line(self):
        self.sync()
        self.write(self.repo / "CLAUDE.md", "# Repo\n")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("CLAUDE.md: the asking-rule line is missing or out of date", out)

    def test_check_fails_when_the_stage_guard_was_unregistered(self):
        self.sync()
        self.write(self.repo / ".claude" / "settings.json", "{}")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("the stage guard is not registered", out)

    def test_broken_settings_json_exits_2_and_says_which_file(self):
        self.write(self.repo / ".claude" / "settings.json", "{oops")
        code, out = self.sync()
        self.assertEqual(code, 2)
        self.assertIn("settings.json is not valid JSON", out)

    def test_the_package_ships_every_skill_the_plugin_lists(self):
        names = skills_sync.skill_names(skills_sync.SHIPPED)
        self.assertEqual(names, ["cc-python", "cc-rust", "cc-swift", "cc-typescript", "codebase-design", "crap",
                                 "diagnosing-bugs", "domain-modeling", "grill-with-docs", "handoff",
                                 "implement", "implement-spec", "improve-codebase-architecture",
                                 "no-comments", "pr", "retro", "review-against-spec",
                                 "setup-matt-pocock-skills", "setup-standards", "standards", "tdd",
                                 "to-spec", "to-tickets", "triage", "wayfinder", "writing-for-agents"])

    def test_every_skill_copied_from_matt_pocock_carries_his_licence(self):
        copied = {Path(local).parts[3] for source in json.loads(upstream.RECORD.read_text())["sources"]
                  if source["repo"] == "mattpocock/skills"
                  for local in source["files"].values() if "/skills/" in local}
        copied.discard("setup-standards")
        self.assertEqual(len(copied), 17)
        for name in copied:
            self.assertTrue((skills_sync.SHIPPED / name / "LICENSE-mattpocock").is_file(), name)

    def test_no_shipped_skill_hides_claude_codes_own_code_review(self):
        self.assertNotIn("code-review", skills_sync.skill_names(skills_sync.SHIPPED))


if __name__ == "__main__":
    unittest.main()
