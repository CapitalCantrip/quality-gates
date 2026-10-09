import json
from pathlib import Path
from subprocess import PIPE, run
from typing import TYPE_CHECKING, Optional

from quality_gates.errors import ToolError

if TYPE_CHECKING:
    from quality_gates.languages import CoverageOf


def _extract_file_funcs(file_data: dict) -> dict:
    file_funcs: dict = {}
    for fn in file_data.get("functions", []):
        raw_name  = fn.get("name", "")
        base_name = raw_name.split("(")[0].strip()
        line_num  = fn.get("lineNumber", 0)
        cov_frac  = min(1.0, max(0.0, float(fn.get("lineCoverage", 0.0))))
        file_funcs[(base_name, line_num)] = cov_frac
        file_funcs.setdefault(base_name, cov_frac)
        short_name = base_name.rsplit(".", 1)[-1]
        if short_name != base_name:
            file_funcs.setdefault((short_name, line_num), cov_frac)
            file_funcs.setdefault(short_name, cov_frac)
    return file_funcs


def _register_file_coverage(cov_map: dict, filepath: str, file_funcs: dict) -> None:
    for key in (filepath, Path(filepath).name, Path(filepath).stem):
        cov_map.setdefault(key, file_funcs)


def load(xcresult_path: str) -> dict:
    result = run(
        ["xcrun", "xccov", "view", "--report", xcresult_path, "--json"],
        stdout=PIPE, stderr=PIPE, text=True,
    )
    if result.returncode != 0:
        raise ToolError(f"xcrun xccov failed:\n{result.stderr.strip()}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ToolError(f"could not parse xccov output: {exc}") from None

    cov_map: dict = {}
    for target in data.get("targets", []):
        for file_data in target.get("files", []):
            filepath = file_data.get("path") or file_data.get("name", "")
            _register_file_coverage(cov_map, filepath, _extract_file_funcs(file_data))
    return cov_map


def function_coverage(
    cov_map: dict,
    filepath: str,
    name: str,
    start_line: int,
) -> Optional[float]:
    for key in (filepath, Path(filepath).name, Path(filepath).stem):
        file_funcs = cov_map.get(key)
        if file_funcs is None:
            continue
        val = file_funcs.get((name, start_line), file_funcs.get(name))
        if val is not None:
            return float(val)
    return None


def read(xcresult_path: str) -> "CoverageOf":
    files = load(xcresult_path)
    return lambda fn: function_coverage(files, fn.file, fn.unlabelled_name, fn.start)
