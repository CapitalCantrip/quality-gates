import argparse
import sys
from pathlib import Path

from quality_gates.manifest import BROKEN_EXIT, COMPONENTS_PATH, ManifestError, load_components

SUMMARY = "print a component's explainer in plain words"
NO_EXPLAINER_EXIT = 1


def build_parser():
    parser = argparse.ArgumentParser(prog="qg explain")
    parser.add_argument("name")
    return parser


def main(argv=None, components_path=COMPONENTS_PATH):
    args = build_parser().parse_args(argv)
    try:
        manifest = load_components(components_path)
    except ManifestError as error:
        print(f"qg explain: {error}", file=sys.stderr)
        return BROKEN_EXIT
    component = next((c for c in manifest.components if c.id == args.name), None)
    if component is None:
        print(f"qg explain: no component named '{args.name}'", file=sys.stderr)
        return NO_EXPLAINER_EXIT
    if component.explainer is None:
        print(f"qg explain: '{args.name}' has no explainer yet", file=sys.stderr)
        return NO_EXPLAINER_EXIT
    try:
        text = (Path(components_path).parent / component.explainer).read_text(encoding="utf-8")
    except OSError as error:
        print(f"qg explain: {error.filename}: {error.strerror}", file=sys.stderr)
        return BROKEN_EXIT
    sys.stdout.write(text)
    return 0
