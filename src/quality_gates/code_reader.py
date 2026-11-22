from dataclasses import dataclass
from typing import Optional

LINE = "line"
LINE_ENDINGS = "\r\n"
NEWLINE = "\n"
BLANK = " "


@dataclass(frozen=True)
class Syntax:
    line: tuple


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


def marker_at(body: str, syntax: Syntax) -> Optional[int]:
    found = [body.find(marker) for marker in syntax.line if marker in body]
    return min(found) if found else None


def lines_of(source: str) -> list:
    parts = source.split(NEWLINE)
    return [part + NEWLINE for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def read(source: str, syntax: Syntax) -> Reading:
    comments, blanked = [], []
    for number, line in enumerate(lines_of(source), 1):
        body = line.rstrip(LINE_ENDINGS)
        at = marker_at(body, syntax)
        if at is not None:
            comments.append(Comment(LINE, body[at:], number, number))
            line = body[:at] + BLANK * (len(body) - at) + line[len(body):]
        blanked.append(line)
    return Reading(tuple(comments), "".join(blanked))
