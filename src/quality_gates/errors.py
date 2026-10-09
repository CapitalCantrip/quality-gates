import sys
from typing import Callable


class ToolError(Exception):
    pass


def run_gate(gate: Callable, argv, root, tag: str) -> int:
    try:
        return gate(argv, root)
    except ToolError as error:
        print(f"{tag}{error}", file=sys.stderr)
        return 2
