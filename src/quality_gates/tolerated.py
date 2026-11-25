import argparse
import os
import sys
from dataclasses import dataclass

from quality_gates import project_files, ratchet
from quality_gates.errors import TOOL_ERROR_EXIT, ToolError

SUMMARY = "say whether the tolerated list grew against a git ref"
DID_NOT_GROW = "the tolerated list did not grow"
GREW = "the tolerated list grew by {count}: {what}; {verdict}"
ITEM_SEPARATOR = ", "
NEEDS_A_LABEL = "it needs the builder's `tolerated-growth` label, or `loosening` on a loosening pull request"
ALLOWED_BY = "the builder's `{label}` label allows it"
BUILDER_LABELS = ("tolerated-growth", "loosening")
LABELS_VARIABLE = "QG_PR_LABELS"
LABEL_SEPARATOR = ","
TOP_EXCLUDE = "exclude"
COMMENT_GATE_EXCLUDE = f"settings.{project_files.COMMENT_GATE}.exclude"
NEW = "{key} {now} (new)"
RAISED = "{key} {then} -> {now}"
NEW_PREFIX = "{entry} (new)"


@dataclass(frozen=True)
class Grown:
    where: str
    what: str

    def __str__(self):
        return f"{self.where} {self.what}"


def entry_grown(key, now, then):
    if key not in then:
        return NEW.format(key=key, now=now)
    return RAISED.format(key=key, then=then[key], now=now) if now > then[key] else None


def baseline_grown(name, now, then):
    if now is None or then is None:
        return []
    grown = ((key, entry_grown(key, number, then)) for key, number in sorted(now.items()))
    return [Grown(name, what) for key, what in grown if what is not None]


def baselines_grown(root, ref):
    return [grown for file in project_files.baseline_files(root)
            for grown in baseline_grown(file.name, ratchet.stored_baseline(file, True),
                                        ratchet.baseline_at(root, ref, file.name))]


def widened(where, now, then):
    return [Grown(f"{project_files.CHOICE_FILE} {where}", NEW_PREFIX.format(entry=entry))
            for entry in now if not project_files.excluded_by(entry, then)]


def excludes_grown(root, ref):
    now, then = project_files.checked_choice(root), project_files.choice_at(root, ref)
    if now is None or then is None:
        return []
    return (widened(TOP_EXCLUDE, now.exclude, then.exclude)
            + widened(COMMENT_GATE_EXCLUDE, now.comment_gate_exclude, then.exclude + then.comment_gate_exclude))


SOURCES = (baselines_grown, excludes_grown)


def growth(root, ref):
    project_files.checked_commit(root, ref)
    return tuple(grown for source in SOURCES for grown in source(root, ref))


def builder_label(environ):
    given = {label.strip() for label in environ.get(LABELS_VARIABLE, "").split(LABEL_SEPARATOR)}
    return next((label for label in BUILDER_LABELS if label in given), None)


def verdict(grown, label):
    if not grown:
        return DID_NOT_GROW, 0
    said = NEEDS_A_LABEL if label is None else ALLOWED_BY.format(label=label)
    line = GREW.format(count=len(grown), what=ITEM_SEPARATOR.join(map(str, grown)), verdict=said)
    return line, 0 if label is not None else 1


def build_parser():
    parser = argparse.ArgumentParser(prog="qg tolerated")
    parser.add_argument("--against", required=True, metavar="REF", help="the git ref to compare with, such as origin/main")
    return parser


def main(argv=None, root=None):
    args = build_parser().parse_args(argv)
    try:
        root = project_files.git_root() if root is None else root
        grown = growth(root, args.against)
    except ToolError as error:
        print(f"qg tolerated: {error}", file=sys.stderr)
        return TOOL_ERROR_EXIT
    line, code = verdict(grown, builder_label(os.environ))
    print(line)
    return code
