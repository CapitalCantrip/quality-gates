import ast
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

from quality_gates import languages
from quality_gates.errors import ToolError

LIZARD_CCN = 1
LIZARD_FILE = 6
LIZARD_NAME = 7
LIZARD_START = 9
LIZARD_END = 10

SKIPPED_FOLDERS = (
    ".git", ".venv", "venv", ".direnv", "node_modules", "__pycache__", "backups", "build", ".build", "dist",
    ".tox", ".mypy_cache", ".pytest_cache", ".worktrees", ".claude/worktrees",
)
SKIPPED_PARTS = [tuple(folder.split("/")) for folder in SKIPPED_FOLDERS]
ORDINAL_MARK = "#"
NAME_SEPARATOR = "."
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
LIZARD_MISSING = "lizard is missing, though quality-gates depends on it.\n  Reinstall quality-gates in this environment."
RADON_MISSING = "radon is not installed.\n  Install with: pip3 install radon"


@dataclass(frozen=True)
class Function:
    file: str
    name: str
    cc: int
    start: int
    end: int
    unlabelled_name: str


@dataclass(frozen=True)
class Scan:
    functions: list
    files: list
    skipped: list
    sources: list


def print_skipped(skipped: list, out) -> None:
    if skipped:
        print(f"Skipped {len(skipped)} folder(s): {', '.join(skipped)}", file=out)


def is_skipped(folder: Path) -> bool:
    return any(folder.parts[-len(parts):] == parts for parts in SKIPPED_PARTS)


def _enter(folder: Path, seen: set) -> bool:
    real = os.path.realpath(folder)
    if real in seen:
        return False
    seen.add(real)
    return True


def _is_link(here: Path, name: str) -> bool:
    return os.path.islink(here / name)


def _subfolders(here: Path, dirnames: list, seen: set) -> tuple:
    kept, skipped = [], []
    for name in sorted(dirnames, key=lambda d: (_is_link(here, d), d)):
        child = here / name
        if is_skipped(child) or not _enter(child, seen):
            skipped.append(os.path.relpath(child))
        else:
            kept.append(name)
    return kept, skipped


def _walk(root: Path, seen: set) -> tuple:
    if not root.is_dir():
        return [root], []
    if not _enter(root, seen):
        return [], [os.path.relpath(root)]
    files, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        here = Path(dirpath)
        dirnames[:], left = _subfolders(here, dirnames, seen)
        skipped.extend(left)
        files.extend(here / name for name in filenames)
    return files, skipped


def _walk_all(paths: list) -> tuple:
    files, skipped, seen = [], set(), set()
    for path in paths:
        if not Path(path).exists():
            raise ToolError(f"path not found: {path}")
        found, folders = _walk(Path(path), seen)
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


def command(file_list: str, lizard_languages: tuple) -> list:
    flags = [arg for language in lizard_languages for arg in ("-l", language)]
    return [sys.executable, "-m", "lizard", *flags, "--csv", "-f", file_list]


def _run_lizard(files: list, lizard_languages: tuple, runner):
    with tempfile.TemporaryDirectory() as folder:
        file_list = os.path.join(folder, "files.txt")
        Path(file_list).write_text("".join(f"{file}\n" for file in files), encoding="utf-8")
        return (runner or run)(command(file_list, lizard_languages), stdout=PIPE, stderr=PIPE, text=True)


def _lizard_functions(files: list, lizard_languages: tuple, runner) -> list:
    if importlib.util.find_spec("lizard") is None:
        raise ToolError(LIZARD_MISSING)
    if not files:
        return []
    result = _run_lizard(files, lizard_languages, runner)
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


def _read_source(file: Path, visitors) -> tuple:
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (OSError, ValueError, SyntaxError):
        return [], {}
    found = visitors.ComplexityVisitor.from_ast(tree)
    nodes = {(n.name, n.lineno, n.col_offset): n for n in ast.walk(tree) if isinstance(n, FUNCTION_NODES)}
    return found.functions + found.classes, nodes


def _classes_in(node) -> list:
    found = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            found.append(child)
        elif not isinstance(child, FUNCTION_NODES):
            found.extend(_classes_in(child))
    return found


def _classes_defined_in(block, nodes: dict, visitors) -> list:
    node = nodes.get((block.name, block.lineno, block.col_offset))
    classes = []
    for class_node in _classes_in(node):
        classes.extend(visitors.ComplexityVisitor.from_ast(class_node).classes)
    return classes


def _flatten(block, file: str, outer: tuple, visitors, nodes: dict) -> list:
    path = (*outer, block.name)
    if isinstance(block, visitors.Class):
        inner = block.methods + block.inner_classes
        own = []
    else:
        inner = block.closures + _classes_defined_in(block, nodes, visitors)
        name = NAME_SEPARATOR.join(path)
        own = [Function(file, name, block.complexity, block.lineno, block.endline, name)]
    return own + [fn for child in inner for fn in _flatten(child, file, path, visitors, nodes)]


def _python_functions(files: list) -> list:
    visitors = _radon_visitors()
    functions = []
    for file in files:
        blocks, nodes = _read_source(file, visitors)
        functions.extend(fn for block in blocks for fn in _flatten(block, str(file), (), visitors, nodes))
    return functions


def with_labels(functions: list) -> list:
    seen: dict = {}
    labelled = []
    for fn in sorted(functions, key=lambda f: (f.file, f.start)):
        count = seen[(fn.file, fn.name)] = seen.get((fn.file, fn.name), 0) + 1
        labelled.append(fn if count == 1 else replace(fn, name=f"{fn.name}{ORDINAL_MARK}{count}"))
    return labelled


def _count_with_radon(sources: list, language: languages.Language, runner) -> tuple:
    return with_labels(_python_functions(sources)), [str(f) for f in sources]


def _count_with_lizard(sources: list, language: languages.Language, runner) -> tuple:
    functions = with_labels(_lizard_functions(sources, language.lizard_languages, runner))
    return functions, sorted({fn.file for fn in functions})


COUNTING_TOOLS = {
    languages.RADON: _count_with_radon,
    languages.LIZARD: _count_with_lizard,
}


def scan(paths: list, lang: str, runner=None) -> Scan:
    files, skipped = _walk_all(paths)
    language = languages.LANGUAGES[lang]
    sources = [f for f in files if f.suffix in language.suffixes]
    functions, analysed = COUNTING_TOOLS[language.counter](sources, language, runner)
    return Scan(functions, analysed, skipped, sources)
