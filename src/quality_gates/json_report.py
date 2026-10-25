import json

from quality_gates.errors import ToolError

MALFORMED_RECORD = (AttributeError, IndexError, KeyError, TypeError, ValueError)
KIND_NAMES = {dict: "an object", list: "a list", str: "text"}


def load_json(path: str, open_label: str, parse_label: str) -> object:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise ToolError(f"cannot open {open_label}: {exc}") from None
    except (ValueError, RecursionError) as exc:
        raise ToolError(f"bad {parse_label}: {exc}") from None


def shaped(value: object, kind: type, parse_label: str, what: str):
    if not isinstance(value, kind):
        raise ToolError(f"bad {parse_label}: {what} must be {KIND_NAMES[kind]}, got {type(value).__name__}")
    return value
