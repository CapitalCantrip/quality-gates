from pathlib import Path

from quality_gates.errors import ToolError


def real_path(filename: str) -> str:
    try:
        return str(Path(filename).resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ToolError(f"cannot resolve path {filename!r}: {exc}") from None
