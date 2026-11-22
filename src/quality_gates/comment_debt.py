#!/usr/bin/env python3
import argparse
import ast
import functools
import io
import re
import sys
import tokenize
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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


def read_debt_lines(language, source, conventions):
    reading = code_reader.read(source, language.syntax)
    allowed = allowed_by(language, conventions, reading, source)
    counted = [c for c in reading.comments if c not in allowed and not language.exempts(c)]
    return sorted({line for comment in counted for line in range(comment.start, comment.end + 1)})


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


BEFORE_A_REGEX = r"[(,=:;!&|?{\[+\-*%<>^~]"
KEYWORDS_BEFORE_A_REGEX = ("return", "typeof", "instanceof", "in", "of", "new", "void", "delete", "case", "yield",
                           "await", "else", "do")
REGEX_MAY_START = "(?:" + "|".join([r"\A", f"(?<={BEFORE_A_REGEX})"]
                                   + [rf"(?<=\b{word})" for word in KEYWORDS_BEFORE_A_REGEX]) + r")\s*"
TEMPLATE_PIECE = r"(?:\\[\s\S]|\$(?!\{)|[^`\\$])*(?:`|\$\{)"
ESLINT_RULES = r"[@\w/-]+(?:\s*,\s*[@\w/-]+)*"
TYPESCRIPT_PRAGMA = rf"eslint-(?:disable(?:-next-line|-line)?|enable)(?:\s+{ESLINT_RULES})?|@ts-expect-error|@ts-ignore|prettier-ignore"

TYPESCRIPT = CommentSyntax(code_reader.Syntax(
    line=("//",),
    block=(("/*", "*/"),),
    doc=(r"/\*\*(?![*/])",),
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

SHELL = CommentSyntax(code_reader.Syntax(
    line=(rf"(?<![^{SHELL_WORD_BREAK}])#",),
    literals=(
        code_reader.Literal(r"\\", r"\\[\s\S]"),
        code_reader.Literal(r"\$'", r"\$'(?:\\[\s\S]|[^'\\])*'"),
        code_reader.Literal(r"'", r"'[^']*'"),
        code_reader.Literal(r'"', r'"(?:\\[\s\S]|[^"\\])*"'),
        code_reader.Literal(r"(?<!<)<<(?!<)",
                            r"<<(-)?[ \t]*(['\"]?)\\?([A-Za-z_]\w*)\2[^\n]*\n(?:[^\n]*\n)*?(?(1)\t*)\3(?=\n|\Z)"),
    ),
), re.compile(r"#\s*shellcheck\s+disable=SC\d+(?:\s*,\s*SC\d+)*\s*"), {}, shebang=True)


@dataclass(frozen=True)
class CommentLanguage:
    component: str
    syntax: Optional[CommentSyntax] = None

    def checker(self, source, conventions):
        if self.syntax is None:
            return debt_lines(source)
        return read_debt_lines(self.syntax, source, conventions)

    def conventions(self):
        return frozenset(self.syntax.conventions) if self.syntax else frozenset()


LANGUAGES = {
    "python": CommentLanguage("no-comments"),
    "rust": CommentLanguage("no-comments-rust", RUST),
    "typescript": CommentLanguage("no-comments-typescript", TYPESCRIPT),
    "swift": CommentLanguage("no-comments-swift", SWIFT),
    "shell": CommentLanguage("no-comments-shell", SHELL),
}


def allowed_conventions():
    return frozenset().union(*(row.conventions() for row in LANGUAGES.values()))


EXCLUDE_REFUSAL = (
    "comment-debt: --exclude is removed. Run /setup-standards: it moves the --exclude prefixes of your "
    "comment-debt commands into settings.no-comments.exclude in quality-gates.json, and the gate reads them there."
)


def checker_of(name, choice):
    return functools.partial(LANGUAGES[name].checker, conventions=choice.conventions if choice else ())


def files_of(root, names, choice):
    return {path: checker_of(name, choice)
            for path, name in project_files.comment_gate_files_under(root, choice, names).items()}


def checked_files(root):
    choice = project_files.checked_choice(root)
    return files_of(root, [name for name, row in LANGUAGES.items() if project_files.is_chosen(choice, row.component)],
                    choice)


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


def files_before_choosing(root, name):
    return files_of(root, [name], project_files.checked_choice(root))


def chosen_only_on_asking():
    return frozenset(row.component for row in LANGUAGES.values()) - project_files.ON_WITHOUT_A_CHOICE_FILE


def languages_switched_on(components):
    return frozenset(name for name, row in LANGUAGES.items() if row.component in components)


def findings_on_choosing(root, names, choice):
    return findings(root, lambda _: files_of(root, names, choice))


def written_in(root, names):
    return lambda path: project_files.language_of_code_file(root, path) in names


def one_language(name):
    return functools.partial(files_before_choosing, name=name)


def debt_report(root, name, out):
    owed = [finding.number for finding in findings(root, one_language(name)) if finding.number]
    out.write(f"# {languages.LANGUAGES[name].label} comment debt: {sum(owed)} lines in {len(owed)} files\n")


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


def status(root, out):
    current = {p: ls for p, ls in measure(root, checked_files(root)).items() if ls}
    areas = group_by_area(root, current)
    total = sum(len(ls) for ls in current.values())
    out.write(f"# Comment debt: {total} lines in {len(current)} files\n\n")
    out.write("Columns: lines, of which rationale (workaround, deliberately, for now, TODO ...)\n")
    for name in sorted(areas, key=lambda a: -sum(n for _, n, _ in areas[a])):
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
    return ratchet.Asked(file, args.update, covers=written_in(root, chosen_languages(root)))


def shown_first(args, root, out):
    if args.status:
        status(root, out)
    if args.report:
        debt_report(root, args.report, out)


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
