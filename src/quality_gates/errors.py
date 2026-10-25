import codecs
import sys
from typing import Callable


class ToolError(Exception):
    pass


OUTPUT_ENCODING = "utf-8"


def _write_utf8(stream) -> None:
    encoding = getattr(stream, "encoding", None) or ""
    if hasattr(stream, "reconfigure") and codecs.lookup(encoding).name != OUTPUT_ENCODING:
        stream.reconfigure(encoding=OUTPUT_ENCODING)


def run_gate(gate: Callable, argv, root, tag: str) -> int:
    _write_utf8(sys.stdout)
    _write_utf8(sys.stderr)
    try:
        return gate(argv, root)
    except ToolError as error:
        print(f"{tag}{error}", file=sys.stderr)
        return 2


def given_path(flag: str, value: str) -> str:
    if not value.strip():
        raise ToolError(f"{flag} was given an empty path")
    return value
