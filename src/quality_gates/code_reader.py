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
OPENER_GROUP = re.compile(r"\\g<(\d+)>")


@dataclass(frozen=True)
class Interpolation:
    pair: tuple
    rest: str


@dataclass(frozen=True)
class Balanced:
    pair: tuple
    close: str


@dataclass(frozen=True)
class Literal:
    start: str
    whole: str
    interpolation: Optional[Interpolation] = None
    body: Optional[str] = None
    balanced: Optional[Balanced] = None
    lead: str = ""


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
    logical_line: re.Pattern
    leads: tuple


@dataclass
class Interpolating:
    literal: int
    depth: int = 0


@dataclass
class Inside:
    scanner: Scanner
    open: list
    bodies: list

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
    openers += [group(f"{STRING}{n}", literal.lead + literal.start) for n, literal in enumerate(syntax.literals)]
    openers += bracket_opener(syntax.literals)
    literals = tuple(re.compile(literal.whole) for literal in syntax.literals)
    rests = tuple(map(rest_of, syntax.literals))
    leads = tuple(re.compile(literal.lead) for literal in syntax.literals)
    return Scanner(syntax, alternatives(openers), literals, alternatives(syntax.doc), rests, logical_line(syntax.line),
                   leads)


def logical_line(markers):
    comment = "|".join(markers) or NOTHING
    return re.compile(rf"(?:\\[\s\S]|(?!{comment})[^\n\\])*(?:(?:{comment})[^\n]*)?\n")


def line_comment_end(source, start):
    end = source.find(NEWLINE, start)
    end = len(source) if end == -1 else end
    return end - 1 if source[start:end].endswith(CARRIAGE_RETURN) else end


def block_ends(pair, nested):
    opening, closing = pair
    return re.compile(re.escape(closing) + ("|" + re.escape(opening) if nested else ""))


def closing_end(source, start, pair, nested):
    ends, depth, at = block_ends(pair, nested), 1, start + len(pair[0])
    while depth:
        found = ends.search(source, at)
        if not found:
            return None
        depth += -1 if found.group() == pair[1] else 1
        at = found.end()
    return at


def block_comment_end(source, start, pair, nested):
    end = closing_end(source, start, pair, nested)
    return len(source) if end is None else end


def piece(source, start, at, literal, pattern, inside):
    found = pattern.match(source, at)
    if not found:
        return None
    interpolation = inside.syntax.literals[literal].interpolation
    if interpolation and found.group().endswith(interpolation.pair[0]):
        inside.open.append(Interpolating(literal))
    return Token(STRING, start, found.end())


def body_pattern(template, opener):
    return re.compile(OPENER_GROUP.sub(lambda group: re.escape(opener.group(int(group.group(1)))), template))


def body_start(source, opener, inside):
    if inside.bodies:
        return inside.bodies[-1].end + len(NEWLINE)
    line = inside.scanner.logical_line.match(source, opener.end())
    return line.end() if line else None


def body_below(source, opener, template, inside):
    start = body_start(source, opener, inside)
    found = None if start is None else body_pattern(template, opener).match(source, start)
    return Token(STRING, start, found.end()) if found else None


def opener_with_body(source, start, literal, inside):
    opener = inside.scanner.literals[literal].match(source, start)
    body = opener and body_below(source, opener, inside.syntax.literals[literal].body, inside)
    if not body:
        return None
    inside.bodies.append(body)
    return Token(STRING, start, opener.end())


def balanced_at(source, start, balanced):
    end = closing_end(source, start, balanced.pair, True)
    return Token(STRING, start, end) if end and source.endswith(balanced.close, start, end) else None


def literal_at(source, start, literal, inside):
    shape = inside.syntax.literals[literal]
    start = inside.scanner.leads[literal].match(source, start).end()
    if shape.balanced:
        return balanced_at(source, start, shape.balanced)
    if shape.body:
        return opener_with_body(source, start, literal, inside)
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


def step(found, source, inside):
    if inside.bodies and (not found or found.start() >= inside.bodies[0].start):
        bodies, inside.bodies = inside.bodies, []
        return bodies, bodies[-1].end
    token = token_at(found, source, inside)
    return ([token], token.end) if token else ([], found.start() + 1)


def tokens(source, scanner):
    inside = Inside(scanner, [], [])
    found = scanner.opener.search(source)
    while found or inside.bodies:
        produced, at = step(found, source, inside)
        yield from produced
        found = scanner.opener.search(source, at)


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
