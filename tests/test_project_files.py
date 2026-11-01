import ast
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
    return {suffix for suffix in TYPESCRIPT_SUFFIXES if f"`{suffix}`" in paragraph}


class DocumentedSuffixes(unittest.TestCase):
    def test_a_paragraph_naming_two_or_more_typescript_suffixes_names_all_of_them(self):
        partial = [
            f"{path.relative_to(ROOT)}: {' '.join(paragraph.split())[:70]}"
            for path in DOCUMENTS
            for paragraph in paragraphs(path.read_text(encoding="utf-8"))
            if 2 <= len(suffixes_named(paragraph)) < len(TYPESCRIPT_SUFFIXES)
        ]
        self.assertEqual(partial, [])

    def test_the_crap_and_cc_python_skills_link_the_naming_rule_instead_of_restating_its_names(self):
        for skill in ("crap", "cc-python"):
            with self.subTest(skill):
                text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("](references/function-names.md)", text)
                for restated in ("K.Inner.deep", "outer.inner"):
                    self.assertNotIn(restated, text)


PACKAGE = ROOT / "src/quality_gates"
PROJECT_MODULE = "project_files"
OS_CALLS = {"walk", "scandir", "listdir", "getcwd"}
PATH_CALLS = {"glob", "rglob", "iterdir"}
GIT_LOOKUPS = ("rev-parse", "ls-files", "--show-toplevel")
ALLOWED = {
    "references.read_rules": "reads the package's own ADRs",
    "references.skill_documents": "reads the package's own skills",
    "references.write": "tidies the package's own skill references",
    "references.strays": "reads the package's own skill references",
    "skills_sync.skill_names": "lists the shipped skills",
    "skills_sync.files_under": "lists a shipped skill's files and its installed copy",
    "quality_check.display_path": "shows a path relative to where the command ran, not a root",
    "stage_guard.main": "the shipped hook runs alone in a project and cannot import the package",
}


def asks_git(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and any(w in node.value for w in GIT_LOOKUPS)


def is_lookup_call(owner, name):
    if owner == "os":
        return name in OS_CALLS
    return name in PATH_CALLS or (owner, name) == ("Path", "cwd")


def is_root_or_walk(node):
    if asks_git(node):
        return True
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    owner = node.func.value.id if isinstance(node.func.value, ast.Name) else None
    return is_lookup_call(owner, node.func.attr)


def places(tree):
    for node in tree.body:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else "<module>"
        yield name, node


def root_lookups_and_walks(module_paths):
    found = {}
    for path in module_paths:
        for name, top in places(ast.parse(path.read_text(encoding="utf-8"))):
            for node in ast.walk(top):
                if is_root_or_walk(node):
                    found.setdefault(f"{path.stem}.{name}", node.lineno)
    return found


def package_modules():
    return sorted(PACKAGE.rglob("*.py"))


class ProjectModuleOwnsTheRootAndTheWalks(unittest.TestCase):
    def test_outside_the_project_module_no_code_asks_git_for_the_root_lists_tracked_files_or_walks_the_project(self):
        outside = [path for path in package_modules() if path.stem != PROJECT_MODULE]
        found = root_lookups_and_walks(outside)
        self.assertEqual({where: line for where, line in found.items() if where not in ALLOWED}, {})

    def test_the_check_recognises_every_kind_of_root_lookup_and_walk(self):
        sources = [
            'run(["git", "rev-parse", "--show-toplevel"])',
            'run(["git", "ls-files", "*.py"])',
            "os.walk(root)",
            "os.listdir(root)",
            "os.getcwd()",
            "Path.cwd()",
            "root.rglob('*')",
            "root.glob('*.py')",
            "root.iterdir()",
        ]
        for source in sources:
            with self.subTest(source):
                self.assertTrue(any(is_root_or_walk(node) for node in ast.walk(ast.parse(source))))

    def test_the_check_ignores_walking_a_syntax_tree(self):
        self.assertFalse(any(is_root_or_walk(node) for node in ast.walk(ast.parse("ast.walk(tree)"))))

    def test_every_allowed_place_still_looks_up_or_walks_so_the_list_holds_no_dead_entry(self):
        self.assertEqual(set(ALLOWED) - set(root_lookups_and_walks(package_modules())), set())


if __name__ == "__main__":
    unittest.main()
