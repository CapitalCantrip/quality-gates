import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Union

from quality_gates.errors import TOOL_ERROR_EXIT
from quality_gates.real_path import real_path

KEY_SEPARATOR = "::"
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
        return [v for v in self.verdicts if v.outcome is outcome]


DID_NOT_RUN = Result((Verdict(None, Outcome.DID_NOT_RUN),))


def location(root, file, function) -> Location:
    relative = os.path.relpath(real_path(file), real_path(root))
    return Location(Path(relative).as_posix(), function)


def key(root, file, name):
    return location(root, file, name).key


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


def _outcome(now, allowed) -> Outcome:
    allowance = 0 if allowed is None else allowed
    if now is None:
        return Outcome.UNMEASURED
    if now > allowance:
        return Outcome.FAILED
    return Outcome.BEHIND if now < allowance else Outcome.PASSED


def judge(findings, baseline: dict) -> Result:
    numbers = strongest(findings)
    dark = unmeasured_keys(findings)
    verdicts = [
        Verdict(Location.from_key(k), _outcome(n, baseline.get(k)), n, baseline.get(k))
        for k, n in numbers.items()
        if k not in dark or n > baseline.get(k, 0)
    ]
    verdicts += [Verdict(Location.from_key(k), Outcome.UNMEASURED, None, baseline.get(k)) for k in dark]
    verdicts += [Verdict(Location.from_key(k), Outcome.BEHIND, None, v) for k, v in baseline.items() if k not in numbers and k not in dark]
    return Result(tuple(sorted(verdicts, key=lambda v: v.location.key)))


def exit_code(result: Result) -> int:
    if result.having(Outcome.DID_NOT_RUN):
        return TOOL_ERROR_EXIT
    return 0 if len(result.having(Outcome.PASSED)) == len(result.verdicts) else 1


def lowered(result: Result) -> dict:
    kept = {v.location.key: v.now for v in result.verdicts if v.outcome in (Outcome.PASSED, Outcome.BEHIND) and v.now}
    held = {v.location.key: v.allowed for v in result.having(Outcome.UNMEASURED) if v.allowed is not None}
    return dict(sorted({**kept, **held}.items()))


def seeded(findings) -> dict:
    return strongest(findings)


def write(file, scores):
    file.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def settle(findings, file: Path, updating: bool) -> Result:
    if file.exists():
        baseline = json.loads(file.read_text(encoding="utf-8"))
    elif updating:
        baseline = seeded(findings)
    else:
        return DID_NOT_RUN
    result = judge(findings, baseline)
    if not updating or result.having(Outcome.FAILED):
        return result
    write(file, lowered(result))
    return judge(findings, lowered(result))


def describe_over(over, out):
    for v in over:
        was = "new" if v.allowed is None else f"baseline allows {v.allowed}"
        out.write(f"FAIL {v.location.key}: {v.now}, {was}\n")


def describe_behind(behind, file, out):
    for v in behind:
        now = "at or below the threshold" if v.now is None else str(v.now)
        out.write(f"PAID {v.location.key}: now {now}, baseline still says {v.allowed}\n")
    out.write(f"\nThe baseline is behind. Run again with --update and commit {file.name}.\n")


def describe_unmeasured(unmeasured, out):
    if not unmeasured:
        return
    for v in unmeasured:
        out.write(f"UNMEASURED {v.location.key}: no coverage figure\n")
    out.write(f"\n{UNMEASURED_ADVICE}\n")


def describe_check(result: Result, file, out):
    if result.having(Outcome.FAILED):
        describe_over(result.having(Outcome.FAILED), out)
    elif result.having(Outcome.BEHIND):
        describe_behind(result.having(Outcome.BEHIND), file, out)
    describe_unmeasured(result.having(Outcome.UNMEASURED), out)
    if exit_code(result) == 0:
        out.write(f"ratchet: {len(result.verdicts)} baselined function(s) over the threshold, none new or worse\n")


def describe_update(result: Result, out):
    if result.having(Outcome.FAILED):
        describe_over(result.having(Outcome.FAILED), out)
        out.write("--update only lowers the baseline. It will not record a new or worse function.\n")
        return
    out.write(f"baseline: {len(lowered(result))} function(s) over the threshold\n")
    describe_unmeasured(result.having(Outcome.UNMEASURED), out)


def describe(result: Result, file: Path, updating: bool, out):
    if result.having(Outcome.DID_NOT_RUN):
        out.write(f"No baseline at {file}. Run with --update to create one.\n")
    elif updating:
        describe_update(result, out)
    else:
        describe_check(result, file, out)


def enforce(findings, file: Path, updating: bool, out) -> int:
    result = settle(findings, file, updating)
    describe(result, file, updating, out)
    return exit_code(result)

