import json
import os
import subprocess
from pathlib import Path

from quality_gates.real_path import real_path

KEY_SEPARATOR = "::"
UNMEASURED_ADVICE = (
    "Unmeasured functions fail the gate. Measure their files or take them out of the scan; "
    "the baseline keeps any entry they already have and records none for them."
)


def repo_root():
    found = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if found.returncode == 0 and found.stdout.strip():
        return Path(found.stdout.strip())
    return Path.cwd()


def key(root, file, name):
    relative = os.path.relpath(real_path(file), real_path(root))
    return Path(relative).as_posix() + KEY_SEPARATOR + name


def record(scores, name, score):
    scores[name] = max(score, scores.get(name, score))


def compare(current, baseline):
    over = {k: (v, baseline.get(k)) for k, v in current.items() if v > baseline.get(k, float("-inf"))}
    behind = {k: (current.get(k), v) for k, v in baseline.items() if current.get(k, float("-inf")) < v}
    return over, behind


def lowered(current, baseline):
    return {k: min(v, baseline[k]) for k, v in sorted(current.items()) if k in baseline}


def load(file, updating):
    if file.exists():
        return json.loads(file.read_text(encoding="utf-8"))
    if updating:
        return None
    raise FileNotFoundError(f"No baseline at {file}. Run with --update to create one.")


def write(file, scores):
    file.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def describe_over(over, out):
    for name, (score, allowed) in sorted(over.items()):
        was = "new" if allowed is None else f"baseline allows {allowed}"
        out.write(f"FAIL {name}: {score}, {was}\n")


def describe_behind(behind, file, out):
    for name, (score, allowed) in sorted(behind.items()):
        now = "at or below the threshold" if score is None else str(score)
        out.write(f"PAID {name}: now {now}, baseline still says {allowed}\n")
    out.write(f"\nThe baseline is behind. Run again with --update and commit {file.name}.\n")


def describe_unmeasured(unmeasured, out):
    if not unmeasured:
        return 0
    for name in sorted(unmeasured):
        out.write(f"UNMEASURED {name}: no coverage figure\n")
    out.write(f"\n{UNMEASURED_ADVICE}\n")
    return 1


def check(current, file, out, unmeasured=frozenset()):
    over, behind = compare(current, load(file, updating=False))
    behind = {k: v for k, v in behind.items() if k not in unmeasured}
    if over:
        describe_over(over, out)
    elif behind:
        describe_behind(behind, file, out)
    if describe_unmeasured(unmeasured, out) or over or behind:
        return 1
    out.write(f"ratchet: {len(current)} baselined function(s) over the threshold, none new or worse\n")
    return 0


def kept(baseline, unmeasured):
    return {k: v for k, v in baseline.items() if k in unmeasured}


def update(current, file, out, unmeasured=frozenset()):
    baseline = load(file, updating=True)
    if baseline is None:
        baseline = dict(current)
    over, _ = compare(current, baseline)
    if over:
        describe_over(over, out)
        out.write("--update only lowers the baseline. It will not record a new or worse function.\n")
        return 1
    scores = dict(sorted({**lowered(current, baseline), **kept(baseline, unmeasured)}.items()))
    write(file, scores)
    out.write(f"baseline: {len(scores)} function(s) over the threshold\n")
    return describe_unmeasured(unmeasured, out)


def enforce(current, file, updating, out, unmeasured=frozenset()):
    try:
        run = update if updating else check
        return run(current, file, out, unmeasured)
    except FileNotFoundError as missing:
        out.write(f"{missing}\n")
        return 2
