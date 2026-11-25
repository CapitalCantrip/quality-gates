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
from typing import Callable, Optional

from quality_gates import code_reader, languages, project_files, ratchet
from quality_gates.errors import Untagged


PRAGMA = re.compile(
    r"#\s*(?:"
    r"noqa(?::\s*[A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*)?"
    r"|type:\s*ignore(?:\[[\w\s,-]+\])?"
    r"|fmt:\s*(?:on|off|skip)"
    r")\s*$"
)
PYTHON_SILENCER = re.compile(r"#\s*(?:pragma|PRAGMA)[:\s]?\s*(?:no|NO)\s*(?:cover|COVER|branch|BRANCH)")
CODING = re.compile(r"^#.*coding[:=]")
FINDING_KIND = "comment lines"
SILENCER_KIND = "silencer"
TAG = "comment-debt: "
UPDATE_REFUSAL = "--update only lowers the baseline. It will not record new comments.\n"
UNREAD_CAUSE = "could not be opened, does not parse or is not UTF-8"
UNREAD = f"{UNREAD_CAUSE}, so its comments were not counted"
UNREAD_ADVICE = (
    "Unmeasured files fail the gate. Finish or fix them, or leave them out with settings.no-comments.exclude; "
    "the baseline keeps any entry they already have and records none for them."
)
UNREAD_SILENCERS = f"{UNREAD_CAUSE}, so its silencers were not counted"
UNREAD_SILENCERS_ADVICE = "The silencer baseline keeps any entry an unmeasured file already has."
SILENCER_REFUSAL = "--update only lowers the silencer baseline. It will not record a new silencer.\n"
SILENCER_ADVICE = (
    "\nA silencer switches off one of the quality gates for the code it marks, so a new one is not allowed. "
    "Remove the marker and test the code it hides.\n"
)
UNREADABLE = (OSError, SyntaxError, ValueError, tokenize.TokenError)
STRING = "string"
TOP_FILES = 5
TOP_AREAS = 5
FileDebt = collections.namedtuple("FileDebt", "path lines rationale")
AreaDebt = collections.namedtuple("AreaDebt", "name lines rationale")
RATIONALE_HEADING = "lines, of which rationale (workaround, deliberately, for now, TODO ...)"
EVERY_FILE = f"Every file: {RATIONALE_HEADING}"
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


@dataclass(frozen=True)
class FileReading:
    debt: dict
    silencers: tuple


def python_kinds(source):
    kinds = {**{line: code_reader.LINE for line in comment_lines(source)}, **{line: STRING for line in string_lines(source)}}
    return dict(sorted(kinds.items()))


def python_silencers(reading, source):
    return tuple(number for number, line in enumerate(source.split(code_reader.NEWLINE), 1) if PYTHON_SILENCER.search(line))


def silences_nothing(reading, source):
    return ()


def in_comments(pattern):
    return lambda reading, source: tuple(sorted({c.start for c in reading.comments if pattern.search(c.text)}))


SAFETY_START = "// SAFETY:"
UNSAFE_BELOW = re.compile(r"\bunsafe\s*\{|^\s*unsafe\s+impl\b")


def own_line_comments(reading, source):
    lines = source.split(code_reader.NEWLINE)
    return {
        comment.start: comment for comment in reading.comments
        if comment.kind == code_reader.LINE and lines[comment.start - 1].strip() == comment.text.strip()
    }


def run_from(own, number):
    run = [number]
    while run[-1] + 1 in own:
        run.append(run[-1] + 1)
    return run


def unsafe_below(code, line):
    return line < len(code) and bool(UNSAFE_BELOW.search(code[line]))


def safety_comments(reading, source):
    own, code = own_line_comments(reading, source), reading.blanked.split(code_reader.NEWLINE)
    runs = [run_from(own, number) for number, comment in own.items() if comment.text.startswith(SAFETY_START)]
    return {own[number] for run in runs if unsafe_below(code, run[-1]) for number in run}


@dataclass(frozen=True)
class CommentSyntax:
    syntax: code_reader.Syntax
    pragma: re.Pattern
    conventions: dict
    shebang: bool = False

    def exempts(self, comment):
        if self.shebang and comment.start == 1 and comment.text.startswith(languages.SHEBANG):
            return True
        return bool(self.pragma.fullmatch(comment.text))


def allowed_by(language, conventions, reading, source):
    return set().union(*(language.conventions[name](reading, source) for name in conventions
                         if name in language.conventions))


def read_comments(language, source, conventions):
    reading = code_reader.read(source, language.syntax)
    allowed = allowed_by(language, conventions, reading, source)
    counted = [c for c in reading.comments if c not in allowed and not language.exempts(c)]
    kinds = {line: comment.kind for comment in counted for line in range(comment.start, comment.end + 1)}
    return reading, dict(sorted(kinds.items()))


RUST = CommentSyntax(code_reader.Syntax(
    line=("//",),
    block=(("/*", "*/"),),
    nested=True,
    doc=(r"///(?!/)", r"//!", r"/\*\*(?![*/])", r"/\*!"),
    literals=(
        code_reader.Literal(r'r#*"', r'r(#*)"[\s\S]*?"\1'),
        code_reader.Literal(r'"', r'"(?:\\[\s\S]|[^"\\])*"'),
        code_reader.Literal(r"'", r"'(?:\\(?:u\{[0-9a-fA-F]+\}|x[0-9a-fA-F]{2}|[\s\S])|[^'\\\n])'"),
    ),
), re.compile(r"//\s*@generated\s*"), {"rust-safety": safety_comments})


BEFORE_A_REGEX = r"[(,=:;!&|?{\[*%>^~]"
OPERATORS_BEFORE_A_REGEX = (r"(?<!\+)\+", r"(?<!-)-", r"<\s", r"[\w$\]}]\sof")
KEYWORDS_BEFORE_A_REGEX = ("return", "typeof", "instanceof", "in", "new", "void", "delete", "case", "yield",
                           "await", "else", "do")
WHOLE_WORD = r"(?<![\w$.#])"
REGEX_MAY_START = "(?:" + "|".join([r"\A", f"(?<={BEFORE_A_REGEX})"]
                                   + [f"(?<={operator})" for operator in OPERATORS_BEFORE_A_REGEX]
                                   + [f"(?<={WHOLE_WORD}{word})" for word in KEYWORDS_BEFORE_A_REGEX]) + r")\s*"
TEMPLATE_PIECE = r"(?:\\[\s\S]|\$(?!\{)|[^`\\$])*(?:`|\$\{)"
ESLINT_RULES = r"[@\w/-]+(?:\s*,\s*[@\w/-]+)*"
TYPESCRIPT_PRAGMA = rf"eslint-(?:disable(?:-next-line|-line)?|enable)(?:\s+{ESLINT_RULES})?|@ts-expect-error|@ts-ignore|prettier-ignore"

TYPESCRIPT = CommentSyntax(code_reader.Syntax(
    line=("//",),
    block=(("/*", "*/"),),
    doc=(r"/\*\*(?![*/])", r"///\s*<reference\b"),
    literals=(
        code_reader.Literal(r'"', r'"(?:\\[\s\S]|[^"\\\n])*"'),
        code_reader.Literal(r"'", r"'(?:\\[\s\S]|[^'\\\n])*'"),
        code_reader.Literal(r"`", r"`" + TEMPLATE_PIECE, code_reader.Interpolation(("{", "}"), TEMPLATE_PIECE)),
        code_reader.Literal(REGEX_MAY_START + r"/(?![/*])",
                            r"\s*/(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+/[A-Za-z]*"),
    ),
), re.compile(rf"//\s*(?:{TYPESCRIPT_PRAGMA})\s*|/\*\s*(?:{TYPESCRIPT_PRAGMA})\s*\*/"), {})


SWIFT_PIECE = r'(?:\\(?!\()[\s\S]|[^"\\\n])*(?:"|\\\()'
SWIFT_MULTILINE_PIECE = r'(?:\\(?!\()[\s\S]|(?!""")[^\\])*(?:"""|\\\()'
SWIFT_INTERPOLATION = ("(", ")")

SWIFT = CommentSyntax(code_reader.Syntax(
    line=("//",),
    block=(("/*", "*/"),),
    nested=True,
    doc=(r"///(?!/)", r"/\*\*(?![*/])"),
    literals=(
        code_reader.Literal(r'#+"""', r'(#+)"""[\s\S]*?"""\1'),
        code_reader.Literal(r'#+"', r'(#+)"[^\n]*?"\1'),
        code_reader.Literal(r'"""', r'"""' + SWIFT_MULTILINE_PIECE,
                            code_reader.Interpolation(SWIFT_INTERPOLATION, SWIFT_MULTILINE_PIECE)),
        code_reader.Literal(r'"', r'"' + SWIFT_PIECE, code_reader.Interpolation(SWIFT_INTERPOLATION, SWIFT_PIECE)),
    ),
), re.compile(r"//\s*swiftlint:(?:disable|enable)(?::(?:next|this|previous))?(?:\s+[\w-]+)*\s*"), {})


SHELL_WORD_BREAK = r"\s;&|()<>"
HEREDOC_OPENER = (r"<<{dash}[ \t]*(['\"])?\\?((?(1)[^'\"\n]+|[^" + SHELL_WORD_BREAK + r"'\"\\]+))(?(1)\1)")
HEREDOC_BODY = r"(?:[^\n]*\n)*?{tabs}\g<2>\r?(?=\n|\Z)"
DOUBLE_QUOTED_PIECE = r'(?:\\[\s\S]|\$(?!\()|[^"\\$])*(?:"|\$\()'
ARITHMETIC_OPENER = r"\(\("

SHELL = CommentSyntax(code_reader.Syntax(
    line=(rf"(?<![^{SHELL_WORD_BREAK}])#",),
    literals=(
        code_reader.Literal(r"\\", r"\\[\s\S]"),
        code_reader.Literal(r"\$'", r"\$'(?:\\[\s\S]|[^'\\])*'"),
        code_reader.Literal(r"'", r"'[^']*'"),
        code_reader.Literal(r'"', r'"' + DOUBLE_QUOTED_PIECE, code_reader.Interpolation(("(", ")"), DOUBLE_QUOTED_PIECE)),
        code_reader.Literal(ARITHMETIC_OPENER, ARITHMETIC_OPENER, balanced=code_reader.Balanced(("(", ")"), "))")),
        code_reader.Literal(r"(?<!<)<<-", HEREDOC_OPENER.format(dash="-"), body=HEREDOC_BODY.format(tabs=r"\t*")),
        code_reader.Literal(r"(?<!<)<<(?![<-])", HEREDOC_OPENER.format(dash=""), body=HEREDOC_BODY.format(tabs="")),
    ),
), re.compile(r"#\s*shellcheck\s+disable=SC\d+(?:\s*,\s*SC\d+)*\s*"), {}, shebang=True)


@dataclass(frozen=True)
class CommentLanguage:
    component: str
    silencer: Callable
    syntax: Optional[CommentSyntax] = None

    def reading(self, source, conventions):
        if self.syntax is None:
            code, debt = None, python_kinds(source)
        else:
            code, debt = read_comments(self.syntax, source, conventions)
        silenced = self.silencer(code, source)
        return FileReading({line: kind for line, kind in debt.items() if line not in silenced}, silenced)


LANGUAGES = {
    "python": CommentLanguage("no-comments", python_silencers),
    "rust": CommentLanguage("no-comments-rust", silences_nothing, RUST),
    "typescript": CommentLanguage("no-comments-typescript", silences_nothing, TYPESCRIPT),
    "swift": CommentLanguage("no-comments-swift", silences_nothing, SWIFT),
    "shell": CommentLanguage("no-comments-shell", silences_nothing, SHELL),
}


EXCLUDE_REFUSAL = (
    "comment-debt: --exclude is removed. Run /setup-standards: it moves the --exclude prefixes of your "
    "comment-debt commands into settings.no-comments.exclude in quality-gates.json, and the gate reads them there."
)


def reader_of(name, choice):
    return functools.partial(LANGUAGES[name].reading, conventions=choice.conventions if choice else ())


def files_of(root, names, choice):
    return {path: reader_of(name, choice)
            for path, name in project_files.comment_gate_files_under(root, choice, names).items()}


def checked_files(root):
    choice = project_files.checked_choice(root)
    return files_of(root, [name for name, row in LANGUAGES.items() if project_files.is_chosen(choice, row.component)],
                    choice)


def reading_of(file, reader):
    try:
        return reader(file.read_text(encoding="utf-8"))
    except UNREADABLE:
        return None


def measure(root, listed):
    return {path: reading_of(root / path, reader) for path, reader in listed.items() if (root / path).exists()}


def debts(measured):
    return {path: None if reading is None else reading.debt for path, reading in measured.items()}


def silencers_in(measured):
    return {path: None if reading is None else reading.silencers for path, reading in measured.items()}


def to_finding(path, lines):
    if lines is None:
        return ratchet.Finding(ratchet.Location(path), None, FINDING_KIND, UNREAD)
    return ratchet.Finding(ratchet.Location(path), len(lines), FINDING_KIND, ", ".join(str(n) for n in lines))


def silencer_finding(path, lines):
    if lines is None:
        return ratchet.Finding(ratchet.Location(path), None, SILENCER_KIND, UNREAD_SILENCERS)
    return ratchet.Finding(ratchet.Location(path), len(lines), SILENCER_KIND, ", ".join(str(n) for n in lines))


def comment_findings(measured):
    return [to_finding(path, lines) for path, lines in sorted(debts(measured).items())]


def silencer_findings(measured):
    return [silencer_finding(path, lines) for path, lines in sorted(silencers_in(measured).items())]


def chosen_only_on_asking():
    return frozenset(row.component for row in LANGUAGES.values()) - project_files.ON_WITHOUT_A_CHOICE_FILE


def languages_of(components):
    return frozenset(name for name, row in LANGUAGES.items() if row.component in components)


def measured_on_choosing(root, names, choice):
    return measure(root, files_of(root, names, choice))


def written_in(root, names):
    return lambda path: project_files.language_among(root, path, names) is not None


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


def every_file_rows(files):
    return [f"{f.lines:5} {f.rationale:4}  {f.path}" for f in sorted(files, key=lambda f: (-f.lines, f.path))]


def report_sections(root, current):
    areas = group_by_area(root, current)
    files = [row for rows in areas.values() for row in rows]
    return (("By kind", kind_rows(current)), (f"By area: {RATIONALE_HEADING}", area_rows(areas)),
            ("Most comment lines", most(((f.path, f.lines) for f in files), TOP_FILES)),
            ("Most rationale lines", most(((f.path, f.rationale) for f in files), TOP_FILES)),
            ("Areas with most rationale lines", most(((a.name, a.rationale) for a in area_totals(areas)), TOP_AREAS)),
            (EVERY_FILE, every_file_rows(files)))


def report_files(root, name, choice):
    return {path: reader_of(language, choice)
            for path, language in project_files.comment_gate_files_after_setup(root, choice, [name]).items()}


def silencer_total_line(measured):
    held = {path: lines for path, lines in silencers_in(measured).items() if lines}
    if not held:
        return []
    return [f"# Silencers: {sum(len(lines) for lines in held.values())} in {len(held)} files\n"]


def debt_report(root, name, files, out, left_out=()):
    measured = measure(root, files)
    debt = debts(measured)
    current = with_debt(debt)
    out.write(total_line(f"{languages.LANGUAGES[name].label} comment debt", current))
    out.writelines(unread_lines(debt))
    out.writelines(silencer_total_line(measured))
    for heading, rows in report_sections(root, current):
        if rows and heading not in left_out:
            out.write(f"\n## {heading}\n" + "".join(row + "\n" for row in rows))


def debt_report_text(root, name, choice):
    out = io.StringIO()
    debt_report(root, name, report_files(root, name, choice), out, left_out=(EVERY_FILE,))
    return out.getvalue()


def describe_failed(settled, out):
    for verdict in settled.failed:
        allowed = verdict.allowed or 0
        out.write(f"FAIL {verdict.location.key}: {verdict.now} comment lines, baseline allows {allowed} — lines {settled.shown(verdict)}\n")
    out.write(
        "\nNew comments are not allowed (no-code-comments policy). Move the knowledge to a test, "
        "a named constant, an ADR or an issue — see the quality-gates README for where each kind goes.\n"
    )


def describe_behind(behind, file, out, noun="lines"):
    for verdict in behind:
        if verdict.now is not None:
            out.write(f"PAID {verdict.location.key}: {verdict.now} {noun}, baseline still says {verdict.allowed}\n")
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


def describe_silencers_failed(settled, out):
    for verdict in settled.failed:
        allowed = verdict.allowed or 0
        out.write(f"FAIL {verdict.location.key}: {verdict.now} silencers, baseline allows {allowed} — lines {settled.shown(verdict)}\n")
    out.write(SILENCER_ADVICE)


def describe_silencers_behind(behind, file, out):
    describe_behind(behind, file, out, noun="silencers")


def describe_silencers_passed(result, out):
    allowed = [verdict.allowed for verdict in result.verdicts if verdict.allowed is not None]
    if allowed:
        out.write(f"silencers: {sum(allowed)} in {len(allowed)} files, none new\n")


def describe_silencers_recorded(counts, out):
    if counts:
        out.write(f"silencer baseline: {sum(counts.values())} in {len(counts)} files\n")


WORDING = ratchet.Wording(describe_failed, describe_behind, describe_passed, describe_recorded, UPDATE_REFUSAL,
                          UNREAD, UNREAD_ADVICE)
SILENCER_WORDING = ratchet.Wording(describe_silencers_failed, describe_silencers_behind, describe_silencers_passed,
                                   describe_silencers_recorded, SILENCER_REFUSAL, UNREAD_SILENCERS,
                                   UNREAD_SILENCERS_ADVICE)


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
    debt = debts(measured)
    current = with_debt(debt)
    areas = group_by_area(root, current)
    out.write(total_line("Comment debt", current))
    out.writelines(unread_lines(debt))
    out.writelines(silencer_total_line(measured))
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
    ratchet.add_rerecord(mode)
    mode.add_argument("--status", action="store_true", help="print the remaining debt, by area")
    mode.add_argument("--report", choices=sorted(LANGUAGES), metavar="LANGUAGE",
                      help="print one language's comment debt, chosen or not")
    parser.add_argument("--baseline", help=f"baseline file (default: {project_files.COMMENT_DEBT_BASELINE} at the repo root)")
    parser.add_argument("--exclude", action="append", default=[], help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def chosen_in(choice):
    return frozenset(name for name, row in LANGUAGES.items() if project_files.is_chosen(choice, row.component))


def chosen_languages(root):
    return chosen_in(project_files.checked_choice(root))


def asked(args, root, baseline) -> ratchet.Asked:
    if args.status or args.report:
        return ratchet.Asked(judged=False)
    file = Path(baseline or args.baseline or project_files.comment_debt_baseline(root))
    return ratchet.Asked(file, args.update or args.rerecord, covers=written_in(root, chosen_languages(root)),
                         rerecording=args.rerecord)


def silencers_asked(args, root):
    if args.status or args.report:
        return ratchet.Asked(judged=False)
    return ratchet.silencer_asked(root, args.update, covers=written_in(root, chosen_languages(root)))


def enforced(args, root, baseline, out):
    measured = functools.lru_cache(maxsize=None)(lambda: measure(root, checked_files(root)))
    comments_wanted = ratchet.readable(asked(args, root, baseline), out)
    silencers_wanted = ratchet.readable(silencers_asked(args, root), out)
    comments = ratchet.enforce(lambda: comment_findings(measured()), comments_wanted, out, WORDING)
    silencers = ratchet.enforce(lambda: silencer_findings(measured()), silencers_wanted, out, SILENCER_WORDING)
    return ratchet.Result(comments.verdicts + silencers.verdicts)


def shown_first(args, root, out):
    if args.status:
        status(root, out)
    if args.report:
        debt_report(root, args.report, report_files(root, args.report, project_files.checked_choice(root)), out)


def gate(argv, root, baseline=None, out=None):
    out = sys.stdout if out is None else out
    args = parse_args(argv)
    if args.exclude:
        raise Untagged(EXCLUDE_REFUSAL)
    if args.baseline is not None and not args.baseline.strip():
        raise Untagged("--baseline was given an empty path")
    root = root or project_files.git_root()
    shown_first(args, root, out)
    return enforced(args, root, baseline, out)


def main(argv=None, root=None, baseline=None, out=None):
    out = sys.stdout if out is None else out
    return ratchet.run_gate(functools.partial(gate, baseline=baseline, out=out), argv, root, TAG, out)


if __name__ == "__main__":
    sys.exit(main())
