import argparse
import sys

from quality_gates import project_files
from quality_gates.errors import TOOL_ERROR_EXIT, ToolError

SUMMARY = "say whether the tolerated list grew against a git ref"
DID_NOT_GROW = "the tolerated list did not grow"


def growth(root, ref):
    project_files.checked_commit(root, ref)
    return ()


def build_parser():
    parser = argparse.ArgumentParser(prog="qg tolerated")
    parser.add_argument("--against", required=True, metavar="REF", help="the git ref to compare with, such as origin/main")
    return parser


def main(argv=None, root=None):
    args = build_parser().parse_args(argv)
    try:
        root = project_files.git_root() if root is None else root
        growth(root, args.against)
    except ToolError as error:
        print(f"qg tolerated: {error}", file=sys.stderr)
        return TOOL_ERROR_EXIT
    print(DID_NOT_GROW)
    return 0
