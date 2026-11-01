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
TRACKED_PYTHON = ("git", "ls-files", "*.py")
SKIPPED_FOLDERS = (
    ".git", ".venv", "venv", ".direnv", "node_modules", "__pycache__", "backups", "build", ".build", "dist",
    ".tox", ".mypy_cache", ".pytest_cache", ".worktrees", ".claude/worktrees",
)
SKIPPED_PARTS = [tuple(folder.split("/")) for folder in SKIPPED_FOLDERS]
ALREADY_SCANNED = " (already scanned)"
BUILD_OUTPUT_FOLDERS = {"target", "Pods", "DerivedData", "site-packages"}
HIDDEN_PREFIX = "."
WORKFLOW_SUFFIXES = (".yml", ".yaml")


class SettingsError(Exception):
    pass


def hook_names(source=HOOKS_SOURCE):
    return sorted(p.name for p in source.glob("*.py"))


def hook_differences(dest, source=HOOKS_SOURCE):
    found = []
    for name in hook_names(source):
        if not (dest / name).is_file():
            found.append(f"hooks/{name}: missing")
        elif not filecmp.cmp(source / name, dest / name, shallow=False):
            found.append(f"hooks/{name}: differs")
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


def differences(claude_dir, root, source=HOOKS_SOURCE):
    found = hook_differences(claude_dir / "hooks", source)
    if not stage_guard_registered(claude_dir / "settings.json"):
        found.append("settings.json: the stage guard is not registered as a PreToolUse hook")
    if not has_asking_line(root):
        found.append(f"{instruction_file(root).name}: the asking-rule line is missing or out of date")
    return found


def sync(claude_dir, root, source=HOOKS_SOURCE):
    sync_hooks(claude_dir / "hooks", source)
    register_stage_guard(claude_dir / "settings.json")
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


def tracked_python_files(root, excluded=()):
    listing = subprocess.run(
        list(TRACKED_PYTHON),
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    return [p for p in listing if not p.startswith(tuple(excluded))]


def workflow_files(root):
    folder = root / ".github" / "workflows"
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
