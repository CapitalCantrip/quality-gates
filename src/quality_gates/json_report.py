import json

from quality_gates.errors import ToolError


def load_json(path: str, open_label: str, parse_label: str) -> object:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise ToolError(f"cannot open {open_label}: {exc}") from None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ToolError(f"bad {parse_label}: {exc}") from None
