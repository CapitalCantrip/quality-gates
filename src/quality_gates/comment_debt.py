#!/usr/bin/env python3
import argparse
import ast
import collections
import functools
import io
import re
import sys
import tokenize
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from quality_gates import code_reader, languages, project_files, ratchet
from quality_gates.errors import Untagged


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
TAG = "comment-debt: "
UPDATE_REFUSAL = "--update only lowers the baseline. It will not record new comments.\n"
UNREAD = "could not be opened, does not parse or is not UTF-8, so its comments were not counted"
UNREAD_ADVICE = (
    "Unmeasured files fail the gate. Finish or fix them, or leave them out with settings.no-comments.exclude; "
    "the baseline keeps any entry they already have and records none for them."
)
UNREADABLE = (OSError, SyntaxError, ValueError, tokenize.TokenError)
STRING = "string"
TOP_FILES = 5
TOP_AREAS = 5
FileDebt = collections.namedtuple("FileDebt", "path lines rationale")
AreaDebt = collections.namedtuple("AreaDebt", "name lines rationale")
RATIONALE_HEADING = "lines, of which rationale (workaround, deliberately, for now, TODO ...)"
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


def debt_kinds(source):
    kinds = {**{line: code_reader.LINE for line in comment_lines(source)}, **{line: STRING for line in string_lines(source)}}
    return dict(sorted(kinds.items()))


def read_debt_kinds(syntax, source):
    comments = code_reader.read(source, syntax).comments
    kinds = {line: comment.kind for comment in comments for line in range(comment.start, comment.end + 1)}
    return dict(sorted(kinds.items()))


@dataclass(frozen=True)
class CommentLanguage:
    component: str
    checker: Callable


LANGUAGES = {
    "python": CommentLanguage("no-comments", debt_kinds),
    "rust": CommentLanguage("no-comments-rust", functools.partial(read_debt_kinds, code_reader.Syntax(line=("//",)))),
}
EXCLUDE_REFUSAL = (
    "comment-debt: --exclude is removed. Run /setup-standards: it moves the --exclude prefixes of your "
    "comment-debt commands into settings.no-comments.exclude in quality-gates.json, and the gate reads them there."
)


def checked_files(root):
    return {
        path: row.checker
        for name, row in LANGUAGES.items()
        for path in project_files.comment_gate_files(root, row.component, languages.suffixes_of([name]))
    }


def lines_in(file, checker):
    try:
        return checker(file.read_text(encoding="utf-8"))
    except UNREADABLE:
        return None


def measure(root, listed):
    return {path: lines_in(root / path, checker) for path, checker in listed.items() if (root / path).exists()}


def to_finding(path, lines):
    if lines is None:
        return ratchet.Finding(ratchet.Location(path), None, FINDING_KIND, UNREAD)
    return ratchet.Finding(ratchet.Location(path), len(lines), FINDING_KIND, ", ".join(str(n) for n in lines))


def findings(root, listed=checked_files):
    return [to_finding(path, lines) for path, lines in sorted(measure(root, listed(root)).items())]


def files_on_choosing(root, names, choice):
    return {
        path: LANGUAGES[name].checker
        for name in names
        for path in project_files.comment_gate_files_under(root, choice, languages.suffixes_of([name]))
    }


def chosen_only_on_asking():
    return frozenset(row.component for row in LANGUAGES.values()) - project_files.ON_WITHOUT_A_CHOICE_FILE


def languages_of(components):
    return frozenset(name for name, row in LANGUAGES.items() if row.component in components)


def findings_on_choosing(root, names, choice):
    return findings(root, lambda _: files_on_choosing(root, names, choice))


def written_in(names):
    return lambda path: languages.language_of_file(path) in names


def with_debt(measured):
    return {path: lines for path, lines in measured.items() if lines}


def unread_lines(measured):
    unread = sorted(path for path, lines in measured.items() if lines is None)
    if not unread:
        return []
    noun = "file" if len(unread) == 1 else "files"
    return [f"# {len(unread)} {noun} could not be read: {', '.join(unread)}\n"]


def total_line(label, current):
    return f"# {label}: {sum(len(lines) for lines in current.values())} lines in {len(current)} files\n"


def kind_rows(current):
    counts = collections.Counter(kind for lines in current.values() for kind in lines.values())
    return [f"{count:5}  {kind}" for kind, count in sorted(counts.items())]


def area_totals(areas):
    return [AreaDebt(name, sum(r.lines for r in rows), sum(r.rationale for r in rows)) for name, rows in areas.items()]


def area_rows(areas):
    ranked = sorted(area_totals(areas), key=lambda t: (-t.lines, t.name))
    return [f"{total.lines:5} {total.rationale:4}  {total.name}" for total in ranked]


def most(counted, limit):
    ranked = sorted((-count, label) for label, count in counted if count)[:limit]
    return [f"{-negated:5}  {label}" for negated, label in ranked]


def report_sections(root, current):
    areas = group_by_area(root, current)
    files = [row for rows in areas.values() for row in rows]
    return (("By kind", kind_rows(current)), (f"By area: {RATIONALE_HEADING}", area_rows(areas)),
            ("Most comment lines", most(((f.path, f.lines) for f in files), TOP_FILES)),
            ("Most rationale lines", most(((f.path, f.rationale) for f in files), TOP_FILES)),
            ("Areas with most rationale lines", most(((a.name, a.rationale) for a in area_totals(areas)), TOP_AREAS)))


def report_files(root, name):
    suffixes = languages.suffixes_of([name])
    return {path: LANGUAGES[name].checker for path in project_files.comment_gate_files_after_setup(root, suffixes)}


def debt_report(root, name, files, out):
    measured = measure(root, files)
    current = with_debt(measured)
    out.write(total_line(f"{languages.LANGUAGES[name].label} comment debt", current))
    out.writelines(unread_lines(measured))
    for heading, rows in report_sections(root, current):
        if rows:
            out.write(f"\n## {heading}\n" + "".join(row + "\n" for row in rows))


def debt_report_text(root, name, choice):
    out = io.StringIO()
    debt_report(root, name, files_on_choosing(root, [name], choice), out)
    return out.getvalue()


def describe_failed(settled, out):
    for verdict in settled.failed:
        allowed = verdict.allowed or 0
        out.write(f"FAIL {verdict.location.key}: {verdict.now} comment lines, baseline allows {allowed} — lines {settled.shown(verdict)}\n")
    out.write(
        "\nNew comments are not allowed (no-code-comments policy). Move the knowledge to a test, "
        "a named constant, an ADR or an issue — see the quality-gates README for where each kind goes.\n"
    )


def describe_behind(behind, file, out):
    for verdict in behind:
        if verdict.now is not None:
            out.write(f"PAID {verdict.location.key}: {verdict.now} lines, baseline still says {verdict.allowed}\n")
    for verdict in behind:
        if verdict.now is None:
            out.write(f"GONE {verdict.location.key}: in the baseline but no longer in scope\n")
    out.write(
        f"\nThe baseline is behind. Run `comment-debt --update` "
        f"and commit {file.name} so the paid debt cannot come back.\n"
    )


def describe_passed(result, out):
    allowed = [verdict.allowed for verdict in result.verdicts if verdict.allowed is not None]
    out.write(f"comment debt: {sum(allowed)} lines in {len(allowed)} files, none new\n")


def describe_recorded(counts, out):
    out.write(f"baseline: {sum(counts.values())} lines in {len(counts)} files\n")


WORDING = ratchet.Wording(describe_failed, describe_behind, describe_passed, describe_recorded, UPDATE_REFUSAL,
                          UNREAD, UNREAD_ADVICE)


def area(path):
    parts = path.split("/")
    return "/".join(parts[:2]) if len(parts) > 2 else parts[0]


def rationale_count(root, path, lines):
    text = (root / path).read_text(encoding="utf-8").split(code_reader.NEWLINE)
    return sum(1 for n in lines if RATIONALE.search(text[n - 1]))


def group_by_area(root, current):
    areas = {}
    for path, lines in current.items():
        areas.setdefault(area(path), []).append(FileDebt(path, len(lines), rationale_count(root, path, lines)))
    return areas


def write_area(name, rows, out):
    rows = sorted(rows, key=lambda r: (-r.rationale, -r.lines, r.path))
    out.write(f"\n## {name} — {sum(r.lines for r in rows)} lines\n")
    for row in rows:
        out.write(f"{row.lines:5} {row.rationale:4}  {row.path}\n")


def status(root, out):
    measured = measure(root, checked_files(root))
    current = with_debt(measured)
    areas = group_by_area(root, current)
    out.write(total_line("Comment debt", current))
    out.writelines(unread_lines(measured))
    out.write(f"\nColumns: {RATIONALE_HEADING}\n")
    for name in sorted(areas, key=lambda a: (-sum(r.lines for r in areas[a]), a)):
        write_area(name, areas[name], out)


def labels():
    return " and ".join(languages.LANGUAGES[name].label for name in LANGUAGES)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description=f"Ratchet on comment lines in {labels()} files in scope.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="lower the baseline to match the tree")
    mode.add_argument("--status", action="store_true", help="print the remaining debt, by area")
    mode.add_argument("--report", choices=sorted(LANGUAGES), metavar="LANGUAGE",
                      help="print one language's comment debt, chosen or not")
    parser.add_argument("--baseline", help=f"baseline file (default: {project_files.COMMENT_DEBT_BASELINE} at the repo root)")
    parser.add_argument("--exclude", action="append", default=[], help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def chosen_languages(root):
    choice = project_files.checked_choice(root)
    return frozenset(name for name, row in LANGUAGES.items() if project_files.is_chosen(choice, row.component))


def asked(args, root, baseline) -> ratchet.Asked:
    if args.status or args.report:
        return ratchet.Asked(judged=False)
    file = Path(baseline or args.baseline or project_files.comment_debt_baseline(root))
    return ratchet.Asked(file, args.update, covers=written_in(chosen_languages(root)))


def shown_first(args, root, out):
    if args.status:
        status(root, out)
    if args.report:
        debt_report(root, args.report, report_files(root, args.report), out)


def gate(argv, root, baseline=None, out=None):
    out = sys.stdout if out is None else out
    args = parse_args(argv)
    if args.exclude:
        raise Untagged(EXCLUDE_REFUSAL)
    if args.baseline is not None and not args.baseline.strip():
        raise Untagged("--baseline was given an empty path")
    root = root or project_files.git_root()
    shown_first(args, root, out)
    return ratchet.enforce(functools.partial(findings, root), asked(args, root, baseline), out, WORDING)


def main(argv=None, root=None, baseline=None, out=None):
    out = sys.stdout if out is None else out
    return ratchet.run_gate(functools.partial(gate, baseline=baseline, out=out), argv, root, TAG, out)


if __name__ == "__main__":
    sys.exit(main())
