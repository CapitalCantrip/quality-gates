import filecmp
import json
import shutil
from pathlib import Path

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
