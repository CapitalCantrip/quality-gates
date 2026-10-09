import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from quality_gates.errors import ToolError

if TYPE_CHECKING:
    from quality_gates.languages import CoverageOf


def load(report_path: str) -> dict:
    try:
        with open(report_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise ToolError(f"cannot open Istanbul coverage file: {exc}") from None
    except json.JSONDecodeError as exc:
        raise ToolError(f"bad Istanbul coverage JSON: {exc}") from None
    return {str(Path(path).resolve()): entry for path, entry in data.items()}


def _end_lines_starting_on(entry: dict, start: int) -> list:
    return [
        fn["loc"]["end"]["line"]
        for fn in entry.get("fnMap", {}).values()
        if fn["decl"]["start"]["line"] == start
    ]


def _matching_end(ends: list, lizard_end: int) -> int:
    containing = [end for end in ends if end >= lizard_end]
    return min(containing) if containing else ends[0]


def function_range(entry: dict, start: int, fallback_end: int) -> tuple:
    ends = _end_lines_starting_on(entry, start)
    if not ends:
        return start, fallback_end
    return start, _matching_end(ends, fallback_end)


def _in_range(line: int, span: tuple) -> bool:
    return span[0] <= line <= span[1]


def _branch_coverage(entry: dict, span: tuple) -> Optional[float]:
    arms = [
        hits
        for key, branch in entry.get("branchMap", {}).items()
        if _in_range(branch["loc"]["start"]["line"], span)
        for hits in entry.get("b", {}).get(key, [])
    ]
    return sum(1 for hits in arms if hits) / len(arms) if arms else None


def _statement_coverage(entry: dict, span: tuple) -> Optional[float]:
    hits = [
        entry.get("s", {}).get(key, 0)
        for key, statement in entry.get("statementMap", {}).items()
        if _in_range(statement["start"]["line"], span)
    ]
    return sum(1 for h in hits if h) / len(hits) if hits else None


def function_coverage(files: dict, filepath: str, start: int, fallback_end: int) -> Optional[float]:
    entry = files.get(str(Path(filepath).resolve()))
    if entry is None:
        return None
    span = function_range(entry, start, fallback_end)
    branch = _branch_coverage(entry, span)
    return branch if branch is not None else _statement_coverage(entry, span)


def read(report_path: str) -> "CoverageOf":
    files = load(report_path)
    return lambda fn: function_coverage(files, fn.file, fn.start, fn.end)
