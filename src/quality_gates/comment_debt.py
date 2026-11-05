#!/usr/bin/env python3
import argparse
import ast
import io
import re
import sys
import tokenize
import warnings
from pathlib import Path

from quality_gates import languages, project_files, ratchet
from quality_gates.errors import ToolError


PRAGMA = re.compile(
    r"#\s*(?:"
    r"noqa(?::\s*[A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*)?"
    r"|type:\s*ignore(?:\[[\w\s,-]+\])?"
    r"|pragma:\s*no\s+(?:cover|branch)"
    r"|fmt:\s*(?:on|off|skip)"
    r")\s*$"
)
CODING = re.compile(r"^#.*coding[:=]")
FINDING_KIND = "comment lines"
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


LANGUAGES = {
    "python": debt_lines,
}


def tracked_files(root, excluded):
    return {
        path: checker
        for name, checker in LANGUAGES.items()
        for path in project_files.tracked_files(root, languages.suffixes_of([name]), excluded)
    }


def measure(root, listed):
    current = {}
    for path, checker in listed.items():
        file = root / path
        if file.exists():
            current[path] = checker(file.read_text(encoding="utf-8"))
    return current


def to_finding(path, lines):
    return ratchet.Finding(ratchet.Location(path), len(lines), FINDING_KIND, ", ".join(str(n) for n in lines))


def findings(root, excluded):
    return [to_finding(path, lines) for path, lines in sorted(measure(root, tracked_files(root, excluded)).items())]


def describe_failed(result, found, out):
    shown = {finding.location.key: finding.display for finding in found}
    for v in result.having(ratchet.Outcome.FAILED):
        allowed = v.allowed or 0
        out.write(f"FAIL {v.location.key}: {v.now} comment lines, baseline allows {allowed} — lines {shown[v.location.key]}\n")
    out.write(
        "\nNew comments are not allowed (no-code-comments policy). Move the knowledge to a test, "
        "a named constant, an ADR or an issue — see the quality-gates README for where each kind goes.\n"
    )


def describe_behind(result, file, out):
    behind = result.having(ratchet.Outcome.BEHIND)
    for v in behind:
        if v.now is not None:
            out.write(f"PAID {v.location.key}: {v.now} lines, baseline still says {v.allowed}\n")
    for v in behind:
        if v.now is None:
            out.write(f"GONE {v.location.key}: in the baseline but no longer tracked\n")
    out.write(
        f"\nThe baseline is behind. Run `comment-debt --update` "
        f"and commit {file.name} so the paid debt cannot come back.\n"
    )


def describe_check(result, found, file, out):
    if result.having(ratchet.Outcome.FAILED):
        describe_failed(result, found, out)
    elif result.having(ratchet.Outcome.BEHIND):
        describe_behind(result, file, out)
    else:
        allowed = [v.allowed for v in result.verdicts if v.allowed is not None]
        out.write(f"comment debt: {sum(allowed)} lines in {len(allowed)} files, none new\n")


def describe_update(result, found, out):
    if result.having(ratchet.Outcome.FAILED):
        describe_failed(result, found, out)
        out.write("--update only lowers the baseline. It will not record new comments.\n")
        return
    counts = ratchet.lowered(result)
    out.write(f"baseline: {sum(counts.values())} lines in {len(counts)} files\n")


def describe(result, found, file, updating, out):
    if result.having(ratchet.Outcome.DID_NOT_RUN):
        ratchet.describe(result, file, updating, out)
    elif updating:
        describe_update(result, found, out)
    else:
        describe_check(result, found, file, out)


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
    current = {p: ls for p, ls in measure(root, tracked_files(root, excluded)).items() if ls}
    areas = group_by_area(root, current)
    total = sum(len(ls) for ls in current.values())
    out.write(f"# Comment debt: {total} lines in {len(current)} files\n\n")
    out.write("Columns: lines, of which rationale (workaround, deliberately, for now, TODO ...)\n")
    for name in sorted(areas, key=lambda a: -sum(n for _, n, _ in areas[a])):
        write_area(name, areas[name], out)
    return 0


def labels():
    return " and ".join(languages.LANGUAGES[name].label for name in LANGUAGES)


def main(argv=None, root=None, baseline=None, out=sys.stdout):
    parser = argparse.ArgumentParser(
        description=f"Ratchet on comment lines in tracked {labels()} files.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="lower the baseline to match the tree")
    mode.add_argument("--status", action="store_true", help="print the remaining debt, by area")
    parser.add_argument("--baseline", help=f"baseline file (default: {project_files.COMMENT_DEBT_BASELINE} at the repo root)")
    parser.add_argument("--exclude", action="append", default=[], metavar="PREFIX", help="skip tracked paths with this prefix")
    args = parser.parse_args(argv)
    if args.baseline is not None and not args.baseline.strip():
        out.write("--baseline was given an empty path\n")
        return ratchet.exit_code(ratchet.DID_NOT_RUN)
    try:
        root = root or project_files.git_root()
    except ToolError as error:
        out.write(f"comment-debt: {error}\n")
        return ratchet.exit_code(ratchet.DID_NOT_RUN)
    return run_mode(args, root, baseline, out)


def run_mode(args, root, baseline, out):
    if args.status:
        return status(root, args.exclude, out)
    file = Path(baseline or args.baseline or project_files.comment_debt_baseline(root))
    found = findings(root, args.exclude)
    result = ratchet.settle(found, file, args.update)
    describe(result, found, file, args.update, out)
    return ratchet.exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
