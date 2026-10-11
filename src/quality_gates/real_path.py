import os
from pathlib import Path

from quality_gates.errors import ToolError

try:
    import fcntl
except ImportError:
    fcntl = None

GET_PATH = getattr(fcntl, "F_GETPATH", None)
PATH_BUFFER = bytes(1024)


def _true_case(resolved: str) -> str:
    if GET_PATH is None:
        return resolved
    try:
        descriptor = os.open(resolved, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return resolved
    try:
        return os.fsdecode(fcntl.fcntl(descriptor, GET_PATH, PATH_BUFFER).rstrip(b"\0")) or resolved
    except OSError:
        return resolved
    finally:
        os.close(descriptor)


def real_path(filename: str) -> str:
    try:
        return _true_case(str(Path(filename).resolve()))
    except (OSError, RuntimeError, ValueError) as exc:
        raise ToolError(f"cannot resolve path {filename!r}: {exc}") from None
