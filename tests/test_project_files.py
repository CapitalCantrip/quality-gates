import ast
import builtins
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from quality_gates import agent_docs, languages, skills_sync, status
from quality_gates import project_files as pf
from quality_gates.errors import ToolError
from quality_gates.manifest import ManifestError


def git_repo(folder):
    subprocess.run(["git", "init", "-q", str(folder)], check=True)
    return Path(folder).resolve()


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
        self.root = git_repo(tempfile.mkdtemp())
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


CONVENTIONS_DOC = ROOT / "docs" / "recognised-conventions.md"


def recorded_convention_ids():
    return re.findall(r"^\*\*Id\.\*\* `([a-z0-9-]+)`\.$", CONVENTIONS_DOC.read_text(encoding="utf-8"), re.MULTILINE)


class ChoiceFile(unittest.TestCase):
    def setUp(self):
        self.root = git_repo(tempfile.mkdtemp())

    def write(self, data):
        (self.root / pf.CHOICE_FILE).write_text(json.dumps(data), encoding="utf-8")

    def valid(self, **changes):
        data = {"format_version": 1, "languages": ["python"], "exclude": ["tests/fixtures/"],
                "components": {"chosen": ["crap"], "declined": ["design-helpers"]}, "commit_time_limit_seconds": 2,
                "settings": {"no-comments": {"exclude": ["gen/"], "conventions": []}}}
        data.update(changes)
        return data

    def broken(self, data):
        self.write(data)
        with self.assertRaises(ManifestError) as raised:
            pf.read_choice(self.root)
        return str(raised.exception)

    def test_a_project_without_a_choice_file_has_no_choice(self):
        self.assertIsNone(pf.read_choice(self.root))

    def test_a_choice_file_is_read_into_its_record(self):
        self.write(self.valid())
        self.assertEqual(pf.read_choice(self.root), pf.Choice(
            languages=("python",), chosen=("crap",), declined=("design-helpers",), exclude=("tests/fixtures/",),
            commit_time_limit_seconds=2, comment_exclude=("gen/",), conventions=()))

    def test_a_written_choice_reads_back_the_same_and_ends_in_a_newline(self):
        choice = pf.Choice(languages=("python", "shell"), chosen=("crap",), exclude=("tests/fixtures/",),
                           comment_exclude=("gen/",), conventions=("rust-safety",))
        pf.write_kept(self.root, pf.CHOICE_FILE, pf.choice_text(choice))
        self.assertEqual(pf.read_choice(self.root), choice)
        self.assertTrue((self.root / pf.CHOICE_FILE).read_text(encoding="utf-8").endswith("}\n"))

    def test_a_new_choice_defaults_to_a_two_second_commit_limit_and_empty_comment_gate_settings(self):
        choice = pf.Choice(languages=("python",))
        self.assertEqual((choice.commit_time_limit_seconds, choice.comment_exclude, choice.conventions), (2, (), ()))
        self.assertEqual(json.loads(pf.choice_text(choice))["settings"], {"no-comments": {"exclude": [], "conventions": []}})

    def test_a_language_the_registry_does_not_know_is_refused(self):
        self.assertIn("unknown language 'cobol'", self.broken(self.valid(languages=["python", "cobol"])))

    def test_rust_and_shell_can_be_recorded(self):
        self.write(self.valid(languages=["rust", "shell"]))
        self.assertEqual(pf.read_choice(self.root).languages, ("rust", "shell"))

    def test_a_convention_id_the_conventions_page_does_not_record_is_refused(self):
        settings = {"no-comments": {"exclude": [], "conventions": ["todo-markers"]}}
        self.assertIn("unknown convention 'todo-markers'", self.broken(self.valid(settings=settings)))

    def test_the_conventions_a_choice_file_accepts_are_exactly_those_the_conventions_page_records(self):
        self.assertEqual(sorted(pf.RECOGNISED_CONVENTIONS), sorted(recorded_convention_ids()))
        self.assertIn("rust-safety", pf.RECOGNISED_CONVENTIONS)

    def test_a_missing_field_is_named(self):
        data = self.valid()
        del data["languages"]
        self.assertIn("missing field 'languages'", self.broken(data))

    def test_a_format_version_this_release_cannot_read_is_refused(self):
        self.assertIn("format_version", self.broken(self.valid(format_version=2)))

    def test_a_component_both_chosen_and_declined_is_refused(self):
        components = {"chosen": ["crap"], "declined": ["crap"]}
        self.assertIn("'crap' is both chosen and declined", self.broken(self.valid(components=components)))

    def test_a_commit_time_limit_that_is_not_a_positive_number_is_refused(self):
        for limit in (0, -1, "2", True):
            with self.subTest(limit):
                self.assertIn("commit_time_limit_seconds", self.broken(self.valid(commit_time_limit_seconds=limit)))

    def test_settings_for_a_component_that_has_none_are_refused(self):
        self.assertIn("unknown settings 'crap'", self.broken(self.valid(settings={"crap": {}})))

    def test_a_file_that_is_not_json_names_the_file(self):
        (self.root / pf.CHOICE_FILE).write_text("{", encoding="utf-8")
        with self.assertRaises(ManifestError) as raised:
            pf.read_choice(self.root)
        self.assertIn(pf.CHOICE_FILE, str(raised.exception))


class OneRootFinder(unittest.TestCase):
    def test_inside_a_git_repo_the_root_is_the_top_of_the_repo_wherever_the_command_runs(self):
        repo = git_repo(tempfile.mkdtemp())
        (repo / "src").mkdir()
        self.assertEqual(pf.git_root(repo / "src"), repo)

    def test_outside_a_git_repo_finding_the_root_fails_with_a_message_naming_git(self):
        folder = Path(tempfile.mkdtemp())
        with self.assertRaises(ToolError) as raised:
            pf.git_root(folder)
        self.assertEqual(str(raised.exception), pf.NOT_A_GIT_REPO)
        self.assertIn("git init", pf.NOT_A_GIT_REPO)

    def test_outside_a_git_repo_every_command_exits_2_with_the_one_message_and_no_traceback(self):
        from quality_gates import comment_debt, crap, quality_check
        commands = {
            "qg status": lambda: status.main([]),
            "comment-debt": lambda: comment_debt.main([], out=sys.stderr),
            "cc-check": lambda: quality_check.main(["."]),
            "crap": lambda: crap.main(["--lang", "python", "."]),
            "qg-agent-docs": lambda: agent_docs.main(["--tracker", "github"]),
        }
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        os.chdir(tempfile.mkdtemp())
        for name, command in commands.items():
            with self.subTest(name):
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    try:
                        code = command()
                    except SystemExit as stop:
                        code = stop.code
                self.assertEqual(code, 2)
                self.assertIn(pf.NOT_A_GIT_REPO, err.getvalue())

    def test_the_project_module_has_one_root_finder_and_no_current_folder_fallback(self):
        self.assertFalse(hasattr(pf, "git_root_or_current_folder"))
        self.assertFalse(hasattr(pf, "current_folder"))


if __name__ == "__main__":
    unittest.main()
