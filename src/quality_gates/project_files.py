import filecmp
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from quality_gates.errors import ToolError

HOOKS_SOURCE = Path(__file__).parent / "hooks"
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
TRACKED_FILES = ("git", "ls-files")
SKIPPED_FOLDERS = (
    ".git", ".venv", "venv", ".direnv", "node_modules", "__pycache__", "backups", "build", ".build", "dist",
    ".tox", ".mypy_cache", ".pytest_cache", ".worktrees", ".claude/worktrees",
)
SKIPPED_PARTS = [tuple(folder.split("/")) for folder in SKIPPED_FOLDERS]
ALREADY_SCANNED = " (already scanned)"
BUILD_OUTPUT_FOLDERS = {"target", "Pods", "DerivedData", "site-packages"}
HIDDEN_PREFIX = "."
WORKFLOW_SUFFIXES = (".yml", ".yaml")
WORKFLOWS = Path(".github") / "workflows"
CLAUDE_DIR = ".claude"
SKILLS_DEST = Path(CLAUDE_DIR) / "skills"
COPIED_HOOKS = "hooks"
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
UNSHIPPED, MISSING, DIFFERS, SAME = "unshipped", "missing", "differs", "same"
READABLE, UNREADABLE = "readable", "unreadable"


class SettingsError(Exception):
    pass


def hook_names(source=HOOKS_SOURCE):
    return sorted(p.name for p in source.glob("*.py"))


def copied_hook(dest, name, source=HOOKS_SOURCE):
    if not (source / name).is_file():
        return UNSHIPPED
    if not (dest / name).is_file():
        return MISSING
    return SAME if filecmp.cmp(source / name, dest / name, shallow=False) else DIFFERS


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


def read_settings(path):
    if not path.is_file():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SettingsError(f"{path} is not valid JSON ({error}); fix it, then run qg-skills again")
    if not isinstance(settings, dict):
        raise SettingsError(f"{path} must hold a JSON object")
    return settings


def registered_commands(settings):
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        for hook in entry.get("hooks", []):
            yield hook.get("command", "")


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


def settings_file(claude_folder):
    return claude_folder / SETTINGS


def comment_debt_baseline(root):
    return root / COMMENT_DEBT_BASELINE


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


def readable_texts(paths):
    texts = []
    for path in paths:
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            texts.append(None)
    return texts


def ci_texts(root, found_in=None):
    if found_in is None:
        return readable_texts(workflow_files(root))
    path = root / found_in
    return readable_texts([path] if path.is_file() else [])


def pre_commit_texts(root):
    return ci_texts(root, PRE_COMMIT_HOOK)


def pin_texts(root):
    return [text for text in readable_texts([root / PIN_FILE] + workflow_files(root)) if text is not None]


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


def git_root():
    top = subprocess.run(list(GIT_ROOT), check=True, capture_output=True, text=True).stdout.strip()
    return Path(top)


def git_root_or_current_folder():
    found = subprocess.run(list(GIT_ROOT), capture_output=True, text=True)
    if found.returncode == 0 and found.stdout.strip():
        return Path(found.stdout.strip())
    return Path.cwd()


def current_folder():
    return Path.cwd()


def root_of_skills_folder(dest):
    return dest.resolve().parent.parent


def tracked_files(root, suffixes, excluded=()):
    listing = subprocess.run(
        [*TRACKED_FILES, *(f"*{suffix}" for suffix in suffixes)],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    return [p for p in listing if not p.startswith(tuple(excluded))]


def workflow_files(root):
    folder = root / WORKFLOWS
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix in WORKFLOW_SUFFIXES)


def is_skipped(folder: Path) -> bool:
    return any(folder.parts[-len(parts):] == parts for parts in SKIPPED_PARTS)


def is_detection_skipped(folder):
    name = folder.name
    return name.startswith(HIDDEN_PREFIX) or name in BUILD_OUTPUT_FOLDERS or is_skipped(folder)


def detection_walk(root):
    for folder, directories, files in os.walk(root):
        directories[:] = [d for d in directories if not is_detection_skipped(Path(folder) / d)]
        yield directories, files


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


def _subfolders(here: Path, dirnames: list, seen: set) -> tuple:
    kept, skipped = [], []
    for _, name, identity in sorted(_entry(here, name) for name in dirnames):
        child = here / name
        if is_skipped(child):
            skipped.append(os.path.relpath(child))
        elif _first_visit(identity, seen):
            kept.append(name)
        else:
            skipped.append(os.path.relpath(child) + ALREADY_SCANNED)
    return kept, skipped


def _walk(root: Path, seen: set) -> tuple:
    if not root.is_dir():
        return [root], []
    if not _first_visit(_identity(root)[1], seen):
        return [], [os.path.relpath(root) + ALREADY_SCANNED]
    files, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        here = Path(dirpath)
        dirnames[:], skipped_here = _subfolders(here, dirnames, seen)
        skipped.extend(skipped_here)
        files.extend(here / name for name in filenames)
    return files, skipped


def scanned_files(paths: list) -> tuple:
    files, skipped, seen = [], set(), set()
    for path in paths:
        if not Path(path).exists():
            raise ToolError(f"path not found: {path}")
        found, folders = _walk(Path(path), seen)
        files.extend(found)
        skipped.update(folders)
    return sorted(files), sorted(skipped)
