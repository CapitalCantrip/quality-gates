import re

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


class Fences:
    def __init__(self):
        self.open = None

    def inside(self, line):
        marker = FENCE.match(line)
        if self.open is None:
            if marker and not (marker.group(1)[0] == "`" and "`" in marker.group(2)):
                self.open = marker.group(1)
            return self.open is not None
        if marker and self.closes(marker):
            self.open = None
        return True

    def closes(self, marker):
        fence = marker.group(1)
        return fence[0] == self.open[0] and len(fence) >= len(self.open) and not marker.group(2).strip()
