import re

OPENING = re.compile(r"^( {0,3}(?:(?:[-*+]|\d{1,9}[.)]) +)*)(`{3,}|~{3,})(.*)$")
CLOSING = re.compile(r"^( *)(`{3,}|~{3,})\s*$")
INDENT_ALLOWED = 3


class Fences:
    def __init__(self):
        self.open = None
        self.column = 0

    def inside(self, line):
        if self.open is None:
            self.opens(line)
            return self.open is not None
        if self.closes(line):
            self.open = None
        return True

    def opens(self, line):
        marker = OPENING.match(line)
        if marker and not (marker.group(2)[0] == "`" and "`" in marker.group(3)):
            self.open = marker.group(2)
            self.column = len(marker.group(1))

    def closes(self, line):
        marker = CLOSING.match(line)
        return bool(marker) and len(marker.group(1)) <= self.column + INDENT_ALLOWED \
            and marker.group(2)[0] == self.open[0] and len(marker.group(2)) >= len(self.open)
