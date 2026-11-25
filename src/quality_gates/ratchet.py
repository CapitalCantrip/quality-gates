import json
import os
import sys
from dataclasses import dataclass, replace
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Callable, Optional, Union

from quality_gates import project_files
from quality_gates.errors import TOOL_ERROR_EXIT, ToolError, Untagged, shown, write_utf8
from quality_gates.real_path import real_path

KEY_SEPARATOR = "::"
MISSING_BASELINE = "No baseline at {}. Run with --update to create one."
BAD_BASELINE = "bad baseline {}: {}"
NOT_AN_OBJECT = "must be an object, got {}"
NOT_A_NUMBER = "value for {} must be a number, got {}"
NAN = "NaN"
MAIN_HAS_THE_BASELINE = ("{file}: the default branch {branch} has this baseline committed. "
                         "Restore it with `git checkout {branch} -- {file}` and run --update from there.")
UNMEASURED_ADVICE = (
    "Unmeasured functions fail the gate. Measure their files or take them out of the scan; "
    "the baseline keeps any entry they already have and records none for them."
)

Number = Union[int, float]


class Outcome(Enum):
    PASSED = "passed"
    FAILED = "failed"
    BEHIND = "behind the baseline"
    UNMEASURED = "unmeasured"
    DID_NOT_RUN = "did not run"


@dataclass(frozen=True)
class Location:
    file: str
    function: Optional[str] = None

    @property
    def key(self) -> str:
        return self.file if self.function is None else self.file + KEY_SEPARATOR + self.function

    @classmethod
    def from_key(cls, key: str) -> "Location":
        file, separator, function = key.partition(KEY_SEPARATOR)
        return cls(file, function if separator else None)


@dataclass(frozen=True)
class Finding:
    location: Location
    number: Optional[Number]
    kind: str
    display: str


@dataclass(frozen=True)
class Verdict:
    location: Optional[Location]
    outcome: Outcome
    now: Optional[Number] = None
    allowed: Optional[Number] = None


@dataclass(frozen=True)
class Result:
    verdicts: tuple

    @cached_property
    def by_outcome(self) -> dict:
        grouped: dict = {outcome: [] for outcome in Outcome}
        for verdict in self.verdicts:
            grouped[verdict.outcome].append(verdict)
        return grouped

    def having(self, outcome: Outcome) -> list:
        return self.by_outcome[outcome]


DID_NOT_RUN = Result((Verdict(None, Outcome.DID_NOT_RUN),))
NOT_JUDGED = Result(())


def covers_every_file(path: str) -> bool:
    return True


@dataclass(frozen=True)
class Asked:
    baseline: Optional[Path] = None
    updating: bool = False
    judged: bool = True
    covers: Callable[[str], bool] = covers_every_file


def location(root, file, function) -> Location:
    relative = os.path.relpath(real_path(file), real_path(root))
    return Location(Path(relative).as_posix(), function)


class BaselineError(Untagged):
    def __init__(self, message: str, stream=None):
        super().__init__(message)
        self.stream = stream


def keyed(find: Callable[[], list], root: Optional[Callable[[], Path]]) -> Callable[[], list]:
    if root is None:
        return find
    base = root()
    found = [replace(f, location=location(base, f.location.file, f.location.function)) for f in find()]
    return lambda: found


def record(scores, name, score):
    scores[name] = max(score, scores.get(name, score))


def strongest(findings) -> dict:
    numbers: dict = {}
    for finding in findings:
        if finding.number is not None:
            record(numbers, finding.location.key, finding.number)
    return numbers


def owed_counts(findings) -> dict:
    return {key: number for key, number in strongest(findings).items() if number}


def unmeasured_keys(findings) -> set:
    return {f.location.key for f in findings if f.number is None}


def located(findings) -> Callable[[str], Location]:
    found = {finding.location.key: finding.location for finding in findings}
    return lambda key: found.get(key) or Location.from_key(key)


def _outcome(now, allowed) -> Outcome:
    allowance = 0 if allowed is None else allowed
    if now is not None and now > allowance:
        return Outcome.FAILED
    return Outcome.BEHIND if now is None or now < allowance else Outcome.PASSED


def _verdict(place: Location, now, dark: bool, allowed) -> Verdict:
    outcome = _outcome(now, allowed)
    if dark and outcome is not Outcome.FAILED:
        return Verdict(place, Outcome.UNMEASURED, None, allowed)
    return Verdict(place, outcome, now, allowed)


def judge(findings, baseline: dict) -> Result:
    at = located(findings)
    numbers = strongest(findings)
    unmeasured = unmeasured_keys(findings)
    keys = sorted(set(numbers) | unmeasured | set(baseline))
    return Result(tuple(_verdict(at(k), numbers.get(k), k in unmeasured, baseline.get(k)) for k in keys))


def exit_code(result: Result) -> int:
    if result.having(Outcome.DID_NOT_RUN):
        return TOOL_ERROR_EXIT
    return 0 if len(result.having(Outcome.PASSED)) == len(result.verdicts) else 1


def owes(verdict: Verdict) -> bool:
    return verdict.outcome in (Outcome.PASSED, Outcome.BEHIND) and bool(verdict.now)


def held_back(stored: Optional[dict], covers: Callable[[str], bool]) -> dict:
    return {key: number for key, number in (stored or {}).items() if not covers(Location.from_key(key).file)}


def surviving(stored: Optional[dict], result: Result, covers: Callable[[str], bool]) -> dict:
    kept = {verdict.location.key: verdict.now for verdict in result.verdicts if owes(verdict)}
    unmeasured = {
        verdict.location.key: verdict.allowed
        for verdict in result.having(Outcome.UNMEASURED)
        if verdict.allowed
    }
    return {key: number for key, number in sorted({**held_back(stored, covers), **kept, **unmeasured}.items()) if number}


def lowered(result: Result, stored: Optional[dict] = None, covers: Callable[[str], bool] = covers_every_file) -> dict:
    return surviving(stored, result, covers)


def baseline_text(scores: dict) -> str:
    return json.dumps(scores, indent=2, sort_keys=True) + "\n"


def write(file, scores, out=None):
    try:
        file.write_text(baseline_text(scores), encoding="utf-8")
    except OSError as error:
        raise BaselineError(str(error), out) from None


def value_kind(value) -> Optional[str]:
    if not isinstance(value, (int, float)):
        return type(value).__name__
    return NAN if value != value else None


def wrong_with(baseline) -> Optional[str]:
    if not isinstance(baseline, dict):
        return NOT_AN_OBJECT.format(type(baseline).__name__)
    kinds = ((key, value_kind(value)) for key, value in baseline.items())
    return next((NOT_A_NUMBER.format(key, kind) for key, kind in kinds if kind is not None), None)


def absent(file: Path, updating: bool, out=None) -> None:
    if not updating:
        raise BaselineError(MISSING_BASELINE.format(file), out)


def baseline_from(data: bytes, where, out=None) -> dict:
    try:
        baseline = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError) as error:
        raise BaselineError(BAD_BASELINE.format(where, error), out) from None
    wrong = wrong_with(baseline)
    if wrong is not None:
        raise BaselineError(BAD_BASELINE.format(where, wrong), out)
    return baseline


def refuse_recreating(file: Path, out=None) -> None:
    branch = project_files.branch_holding(file)
    if branch is not None:
        raise BaselineError(MAIN_HAS_THE_BASELINE.format(file=file, branch=branch), out)


def stored_baseline(file: Path, updating: bool, out=None) -> Optional[dict]:
    try:
        if not file.exists():
            return absent(file, updating, out)
        data = file.read_bytes()
    except OSError as error:
        raise BaselineError(str(error), out) from None
    return baseline_from(data, file, out)


def baseline_at(root, ref, name) -> Optional[dict]:
    data = project_files.copy_at(root, ref, name)
    return None if data is None else baseline_from(data, f"{ref}:{name}")


def silencer_asked(root, updating: bool = False) -> Asked:
    return Asked(project_files.silencer_baseline(root), updating)


def told_on(error: ToolError, err):
    return getattr(error, "stream", None) or err or sys.stderr


def attempt(run: Callable[[], Result], told: Callable[[ToolError], None]) -> Result:
    try:
        return run()
    except ToolError as error:
        told(error)
        return DID_NOT_RUN


@dataclass(frozen=True)
class Settled:
    findings: list
    result: Result
    unmeasured: frozenset
    recorded: Optional[dict] = None

    @property
    def failed(self) -> list:
        return self.result.having(Outcome.FAILED)

    @cached_property
    def displays(self) -> dict:
        return {finding.location.key: finding.display for finding in self.findings}

    def shown(self, verdict: Verdict) -> str:
        return self.displays[verdict.location.key]


def settle(find: Callable[[], list], file: Path, updating: bool, root=None, out=None,
           covers: Callable[[str], bool] = covers_every_file) -> Settled:
    find = keyed(find, root)
    stored = stored_baseline(file, updating, out)
    if updating and stored is None:
        refuse_recreating(file, out)
    held = held_back(stored, covers)
    findings = find()
    unmeasured = frozenset(unmeasured_keys(findings))
    judged = strongest(findings) if stored is None else {k: v for k, v in stored.items() if k not in held}
    result = judge(findings, judged)
    if not updating or result.having(Outcome.FAILED):
        return Settled(findings, result, unmeasured)
    written = lowered(result, stored, covers)
    write(file, written, out)
    return Settled(findings, judge(findings, without(written, held)), unmeasured, written)


def without(scores: dict, held: dict) -> dict:
    return {key: number for key, number in scores.items() if key not in held}


def recorded(findings: list, file: Path, replaces: Callable[[str], bool]) -> dict:
    stored = stored_baseline(file, True) or {}
    result = judge(findings, {**stored, **owed_counts(findings)})
    return surviving(stored, result, replaces)


def describe_over(settled: Settled, out):
    for verdict in settled.failed:
        was = "new" if verdict.allowed is None else f"baseline allows {verdict.allowed}"
        out.write(f"FAIL {verdict.location.key}: {verdict.now}, {was}\n")


def describe_behind(behind, file, out):
    for verdict in behind:
        now = "at or below the threshold" if verdict.now is None else str(verdict.now)
        out.write(f"PAID {verdict.location.key}: now {now}, baseline still says {verdict.allowed}\n")
    out.write(f"\nThe baseline is behind. Run again with --update and commit {file.name}.\n")


def describe_passed(result: Result, out):
    out.write(f"ratchet: {len(result.verdicts)} baselined function(s) over the threshold, none new or worse\n")


def describe_recorded(counts: dict, out):
    out.write(f"baseline: {len(counts)} function(s) over the threshold\n")


@dataclass(frozen=True)
class Wording:
    failed: Callable
    behind: Callable
    passed: Callable
    recorded: Callable
    refusal: str
    unmeasured: str = "no coverage figure"
    unmeasured_advice: str = UNMEASURED_ADVICE


FUNCTION_WORDING = Wording(
    describe_over, describe_behind, describe_passed, describe_recorded,
    "--update only lowers the baseline. It will not record a new or worse function.\n",
)


def unmeasured_in(settled: Settled) -> list:
    return [verdict for verdict in settled.result.verdicts if verdict.location.key in settled.unmeasured]


def describe_unmeasured(unmeasured, out, wording: Wording):
    if not unmeasured:
        return
    for verdict in unmeasured:
        out.write(f"UNMEASURED {verdict.location.key}: {wording.unmeasured}\n")
    out.write(f"\n{wording.unmeasured_advice}\n")


def describe_check(settled: Settled, file, out, wording: Wording):
    result = settled.result
    behind = result.having(Outcome.BEHIND)
    if settled.failed:
        wording.failed(settled, out)
    elif behind:
        wording.behind(behind, file, out)
    describe_unmeasured(unmeasured_in(settled), out, wording)
    if exit_code(result) == 0:
        wording.passed(result, out)


def describe_update(settled: Settled, out, wording: Wording):
    if settled.recorded is None:
        wording.failed(settled, out)
        out.write(wording.refusal)
        return
    wording.recorded(settled.recorded, out)
    describe_unmeasured(unmeasured_in(settled), out, wording)


def describe(settled: Settled, file: Path, updating: bool, out, wording: Wording = FUNCTION_WORDING):
    if updating:
        describe_update(settled, out, wording)
    else:
        describe_check(settled, file, out, wording)


def enforce(find: Callable[[], list], asked: Asked, out, wording: Wording = FUNCTION_WORDING, root=None) -> Result:
    if not asked.judged:
        return NOT_JUDGED
    if asked.baseline is None:
        return judge(find(), {})
    settled = settle(find, asked.baseline, asked.updating, root, out, asked.covers)
    describe(settled, asked.baseline, asked.updating, out, wording)
    return settled.result


def result_of(gate: Callable, argv, root, tag: str, err=None) -> Result:
    return attempt(lambda: gate(argv, root), lambda error: print(shown(error, tag), file=told_on(error, err)))


def run_gate(gate: Callable, argv, root, tag: str, err=None) -> int:
    write_utf8()
    return exit_code(result_of(gate, argv, root, tag, err))
