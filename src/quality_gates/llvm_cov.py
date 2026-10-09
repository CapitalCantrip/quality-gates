import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from quality_gates.errors import ToolError

if TYPE_CHECKING:
    from quality_gates.languages import CoverageOf

SEGMENT_LINE = 0
SEGMENT_COUNT = 2
SEGMENT_HAS_COUNT = 3
SEGMENT_IS_REGION_ENTRY = 4
SEGMENT_IS_GAP = 5
REGION_LINE_START = 0
REGION_LINE_END = 2
REGION_FILE_ID = 5


@dataclass
class SourceFile:
    line_counts: dict = field(default_factory=dict)
    bodies: set = field(default_factory=set)


def _starts_region(segment: list) -> bool:
    return segment[SEGMENT_HAS_COUNT] and segment[SEGMENT_IS_REGION_ENTRY] and not segment[SEGMENT_IS_GAP]


def _opens_skipped_region(starting: list) -> bool:
    return bool(starting) and not starting[0][SEGMENT_HAS_COUNT] and starting[0][SEGMENT_IS_REGION_ENTRY]


def _is_mapped(starting: list, wrapped: Optional[list]) -> bool:
    if any(s[SEGMENT_IS_REGION_ENTRY] and s[SEGMENT_HAS_COUNT] for s in starting):
        return True
    if _opens_skipped_region(starting):
        return False
    return wrapped is not None and bool(wrapped[SEGMENT_HAS_COUNT])


def _line_count(starting: list, wrapped: Optional[list]) -> Optional[int]:
    if not _is_mapped(starting, wrapped):
        return None
    counts = [s[SEGMENT_COUNT] for s in starting if _starts_region(s)]
    if wrapped is not None:
        counts.append(wrapped[SEGMENT_COUNT])
    return max(counts, default=0)


def line_counts(segments: list) -> dict:
    by_line: dict = {}
    for segment in segments:
        by_line.setdefault(segment[SEGMENT_LINE], []).append(segment)
    counts: dict = {}
    wrapped = None
    for line in range(min(by_line, default=0), max(by_line, default=-1) + 1):
        starting = by_line.get(line, [])
        count = _line_count(starting, wrapped)
        if count is not None:
            counts[line] = count
        if starting:
            wrapped = starting[-1]
    return counts


def _merge_lines(source: SourceFile, segments: list) -> None:
    for line, count in line_counts(segments).items():
        source.line_counts[line] = max(count, source.line_counts.get(line, 0))


def _add_body(files: dict, record: dict) -> None:
    body = record["regions"][0]
    filename = record["filenames"][body[REGION_FILE_ID]]
    files.setdefault(filename, SourceFile()).bodies.add((body[REGION_LINE_START], body[REGION_LINE_END]))


def _read_export(export_path: str) -> dict:
    try:
        with open(export_path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise ToolError(f"cannot open llvm-cov export: {exc}") from None
    except json.JSONDecodeError as exc:
        raise ToolError(f"bad llvm-cov export JSON: {exc}") from None


def load(export_path: str) -> dict:
    files: dict = {}
    for export in _read_export(export_path).get("data", []):
        for file_data in export.get("files", []):
            _merge_lines(files.setdefault(file_data["filename"], SourceFile()), file_data.get("segments", []))
        for record in export.get("functions", []):
            _add_body(files, record)
    return files


def _shared_tail(left: tuple, right: tuple) -> int:
    shared = 0
    for a, b in zip(reversed(left), reversed(right)):
        if a != b:
            break
        shared += 1
    return shared


def report_file(files: dict, filepath: str) -> Optional[SourceFile]:
    parts = Path(filepath).resolve().parts
    tails = {name: _shared_tail(parts, Path(name).parts) for name in files}
    longest = max(tails.values(), default=0)
    best = [name for name, tail in tails.items() if tail == longest]
    if longest == 0 or len(best) != 1:
        return None
    return files[best[0]]


def body_of(source: SourceFile, start: int, end: int) -> Optional[tuple]:
    inside = [body for body in source.bodies if start <= body[0] <= end]
    return min(inside, key=lambda body: (body[0], -body[1]), default=None)


def line_coverage(source: SourceFile, body: tuple) -> Optional[float]:
    counts = [count for line, count in source.line_counts.items() if body[0] <= line <= body[1]]
    if not counts:
        return None
    return sum(1 for count in counts if count) / len(counts)


def function_coverage(files: dict, filepath: str, start: int, end: int) -> Optional[float]:
    source = report_file(files, filepath)
    body = body_of(source, start, end) if source else None
    return line_coverage(source, body) if body else None


def read(export_path: str) -> "CoverageOf":
    files = load(export_path)
    return lambda fn: function_coverage(files, fn.file, fn.start, fn.end)
