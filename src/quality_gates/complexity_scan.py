import csv
import importlib.util
import io
import os
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from subprocess import PIPE, run
from typing import Optional

from quality_gates.errors import ToolError

LIZARD_CCN = 1
LIZARD_FILE = 6
LIZARD_NAME = 7
LIZARD_START = 9
LIZARD_END = 10

LIZARD_LANGUAGES = {
    "swift": ["swift"],
    "typescript": ["typescript", "tsx", "javascript", "jsx"],
}
LIZARD_SUFFIXES = {
    "swift": {".swift"},
    "typescript": {".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"},
}
PYTHON_SUFFIX = ".py"
SKIPPED_FOLDERS = (
    ".git", ".venv", "venv", ".direnv", "node_modules", "__pycache__", "backups", "build", "dist",
    ".tox", ".mypy_cache", ".pytest_cache", ".worktrees", ".claude/worktrees",
)
SKIPPED_PARTS = [tuple(folder.split("/")) for folder in SKIPPED_FOLDERS]
ORDINAL_MARK = "#"
NAME_SEPARATOR = "."
LIZARD_MISSING = "lizard is missing, though quality-gates depends on it.\n  Reinstall quality-gates in this environment."
RADON_MISSING = "radon is not installed.\n  Install with: pip3 install radon"


@dataclass(frozen=True)
class Function:
    file: str
    name: str
    cc: int
    start: int
    end: int
    plain_name: str


@dataclass(frozen=True)
class Scan:
    functions: list
    files: list
    skipped: list


def print_skipped(skipped: list, out) -> None:
    if skipped:
        print(f"Skipped {len(skipped)} folder(s): {', '.join(skipped)}", file=out)


def is_skipped(folder: Path) -> bool:
    return any(folder.parts[-len(parts):] == parts for parts in SKIPPED_PARTS)


def _walk(root: Path) -> tuple:
    if not root.is_dir():
        return [root], []
    files, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        skipped.extend(os.path.relpath(here / d) for d in dirnames if is_skipped(here / d))
        dirnames[:] = [d for d in dirnames if not is_skipped(here / d)]
        files.extend(here / name for name in filenames)
    return files, skipped


def _walk_all(paths: list) -> tuple:
    files, skipped = [], set()
    for path in paths:
        if not Path(path).exists():
            raise ToolError(f"path not found: {path}")
        found, folders = _walk(Path(path))
        files.extend(found)
        skipped.update(folders)
    return sorted(files), sorted(skipped)


def parse_row(row: list) -> Optional[Function]:
    if len(row) <= LIZARD_END:
        return None
    try:
        name = row[LIZARD_NAME].strip()
        return Function(row[LIZARD_FILE].strip(), name, int(row[LIZARD_CCN]),
                        int(row[LIZARD_START]), int(row[LIZARD_END]), name)
    except ValueError:
        return None


def command(file_list: str, lang: str) -> list:
    flags = [arg for language in LIZARD_LANGUAGES[lang] for arg in ("-l", language)]
    return [sys.executable, "-m", "lizard", *flags, "--csv", "-f", file_list]


def _run_lizard(files: list, lang: str, runner):
    with tempfile.TemporaryDirectory() as folder:
        file_list = os.path.join(folder, "files.txt")
        Path(file_list).write_text("".join(f"{file}\n" for file in files), encoding="utf-8")
        return (runner or run)(command(file_list, lang), stdout=PIPE, stderr=PIPE, text=True)


def _lizard_functions(files: list, lang: str, runner) -> list:
    if importlib.util.find_spec("lizard") is None:
        raise ToolError(LIZARD_MISSING)
    if not files:
        return []
    result = _run_lizard(files, lang, runner)
    if result.returncode not in (0, 1):
        raise ToolError(f"lizard failed:\n{result.stderr.strip()}")
    rows = csv.reader(io.StringIO(result.stdout.strip()))
    return [fn for fn in map(parse_row, rows) if fn is not None]


def _radon_visitors():
    try:
        from radon import visitors
    except ImportError:
        raise ToolError(RADON_MISSING) from None
    return visitors


def _read_blocks(file: Path, visitors) -> list:
    try:
        found = visitors.ComplexityVisitor.from_code(file.read_text(encoding="utf-8"))
    except (OSError, ValueError, SyntaxError):
        return []
    return found.functions + found.classes


def _flatten(block, file: str, outer: tuple, visitors) -> list:
    path = (*outer, block.name)
    if isinstance(block, visitors.Class):
        inner = block.methods + block.inner_classes
        own = []
    else:
        inner = block.closures
        name = NAME_SEPARATOR.join(path)
        own = [Function(file, name, block.complexity, block.lineno, block.endline, name)]
    return own + [fn for child in inner for fn in _flatten(child, file, path, visitors)]


def _python_functions(files: list) -> list:
    visitors = _radon_visitors()
    return [
        fn
        for file in files
        for block in _read_blocks(file, visitors)
        for fn in _flatten(block, str(file), (), visitors)
    ]


def with_labels(functions: list) -> list:
    seen: dict = {}
    labelled = []
    for fn in sorted(functions, key=lambda f: (f.file, f.start)):
        count = seen[(fn.file, fn.name)] = seen.get((fn.file, fn.name), 0) + 1
        labelled.append(fn if count == 1 else replace(fn, name=f"{fn.name}{ORDINAL_MARK}{count}"))
    return labelled


def scan(paths: list, lang: str, runner=None) -> Scan:
    files, skipped = _walk_all(paths)
    if lang == "python":
        sources = [f for f in files if f.suffix == PYTHON_SUFFIX]
        return Scan(with_labels(_python_functions(sources)), [str(f) for f in sources], skipped)
    sources = [f for f in files if f.suffix in LIZARD_SUFFIXES[lang]]
    functions = with_labels(_lizard_functions(sources, lang, runner))
    return Scan(functions, sorted({fn.file for fn in functions}), skipped)
