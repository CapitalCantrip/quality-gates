from pathlib import Path
from typing import TYPE_CHECKING, Optional

from quality_gates.json_report import load_json

if TYPE_CHECKING:
    from quality_gates.languages import CoverageOf


def load(report_path: str) -> dict:
    data = load_json(report_path, "Istanbul coverage file", "Istanbul coverage JSON")
    return {str(Path(path).resolve()): entry for path, entry in data.items()}


def _end_lines_starting_on(entry: dict, start: int) -> list:
    return [
        fn["loc"]["end"]["line"]
        for fn in entry.get("fnMap", {}).values()
        if fn["decl"]["start"]["line"] == start
    ]


def _matching_end(ends: list, lizard_end: int) -> int:
    containing = [end for end in ends if end >= lizard_end]
    return min(containing) if containing else max(ends)


def function_range(entry: dict, start: int, lizard_end: int) -> tuple:
    ends = _end_lines_starting_on(entry, start)
    if not ends:
        return start, lizard_end
    return start, _matching_end(ends, lizard_end)


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


def function_coverage(files: dict, filepath: str, start: int, lizard_end: int) -> Optional[float]:
    entry = files.get(str(Path(filepath).resolve()))
    if entry is None:
        return None
    span = function_range(entry, start, lizard_end)
    branch = _branch_coverage(entry, span)
    return branch if branch is not None else _statement_coverage(entry, span)


def read(report_path: str) -> "CoverageOf":
    files = load(report_path)
    return lambda fn: function_coverage(files, fn.file, fn.start, fn.end)
