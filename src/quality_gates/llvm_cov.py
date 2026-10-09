import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, NamedTuple, Optional, Tuple

from quality_gates.errors import ToolError

if TYPE_CHECKING:
    from quality_gates.languages import CoverageOf

EXPORT_TYPE = "llvm.coverage.json.export"
EXPANSION, SKIPPED, GAP = 1, 2, 3
MIN_SHARED_TAIL = 2
REGION_FILE_ID = 5
REGION_EXPANDED_FILE_ID = 6
REGION_KIND = 7

Location = Tuple[int, int]
LineCounts = Dict[int, int]


class _Region(NamedTuple):
    start: Location
    end: Location
    count: int
    kind: int


class _Segment(NamedTuple):
    line: int
    count: int
    has_count: bool
    is_entry: bool
    is_gap: bool


class _Body(NamedTuple):
    start: int
    end: int


def _region(raw: list) -> _Region:
    return _Region((raw[0], raw[1]), (raw[2], raw[3]), raw[4], raw[REGION_KIND])


def _nesting_order(region: _Region) -> tuple:
    return region.start, (-region.end[0], -region.end[1]), region.kind


def _combined(regions: List[_Region]) -> List[_Region]:
    combined: List[_Region] = []
    for region in sorted(regions, key=_nesting_order):
        last = combined[-1] if combined else None
        if last is None or (last.start, last.end) != (region.start, region.end):
            combined.append(region)
        elif last.kind == region.kind:
            combined[-1] = last._replace(count=last.count + region.count)
    return combined


def _repeats(last: _Segment, has_count: bool, count: int) -> bool:
    return last.has_count == has_count and last.count == count and not last.is_entry


def _segment_for(region: _Region, line: int, is_entry: bool, skipped: bool) -> _Segment:
    has_count = not skipped and region.kind != SKIPPED
    return _Segment(line, region.count if has_count else 0, has_count, is_entry, has_count and region.kind == GAP)


class _SegmentBuilder:
    def __init__(self) -> None:
        self.segments: List[_Segment] = []
        self.active: List[_Region] = []

    def _start(self, region: _Region, loc: Location, is_entry: bool, skipped: bool = False) -> None:
        segment = _segment_for(region, loc[0], is_entry, skipped)
        if self.segments and not (is_entry or skipped) and _repeats(self.segments[-1], segment.has_count, region.count):
            return
        self.segments.append(segment)

    def _last_ending_like(self, index: int) -> _Region:
        end = self.active[index].end
        return [region for region in self.active[index:] if region.end == end][-1]

    def _close(self, loc: Optional[Location], first: int) -> None:
        last = self.active[-1]
        if last.end == loc:
            return
        if first:
            self._start(self.active[first - 1], last.end, False)
        else:
            self._start(last, last.end, False, skipped=True)

    def _complete_until(self, loc: Optional[Location], first: int) -> None:
        self.active[first:] = sorted(self.active[first:], key=lambda region: region.end)
        for index in range(first + 1, len(self.active)):
            previous_end = self.active[index - 1].end
            if previous_end == loc:
                break
            if previous_end != self.active[index].end:
                self._start(self._last_ending_like(index), previous_end, False)
        self._close(loc, first)
        del self.active[first:]

    def _complete_before(self, loc: Location) -> None:
        open_regions = [region for region in self.active if not region.end <= loc]
        if len(open_regions) < len(self.active):
            self.active = open_regions + [region for region in self.active if region.end <= loc]
            self._complete_until(loc, len(open_regions))

    def _start_empty(self, region: _Region, is_last: bool) -> None:
        skipped = is_last or region.kind == SKIPPED
        self._start(self.active[-1] if self.active else region, region.start, region.kind != GAP, skipped)
        if skipped and self.active:
            self._start(self.active[-1], region.start, False)

    def build(self, regions: List[_Region]) -> List[_Segment]:
        for index, region in enumerate(regions):
            self._complete_before(region.start)
            following = regions[index + 1].start if index + 1 < len(regions) else None
            if region.start == region.end:
                self._start_empty(region, following is None)
                continue
            if following != region.start:
                self._start(region, region.start, region.kind != GAP)
            self.active.append(region)
        if self.active:
            self._complete_until(None, 0)
        return self.segments


def _enters_counted(segment: _Segment) -> bool:
    return segment.has_count and segment.is_entry


def _starts_region(segment: _Segment) -> bool:
    return _enters_counted(segment) and not segment.is_gap


def _is_mapped(starting: List[_Segment], wrapped: Optional[_Segment]) -> bool:
    if any(_enters_counted(segment) for segment in starting):
        return True
    if starting and not starting[0].has_count and starting[0].is_entry:
        return False
    return wrapped is not None and wrapped.has_count


def _line_count(starting: List[_Segment], wrapped: Optional[_Segment]) -> Optional[int]:
    if not _is_mapped(starting, wrapped):
        return None
    counts = [segment.count for segment in starting if _starts_region(segment)]
    if wrapped is not None:
        counts.append(wrapped.count)
    return max(counts, default=0)


def _line_counts(segments: List[_Segment]) -> LineCounts:
    by_line: Dict[int, List[_Segment]] = {}
    for segment in segments:
        by_line.setdefault(segment.line, []).append(segment)
    counts: LineCounts = {}
    wrapped = None
    for line in range(min(by_line, default=0), max(by_line, default=-1) + 1):
        starting = by_line.get(line, [])
        count = _line_count(starting, wrapped)
        if count is not None:
            counts[line] = count
        if starting:
            wrapped = starting[-1]
    return counts


def _main_file_id(record: dict) -> Optional[int]:
    expanded = {raw[REGION_EXPANDED_FILE_ID] for raw in record["regions"] if raw[REGION_KIND] == EXPANSION}
    return next((file_id for file_id in range(len(record["filenames"])) if file_id not in expanded), None)


def _own_regions(record: dict, main: int) -> List[_Region]:
    return _combined([_region(raw) for raw in record["regions"] if raw[REGION_FILE_ID] == main])


@dataclass
class _Report:
    files: Dict[str, Dict[_Body, LineCounts]] = field(default_factory=dict)
    resolved: Dict[str, Optional[str]] = field(default_factory=dict)
    by_file_name: Dict[str, List[str]] = field(default_factory=dict)

    def add(self, record: dict) -> None:
        main = _main_file_id(record)
        regions = _own_regions(record, main) if main is not None else []
        if not regions:
            return
        body = _Body(regions[0].start[0], regions[0].end[0])
        filename = record["filenames"][main]
        if filename not in self.files:
            self.by_file_name.setdefault(Path(filename).name, []).append(filename)
        lines = self.files.setdefault(filename, {}).setdefault(body, {})
        for line, count in _line_counts(_SegmentBuilder().build(regions)).items():
            lines[line] = max(count, lines.get(line, 0))

    def bodies_in(self, filepath: str) -> Dict[_Body, LineCounts]:
        if filepath not in self.resolved:
            self.resolved[filepath] = _report_name(self.by_file_name, filepath)
        name = self.resolved[filepath]
        return self.files[name] if name is not None else {}


def _shared_tail(left: tuple, right: tuple) -> int:
    shared = 0
    for a, b in zip(reversed(left), reversed(right)):
        if a != b:
            break
        shared += 1
    return shared


def _report_name(by_file_name: Dict[str, List[str]], filepath: str) -> Optional[str]:
    path = Path(filepath).resolve()
    names = by_file_name.get(path.name, [])
    if str(path) in names:
        return str(path)
    tails = {name: _shared_tail(path.parts, Path(name).parts) for name in names}
    longest = max(tails.values(), default=0)
    best = [name for name, tail in tails.items() if tail == longest]
    return best[0] if longest >= MIN_SHARED_TAIL and len(best) == 1 else None


def _body_within(bodies: Dict[_Body, LineCounts], start: int, end: int) -> Optional[_Body]:
    inside = [body for body in bodies if start <= body.start <= end]
    return min(inside, key=lambda body: (body.start, -body.end), default=None)


def _coverage(lines: LineCounts) -> Optional[float]:
    if not lines:
        return None
    return sum(1 for count in lines.values() if count) / len(lines)


def _function_coverage(report: _Report, filepath: str, start: int, end: int) -> Optional[float]:
    bodies = report.bodies_in(filepath)
    body = _body_within(bodies, start, end)
    return _coverage(bodies[body]) if body is not None else None


def _read_export(export_path: str) -> object:
    try:
        with open(export_path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise ToolError(f"cannot open llvm-cov export: {exc}") from None
    except json.JSONDecodeError as exc:
        raise ToolError(f"bad llvm-cov export JSON: {exc}") from None


def _exports(export_path: str) -> list:
    document = _read_export(export_path)
    if not isinstance(document, dict) or document.get("type") != EXPORT_TYPE or not isinstance(document.get("data"), list):
        raise ToolError(f"not an llvm-cov export: {export_path} needs \"type\": \"{EXPORT_TYPE}\" and a \"data\" list")
    return document["data"]


def read(export_path: str) -> "CoverageOf":
    report = _Report()
    for export in _exports(export_path):
        for record in export.get("functions", []):
            report.add(record)
    return lambda fn: _function_coverage(report, fn.file, fn.start, fn.end)
