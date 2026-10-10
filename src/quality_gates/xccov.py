import json
import math
from subprocess import PIPE, run
from typing import TYPE_CHECKING, Optional

from quality_gates.errors import ToolError
from quality_gates.real_path import real_path

if TYPE_CHECKING:
    from quality_gates.languages import CoverageOf


def _line_coverage(figure: object) -> Optional[float]:
    if isinstance(figure, bool) or not isinstance(figure, (int, float)):
        return None
    try:
        number = float(figure)
    except OverflowError:
        return None
    return min(1.0, max(0.0, number)) if math.isfinite(number) else None


def _extract_file_funcs(file_data: dict) -> dict:
    file_funcs: dict = {}
    for fn in file_data.get("functions", []):
        raw_name  = fn.get("name", "")
        base_name = raw_name.split("(")[0].strip()
        line_num  = fn.get("lineNumber", 0)
        cov_frac  = _line_coverage(fn.get("lineCoverage"))
        file_funcs[(base_name, line_num)] = cov_frac
        file_funcs.setdefault(base_name, cov_frac)
        short_name = base_name.rsplit(".", 1)[-1]
        if short_name != base_name:
            file_funcs.setdefault((short_name, line_num), cov_frac)
            file_funcs.setdefault(short_name, cov_frac)
    return file_funcs


def _register_file_coverage(cov_map: dict, filepath: object, file_funcs: dict) -> None:
    if isinstance(filepath, str) and filepath:
        cov_map.setdefault(real_path(filepath), file_funcs)


def load(xcresult_path: str) -> dict:
    result = run(
        ["xcrun", "xccov", "view", "--report", xcresult_path, "--json"],
        stdout=PIPE, stderr=PIPE, text=True,
    )
    if result.returncode != 0:
        raise ToolError(f"xcrun xccov failed:\n{result.stderr.strip()}")
    try:
        data = json.loads(result.stdout)
    except (ValueError, RecursionError) as exc:
        raise ToolError(f"could not parse xccov output: {exc}") from None

    cov_map: dict = {}
    for target in data.get("targets", []):
        for file_data in target.get("files", []):
            _register_file_coverage(cov_map, file_data.get("path"), _extract_file_funcs(file_data))
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
