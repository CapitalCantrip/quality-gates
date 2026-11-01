import ast
import builtins
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from quality_gates import agent_docs, languages, skills_sync, status
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
OS_LOOKUPS = {"os.walk", "os.scandir", "os.listdir", "os.getcwd"}
CWD_LOOKUP = "Path.cwd"
PATH_CALLS = {"glob", "rglob", "iterdir"}
GIT_LOOKUPS = ("rev-parse", "ls-files", "--show-toplevel")
ALLOWED = {
    ("references.read_rules", "glob"): "reads the package's own ADRs",
    ("references.skill_documents", "rglob"): "reads the package's own skills",
    ("references.write", "iterdir"): "tidies the package's own skill references",
    ("references.strays", "glob"): "reads the package's own skill references",
    ("skills_sync.skill_names", "iterdir"): "lists the shipped skills",
    ("skills_sync.files_under", "rglob"): "lists a shipped skill's files and its installed copy",
    ("quality_check.display_path", CWD_LOOKUP): "shows a path relative to where the command ran, not a root",
    ("stage_guard.main", "os.getcwd"): "the shipped hook runs alone in a project and cannot import the package",
}


def git_lookup(node):
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return None
    return next((word for word in GIT_LOOKUPS if word in node.value), None)


def import_names(node):
    if isinstance(node, ast.ImportFrom) and node.module:
        return {alias.asname or alias.name: f"{node.module}.{alias.name}" for alias in node.names}
    if isinstance(node, ast.Import):
        return {alias.asname: alias.name for alias in node.names if alias.asname}
    return {}


def imported_as(tree):
    return {name: full for node in ast.walk(tree) for name, full in import_names(node).items()}


def dotted_name(func):
    parts = []
    while isinstance(func, ast.Attribute):
        parts.insert(0, func.attr)
        func = func.value
    return ".".join([func.id, *parts]) if isinstance(func, ast.Name) else ""


def resolved(name, imports):
    head, dot, rest = name.partition(".")
    return imports.get(head, head) + dot + rest


def call_lookup(node, imports):
    if not isinstance(node, ast.Call):
        return None
    name = resolved(dotted_name(node.func), imports)
    if name in OS_LOOKUPS:
        return name
    if name.split(".")[-2:] == CWD_LOOKUP.split("."):
        return CWD_LOOKUP
    method = getattr(node.func, "attr", None)
    return method if method in PATH_CALLS else None


def lookups_in(tree):
    imports = imported_as(tree)
    for name, top in places(tree):
        for node in ast.walk(top):
            label = git_lookup(node) or call_lookup(node, imports)
            if label:
                yield name, node.lineno, label


def places(tree):
    for node in tree.body:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else "<module>"
        yield name, node


def root_lookups_and_walks(module_paths):
    found = {}
    for path in module_paths:
        for name, line, label in lookups_in(ast.parse(path.read_text(encoding="utf-8"))):
            found.setdefault((f"{path.stem}.{name}", label), line)
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
            "pathlib.Path.cwd()",
            "from os import walk\nwalk(root)",
            "from os import listdir as ls\nls(root)",
            "import os as o\no.scandir(root)",
            "from pathlib import Path as P\nP.cwd()",
        ]
        for source in sources:
            with self.subTest(source):
                self.assertTrue(any(lookups_in(ast.parse(source))))

    def test_the_check_ignores_walking_a_syntax_tree(self):
        for source in ("ast.walk(tree)", "from ast import walk\nwalk(tree)"):
            with self.subTest(source):
                self.assertFalse(any(lookups_in(ast.parse(source))))

    def test_an_allowed_place_is_allowed_only_the_lookup_it_lists(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "references.py"
            path.write_text("import os\n\ndef read_rules(adr_dir):\n    return adr_dir.glob('ADR-*.md'), os.walk(adr_dir)\n",
                            encoding="utf-8")
            found = root_lookups_and_walks([path])
        self.assertEqual({where for where in found if where not in ALLOWED}, {("references.read_rules", "os.walk")})

    def test_every_allowed_place_still_looks_up_or_walks_so_the_list_holds_no_dead_entry(self):
        self.assertEqual(set(ALLOWED) - set(root_lookups_and_walks(package_modules())), set())


KEPT_NAMES = {
    "CLAUDE.md", "AGENTS.md", "agents", "pull_request_template.md", ".github", "workflows",
    ".githooks", "pre-commit", ".claude", "settings.json", "comment-debt.json",
}


def names_kept_file(node):
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    text = node.value
    return not any(c.isspace() for c in text) and bool(KEPT_NAMES & set(text.split("/")))


def kept_file_names(module_paths):
    found = {}
    for path in module_paths:
        for name, top in places(ast.parse(path.read_text(encoding="utf-8"))):
            for node in ast.walk(top):
                if names_kept_file(node):
                    found.setdefault(f"{path.stem}.{name}", node.lineno)
    return found


class ProjectModuleOwnsTheKeptFiles(unittest.TestCase):
    def test_outside_the_project_module_no_code_names_a_file_quality_gates_keeps_in_a_project(self):
        outside = [path for path in package_modules() if path.stem != PROJECT_MODULE]
        self.assertEqual(kept_file_names(outside), {})

    def test_the_check_recognises_every_kept_file_however_its_path_is_spelled(self):
        sources = [
            'root / "CLAUDE.md"',
            'root / "AGENTS.md"',
            'Path("docs") / "agents"',
            '"docs/agents/domain.md"',
            'Path(".github") / "pull_request_template.md"',
            'root / ".github" / "workflows"',
            '".githooks/pre-commit"',
            'root / ".claude"',
            'claude_dir / "settings.json"',
            'Path(".claude") / "skills"',
            'root / "comment-debt.json"',
        ]
        for source in sources:
            with self.subTest(source):
                self.assertTrue(any(names_kept_file(node) for node in ast.walk(ast.parse(source))))

    def test_the_check_ignores_prose_that_mentions_a_kept_file(self):
        prose = '"Add the asking-rule line to CLAUDE.md. See `docs/agents/domain.md`."'
        self.assertFalse(any(names_kept_file(node) for node in ast.walk(ast.parse(prose))))


OPENS_ALLOWED = {
    "skills_sync.sync": "copies the shipped skills into the project's skills folder",
    "skills_sync.skill_differences": "compares the skill copies with the shipped skills",
}


COMPREHENSION_FRAMES = {"<listcomp>", "<setcomp>", "<dictcomp>", "<genexpr>"}


def package_caller():
    frame = sys._getframe(2)
    while frame is not None:
        path, name = Path(frame.f_code.co_filename), frame.f_code.co_name
        if PACKAGE in path.parents and name not in COMPREHENSION_FRAMES:
            return f"{path.stem}.{name}"
        frame = frame.f_back
    return None


@contextlib.contextmanager
def opens_inside(root):
    found = {}
    original = builtins.open

    def recording_open(file, *args, **kwargs):
        if isinstance(file, (str, os.PathLike)) and root in Path(os.path.abspath(file)).parents:
            found.setdefault(package_caller(), Path(file).relative_to(root).as_posix())
        return original(file, *args, **kwargs)

    with mock.patch("builtins.open", recording_open), mock.patch("io.open", recording_open):
        yield found


class ProjectModuleReadsAndWritesTheKeptFiles(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        (self.root / ".github" / "workflows").mkdir(parents=True)
        (self.root / ".github" / "workflows" / "ci.yml").write_text("run: crap --lang python\n")
        (self.root / ".githooks").mkdir()
        (self.root / ".githooks" / "pre-commit").write_text("comment-debt\n")
        (self.root / "pyproject.toml").write_text("[project]\n")
        (self.root / "a.py").write_text("x = 1\n")

    def run_commands(self):
        with contextlib.redirect_stdout(io.StringIO()):
            for command in (
                lambda: agent_docs.main(["--tracker", "github", "--root", str(self.root)]),
                lambda: skills_sync.main(["--dest", str(self.root / ".claude" / "skills")]),
                lambda: skills_sync.main(["--check", "--dest", str(self.root / ".claude" / "skills")]),
            ):
                with self.assertRaises(SystemExit):
                    command()
            status.main([], root=self.root)

    def test_outside_the_project_module_qg_agent_docs_qg_skills_and_qg_status_open_no_file_in_the_project(self):
        with opens_inside(self.root) as found:
            self.run_commands()
        self.assertEqual({caller: path for caller, path in found.items() if caller.split(".")[0] != PROJECT_MODULE and caller not in OPENS_ALLOWED}, {})

    def test_the_commands_do_open_the_kept_files_so_the_recording_sees_them(self):
        with opens_inside(self.root) as found:
            self.run_commands()
        self.assertTrue(any(caller.startswith(PROJECT_MODULE + ".") for caller in found))

    def test_every_allowed_opener_still_opens_a_file_in_the_project_so_the_list_holds_no_dead_entry(self):
        with opens_inside(self.root) as found:
            self.run_commands()
        self.assertEqual(set(OPENS_ALLOWED) - set(found), set())


if __name__ == "__main__":
    unittest.main()
