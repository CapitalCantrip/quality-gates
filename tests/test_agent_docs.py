import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from quality_gates import agent_docs


class AgentDocs(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.templates = self.root / "templates"
        self.templates.mkdir()
        for name in ["issue-tracker-github.md", "issue-tracker-local.md", "triage-labels.md", "domain.md", "pull-request.md"]:
            (self.templates / name).write_text(f"{name} v1\n")
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "CLAUDE.md").write_text("# Repo\n")
        self.docs = self.repo / "docs" / "agents"

    def run_tool(self, tracker="github"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stop:
            agent_docs.main(["--tracker", tracker, "--root", str(self.repo)], self.templates)
        self.assertEqual(stop.exception.code, 0)
        return out.getvalue()

    def template(self, name, text):
        (self.templates / name).write_text(text)

    def test_a_first_run_writes_the_three_docs_from_the_chosen_trackers_templates(self):
        out = self.run_tool()
        self.assertEqual((self.docs / "issue-tracker.md").read_text(), "issue-tracker-github.md v1\n")
        self.assertEqual((self.docs / "triage-labels.md").read_text(), "triage-labels.md v1\n")
        self.assertEqual((self.docs / "domain.md").read_text(), "domain.md v1\n")
        self.assertIn("docs/agents/issue-tracker.md: created", out)

    def test_a_local_tracker_gets_the_local_template_and_summary(self):
        self.run_tool("local")
        self.assertEqual((self.docs / "issue-tracker.md").read_text(), "issue-tracker-local.md v1\n")
        self.assertIn("Markdown files under `.scratch/`", (self.repo / "CLAUDE.md").read_text())

    def test_the_agent_skills_block_is_added_once(self):
        self.run_tool()
        self.run_tool()
        text = (self.repo / "CLAUDE.md").read_text()
        self.assertTrue(text.startswith("# Repo\n\n## Agent skills\n"))
        self.assertEqual(text.count("## Agent skills"), 1)
        self.assertIn("GitHub Issues on this repo, through the `gh` CLI. See `docs/agents/issue-tracker.md`.", text)

    def test_a_first_run_writes_the_pull_request_template(self):
        out = self.run_tool()
        self.assertEqual((self.repo / ".github" / "pull_request_template.md").read_text(), "pull-request.md v1\n")
        self.assertIn(".github/pull_request_template.md: created", out)

    def test_the_agent_skills_block_routes_pull_requests_to_the_pr_skill(self):
        self.run_tool()
        self.assertIn("### Pull requests\n\nWrite every PR body with the `pr` skill", (self.repo / "CLAUDE.md").read_text())

    def test_an_older_agent_skills_block_gains_the_pull_requests_section_once(self):
        (self.repo / "CLAUDE.md").write_text("# Repo\n\n## Agent skills\n\n### Issue tracker\n\nOurs.\n\n## Later\n")
        out = self.run_tool()
        self.run_tool()
        text = (self.repo / "CLAUDE.md").read_text()
        self.assertEqual(text.count("### Pull requests"), 1)
        self.assertLess(text.index("### Pull requests"), text.index("## Later"))
        self.assertIn("Ours.", text)
        self.assertIn("Agent skills block: pull requests section added", out)

    def test_the_shipped_pull_request_template_matches_the_pr_skill(self):
        skill = (agent_docs.TEMPLATES.parent / "skills" / "pr" / "SKILL.md").read_text()
        shipped = (agent_docs.TEMPLATES / "pull-request.md").read_text()
        body = skill.split("```markdown\n", 1)[1].split("```\n", 1)[0]
        self.assertTrue(shipped.endswith(body))

    def test_a_second_run_reports_everything_in_place_and_changes_nothing(self):
        self.run_tool()
        before = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()}
        out = self.run_tool()
        after = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(out.count("already in place"), 5)

    def test_an_unedited_doc_follows_a_template_upgrade(self):
        self.run_tool()
        self.template("domain.md", "domain.md v2\n")
        out = self.run_tool()
        self.assertEqual((self.docs / "domain.md").read_text(), "domain.md v2\n")
        self.assertIn("domain.md: updated to the new template; you had not edited it", out)

    def test_an_edited_doc_is_kept_and_the_templates_own_change_is_shown(self):
        self.run_tool()
        (self.docs / "domain.md").write_text("domain.md v1\nour rule\n")
        self.template("domain.md", "domain.md v2\n")
        out = self.run_tool()
        self.assertEqual((self.docs / "domain.md").read_text(), "domain.md v1\nour rule\n")
        self.assertIn("customised by you, and the template has changed since", out)
        self.assertIn("-domain.md v1\n+domain.md v2\n", out)
        self.assertNotIn("our rule", out)

    def test_an_edited_doc_with_an_unchanged_template_is_left_quietly(self):
        self.run_tool()
        (self.docs / "triage-labels.md").write_text("our labels\n")
        out = self.run_tool()
        self.assertEqual((self.docs / "triage-labels.md").read_text(), "our labels\n")
        self.assertIn("triage-labels.md: customised by you; the template has not changed", out)

    def test_a_doc_written_before_this_tool_is_kept_and_compared_with_the_template(self):
        self.docs.mkdir(parents=True)
        (self.docs / "domain.md").write_text("hand written\n")
        out = self.run_tool()
        self.assertEqual((self.docs / "domain.md").read_text(), "hand written\n")
        self.assertIn("no record of the template it started from", out)
        self.assertIn("-hand written\n+domain.md v1\n", out)

    def test_the_package_ships_a_template_for_every_tracker_it_offers(self):
        for tracker in agent_docs.TRACKER_SUMMARIES:
            for template in agent_docs.plan(tracker).values():
                self.assertTrue((agent_docs.TEMPLATES / template).is_file(), template)


if __name__ == "__main__":
    unittest.main()
