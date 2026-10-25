import json
import math
from subprocess import PIPE, run
from typing import TYPE_CHECKING, Optional

from quality_gates.errors import ToolError
from quality_gates.json_report import shaped
from quality_gates.real_path import real_path

if TYPE_CHECKING:
    from quality_gates.languages import CoverageOf

XCCOV_ENCODING = "utf-8"
XCCOV_OUTPUT = "xccov output"


def _line_coverage(figure: object) -> Optional[float]:
    if isinstance(figure, bool) or not isinstance(figure, (int, float)):
        return None
    try:
        number = float(figure)
    except OverflowError:
        return None
    return min(1.0, max(0.0, number)) if math.isfinite(number) else None


def _listed(record: object, field: str, what: str) -> list:
    return shaped(shaped(record, dict, XCCOV_OUTPUT, what).get(field, []), list, XCCOV_OUTPUT, f'"{field}" in {what}')


def _extract_file_funcs(file_data: dict) -> dict:
    file_funcs: dict = {}
    for fn in _listed(file_data, "functions", "a file entry"):
        record    = shaped(fn, dict, XCCOV_OUTPUT, "a function record")
        raw_name  = shaped(record.get("name", ""), str, XCCOV_OUTPUT, "a function name")
        base_name = raw_name.split("(")[0].strip()
        line_num  = record.get("lineNumber", 0)
        cov_frac  = _line_coverage(record.get("lineCoverage"))
        file_funcs[(base_name, line_num)] = cov_frac
        file_funcs.setdefault(base_name, cov_frac)
        short_name = base_name.rsplit(".", 1)[-1]
        if short_name != base_name:
            file_funcs.setdefault((short_name, line_num), cov_frac)
            file_funcs.setdefault(short_name, cov_frac)
    return file_funcs


def _register_file_coverage(cov_map: dict, file_data: dict) -> None:
    file_funcs = _extract_file_funcs(file_data)
    filepath = file_data.get("path")
    if filepath is None:
        return
    if shaped(filepath, str, XCCOV_OUTPUT, "a file path"):
        cov_map.setdefault(real_path(filepath), file_funcs)


def _xccov_report(xcresult_path: str) -> str:
    result = run(
        ["xcrun", "xccov", "view", "--report", xcresult_path, "--json"],
        stdout=PIPE, stderr=PIPE,
    )
    if result.returncode != 0:
        raise ToolError(f"xcrun xccov failed:\n{_text(result.stderr, 'replace').strip()}")
    try:
        return _text(result.stdout, "strict")
    except UnicodeDecodeError as exc:
        raise ToolError(f"xccov output is not UTF-8: {exc}") from None


def _text(output: bytes, errors: str) -> str:
    return output.decode(XCCOV_ENCODING, errors)


def load(xcresult_path: str) -> dict:
    report = _xccov_report(xcresult_path)
    try:
        data = json.loads(report)
    except (ValueError, RecursionError) as exc:
        raise ToolError(f"could not parse xccov output: {exc}") from None

    cov_map: dict = {}
    for target in _listed(data, "targets", "the report"):
        for file_data in _listed(target, "files", "a target"):
            _register_file_coverage(cov_map, file_data)
    return cov_map


def function_coverage(
    cov_map: dict,
    filepath: str,
    name: str,
    start_line: int,
) -> Optional[float]:
    file_funcs = cov_map.get(real_path(filepath), {})
    for figure_key in ((name, start_line), name):
        if figure_key in file_funcs:
            return file_funcs[figure_key]
    return None


def read(xcresult_path: str) -> "CoverageOf":
    files = load(xcresult_path)
    return lambda fn: function_coverage(files, fn.file, fn.unlabelled_name, fn.start)
