import codecs
import sys


class ToolError(Exception):
    pass


class Untagged(ToolError):
    pass


OUTPUT_ENCODING = "utf-8"
TOOL_ERROR_EXIT = 2


def _write_utf8(stream) -> None:
    encoding = getattr(stream, "encoding", None) or ""
    if hasattr(stream, "reconfigure") and codecs.lookup(encoding).name != OUTPUT_ENCODING:
        stream.reconfigure(encoding=OUTPUT_ENCODING)


def write_utf8() -> None:
    _write_utf8(sys.stdout)
    _write_utf8(sys.stderr)


def shown(error: ToolError, tag: str) -> str:
    return str(error) if isinstance(error, Untagged) else f"{tag}{error}"


def given_path(flag: str, value: str) -> str:
    if not value.strip():
        raise ToolError(f"{flag} was given an empty path")
    return value
