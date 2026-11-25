import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import manifest, project_files, skills_sync


def run(argv, source, hooks, agents):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), self_exit() as code:
        skills_sync.main(argv, source, hooks, agents)
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
        self.agents_source = self.tmp / "shipped-agents"
        self.write(self.agents_source / "implementer.md", "implementer v1")
        self.write(self.agents_source / "reviewer.md", "reviewer v1")
        self.repo = self.tmp / "repo"
        self.write(self.repo / "CLAUDE.md", "# Repo\n")

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def sync(self):
        return run(["--dest", str(self.dest)], self.source, self.hooks, self.agents_source)

    def check(self):
        return run(["--dest", str(self.dest), "--check"], self.source, self.hooks, self.agents_source)

    def test_sync_copies_every_shipped_skill_with_its_files(self):
        code, _ = self.sync()
        self.assertEqual(code, 0)
        self.assertEqual((self.dest / "crap" / "reference.md").read_text(), "crap ref")
        self.assertEqual((self.dest / "cc-python" / "SKILL.md").read_text(), "cc python v1")

    def test_sync_copies_the_reference_files_in_a_skills_subfolder(self):
        self.write(self.source / "crap" / "references" / "skip-list.md", "skip list rule")
        self.sync()
        self.assertEqual((self.dest / "crap" / "references" / "skip-list.md").read_text(), "skip list rule")

    def test_check_fails_when_a_reference_file_is_missing_from_the_copy(self):
        self.write(self.source / "crap" / "references" / "skip-list.md", "skip list rule")
        self.sync()
        (self.dest / "crap" / "references" / "skip-list.md").unlink()
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("crap/references/skip-list.md: missing", out)

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

    @property
    def agents(self):
        return self.repo / ".claude" / "agents"

    def test_sync_copies_every_shipped_agent_into_the_agents_folder_beside_the_skills(self):
        code, out = self.sync()
        self.assertEqual(code, 0)
        self.assertEqual((self.agents / "implementer.md").read_text(), "implementer v1")
        self.assertEqual((self.agents / "reviewer.md").read_text(), "reviewer v1")
        self.assertIn("agents implementer, reviewer", out)

    def test_check_fails_when_an_agent_has_not_been_copied(self):
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("agents/implementer.md: missing", out)

    def test_check_fails_when_the_pinned_version_ships_a_newer_agent(self):
        self.sync()
        self.write(self.agents_source / "reviewer.md", "reviewer v2")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("agents/reviewer.md: differs", out)

    def test_sync_removes_an_agent_it_shipped_and_no_longer_ships(self):
        self.sync()
        (self.agents_source / "reviewer.md").unlink()
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("agents/reviewer.md: not shipped", out)
        self.sync()
        self.assertFalse((self.agents / "reviewer.md").exists())
        self.assertEqual(self.check()[0], 0)

    def test_sync_leaves_the_repos_own_agent_untouched(self):
        self.write(self.agents / "planner.md", "the repo's own agent")
        self.sync()
        (self.agents_source / "reviewer.md").unlink()
        self.sync()
        self.assertEqual((self.agents / "planner.md").read_text(), "the repo's own agent")
        self.assertEqual(self.check()[0], 0)

    def test_sync_takes_over_an_unlisted_agent_that_already_matches_the_shipped_one(self):
        self.write(self.agents / "reviewer.md", "reviewer v1")
        self.assertEqual(self.sync()[0], 0)
        self.write(self.agents_source / "reviewer.md", "reviewer v2")
        self.assertEqual(self.sync()[0], 0)
        self.assertEqual((self.agents / "reviewer.md").read_text(), "reviewer v2")

    def test_sync_stops_and_changes_nothing_when_the_repo_has_its_own_agent_with_a_shipped_name(self):
        self.write(self.agents / "reviewer.md", "the repo's own reviewer")
        code, out = self.sync()
        self.assertEqual(code, 2)
        self.assertIn(str(self.agents / "reviewer.md"), out)
        self.assertEqual((self.agents / "reviewer.md").read_text(), "the repo's own reviewer")
        self.assertEqual(sorted(p.name for p in self.agents.iterdir()), ["reviewer.md"])
        self.assertFalse(self.dest.exists())

    def test_check_names_an_unlisted_agent_with_a_shipped_name(self):
        self.write(self.agents / "reviewer.md", "the repo's own reviewer")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("agents/reviewer.md: the project's own agent has a name quality-gates ships", out)

    def test_sync_stops_when_a_project_agent_under_another_filename_declares_a_shipped_name(self):
        self.write(self.agents / "code-reviewer.md", "---\nname: reviewer\ndescription: ours\n---\nbody")
        code, out = self.sync()
        self.assertEqual(code, 2)
        self.assertIn(str(self.agents / "code-reviewer.md"), out)
        self.assertFalse((self.agents / "reviewer.md").exists())

    def test_check_names_a_project_agent_under_another_filename_that_declares_a_shipped_name(self):
        self.sync()
        self.write(self.agents / "code-reviewer.md", "---\nname: 'reviewer'\n---\nbody")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("agents/code-reviewer.md: the project's own agent has a name quality-gates ships", out)

    def test_a_project_agent_whose_frontmatter_names_its_own_agent_passes(self):
        self.write(self.agents / "planner.md", "---\nname: planner\n---\nreviewer: mentioned in the body")
        self.assertEqual(self.sync()[0], 0)
        self.assertEqual(self.check()[0], 0)

    def test_sync_deletes_nothing_outside_the_agents_folder_whatever_the_shipped_list_says(self):
        self.sync()
        self.write(self.repo / "notes.md", "the repo's notes")
        self.write(self.agents / ".shipped-by-quality-gates", "implementer\nreviewer\n../../notes\n")
        self.assertEqual(self.sync()[0], 0)
        self.assertEqual((self.repo / "notes.md").read_text(), "the repo's notes")

    def test_broken_settings_json_stops_qg_skills_before_it_copies_anything(self):
        self.write(self.repo / ".claude" / "settings.json", "{oops")
        code, _ = self.sync()
        self.assertEqual(code, 2)
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.agents.exists())

    def assert_sync_stops_on(self, filename, text):
        self.write(self.agents / filename, text)
        code, out = self.sync()
        self.assertEqual(code, 2, out)
        self.assertIn(filename, out)
        self.assertEqual((self.agents / filename).read_text(), text)

    def test_sync_stops_on_a_project_agent_whose_filename_differs_from_a_shipped_one_only_in_case(self):
        self.assert_sync_stops_on("Reviewer.md", "the repo's own reviewer")

    def test_sync_stops_on_a_project_agent_with_an_upper_case_suffix(self):
        self.assert_sync_stops_on("reviewer.MD", "the repo's own reviewer")

    def test_a_frontmatter_name_with_an_inline_comment_still_counts_as_that_name(self):
        self.assert_sync_stops_on("code-reviewer.md", "---\nname: reviewer  # ours\n---\n")

    def test_a_frontmatter_name_after_a_byte_order_mark_still_counts(self):
        self.assert_sync_stops_on("code-reviewer.md", "\ufeff---\nname: reviewer\n---\n")

    def test_a_closing_fence_with_trailing_spaces_still_ends_the_frontmatter(self):
        self.assert_sync_stops_on("code-reviewer.md", "---\nname: reviewer\n---   \nbody\n")

    def test_an_indented_name_key_inside_another_mapping_is_not_the_agents_name(self):
        self.write(self.agents / "planner.md", "---\nowner:\n  name: reviewer\nname: planner\n---\n")
        self.assertEqual(self.sync()[0], 0)

    def test_check_names_a_clashing_file_once_even_when_it_claims_two_shipped_names(self):
        self.write(self.agents / "reviewer.md", "---\nname: implementer\n---\nours")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(out.count("agents/reviewer.md: the project's own agent"), 1)

    def test_an_unreadable_shipped_list_stops_qg_skills_with_exit_2_and_names_it(self):
        self.sync()
        (self.agents / ".shipped-by-quality-gates").write_bytes(b"\xff\xfe")
        for result in (self.sync(), self.check()):
            self.assertEqual(result[0], 2)
            self.assertIn(".shipped-by-quality-gates", result[1])

    def test_settings_json_of_the_wrong_shape_stops_qg_skills_before_it_copies_anything(self):
        for text in ('{"hooks": []}', '{"hooks": {"PreToolUse": {}}}', '{"hooks": {"PreToolUse": [{"hooks": [1]}]}}'):
            self.write(self.repo / ".claude" / "settings.json", text)
            code, out = self.sync()
            self.assertEqual(code, 2, text)
            self.assertIn("settings.json", out)
            self.assertFalse(self.dest.exists(), text)

    def test_the_package_ships_the_four_engineering_agents(self):
        self.assertEqual(project_files.agent_names(project_files.AGENTS_SOURCE),
                         ["debt-payer", "diagnoser", "implementer", "reviewer"])

    def in_folder(self, folder):
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        os.chdir(folder)

    def test_outside_a_git_repo_without_dest_it_exits_2_with_one_line_and_copies_nothing(self):
        self.in_folder(self.repo)
        for argv in ([], ["--check"]):
            code, out = run(argv, self.source, self.hooks, self.agents_source)
            self.assertEqual((code, out), (2, f"qg-skills: {project_files.NOT_A_GIT_REPO}\n"))
        self.assertFalse((self.repo / ".claude").exists())

    def test_from_a_subfolder_without_dest_it_copies_into_the_top_of_the_git_repo(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "src").mkdir()
        self.in_folder(self.repo / "src")
        code, _ = run([], self.source, self.hooks, self.agents_source)
        self.assertEqual(code, 0)
        self.assertTrue((self.repo / ".claude" / "skills" / "crap" / "SKILL.md").is_file())
        self.assertFalse((self.repo / "src" / ".claude").exists())

    def test_the_package_ships_every_skill_the_plugin_lists(self):
        names = skills_sync.skill_names(skills_sync.SHIPPED)
        self.assertEqual(names, ["cc-python", "cc-rust", "cc-swift", "cc-typescript", "codebase-design", "crap",
                                 "diagnosing-bugs", "domain-modeling", "grill-me", "grill-with-docs", "grilling", "handoff",
                                 "implement", "implement-spec", "improve-codebase-architecture",
                                 "no-comments", "pr", "prototype", "research", "retro", "review-against-spec",
                                 "setup-matt-pocock-skills", "setup-standards", "standards", "tdd",
                                 "to-spec", "to-tickets", "triage", "wait-what", "wayfinder", "wizard",
                                 "writing-for-agents"])

    def test_every_skill_copied_from_matt_pocock_carries_his_licence(self):
        copied = {Path(local).parts[3] for source in manifest.load_sources()
                  if source.repo == "mattpocock/skills"
                  for local in source.files.values() if "/skills/" in local}
        copied.discard("setup-standards")
        self.assertEqual(len(copied), 23)
        for name in copied:
            self.assertTrue((skills_sync.SHIPPED / name / "LICENSE-mattpocock").is_file(), name)

    def test_no_shipped_skill_hides_claude_codes_own_code_review(self):
        self.assertNotIn("code-review", skills_sync.skill_names(skills_sync.SHIPPED))


if __name__ == "__main__":
    unittest.main()
