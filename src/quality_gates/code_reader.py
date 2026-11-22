import functools
import re
from dataclasses import dataclass

LINE = "line"
BLOCK = "block"
DOC = "doc"
STRING = "string"
NEWLINE = "\n"
CARRIAGE_RETURN = "\r"
NOT_A_LINE_END = re.compile(r"[^\r\n]")
BLANK = " "
NOTHING = "(?!)"


@dataclass(frozen=True)
class Literal:
    start: str
    whole: str


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


def group(name, pattern):
    return f"(?P<{name}>{pattern})"


def alternatives(patterns):
    return re.compile("|".join(patterns) or NOTHING)


@functools.lru_cache(maxsize=None)
def scanner_for(syntax):
    openers = [group(f"{LINE}{n}", marker) for n, marker in enumerate(syntax.line)]
    openers += [group(f"{BLOCK}{n}", re.escape(pair[0])) for n, pair in enumerate(syntax.block)]
    openers += [group(f"{STRING}{n}", literal.start) for n, literal in enumerate(syntax.literals)]
    literals = tuple(re.compile(literal.whole) for literal in syntax.literals)
    return Scanner(syntax, alternatives(openers), literals, alternatives(syntax.doc))


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


def literal_at(source, start, whole):
    found = whole.match(source, start)
    return Token(STRING, start, found.end()) if found else None


def token_at(found, source, scanner):
    name, start = found.lastgroup, found.start()
    if name.startswith(LINE):
        return Token(LINE, start, line_comment_end(source, start))
    if name.startswith(STRING):
        return literal_at(source, start, scanner.literals[int(name[len(STRING):])])
    pair = scanner.syntax.block[int(name[len(BLOCK):])]
    return Token(BLOCK, start, block_comment_end(source, start, pair, scanner.syntax.nested))


def tokens(source, scanner):
    found = scanner.opener.search(source)
    while found:
        token = token_at(found, source, scanner)
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
