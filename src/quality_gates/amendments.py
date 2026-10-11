import re
from collections import namedtuple

from quality_gates.fences import Fences

HEADING = re.compile(r"^(#{1,6}) (.+?)\s*#*\s*$")
AMENDS = "Amends:"
AMENDED_BY = "Amended by:"
ANCHOR_LINK = re.compile(r"\[[^\]]*\]\(#([^)\s]+)\)")
AMENDING_PREFIXES = ("Addendum", "Amended", "Current rule")
SLUG_DROPS = re.compile(r"[^\w\- ]")

Section = namedtuple("Section", "title anchor line amends amended_by")


def slug(title):
    return SLUG_DROPS.sub("", title.lower()).replace(" ", "-")


def plain(title):
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)


class Sections:
    def __init__(self, path):
        self.name = path.name
        self.sections = []
        self.counts = {}
        self.fences = Fences()
        self.text_started = False
        self.problems = []
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            self.read_line(index + 1, line)

    def read_line(self, number, line):
        if self.fences.inside(line):
            return
        heading = HEADING.match(line)
        if heading:
            self.add(number, heading.group(2))
            self.text_started = False
        elif self.sections and line.startswith((AMENDS, AMENDED_BY)):
            self.add_links(number, line)
        elif line.strip():
            self.text_started = True

    def add(self, number, title):
        base = slug(plain(title))
        seen = self.counts.get(base, 0)
        self.counts[base] = seen + 1
        anchor = base if seen == 0 else f"{base}-{seen}"
        self.sections.append(Section(title, anchor, number, [], []))

    def add_links(self, number, line):
        if self.text_started:
            self.problems.append(f"{self.name}:{number}: an Amends: or Amended by: line sits directly under its "
                                 f"heading, above the section's text")
        field = self.sections[-1].amends if line.startswith(AMENDS) else self.sections[-1].amended_by
        field += [(number, anchor) for anchor in ANCHOR_LINK.findall(line)]


def problems(path):
    reader = Sections(path)
    by_anchor = {section.anchor: section for section in reader.sections}
    found = list(reader.problems)
    for section in reader.sections:
        found += section_problems(reader.name, section, by_anchor)
    return found


def section_problems(name, section, by_anchor):
    found = []
    if section.title.startswith(AMENDING_PREFIXES) and not section.amends:
        found.append(f'{name}:{section.line}: "{section.title}" amends nothing; '
                     f'add an Amends: line linking the text it changes')
    found += [f"{name}:{number}: links #{anchor}, which no heading in this ADR has"
              for number, anchor in section.amends + section.amended_by if anchor not in by_anchor]
    found += [f'{name}:{section.line}: "{section.title}" amends "{other.title}", '
              f'but "{other.title}" has no Amended by: link back to it'
              for other in one_way(section, section.amends, by_anchor, "amended_by")]
    found += [f'{name}:{section.line}: "{section.title}" is amended by "{other.title}", '
              f'but "{other.title}" has no Amends: link to it'
              for other in one_way(section, section.amended_by, by_anchor, "amends")]
    return found


def one_way(section, links, by_anchor, returning):
    others = [by_anchor[anchor] for _, anchor in links if anchor in by_anchor]
    return [other for other in others if section.anchor not in anchors(getattr(other, returning))]


def anchors(links):
    return [anchor for _, anchor in links]
