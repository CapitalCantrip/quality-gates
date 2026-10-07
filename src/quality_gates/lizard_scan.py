import csv
import importlib.util
import io
import sys
from subprocess import PIPE, run
from typing import Optional

LIZARD_CCN = 1
LIZARD_FILE = 6
LIZARD_NAME = 7
LIZARD_START = 9
LIZARD_END = 10

LANGUAGES = {
    "swift": ["swift"],
    "typescript": ["typescript", "tsx", "javascript", "jsx"],
}
EXCLUDED = ["*/node_modules/*", "*/.git/*", "*/.venv/*", "*/venv/*"]
ORDINAL_MARK = "#"


def parse_row(row: list) -> Optional[dict]:
    if len(row) <= LIZARD_END:
        return None
    try:
        return {
            "file":  row[LIZARD_FILE].strip(),
            "name":  row[LIZARD_NAME].strip(),
            "cc":    int(row[LIZARD_CCN]),
            "start": int(row[LIZARD_START]),
            "end":   int(row[LIZARD_END]),
        }
    except (ValueError, IndexError):
        return None


def command(paths: list, lang: str) -> list:
    flags = [arg for language in LANGUAGES[lang] for arg in ("-l", language)]
    excludes = [arg for pattern in EXCLUDED for arg in ("-x", pattern)]
    return [sys.executable, "-m", "lizard", *flags, *excludes, "--csv", *paths]


def _require_lizard() -> None:
    if importlib.util.find_spec("lizard") is None:
        print(
            "[lizard] lizard is missing, though quality-gates depends on it.\n"
            "  Reinstall quality-gates in this environment.",
            file=sys.stderr,
        )
        sys.exit(2)


def scan(paths: list, lang: str, runner=run) -> list:
    _require_lizard()
    result = runner(command(paths, lang), stdout=PIPE, stderr=PIPE, text=True)
    if result.returncode not in (0, 1):
        print(f"[lizard] lizard failed:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    rows = csv.reader(io.StringIO(result.stdout.strip()))
    return with_labels([fn for fn in map(parse_row, rows) if fn is not None])


def with_labels(functions: list) -> list:
    seen: dict = {}
    labelled = []
    for fn in sorted(functions, key=lambda f: (f["file"], f["start"])):
        count = seen[(fn["file"], fn["name"])] = seen.get((fn["file"], fn["name"]), 0) + 1
        label = fn["name"] if count == 1 else f"{fn['name']}{ORDINAL_MARK}{count}"
        labelled.append({**fn, "label": label})
    return labelled
