import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, Optional

from quality_gates.errors import ToolError
from quality_gates.json_report import MALFORMED_RECORD, load_json, shaped
from quality_gates.real_path import real_path

if TYPE_CHECKING:
    from quality_gates.languages import CoverageOf

COVERAGE_JSON = "coverage JSON"
NO_BRANCH_DATA = (
    "[crap] ⚠️  no branch data in coverage file — using line coverage only.\n"
    "  For more accurate scores add [run] branch=True to .coveragerc."
)


@dataclass
class FileCoverage:
    lines: dict
    branches: dict
    has_branches: bool


def _build_branch_map(exec_b: list, miss_b: list) -> dict:
    bmap: dict = {}
    for from_ln, _ in miss_b:
        bmap.setdefault(from_ln, [0, 0])[1] += 1
    for from_ln, _ in exec_b:
        entry = bmap.setdefault(from_ln, [0, 0])
        entry[0] += 1
        entry[1] += 1
    return bmap


def _parse_file_coverage(fd: dict) -> FileCoverage:
    executed = set(fd.get("executed_lines", []))
    missing  = set(fd.get("missing_lines", []))
    lines = {ln: True for ln in executed}
    lines.update({ln: False for ln in missing})
    exec_b = fd.get("executed_branches", [])
    miss_b = fd.get("missing_branches", [])
    has_branches = bool(exec_b or miss_b)
    branches = _build_branch_map(exec_b, miss_b) if has_branches else {}
    return FileCoverage(lines=lines, branches=branches, has_branches=has_branches)


def _branch_coverage_for_range(branches: dict, start: int, end: int) -> Optional[float]:
    in_range = {ln: v for ln, v in branches.items() if start <= ln <= end}
    if not in_range:
        return None
    total = sum(v[1] for v in in_range.values())
    return (sum(v[0] for v in in_range.values()) / total) if total else None


def _line_coverage_for_range(lines: dict, start: int, end: int) -> Optional[float]:
    in_range = {ln: hit for ln, hit in lines.items() if start <= ln <= end}
    if not in_range:
        return None
    return sum(1 for hit in in_range.values() if hit) / len(in_range)


def _file_entry(relpath: str, fd: object) -> FileCoverage:
    what = f"the entry for {relpath}"
    try:
        return _parse_file_coverage(shaped(fd, dict, COVERAGE_JSON, what))
    except MALFORMED_RECORD as exc:
        raise ToolError(f"bad {COVERAGE_JSON}: {what}: {exc!r}") from None


def load(coverage_json_path: str) -> dict:
    data = shaped(load_json(coverage_json_path, "coverage file", COVERAGE_JSON), dict, COVERAGE_JSON, "the document")
    out: dict = {}
    any_branches = False
    for relpath, fd in shaped(data.get("files", {}), dict, COVERAGE_JSON, '"files"').items():
        entry = _file_entry(relpath, fd)
        if entry.has_branches:
            any_branches = True
        out[real_path(relpath)] = entry
        out[relpath] = entry

    if not any_branches:
        print(NO_BRANCH_DATA, file=sys.stderr)
    return out


def function_coverage(
    cov_map: dict,
    filepath: str,
    start_line: int,
    end_line: int,
    resolve: Callable[[str], str] = real_path,
) -> Optional[float]:
    entry = cov_map.get(resolve(filepath)) or cov_map.get(filepath)
    if not entry:
        return None
    if entry.has_branches:
        cov = _branch_coverage_for_range(entry.branches, start_line, end_line)
        if cov is not None:
            return cov
    return _line_coverage_for_range(entry.lines, start_line, end_line)


def read(coverage_json_path: str) -> "CoverageOf":
    files = load(coverage_json_path)
    real_paths: Dict[str, str] = {}

    def resolve(filepath: str) -> str:
        if filepath not in real_paths:
            real_paths[filepath] = real_path(filepath)
        return real_paths[filepath]

    return lambda fn: function_coverage(files, fn.file, fn.start, fn.end, resolve)
