#!/usr/bin/env python3
import argparse
import ast
import io
import json
import re
import subprocess
import sys
import tokenize
import warnings
from pathlib import Path

DEFAULT_BASELINE = "comment-debt.json"

PRAGMA = re.compile(
    r"#\s*(?:"
    r"noqa(?::\s*[A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*)?"
    r"|type:\s*ignore(?:\[[\w\s,-]+\])?"
    r"|pragma:\s*no\s+(?:cover|branch)"
    r"|fmt:\s*(?:on|off|skip)"
    r")\s*$"
)
CODING = re.compile(r"^#.*coding[:=]")
RATIONALE = re.compile(
    r"workaround|hack|for now|todo|fixme|xxx|temporar|on purpose|deliberate|intentional",
    re.IGNORECASE,
)


def exempt(text, line):
    if line == 1 and text.startswith("#!"):
        return True
    if line <= 2 and CODING.match(text):
        return True
    return bool(PRAGMA.match(text))


def comment_lines(source):
    readline = io.StringIO(source).readline
    return {
        tok.start[0]
        for tok in tokenize.generate_tokens(readline)
        if tok.type == tokenize.COMMENT and not exempt(tok.string, tok.start[0])
    }


def is_bare_string(node):
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def string_lines(source):
    lines = set()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tree = ast.parse(source)
    for node in ast.walk(tree):
        if is_bare_string(node):
            lines.update(range(node.lineno, node.end_lineno + 1))
    return lines


def debt_lines(source):
    return sorted(comment_lines(source) | string_lines(source))


def tracked(root, excluded=()):
    listing = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    return [p for p in listing if not p.startswith(tuple(excluded))]


def measure(root, paths):
    current = {}
    for path in paths:
        file = root / path
        if file.exists():
            current[path] = debt_lines(file.read_text(encoding="utf-8"))
    return current


def ratchet(current, baseline):
    over, under = {}, {}
    for path, lines in current.items():
        allowed = baseline.get(path, 0)
        if len(lines) > allowed:
            over[path] = (lines, allowed)
        elif len(lines) < allowed:
            under[path] = (len(lines), allowed)
    stale = sorted(p for p in baseline if p not in current)
    return over, under, stale


def lowered(current, baseline):
    return {
        path: min(len(lines), baseline.get(path, 0))
        for path, lines in sorted(current.items())
        if min(len(lines), baseline.get(path, 0)) > 0
    }


def load_baseline(file):
    if not file.exists():
        return None
    return json.loads(file.read_text(encoding="utf-8"))


def write_baseline(file, counts):
    text = json.dumps(counts, indent=2, sort_keys=True) + "\n"
    file.write_text(text, encoding="utf-8")


def report_over(over, out):
    for path, (lines, allowed) in sorted(over.items()):
        where = ", ".join(str(n) for n in lines)
        out.write(f"FAIL {path}: {len(lines)} comment lines, baseline allows {allowed} — lines {where}\n")
    out.write(
        "\nNew comments are not allowed (no-code-comments policy). Move the knowledge to a test, "
        "a named constant, an ADR or an issue — see the quality-gates README for where each kind goes.\n"
    )


def report_behind(under, stale, file, out):
    for path, (count, allowed) in sorted(under.items()):
        out.write(f"PAID {path}: {count} lines, baseline still says {allowed}\n")
    for path in stale:
        out.write(f"GONE {path}: in the baseline but no longer tracked\n")
    out.write(
        f"\nThe baseline is behind. Run `comment-debt --update` "
        f"and commit {file.name} so the paid debt cannot come back.\n"
    )


def check(root, file, excluded, out):
    baseline = load_baseline(file)
    if baseline is None:
        out.write(f"No baseline at {file}. Run with --update to create one.\n")
        return 2
    over, under, stale = ratchet(measure(root, tracked(root, excluded)), baseline)
    if over:
        report_over(over, out)
        return 1
    if under or stale:
        report_behind(under, stale, file, out)
        return 1
    out.write(f"comment debt: {sum(baseline.values())} lines in {len(baseline)} files, none new\n")
    return 0


def update(root, file, excluded, out):
    current = measure(root, tracked(root, excluded))
    baseline = load_baseline(file)
    if baseline is None:
        baseline = {path: len(lines) for path, lines in current.items()}
    over, _, _ = ratchet(current, baseline)
    if over:
        report_over(over, out)
        out.write("--update only lowers the baseline. It will not record new comments.\n")
        return 1
    counts = lowered(current, baseline)
    write_baseline(file, counts)
    out.write(f"baseline: {sum(counts.values())} lines in {len(counts)} files\n")
    return 0


def area(path):
    parts = path.split("/")
    return "/".join(parts[:2]) if len(parts) > 2 else parts[0]


def rationale_count(root, path, lines):
    text = (root / path).read_text(encoding="utf-8").splitlines()
    return sum(1 for n in lines if RATIONALE.search(text[n - 1]))


def group_by_area(root, current):
    areas = {}
    for path, lines in current.items():
        areas.setdefault(area(path), []).append((path, len(lines), rationale_count(root, path, lines)))
    return areas


def write_area(name, rows, out):
    rows = sorted(rows, key=lambda r: (-r[2], r[1]))
    out.write(f"\n## {name} — {sum(n for _, n, _ in rows)} lines\n")
    for path, count, flagged in rows:
        out.write(f"{count:5} {flagged:4}  {path}\n")


def status(root, excluded, out):
    current = {p: ls for p, ls in measure(root, tracked(root, excluded)).items() if ls}
    areas = group_by_area(root, current)
    total = sum(len(ls) for ls in current.values())
    out.write(f"# Comment debt: {total} lines in {len(current)} files\n\n")
    out.write("Columns: lines, of which rationale (workaround, deliberately, for now, TODO ...)\n")
    for name in sorted(areas, key=lambda a: -sum(n for _, n, _ in areas[a])):
        write_area(name, areas[name], out)
    return 0


def repo_root():
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return Path(top)


def main(argv=None, root=None, baseline=None, out=sys.stdout):
    parser = argparse.ArgumentParser(
        description="Ratchet on comment lines in tracked Python files.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="lower the baseline to match the tree")
    mode.add_argument("--status", action="store_true", help="print the remaining debt, by area")
    parser.add_argument("--baseline", help=f"baseline file (default: {DEFAULT_BASELINE} at the repo root)")
    parser.add_argument("--exclude", action="append", default=[], metavar="PREFIX", help="skip tracked paths with this prefix")
    args = parser.parse_args(argv)
    root = root or repo_root()
    baseline = Path(baseline or args.baseline or root / DEFAULT_BASELINE)
    if args.update:
        return update(root, baseline, args.exclude, out)
    if args.status:
        return status(root, args.exclude, out)
    return check(root, baseline, args.exclude, out)


if __name__ == "__main__":
    sys.exit(main())
