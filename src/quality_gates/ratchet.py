import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Union

from quality_gates.errors import TOOL_ERROR_EXIT, ToolError, Untagged, shown, write_utf8
from quality_gates.real_path import real_path

KEY_SEPARATOR = "::"
MISSING_BASELINE = "No baseline at {}. Run with --update to create one."
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

    def having(self, outcome: Outcome) -> list:
        return [verdict for verdict in self.verdicts if verdict.outcome is outcome]


DID_NOT_RUN = Result((Verdict(None, Outcome.DID_NOT_RUN),))


def location(root, file, function) -> Location:
    relative = os.path.relpath(real_path(file), real_path(root))
    return Location(Path(relative).as_posix(), function)


def record(scores, name, score):
    scores[name] = max(score, scores.get(name, score))


def strongest(findings) -> dict:
    numbers: dict = {}
    for finding in findings:
        if finding.number is not None:
            record(numbers, finding.location.key, finding.number)
    return numbers


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


def _verdict(location: Location, now, dark: bool, allowed) -> Verdict:
    outcome = _outcome(now, allowed)
    if dark and outcome is not Outcome.FAILED:
        return Verdict(location, Outcome.UNMEASURED, None, allowed)
    return Verdict(location, outcome, now, allowed)


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


def lowered(result: Result) -> dict:
    kept = {verdict.location.key: verdict.now for verdict in result.verdicts if owes(verdict)}
    held = {
        verdict.location.key: verdict.allowed
        for verdict in result.having(Outcome.UNMEASURED)
        if verdict.allowed is not None
    }
    return dict(sorted({**kept, **held}.items()))


def write(file, scores):
    file.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    recorded: Optional[dict] = None


def settle(find: Callable[[], list], file: Path, updating: bool) -> Settled:
    if not file.exists() and not updating:
        raise Untagged(MISSING_BASELINE.format(file))
    findings = find()
    baseline = json.loads(file.read_text(encoding="utf-8")) if file.exists() else strongest(findings)
    result = judge(findings, baseline)
    if not updating or result.having(Outcome.FAILED):
        return Settled(findings, result)
    counts = lowered(result)
    write(file, counts)
    return Settled(findings, judge(findings, counts), counts)


def describe_over(over, displays, out):
    for verdict in over:
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


FUNCTION_WORDING = Wording(
    describe_over, describe_behind, describe_passed, describe_recorded,
    "--update only lowers the baseline. It will not record a new or worse function.\n",
)


def unmeasured_in(settled: Settled) -> list:
    dark = unmeasured_keys(settled.findings)
    return [verdict for verdict in settled.result.verdicts if verdict.location.key in dark]


def describe_unmeasured(unmeasured, out):
    if not unmeasured:
        return
    for verdict in unmeasured:
        out.write(f"UNMEASURED {verdict.location.key}: no coverage figure\n")
    out.write(f"\n{UNMEASURED_ADVICE}\n")


def describe_failed(settled: Settled, out, wording: Wording):
    displays = {finding.location.key: finding.display for finding in settled.findings}
    wording.failed(settled.result.having(Outcome.FAILED), displays, out)


def describe_check(settled: Settled, file, out, wording: Wording):
    result = settled.result
    if result.having(Outcome.FAILED):
        describe_failed(settled, out, wording)
    elif result.having(Outcome.BEHIND):
        wording.behind(result.having(Outcome.BEHIND), file, out)
    describe_unmeasured(unmeasured_in(settled), out)
    if exit_code(result) == 0:
        wording.passed(result, out)


def describe_update(settled: Settled, out, wording: Wording):
    if settled.recorded is None:
        describe_failed(settled, out, wording)
        out.write(wording.refusal)
        return
    wording.recorded(settled.recorded, out)
    describe_unmeasured(unmeasured_in(settled), out)


def describe(settled: Settled, file: Path, updating: bool, out, wording: Wording = FUNCTION_WORDING):
    if updating:
        describe_update(settled, out, wording)
    else:
        describe_check(settled, file, out, wording)


def enforce(find: Callable[[], list], file: Path, updating: bool, out) -> Result:
    try:
        settled = settle(find, file, updating)
    except ToolError as error:
        out.write(f"{error}\n")
        return DID_NOT_RUN
    describe(settled, file, updating, out)
    return settled.result


def result_of(gate: Callable, argv, root, tag: str) -> Result:
    return attempt(lambda: gate(argv, root), lambda error: print(shown(error, tag), file=sys.stderr))


def run_gate(gate: Callable, argv, root, tag: str) -> int:
    write_utf8()
    return exit_code(result_of(gate, argv, root, tag))
