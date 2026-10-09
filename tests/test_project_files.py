import json
import re
import tempfile
import unittest
from pathlib import Path

from quality_gates import languages
from quality_gates import project_files as pf


class ProjectFiles(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.claude = self.root / ".claude"
        self.hooks = self.root / "shipped-hooks"
        self.hooks.mkdir()
        (self.hooks / "stage_guard.py").write_text("guard v1\n")

    def differences(self):
        return pf.differences(self.claude, self.root, self.hooks)

    def sync(self):
        pf.sync(self.claude, self.root, self.hooks)

    def settings(self):
        return json.loads((self.claude / "settings.json").read_text())

    def test_a_bare_project_lacks_the_guard_its_registration_and_the_asking_line(self):
        self.assertEqual(self.differences(), [
            "hooks/stage_guard.py: missing",
            "settings.json: the stage guard is not registered as a PreToolUse hook",
            "CLAUDE.md: the asking-rule line is missing or out of date",
        ])

    def test_after_a_sync_nothing_differs(self):
        self.sync()
        self.assertEqual(self.differences(), [])

    def test_a_second_sync_changes_nothing(self):
        self.sync()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.sync()
        after = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_the_copied_guard_is_executable(self):
        self.sync()
        self.assertTrue((self.claude / "hooks" / "stage_guard.py").stat().st_mode & 0o100)

    def test_an_edited_guard_differs_and_a_sync_restores_it(self):
        self.sync()
        (self.claude / "hooks" / "stage_guard.py").write_text("weakened\n")
        self.assertEqual(self.differences(), ["hooks/stage_guard.py: differs"])
        self.sync()
        self.assertEqual((self.claude / "hooks" / "stage_guard.py").read_text(), "guard v1\n")

    def test_registration_keeps_the_projects_other_settings_and_hooks(self):
        self.claude.mkdir()
        existing = {"model": "x", "hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "lint"}]}],
                                            "SessionStart": [{"hooks": [{"type": "command", "command": "setup"}]}]}}
        (self.claude / "settings.json").write_text(json.dumps(existing))
        self.sync()
        settings = self.settings()
        self.assertEqual(settings["model"], "x")
        self.assertEqual(settings["hooks"]["SessionStart"], existing["hooks"]["SessionStart"])
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "lint")
        self.assertEqual(settings["hooks"]["PreToolUse"][1], {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/stage_guard.py"'}],
        })

    def test_a_guard_registered_by_hand_is_not_registered_twice(self):
        self.claude.mkdir()
        mine = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "python3 .claude/hooks/stage_guard.py"}]}]}}
        (self.claude / "settings.json").write_text(json.dumps(mine))
        self.sync()
        self.assertEqual(self.settings(), mine)

    def test_invalid_settings_json_is_reported_and_left_untouched(self):
        self.claude.mkdir()
        (self.claude / "settings.json").write_text("{not json")
        with self.assertRaises(pf.SettingsError):
            self.sync()
        self.assertEqual((self.claude / "settings.json").read_text(), "{not json")

    def test_settings_that_are_not_an_object_are_reported(self):
        self.claude.mkdir()
        (self.claude / "settings.json").write_text("[]")
        with self.assertRaises(pf.SettingsError):
            self.differences()

    def test_the_asking_line_is_appended_to_an_existing_claude_md(self):
        (self.root / "CLAUDE.md").write_text("# Project\n\nRules.\n")
        self.sync()
        self.assertEqual((self.root / "CLAUDE.md").read_text(), "# Project\n\nRules.\n\n" + pf.ASKING_LINE + "\n")

    def test_an_older_wording_of_the_asking_line_is_replaced_in_place(self):
        (self.root / "CLAUDE.md").write_text("# P\n\n**Asking the builder:** old words.\n\n## More\n")
        self.sync()
        self.assertEqual((self.root / "CLAUDE.md").read_text(), "# P\n\n" + pf.ASKING_LINE + "\n\n## More\n")

    def test_agents_md_is_used_when_there_is_no_claude_md(self):
        (self.root / "AGENTS.md").write_text("# Agents\n")
        self.sync()
        self.assertIn(pf.ASKING_LINE, (self.root / "AGENTS.md").read_text())
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_claude_md_is_created_when_the_project_has_neither_file(self):
        self.sync()
        self.assertEqual((self.root / "CLAUDE.md").read_text(), pf.ASKING_LINE + "\n")


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "src/quality_gates/skills"
DOCUMENTS = [ROOT / "README.md", ROOT / "docs/adr/ADR-001-complexity-standards.md", *sorted(SKILLS.rglob("*.md"))]
TYPESCRIPT_SUFFIXES = languages.LANGUAGES["typescript"].suffixes


def paragraphs(text):
    return [paragraph for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def suffixes_named(paragraph):
    return {suffix for suffix in TYPESCRIPT_SUFFIXES if re.search(re.escape(suffix) + r"\b", paragraph)}


class DocumentedSuffixes(unittest.TestCase):
    def test_a_paragraph_naming_two_or_more_typescript_suffixes_names_all_of_them(self):
        partial = [
            f"{path.relative_to(ROOT)}: {' '.join(paragraph.split())[:70]}"
            for path in DOCUMENTS
            for paragraph in paragraphs(path.read_text(encoding="utf-8"))
            if 2 <= len(suffixes_named(paragraph)) < len(TYPESCRIPT_SUFFIXES)
        ]
        self.assertEqual(partial, [])

    def test_the_crap_and_cc_python_skills_cite_adr_001_instead_of_restating_its_names(self):
        for skill in ("crap", "cc-python"):
            with self.subTest(skill):
                text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("ADR-001", text)
                for restated in ("K.Inner.deep", "outer.inner", "#2"):
                    self.assertNotIn(restated, text)


if __name__ == "__main__":
    unittest.main()
