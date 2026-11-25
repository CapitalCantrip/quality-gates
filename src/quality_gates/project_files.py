import filecmp
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from quality_gates import languages
from quality_gates.errors import ToolError
from quality_gates.manifest import BrokenFileError, fail_unless, known, known_languages, read_json, require, unique

HOOKS_SOURCE = Path(__file__).parent / "hooks"
AGENTS_SOURCE = Path(__file__).parent / "agents"
AGENT_SUFFIX = ".md"
SHIPPED_AGENTS_LIST = ".shipped-by-quality-gates"
OWN_AGENT = "the project's own agent has a name quality-gates ships"
NO_LONGER_SHIPPED = "not shipped"
AGENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
FRONTMATTER_FENCE = "---"
FRONTMATTER_NAME = re.compile(r"name:\s*(?P<value>.*?)\s*(?:\s#.*)?$")
TEXT_WITH_BOM = "utf-8-sig"
STAGE_GUARD = "stage_guard.py"
STAGE_GUARD_COMMAND = 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/stage_guard.py"'
INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md")
ASKING_PREFIX = "**Asking the builder:**"
ASKING_LINE = (
    ASKING_PREFIX + " ask when uncertain about anything irreversible, outward-facing or large "
    "in scope, and proceed on reversible work with a stated default. Every question gives what "
    "is at stake in plain words, two or three options with only the pros and cons the builder "
    "would notice, and a recommendation with its reason (`standards` skill, *ask the builder*)."
)
GIT_ROOT = ("git", "rev-parse", "--show-toplevel")
FILES_GIT_WOULD_COMMIT = ("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard")
COMMIT_OF = ("git", "rev-parse", "--verify", "--quiet", "--end-of-options")
AS_A_COMMIT = "^{commit}"
BLOB_AT = ("git", "cat-file", "blob")
DEFAULT_BRANCHES = (
    "refs/remotes/origin/HEAD", "refs/heads/main", "refs/heads/master", "refs/remotes/origin/main",
    "refs/remotes/origin/master",
)
NOT_A_GIT_REPO = (
    "not inside a git repository: quality-gates looks at the files git would commit, so run it inside the "
    "project's repository, or run `git init` there first"
)
ALREADY_SCANNED = " (already scanned)"
A_SUBMODULE = " (a submodule: scan it from inside)"
FOLDERS_SKIPPED_OUTSIDE_THE_REPO = frozenset({
    ".git", ".venv", "venv", ".direnv", "node_modules", "__pycache__", "backups", "build", ".build", "dist",
    ".tox", ".mypy_cache", ".pytest_cache", ".worktrees",
})
IGNORED_NOTE = "Skipped {}: git ignores it, and quality-gates scores only the files git would commit"
WORKFLOW_SUFFIXES = (".yml", ".yaml")
WORKFLOWS = Path(".github") / "workflows"
CLAUDE_DIR = ".claude"
SKILLS_DEST = Path(CLAUDE_DIR) / "skills"
COPIED_HOOKS = "hooks"
COPIED_AGENTS = "agents"
SETTINGS = "settings.json"
PRE_COMMIT_HOOK = ".githooks/pre-commit"
PIN_FILE = "pyproject.toml"
AGENT_DOCS = Path("docs") / "agents"
TEMPLATE_BASES = AGENT_DOCS / ".base"
ISSUE_TRACKER_DOC = AGENT_DOCS / "issue-tracker.md"
TRIAGE_LABELS_DOC = AGENT_DOCS / "triage-labels.md"
DOMAIN_DOC = AGENT_DOCS / "domain.md"
PR_TEMPLATE = Path(".github") / "pull_request_template.md"
COMMENT_DEBT_BASELINE = "comment-debt.json"
CC_BASELINE = "cc-baseline.json"
CRAP_BASELINE = "crap-baseline.json"
SILENCER_BASELINE = "silencer-baseline.json"
BASELINES = (CC_BASELINE, CRAP_BASELINE, COMMENT_DEBT_BASELINE, SILENCER_BASELINE)
CHOICE_FILE = "quality-gates.json"
CHOICE_FORMAT_VERSION = 1
CHOICE_REQUIRED = ("format_version", "languages", "exclude", "components", "commit_time_limit_seconds", "settings")
COMPONENTS_REQUIRED = ("chosen", "declined")
COMMENT_GATE = "no-comments"
COMMENT_GATE_REQUIRED = ("exclude", "conventions")
ON_WITHOUT_A_CHOICE_FILE = frozenset({COMMENT_GATE})
RECOGNISED_CONVENTIONS = frozenset({"rust-safety"})
DEFAULT_COMMIT_TIME_LIMIT_SECONDS = 2
KEPT_BY_QUALITY_GATES = (".claude/skills/", ".claude/hooks/", PRE_COMMIT_HOOK)
FIXTURE_FOLDERS = ("fixtures", "fixture", "__fixtures__", "testdata")
FIRST_LINE_BYTES = 256
WILL_CREATE = "will be created"
WILL_CHANGE = "will change"
UNCHANGED = "unchanged"
CHOSEN, DECLINED, UNLISTED = "chosen", "declined", "unlisted"
FILES_SHOWN = 3
COMMENT_GATE_COMMAND = "comment-debt"
EXCLUDE_FLAG = "--exclude"
COMMAND_SEPARATORS = frozenset({"&&", "||", "|", ";"})
GATE_COMMANDS = (COMMENT_GATE_COMMAND, "cc-check", "crap")
ON_PULL_REQUESTS = re.compile(r"(?<![\w-])pull_request(?![\w-])")
STEP_START = re.compile(r"([ \t]*)- ")
CI_BEGIN = "# quality-gates: begin"
CI_END = "# quality-gates: end"
TOLERATED_STEP = (
    "- name: qg tolerated",
    "  if: github.event_name == 'pull_request'",
    "  env:",
    "    BASE: ${{ github.base_ref }}",
    "  run: |",
    '    git fetch --no-tags --depth=1 origin "+refs/heads/${BASE}:refs/remotes/origin/${BASE}"',
    '    qg tolerated --against "origin/${BASE}"',
)
BROKEN_MARKERS = f"{{}}: quality-gates' markers are broken: keep one `{CI_BEGIN}` line and, below it, one `{CI_END}` line"
CRLF, LF = "\r\n", "\n"
CONTINUATION = "\\"
UNSHIPPED, MISSING, DIFFERS, SAME = "unshipped", "missing", "differs", "same"
READABLE, UNREADABLE = "readable", "unreadable"


class SettingsError(Exception):
    pass


class UnreadableAgentList(Exception):
    pass


def hook_names(source=HOOKS_SOURCE):
    return sorted(p.name for p in source.glob("*.py"))


def copied_file(shipped, copy):
    if not shipped.is_file():
        return UNSHIPPED
    if not copy.is_file():
        return MISSING
    return SAME if filecmp.cmp(shipped, copy, shallow=False) else DIFFERS


def copied_hook(dest, name, source=HOOKS_SOURCE):
    return copied_file(source / name, dest / name)


def hook_differences(dest, source=HOOKS_SOURCE):
    found = []
    for name in hook_names(source):
        state = copied_hook(dest, name, source)
        if state != SAME:
            found.append(f"hooks/{name}: {state}")
    return found


def sync_hooks(dest, source=HOOKS_SOURCE):
    dest.mkdir(parents=True, exist_ok=True)
    for name in hook_names(source):
        shutil.copyfile(source / name, dest / name)
        (dest / name).chmod(0o755)


def agent_names(source=AGENTS_SOURCE):
    return sorted(p.stem for p in source.glob(f"*{AGENT_SUFFIX}") if p.is_file())


def agent_file(folder, name):
    return folder / f"{name}{AGENT_SUFFIX}"


def shipped_agents(dest):
    path = dest / SHIPPED_AGENTS_LIST
    if not path.is_file():
        return set()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise UnreadableAgentList(f"{path} cannot be read ({error}); delete it, then rerun qg-skills") from error
    return {name for name in text.split() if AGENT_NAME.fullmatch(name)}


def frontmatter_lines(path):
    try:
        lines = path.read_text(encoding=TEXT_WITH_BOM).splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        return []
    for end, line in enumerate(lines[1:], 1):
        if line.strip() == FRONTMATTER_FENCE:
            return lines[1:end]
    return []


def declared_agent_name(path):
    for line in frontmatter_lines(path):
        found = FRONTMATTER_NAME.match(line)
        if found:
            return found.group("value").strip("\"'").lower()
    return None


def agent_files_in(dest):
    if not dest.is_dir():
        return []
    return sorted(p for p in dest.iterdir() if p.suffix.lower() == AGENT_SUFFIX and p.is_file())


def same_bytes(a, b):
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def claims_shipped_name(path, name, source):
    return path.name != agent_file(Path(), name).name or not same_bytes(path, agent_file(source, name))


def clashes_in(dest, source, listed, names):
    found = []
    for path in agent_files_in(dest):
        if path.name not in {agent_file(Path(), name).name for name in listed}:
            claimed = sorted({path.stem.lower(), declared_agent_name(path)} & names)
            found += [(path, name) for name in claimed if claims_shipped_name(path, name, source)]
    return found


@dataclass(frozen=True)
class AgentSurvey:
    states: dict
    clashes: tuple
    stale: tuple

    @property
    def clashing_files(self):
        return sorted({path for path, _ in self.clashes})


def survey_agents(dest, source=AGENTS_SOURCE):
    listed, names = shipped_agents(dest), agent_names(source)
    clashes = tuple(clashes_in(dest, source, listed, set(names)))
    claimed = {name for _, name in clashes}
    states = {name: OWN_AGENT if name in claimed else copied_agent(dest, name, source) for name in names}
    stale = tuple(name for name in sorted(listed - set(names)) if agent_file(dest, name).is_file())
    return AgentSurvey(states, clashes, stale)


def copied_agent(dest, name, source=AGENTS_SOURCE):
    return copied_file(agent_file(source, name), agent_file(dest, name))


def agent_differences(dest, source=AGENTS_SOURCE):
    survey = survey_agents(dest, source)
    found = [(agent_file(Path(), name).name, state) for name, state in survey.states.items()
             if state not in (SAME, OWN_AGENT)]
    found += [(path.name, OWN_AGENT) for path in survey.clashing_files]
    found += [(agent_file(Path(), name).name, NO_LONGER_SHIPPED) for name in survey.stale]
    return [f"{COPIED_AGENTS}/{name}: {state}" for name, state in found]


def refuse_agent_clashes(dest, source=AGENTS_SOURCE):
    clashes = survey_agents(dest, source).clashing_files
    if clashes:
        raise ToolError(f"{', '.join(str(path) for path in clashes)}: the project's own agent, not one quality-gates "
                        f"installed, has the name of an agent quality-gates ships. Nothing was changed. "
                        f"Rename it, or remove it, then rerun qg-skills.")


def check_before_install(claude_folder, agents_source=AGENTS_SOURCE):
    stage_guard_registered(settings_file(claude_folder))
    refuse_agent_clashes(agents_dir(claude_folder), agents_source)


def sync_agents(dest, source=AGENTS_SOURCE):
    names = agent_names(source)
    for name in sorted(shipped_agents(dest) - set(names)):
        agent_file(dest, name).unlink(missing_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copyfile(agent_file(source, name), agent_file(dest, name))
    (dest / SHIPPED_AGENTS_LIST).write_text("".join(f"{name}\n" for name in names), encoding="utf-8")
    return names


def read_settings(path):
    if not path.is_file():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SettingsError(f"{path} is not valid JSON ({error}); fix it, then run qg-skills again")
    if not isinstance(settings, dict):
        raise SettingsError(f"{path} must hold a JSON object")
    problem = hook_shape_problem(settings)
    if problem:
        raise SettingsError(f"{path}: {problem}; fix it, then run qg-skills again")
    return settings


def objects_list(value):
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def hook_shape_problem(settings):
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return "`hooks` must be a JSON object"
    entries = hooks.get("PreToolUse", [])
    if not objects_list(entries):
        return "`hooks.PreToolUse` must be a list of objects"
    if not all(objects_list(entry.get("hooks", [])) for entry in entries):
        return "each `hooks.PreToolUse` entry's `hooks` must be a list of objects"
    return None


def registered_commands(settings):
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        for hook in entry.get("hooks", []):
            command = hook.get("command", "")
            if isinstance(command, str):
                yield command


def stage_guard_registered(path):
    return any(STAGE_GUARD in command for command in registered_commands(read_settings(path)))


def register_stage_guard(path):
    settings = read_settings(path)
    if any(STAGE_GUARD in command for command in registered_commands(settings)):
        return False
    entry = {"matcher": "Bash", "hooks": [{"type": "command", "command": STAGE_GUARD_COMMAND}]}
    settings.setdefault("hooks", {}).setdefault("PreToolUse", []).append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return True


def instruction_file(root):
    for name in INSTRUCTION_FILES:
        if (root / name).is_file():
            return root / name
    return root / INSTRUCTION_FILES[0]


def has_asking_line(root):
    path = instruction_file(root)
    return path.is_file() and ASKING_LINE in path.read_text(encoding="utf-8").splitlines()


def with_asking_line(text):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(ASKING_PREFIX):
            lines[index] = ASKING_LINE
            return "\n".join(lines) + "\n"
    body = text.rstrip("\n")
    return (body + "\n\n" if body else "") + ASKING_LINE + "\n"


def add_asking_line(root):
    path = instruction_file(root)
    if has_asking_line(root):
        return None
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    path.write_text(with_asking_line(text), encoding="utf-8")
    return path


def claude_dir(root):
    return root / CLAUDE_DIR


def skills_dir(root):
    return claude_dir(root) / SKILLS_DEST.name


def hooks_dir(claude_folder):
    return claude_folder / COPIED_HOOKS


def agents_dir(claude_folder):
    return claude_folder / COPIED_AGENTS


def settings_file(claude_folder):
    return claude_folder / SETTINGS


def comment_debt_baseline(root):
    return root / COMMENT_DEBT_BASELINE


def silencer_baseline(root):
    return root / SILENCER_BASELINE


def baseline_files(root):
    return [root / name for name in BASELINES]


def template_base(name):
    return TEMPLATE_BASES / name.name


def read_kept(root, name):
    path = root / name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def write_kept(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_instruction_file(root):
    return read_kept(root, instruction_file(root).name)


def write_instruction_file(root, text):
    write_kept(root, instruction_file(root).name, text)


def file_state(root, name):
    path = root / name
    if not path.exists():
        return MISSING
    return READABLE if path.is_file() and os.access(path, os.R_OK) else UNREADABLE


def each_text(paths):
    for path in paths:
        try:
            yield path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            yield None


def readable_texts(paths):
    return list(each_text(paths))


def ci_texts(root, found_in=None):
    if found_in is None:
        return readable_texts(workflow_files(root))
    path = root / found_in
    return readable_texts([path] if path.is_file() else [])


def pre_commit_texts(root):
    return ci_texts(root, PRE_COMMIT_HOOK)


def pin_paths(root):
    yield root / PIN_FILE
    yield from workflow_files(root)


def pin_texts(root):
    return (text for text in each_text(pin_paths(root)) if text is not None)


def differences(claude_dir, root, source=HOOKS_SOURCE):
    found = hook_differences(hooks_dir(claude_dir), source)
    if not stage_guard_registered(settings_file(claude_dir)):
        found.append("settings.json: the stage guard is not registered as a PreToolUse hook")
    if not has_asking_line(root):
        found.append(f"{instruction_file(root).name}: the asking-rule line is missing or out of date")
    return found


def sync(claude_dir, root, source=HOOKS_SOURCE):
    sync_hooks(hooks_dir(claude_dir), source)
    register_stage_guard(settings_file(claude_dir))
    add_asking_line(root)


def git_root(start=None):
    found = subprocess.run(list(GIT_ROOT), cwd=start, capture_output=True, text=True)
    if found.returncode != 0 or not found.stdout.strip():
        raise ToolError(NOT_A_GIT_REPO)
    return Path(found.stdout.strip())


def commit_of(root, ref):
    found = subprocess.run([*COMMIT_OF, ref + AS_A_COMMIT], cwd=root, capture_output=True, text=True)
    return found.stdout.strip() if found.returncode == 0 and found.stdout.strip() else None


def default_branch(root):
    return next((ref for ref in DEFAULT_BRANCHES if commit_of(root, ref) is not None), None)


def copy_at(root, ref, name):
    commit = commit_of(root, ref)
    if commit is None:
        return None
    found = subprocess.run([*BLOB_AT, f"{commit}:{Path(name).as_posix()}"], cwd=root, capture_output=True)
    return found.stdout if found.returncode == 0 else None


def main_copy(root, name):
    branch = default_branch(root)
    return None if branch is None else copy_at(root, branch, name)


def root_of_skills_folder(dest):
    return dest.resolve().parent.parent


def workflow_files(root):
    folder = root / WORKFLOWS
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix in WORKFLOW_SUFFIXES)


def _identity(folder: Path) -> tuple:
    info = os.lstat(folder)
    is_link = stat.S_ISLNK(info.st_mode)
    if is_link:
        info = os.stat(folder)
    return is_link, (info.st_dev, info.st_ino)


def _entry(here: Path, name: str) -> tuple:
    is_link, identity = _identity(here / name)
    return is_link, name, identity


def _first_visit(identity: tuple, seen: set) -> bool:
    if identity in seen:
        return False
    seen.add(identity)
    return True


@dataclass(frozen=True)
class Scope:
    root: str
    listed: frozenset
    walkable: frozenset
    excluded: tuple = ()

    def location(self, real_here, name):
        return os.path.relpath(os.path.join(real_here, name), self.root)

    def keeps(self, location, names):
        if is_outside(location):
            return True
        return location in names and not excluded_by(location, self.excluded)

    def keeps_folder(self, real_here, name):
        location = self.location(real_here, name)
        if is_outside(location):
            return name not in FOLDERS_SKIPPED_OUTSIDE_THE_REPO
        return self.keeps(location, self.walkable)

    def is_submodule(self, real_here, name):
        return self.location(real_here, name) in self.listed

    def keeps_file(self, real_here, name):
        return self.keeps(self.location(real_here, name), self.listed)

    def given(self, path):
        location = os.path.relpath(os.path.realpath(path), self.root)
        kept = tuple(entry for entry in self.excluded if not covers(entry, location))
        return replace(self, excluded=kept)

    def ignores(self, path):
        location = os.path.relpath(os.path.realpath(path), self.root)
        if is_outside(location) or location == os.curdir:
            return False
        if Path(path).is_dir():
            return location not in self.walkable and not is_empty(path)
        return location not in self.listed


def is_empty(folder):
    with os.scandir(folder) as entries:
        return next(entries, None) is None


def is_outside(location):
    return location == os.pardir or location.startswith(os.pardir + os.sep)


def covers(entry, location):
    named = entry.rstrip("/")
    return location == named or location.startswith(named + "/")


def excluded_by(location, entries):
    return any(covers(entry, location) for entry in entries)


def parent_folders(names):
    return frozenset(str(parent) for name in names for parent in PurePosixPath(name).parents if str(parent) != ".")


def committable_files(root):
    listing = subprocess.run(list(FILES_GIT_WOULD_COMMIT), cwd=root, capture_output=True)
    if listing.returncode != 0:
        raise ToolError(NOT_A_GIT_REPO)
    return frozenset(name for name in os.fsdecode(listing.stdout).split("\0") if name)


def default_exclusions(listed):
    found = sorted(f"{folder}/" for folder in parent_folders(listed) if PurePosixPath(folder).name.lower() in FIXTURE_FOLDERS)
    return tuple(prefix for prefix in found if not excluded_by(prefix, tuple(other for other in found if other != prefix)))


def checked_choice(root):
    try:
        return read_choice(root)
    except BrokenFileError as error:
        raise ToolError(str(error)) from error


def scope_exclusions(root, listed):
    choice = checked_choice(root)
    return default_exclusions(listed) if choice is None else choice.exclude


def scope_of(root, excluded=None):
    listed = committable_files(root)
    excluded = scope_exclusions(root, listed) if excluded is None else tuple(excluded)
    return Scope(os.path.realpath(root), listed, listed | parent_folders(listed), excluded)


def is_chosen(choice, component):
    if choice is None:
        return component in ON_WITHOUT_A_CHOICE_FILE
    return choice.recorded(component) == CHOSEN


def comment_gate_skips(choice, scope):
    return scope.excluded if choice is None else scope.excluded + choice.comment_gate_exclude


def comment_gate_files_under(root, choice, names):
    scope = scope_of(root, choice.exclude if choice else None)
    skipped = comment_gate_skips(choice, scope)
    kept = (name for name in sorted(scope.listed) if not excluded_by(name, skipped))
    return {name: language for name in kept for language in [language_among(root, name, names)] if language}


def comment_gate_exclude_after_setup(root, choice):
    return tuple(sorted(set(choice.comment_gate_exclude if choice else ()) | comment_gate_exclusions(root)))


def comment_gate_files_after_setup(root, choice, names):
    moved = comment_gate_exclude_after_setup(root, choice)
    return {name: language for name, language in comment_gate_files_under(root, choice, names).items()
            if not excluded_by(name, moved)}


def language_among(root, name, names):
    by_first_line = any(languages.LANGUAGES[language].interpreters for language in names)
    found = language_of_code_file(root, name, by_first_line)
    return found if found in names else None


def first_line(path):
    try:
        with open(path, "rb") as handle:
            return handle.readline(FIRST_LINE_BYTES).decode("utf-8", "replace").strip()
    except OSError:
        return ""


def language_of_code_file(root, name, by_first_line=True):
    found = languages.language_of_file(name)
    if found or not by_first_line or PurePosixPath(name).suffix:
        return found
    return languages.language_of_first_line(first_line(Path(root) / name))


def language_of_listed(root, name):
    folder = next((language for language in map(languages.language_of_folder, PurePosixPath(name).parent.parts)
                   if language), None)
    return languages.language_of_file(name) or folder or language_of_code_file(root, name)


def marker_files(root, scope):
    return [(language.name, marker) for language in languages.REGISTERED for marker in language.markers
            if marker in scope.listed and not excluded_by(marker, scope.excluded) and (Path(root) / marker).exists()]


def detected_languages(root, scope=None):
    scope = scope_of(root) if scope is None else scope
    found = {}
    for name in sorted(scope.listed):
        language = None if excluded_by(name, scope.excluded + KEPT_BY_QUALITY_GATES) else language_of_listed(root, name)
        if language and os.path.lexists(Path(root) / name):
            found.setdefault(language, set()).add(name)
    for language, marker in marker_files(root, scope):
        found.setdefault(language, set()).add(marker)
    return {language: sorted(names) for language, names in found.items()}


def _subfolders(here: Path, real_here: str, dirnames: list, seen: set, scope: Scope) -> tuple:
    kept, skipped = [], []
    for is_link, name, identity in sorted(_entry(here, name) for name in dirnames):
        if not scope.keeps_folder(real_here, name):
            continue
        if not is_link and scope.is_submodule(real_here, name):
            skipped.append(os.path.relpath(here / name) + A_SUBMODULE)
        elif _first_visit(identity, seen):
            kept.append(name)
        else:
            skipped.append(os.path.relpath(here / name) + ALREADY_SCANNED)
    return kept, skipped


def _walk(root: Path, seen: set, scope: Scope) -> tuple:
    if not root.is_dir():
        return ([root] if scope.keeps_file(os.path.realpath(root.parent), root.name) else []), []
    if not _first_visit(_identity(root)[1], seen):
        return [], [os.path.relpath(root) + ALREADY_SCANNED]
    files, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        here, real_here = Path(dirpath), os.path.realpath(dirpath)
        dirnames[:], skipped_here = _subfolders(here, real_here, dirnames, seen, scope)
        skipped.extend(skipped_here)
        files.extend(here / name for name in sorted(filenames) if scope.keeps_file(real_here, name))
    return files, skipped


def once_each(files):
    seen, kept = set(), []
    for file in files:
        real = os.path.realpath(file)
        if real not in seen:
            seen.add(real)
            kept.append(file)
    return kept


def root_of_scanned(path):
    try:
        return git_root(start=path if path.is_dir() else path.parent)
    except ToolError:
        return git_root()


def root_for(paths, root=None):
    return root_of_scanned(Path(paths[0])) if root is None else root


def spelled_on_disk(folder, name):
    if name in (os.curdir, os.pardir):
        return name
    entries = os.listdir(folder)
    if name in entries:
        return name
    return next((entry for entry in entries if entry.lower() == name.lower()
                 and os.path.samefile(os.path.join(folder, entry), os.path.join(folder, name))), name)


def on_disk_case(path):
    fixed = Path(path.anchor) if path.is_absolute() else Path()
    for name in path.parts[1 if path.is_absolute() else 0:]:
        fixed = fixed / spelled_on_disk(str(fixed), name)
    return fixed


def files_in_scope(paths: list, root=None) -> tuple:
    for path in paths:
        if not Path(path).exists():
            raise ToolError(f"path not found: {path}")
    paths = [on_disk_case(Path(path)) for path in paths]
    scope = scope_of(root_for(paths, root))
    files, skipped, seen = [], set(), set()
    for path in paths:
        if scope.ignores(path):
            print(IGNORED_NOTE.format(path), file=sys.stderr)
        found, folders = _walk(Path(path), seen, scope.given(path))
        files.extend(found)
        skipped.update(folders)
    return sorted(once_each(files)), sorted(skipped)


def files_named(files):
    shown = ", ".join(files[:FILES_SHOWN])
    more = len(files) - FILES_SHOWN
    return f"{shown} and {more} more" if more > 0 else shown


def runs_command(text, command):
    return re.search(rf"(?<![\w-]){re.escape(command)}(?![\w-])", text) is not None


def logical_lines(text):
    pending = ""
    for line in text.splitlines():
        if line.rstrip().endswith(CONTINUATION):
            pending += line.rstrip()[:-len(CONTINUATION)] + " "
            continue
        yield pending + line
        pending = ""
    if pending:
        yield pending


def words_of(line):
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return line.split()


def command_segments(words):
    segment = []
    for word in words:
        if word in COMMAND_SEPARATORS:
            yield segment
            segment = []
        else:
            segment.append(word)
    yield segment


def exclude_flags(words):
    for at, word in enumerate(words):
        if word == EXCLUDE_FLAG and at + 1 < len(words):
            yield words[at + 1]
        elif word.startswith(EXCLUDE_FLAG + "="):
            yield word[len(EXCLUDE_FLAG) + 1:]


def indent_of(line):
    return line[:len(line) - len(line.lstrip(" \t"))]


def line_ending(lines):
    return CRLF if lines and lines[0].endswith(CRLF) else LF


def marked_step(indent, newline):
    return [indent + line + newline for line in (CI_BEGIN, *TOLERATED_STEP, CI_END)]


def marker_lines(lines, marker):
    return [at for at, line in enumerate(lines) if line.strip() == marker]


def marked_span(lines, where):
    begins, ends = marker_lines(lines, CI_BEGIN), marker_lines(lines, CI_END)
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        raise ToolError(BROKEN_MARKERS.format(where))
    return begins[0], ends[0] + 1


def runs_a_gate(line):
    return any(runs_command(line, command) for command in GATE_COMMANDS)


def step_indent(lines, at):
    limit = len(indent_of(lines[at]))
    for line in reversed(lines[:at + 1]):
        found = STEP_START.match(line)
        if found and len(found.group(1)) <= limit:
            return found.group(1)
    return None


def gate_step(lines):
    for at, line in enumerate(lines):
        indent = step_indent(lines, at) if runs_a_gate(line) else None
        if indent is not None:
            return at, indent
    return None


def in_steps(line, indent):
    here = len(indent_of(line))
    return not line.strip() or here > len(indent) or (here == len(indent) and line.lstrip().startswith("- "))


def steps_end(lines, at, indent):
    end = at + 1
    while end < len(lines) and in_steps(lines[end], indent):
        end += 1
    while end > at + 1 and not lines[end - 1].strip():
        end -= 1
    return end


def ended(lines, newline):
    return lines[:-1] + [lines[-1] if lines[-1].endswith(LF) else lines[-1] + newline]


def with_step_added(lines, newline):
    found = gate_step(lines)
    if found is None:
        return None
    at, indent = found
    end = steps_end(lines, at, indent)
    return "".join(ended(lines[:end], newline) + marked_step(indent, newline) + lines[end:])


def with_tolerated_step(text, where):
    if not ON_PULL_REQUESTS.search(text):
        return None
    lines = text.splitlines(keepends=True)
    newline = line_ending(lines)
    span = marked_span(lines, where)
    if span is None:
        return with_step_added(lines, newline)
    begin, end = span
    return "".join(lines[:begin] + marked_step(indent_of(lines[begin]), newline) + lines[end:])


def tolerated_step_changes(root):
    files = workflow_files(root)
    found = sorted(((path, text) for path, text in zip(files, each_text(files)) if text is not None),
                   key=lambda pair: CI_BEGIN not in pair[1])
    for path, text in found:
        name = path.relative_to(root).as_posix()
        changed = with_tolerated_step(text, name)
        if changed is not None:
            return [PlannedChange(name, changed)]
    return []


def comment_gate_exclusions(root):
    found = set()
    for text in pre_commit_texts(root) + ci_texts(root):
        for line in logical_lines(text or ""):
            found.update(flag for segment in command_segments(words_of(line))
                         if runs_command(" ".join(segment), COMMENT_GATE_COMMAND) for flag in exclude_flags(segment))
    return found


@dataclass(frozen=True)
class Choice:
    languages: tuple
    chosen: tuple = ()
    declined: tuple = ()
    exclude: tuple = ()
    commit_time_limit_seconds: float = DEFAULT_COMMIT_TIME_LIMIT_SECONDS
    comment_gate_exclude: tuple = ()
    conventions: tuple = ()

    def recorded(self, component_id):
        if component_id in self.declined:
            return DECLINED
        return CHOSEN if component_id in self.chosen else UNLISTED


def text_list(data, field, where):
    values = data[field]
    fail_unless(isinstance(values, list) and all(isinstance(v, str) for v in values),
                f"{where}: field '{field}' must be a list of text")
    unique(values, where, lambda value: f"'{value}' in '{field}'")
    return tuple(values)


def check_version(data, where):
    version = data["format_version"]
    fail_unless(version == CHOICE_FORMAT_VERSION and not isinstance(version, bool),
                f"{where}: field 'format_version' must be {CHOICE_FORMAT_VERSION}; this quality-gates cannot read {version!r}")


def check_limit(value, where):
    fail_unless(isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0,
                f"{where}: field 'commit_time_limit_seconds' must be a number of seconds above 0")
    return value


def check_not_both(chosen, declined, where):
    for both in sorted(set(chosen) & set(declined)):
        raise BrokenFileError(f"{where}: component '{both}' is both chosen and declined")


def components_of(data, where):
    require(data, COMPONENTS_REQUIRED, f"{where}: components")
    chosen, declined = text_list(data, "chosen", where), text_list(data, "declined", where)
    check_not_both(chosen, declined, where)
    return chosen, declined


def comment_gate_settings(settings, where):
    fail_unless(isinstance(settings, dict), f"{where}: field 'settings' must be an object")
    for name in settings:
        known(name, {COMMENT_GATE}, "settings", where)
    gate = require(settings.get(COMMENT_GATE, {"exclude": [], "conventions": []}), COMMENT_GATE_REQUIRED,
                   f"{where}: settings '{COMMENT_GATE}'")
    conventions = text_list(gate, "conventions", where)
    for convention in conventions:
        known(convention, RECOGNISED_CONVENTIONS, "convention", where)
    return text_list(gate, "exclude", where), conventions


def is_from_root(entry):
    segments = entry.rstrip("/").split("/")
    return not entry.startswith("/") and not any(segment in ("", os.curdir, os.pardir) for segment in segments)


def exclude_entries(data, where):
    entries = text_list(data, "exclude", where)
    for entry in entries:
        fail_unless(is_from_root(entry), f"{where}: exclude entry '{entry}' must be a path from the repo root, "
                                         f"such as 'tests/fixtures/', with no '/', './' or '../' in front")
    return entries


def choice_from(data, where=CHOICE_FILE):
    require(data, CHOICE_REQUIRED, where)
    check_version(data, where)
    chosen, declined = components_of(data["components"], where)
    comment_gate_exclude, conventions = comment_gate_settings(data["settings"], where)
    return Choice(known_languages(text_list(data, "languages", where), where), chosen, declined,
                  exclude_entries(data, where), check_limit(data["commit_time_limit_seconds"], where),
                  comment_gate_exclude, conventions)


def read_choice(root):
    path = Path(root) / CHOICE_FILE
    if not path.exists():
        return None
    return choice_from(read_json(path))


def choice_text(choice):
    data = {
        "format_version": CHOICE_FORMAT_VERSION,
        "languages": list(choice.languages),
        "exclude": list(choice.exclude),
        "components": {"chosen": list(choice.chosen), "declined": list(choice.declined)},
        "commit_time_limit_seconds": choice.commit_time_limit_seconds,
        "settings": {COMMENT_GATE: {"exclude": list(choice.comment_gate_exclude),"conventions": list(choice.conventions)}},
    }
    return json.dumps(data, indent=2) + "\n"


@dataclass(frozen=True)
class PlannedChange:
    name: str
    text: str


def planned_state(root, change):
    found = read_kept(Path(root), change.name)
    if found is None:
        return WILL_CREATE
    return UNCHANGED if found == change.text else WILL_CHANGE


def apply_planned(root, changes):
    written = [change for change in changes if planned_state(root, change) != UNCHANGED]
    for change in written:
        write_kept(Path(root), change.name, change.text)
    return [change.name for change in written]


def choice_change(choice):
    return PlannedChange(CHOICE_FILE, choice_text(choice))


def comment_debt_change(text):
    return PlannedChange(COMMENT_DEBT_BASELINE, text)
