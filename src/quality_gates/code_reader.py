import functools
import re
from dataclasses import dataclass
from typing import Optional

LINE = "line"
BLOCK = "block"
DOC = "doc"
STRING = "string"
BRACKET = "bracket"
NEWLINE = "\n"
CARRIAGE_RETURN = "\r"
NOT_A_LINE_END = re.compile(r"[^\r\n]")
BLANK = " "
NOTHING = "(?!)"


@dataclass(frozen=True)
class Interpolation:
    pair: tuple
    rest: str


@dataclass(frozen=True)
class Literal:
    start: str
    whole: str
    interpolation: Optional[Interpolation] = None


@dataclass(frozen=True)
class Syntax:
    line: tuple = ()
    block: tuple = ()
    nested: bool = False
    doc: tuple = ()
    literals: tuple = ()


@dataclass(frozen=True)
class Comment:
    kind: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Reading:
    comments: tuple
    blanked: str


@dataclass(frozen=True)
class Token:
    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class Scanner:
    syntax: Syntax
    opener: re.Pattern
    literals: tuple
    doc: re.Pattern
    rests: tuple


@dataclass
class Interpolating:
    literal: int
    depth: int = 0


@dataclass
class Inside:
    scanner: Scanner
    open: list

    @property
    def syntax(self):
        return self.scanner.syntax


def group(name, pattern):
    return f"(?P<{name}>{pattern})"


def alternatives(patterns):
    return re.compile("|".join(patterns) or NOTHING)


def bracket_opener(literals):
    marks = sorted({mark for literal in literals if literal.interpolation for mark in literal.interpolation.pair})
    return [group(BRACKET, "|".join(map(re.escape, marks)))] if marks else []


def rest_of(literal):
    return re.compile(literal.interpolation.rest) if literal.interpolation else None


@functools.lru_cache(maxsize=None)
def scanner_for(syntax):
    openers = [group(f"{LINE}{n}", marker) for n, marker in enumerate(syntax.line)]
    openers += [group(f"{BLOCK}{n}", re.escape(pair[0])) for n, pair in enumerate(syntax.block)]
    openers += [group(f"{STRING}{n}", literal.start) for n, literal in enumerate(syntax.literals)]
    openers += bracket_opener(syntax.literals)
    literals = tuple(re.compile(literal.whole) for literal in syntax.literals)
    rests = tuple(map(rest_of, syntax.literals))
    return Scanner(syntax, alternatives(openers), literals, alternatives(syntax.doc), rests)


def line_comment_end(source, start):
    end = source.find(NEWLINE, start)
    end = len(source) if end == -1 else end
    return end - 1 if source[start:end].endswith(CARRIAGE_RETURN) else end


def block_ends(pair, nested):
    opening, closing = pair
    return re.compile(re.escape(closing) + ("|" + re.escape(opening) if nested else ""))


def block_comment_end(source, start, pair, nested):
    ends, depth, at = block_ends(pair, nested), 1, start + len(pair[0])
    while depth:
        found = ends.search(source, at)
        if not found:
            return len(source)
        depth += -1 if found.group() == pair[1] else 1
        at = found.end()
    return at


def piece(source, start, at, literal, pattern, inside):
    found = pattern.match(source, at)
    if not found:
        return None
    interpolation = inside.syntax.literals[literal].interpolation
    if interpolation and found.group().endswith(interpolation.pair[0]):
        inside.open.append(Interpolating(literal))
    return Token(STRING, start, found.end())


def literal_at(source, start, literal, inside):
    return piece(source, start, start, literal, inside.scanner.literals[literal], inside)


def bracket_at(source, start, inside):
    if not inside.open:
        return None
    top, mark = inside.open[-1], source[start]
    opening, closing = inside.syntax.literals[top.literal].interpolation.pair
    if mark == opening:
        top.depth += 1
        return None
    if mark != closing:
        return None
    if top.depth:
        top.depth -= 1
        return None
    inside.open.pop()
    return piece(source, start, start + len(closing), top.literal, inside.scanner.rests[top.literal], inside)


def token_at(found, source, inside):
    name, start = found.lastgroup, found.start()
    if name.startswith(LINE):
        return Token(LINE, start, line_comment_end(source, start))
    if name.startswith(STRING):
        return literal_at(source, start, int(name[len(STRING):]), inside)
    if name == BRACKET:
        return bracket_at(source, start, inside)
    pair = inside.syntax.block[int(name[len(BLOCK):])]
    return Token(BLOCK, start, block_comment_end(source, start, pair, inside.syntax.nested))


def tokens(source, scanner):
    inside = Inside(scanner, [])
    found = scanner.opener.search(source)
    while found:
        token = token_at(found, source, inside)
        if token:
            yield token
        found = scanner.opener.search(source, token.end if token else found.start() + 1)


def blanked(source, spans):
    pieces, at = [], 0
    for token in spans:
        pieces += [source[at:token.start], NOT_A_LINE_END.sub(BLANK, source[token.start:token.end])]
        at = token.end
    return "".join(pieces) + source[at:]


def read(source: str, syntax: Syntax) -> Reading:
    scanner, comments, spans, line, counted = scanner_for(syntax), [], [], 1, 0
    for token in tokens(source, scanner):
        spans.append(token)
        if token.kind == STRING:
            continue
        line += source.count(NEWLINE, counted, token.start)
        text = source[token.start:token.end]
        kind = DOC if scanner.doc.match(text) else token.kind
        comments.append(Comment(kind, text, line, line + text.count(NEWLINE)))
        counted = token.start
    return Reading(tuple(comments), blanked(source, spans))
