import argparse
import sys

from quality_gates.manifest import BROKEN_EXIT, COMPONENTS_PATH, BrokenFileError, load_components

SUMMARY = "print a component's explainer in plain words"
NOTHING_TO_EXPLAIN_EXIT = 1


def build_parser():
    parser = argparse.ArgumentParser(prog="qg explain")
    parser.add_argument("name")
    return parser


def main(argv=None, components_path=COMPONENTS_PATH):
    args = build_parser().parse_args(argv)
    try:
        manifest = load_components(components_path)
    except BrokenFileError as error:
        print(f"qg explain: {error}", file=sys.stderr)
        return BROKEN_EXIT
    component = manifest.component(args.name)
    if component is None:
        print(f"qg explain: no component named '{args.name}'", file=sys.stderr)
        return NOTHING_TO_EXPLAIN_EXIT
    if component.explainer is None:
        print(f"qg explain: '{args.name}' has no explainer yet", file=sys.stderr)
        return NOTHING_TO_EXPLAIN_EXIT
    try:
        text = manifest.explainer_path(component).read_text(encoding="utf-8")
    except OSError as error:
        print(f"qg explain: {error.filename}: {error.strerror}", file=sys.stderr)
        return BROKEN_EXIT
    sys.stdout.write(text)
    return 0
