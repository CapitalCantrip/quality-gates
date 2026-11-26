import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from quality_gates import agent_docs, project_files


class AgentDocs(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.templates = self.root / "templates"
        self.templates.mkdir()
        for name in ["issue-tracker-github.md", "issue-tracker-local.md", "triage-labels.md", "domain.md", "pull-request.md"]:
            (self.templates / name).write_text(f"{name} v1\n")
        (self.templates / "escaped.md").write_text("escaped.md v1 ({gates})\n")
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "CLAUDE.md").write_text("# Repo\n")
        self.docs = self.repo / "docs" / "agents"
        self.issue_templates = self.repo / ".github" / "ISSUE_TEMPLATE"
        self.escaped = self.issue_templates / "escaped.md"

    def run_tool(self, tracker="github"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stop:
            agent_docs.main(["--tracker", tracker, "--root", str(self.repo)], self.templates)
        self.assertEqual(stop.exception.code, 0)
        return out.getvalue()

    def choose(self, *components):
        choice = project_files.Choice(languages=("python",), chosen=components)
        (self.repo / "quality-gates.json").write_text(project_files.choice_text(choice))

    def run_tool_exit(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stop:
            agent_docs.main(["--tracker", "github", "--root", str(self.repo)], self.templates)
        return stop.exception.code, err.getvalue()

    def template(self, name, text):
        (self.templates / name).write_text(text)

    def test_a_first_run_writes_the_three_docs_from_the_chosen_trackers_templates(self):
        out = self.run_tool()
        self.assertEqual((self.docs / "issue-tracker.md").read_text(), "issue-tracker-github.md v1\n")
        self.assertEqual((self.docs / "triage-labels.md").read_text(), "triage-labels.md v1\n")
        self.assertEqual((self.docs / "domain.md").read_text(), "domain.md v1\n")
        self.assertIn("docs/agents/issue-tracker.md: created", out)

    def test_a_root_flag_works_from_a_working_folder_that_was_deleted(self):
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        gone = self.root / "gone"
        gone.mkdir()
        os.chdir(gone)
        gone.rmdir()
        self.assertIn("docs/agents/issue-tracker.md: created", self.run_tool())

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
        self.assertEqual(out.count("already in place"), 6)

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

    def test_a_first_run_writes_the_escaped_issue_template(self):
        out = self.run_tool()
        self.assertEqual(self.escaped.read_text(), "escaped.md v1 (none could)\n")
        self.assertIn(".github/ISSUE_TEMPLATE/escaped.md: created", out)

    def test_the_third_question_offers_the_projects_gates_and_none_could(self):
        self.choose("complexity-python", "crap", "no-comments", "no-comments-shell", "session-helpers")
        self.run_tool()
        self.assertEqual(self.escaped.read_text(), "escaped.md v1 (comment-debt, cc-check, crap, or none could)\n")

    def test_a_gate_with_no_command_of_its_own_is_offered_by_its_step_name_once(self):
        self.choose("complexity-swift", "complexity-rust")
        self.run_tool()
        self.assertEqual(self.escaped.read_text(), "escaped.md v1 (swiftlint, cargo-clippy, or none could)\n")

    def test_a_component_that_is_no_gate_adds_no_option(self):
        self.choose("design-helpers", "session-helpers")
        self.run_tool()
        self.assertEqual(self.escaped.read_text(), "escaped.md v1 (none could)\n")

    def test_a_chosen_component_this_release_does_not_know_adds_no_option(self):
        self.choose("complexity-python", "from-a-later-release")
        self.run_tool()
        self.assertEqual(self.escaped.read_text(), "escaped.md v1 (cc-check, or none could)\n")

    def test_an_unedited_template_follows_the_gates_the_project_gains(self):
        self.run_tool()
        self.choose("crap")
        out = self.run_tool()
        self.assertEqual(self.escaped.read_text(), "escaped.md v1 (crap, or none could)\n")
        self.assertIn("escaped.md: updated to the new template; you had not edited it", out)

    def test_an_edited_escaped_template_is_kept_when_the_gates_change(self):
        self.run_tool()
        self.escaped.write_text("our three questions\n")
        self.choose("crap")
        out = self.run_tool()
        self.assertEqual(self.escaped.read_text(), "our three questions\n")
        self.assertIn("escaped.md: customised by you", out)

    def test_an_escaped_template_written_before_this_tool_is_kept(self):
        self.issue_templates.mkdir(parents=True)
        self.escaped.write_text("hand written\n")
        out = self.run_tool()
        self.assertEqual(self.escaped.read_text(), "hand written\n")
        self.assertIn("no record of the template it started from", out)

    def test_a_template_whose_file_name_differs_only_in_case_is_kept_and_no_second_one_is_written(self):
        self.issue_templates.mkdir(parents=True)
        (self.issue_templates / "Escaped.md").write_text("hand written\n")
        out = self.run_tool()
        self.assertEqual(sorted(p.name for p in self.issue_templates.iterdir()), ["Escaped.md"])
        self.assertIn(".github/ISSUE_TEMPLATE/escaped.md: not written; .github/ISSUE_TEMPLATE/Escaped.md is already an escaped template", out)

    def test_a_template_in_another_file_that_names_itself_escaped_is_kept_and_no_second_one_is_written(self):
        self.issue_templates.mkdir(parents=True)
        for file_name, text in (("bug.md", "---\nname: 'Escaped'\nabout: ours\n---\n"),
                                ("form.yml", "\ufeffname: escaped\nbody: []\n")):
            with self.subTest(file_name):
                (self.issue_templates / file_name).write_text(text, encoding="utf-8")
                out = self.run_tool()
                self.assertFalse(self.escaped.exists())
                self.assertIn(f"not written; .github/ISSUE_TEMPLATE/{file_name} is already an escaped template", out)
                (self.issue_templates / file_name).unlink()

    def test_a_template_that_only_mentions_escaped_in_its_text_does_not_block_ours(self):
        self.issue_templates.mkdir(parents=True)
        (self.issue_templates / "bug.md").write_text("---\nname: bug\nabout: name: escaped\n---\nname: escaped\n")
        (self.issue_templates / "plain.md").write_text("name: escaped\n")
        self.run_tool()
        self.assertTrue(self.escaped.exists())

    def test_an_escaped_template_that_is_not_text_is_kept_and_reported(self):
        self.issue_templates.mkdir(parents=True)
        self.escaped.write_bytes(b"\xff\xfe\x00bad")
        out = self.run_tool()
        self.assertEqual(self.escaped.read_bytes(), b"\xff\xfe\x00bad")
        self.assertIn("escaped.md: not written; .github/ISSUE_TEMPLATE/escaped.md cannot be read as text", out)

    def test_a_record_of_the_template_that_is_not_text_stops_the_write_and_is_reported(self):
        self.run_tool()
        (self.docs / ".base" / "escaped.md").write_bytes(b"\xff\xfe\x00bad")
        self.choose("crap")
        out = self.run_tool()
        self.assertEqual(self.escaped.read_text(), "escaped.md v1 (none could)\n")
        self.assertIn("not written; docs/agents/.base/escaped.md cannot be read as text", out)

    def test_an_escaped_template_path_that_is_a_folder_is_reported_and_nothing_is_written_there(self):
        self.escaped.mkdir(parents=True)
        out = self.run_tool()
        self.assertEqual(list(self.escaped.iterdir()), [])
        self.assertIn("escaped.md: not written; .github/ISSUE_TEMPLATE/escaped.md is not a file", out)

    def test_an_issue_template_folder_that_is_a_file_is_reported_and_left_alone(self):
        (self.repo / ".github").mkdir()
        self.issue_templates.write_text("not a folder\n")
        out = self.run_tool()
        self.assertEqual(self.issue_templates.read_text(), "not a folder\n")
        self.assertIn("not written; .github/ISSUE_TEMPLATE is not a folder", out)

    def test_a_github_folder_that_links_outside_the_project_is_not_written_through(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.repo / ".github").symlink_to(outside, target_is_directory=True)
        out = self.run_tool()
        self.assertFalse((outside / "ISSUE_TEMPLATE").exists())
        self.assertIn("not written; .github leads outside the project", out)

    def test_an_unreadable_choice_file_stops_before_anything_is_written(self):
        (self.repo / "quality-gates.json").write_text("{not json")
        code, err = self.run_tool_exit()
        self.assertEqual(code, 3)
        self.assertIn("quality-gates.json: not valid JSON", err)
        self.assertEqual(sorted(p.name for p in self.repo.iterdir()), ["CLAUDE.md", "quality-gates.json"])

    def test_the_shipped_escaped_template_takes_the_projects_gates_in_its_third_heading(self):
        self.choose("complexity-python", "crap", "no-comments")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            agent_docs.main(["--tracker", "github", "--root", str(self.repo)])
        self.assertIn("\n## Which gate should have caught it (comment-debt, cc-check, crap, or none could)\n",
                      self.escaped.read_text())

    def test_the_shipped_escaped_template_asks_exactly_three_questions_in_front_matter_that_labels_it(self):
        text = (agent_docs.TEMPLATES / "escaped.md").read_text()
        self.assertTrue(text.startswith("---\nname: escaped\n"))
        self.assertIn("\nlabels: escaped\n", text)
        self.assertEqual([line for line in text.splitlines() if line.startswith("## ")], [
            "## What happened",
            "## How it was found (using the product, a review, a crash, other)",
            "## Which gate should have caught it ({gates})",
        ])


if __name__ == "__main__":
    unittest.main()
