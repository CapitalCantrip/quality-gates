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


def given_path(flag: str, value: str) -> str:
    if not value.strip():
        raise ToolError(f"{flag} was given an empty path")
    return value
