#!/usr/bin/env python3
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from subprocess import run, PIPE
from typing import Optional

from quality_gates import complexity_scan, istanbul, ratchet
from quality_gates.errors import ToolError

FAIL_THRESHOLD = 8.0
WARN_THRESHOLD = 5.0
LABEL_WIDTH = 50
TAG = "[crap] "

USAGE = """\
A fully covered function scores its CC; an uncovered one scores CC² + CC.

Languages:
  python      CC from radon, coverage from `coverage json`
  swift       CC from lizard, coverage from an Xcode .xcresult bundle via xcrun xccov
  typescript  CC from lizard (.ts .tsx .js .jsx), coverage from Istanbul's
              coverage-final.json, written by Vitest and Jest

Examples:
  coverage run -m unittest && coverage json
  crap --lang python src/ --coverage-json coverage.json

  xcodebuild test -scheme MyScheme -resultBundlePath /tmp/MyScheme.xcresult
  crap --lang swift Sources/ --xcresult /tmp/MyScheme.xcresult

  vitest run --coverage --coverage.reporter=json
  crap --lang typescript src/ --istanbul-json coverage/coverage-final.json

  crap --lang python src/ --no-coverage    worst-case ranking, not a gate

SwiftPM's `swift test --enable-code-coverage` writes .profdata, not .xcresult;
use --no-coverage for SwiftPM packages.

Exit codes:
  0  no function scores above --threshold
  1  one or more functions score above --threshold
  2  tool error: missing dependency, bad input, or no functions found

Dependencies: radon (Python CC), coverage (Python coverage), lizard (Swift and
TypeScript CC), xcrun xccov (Swift coverage, from Xcode).
"""


def crap_score(cc: float, coverage: float) -> float:
    coverage = min(1.0, max(0.0, coverage))
    return cc ** 2 * (1 - coverage) ** 3 + cc


def crap_grade(score: float, warn_threshold: float, fail_threshold: float) -> str:
    if score > fail_threshold:
        return "FAIL"
    if score > warn_threshold:
        return "WARN"
    return "ok"


@dataclass
class FunctionResult:
    file: str
    name: str
    line: int
    cc: int
    coverage: Optional[float]
    crap: float
    grade: str


@dataclass
class FileCoverage:
    lines: dict
    branches: dict
    has_branches: bool


def _build_branch_map(exec_b: list, miss_b: list) -> dict:
    bmap: dict = {}
    for from_ln, _ in miss_b:
        bmap.setdefault(from_ln, [0, 0])[1] += 1
    for from_ln, _ in exec_b:
        entry = bmap.setdefault(from_ln, [0, 0])
        entry[0] += 1
        entry[1] += 1
    return bmap


def _parse_file_coverage(fd: dict) -> FileCoverage:
    executed = set(fd.get("executed_lines", []))
    missing  = set(fd.get("missing_lines", []))
    lines = {ln: True for ln in executed}
    lines.update({ln: False for ln in missing})
    exec_b = fd.get("executed_branches", [])
    miss_b = fd.get("missing_branches", [])
    has_branches = bool(exec_b or miss_b)
    branches = _build_branch_map(exec_b, miss_b) if has_branches else {}
    return FileCoverage(lines=lines, branches=branches, has_branches=has_branches)


def _branch_coverage_for_range(branches: dict, start: int, end: int) -> Optional[float]:
    in_range = {ln: v for ln, v in branches.items() if start <= ln <= end}
    if not in_range:
        return None
    total = sum(v[1] for v in in_range.values())
    return (sum(v[0] for v in in_range.values()) / total) if total else None


def _line_coverage_for_range(lines: dict, start: int, end: int) -> Optional[float]:
    in_range = {ln: hit for ln, hit in lines.items() if start <= ln <= end}
    if not in_range:
        return None
    return sum(1 for hit in in_range.values() if hit) / len(in_range)


def coverage_python(coverage_json_path: str) -> tuple:
    try:
        with open(coverage_json_path) as fh:
            data = json.load(fh)
    except OSError as exc:
        raise ToolError(f"cannot open coverage file: {exc}") from None
    except json.JSONDecodeError as exc:
        raise ToolError(f"bad coverage JSON: {exc}") from None

    out: dict = {}
    any_branches = False
    for relpath, fd in data.get("files", {}).items():
        entry = _parse_file_coverage(fd)
        if entry.has_branches:
            any_branches = True
        abspath = str(Path(relpath).resolve())
        out[abspath] = entry
        out[relpath] = entry

    if not any_branches:
        print(
            "[crap] ⚠️  no branch data in coverage file — using line coverage only.\n"
            "  For more accurate scores add [run] branch=True to .coveragerc.",
            file=sys.stderr,
        )
    return out, any_branches


def function_coverage_python(
    cov_map: dict,
    filepath: str,
    start_line: int,
    end_line: int,
) -> Optional[float]:
    key = str(Path(filepath).resolve())
    entry = cov_map.get(key) or cov_map.get(filepath)
    if not entry:
        return None
    if entry.has_branches:
        cov = _branch_coverage_for_range(entry.branches, start_line, end_line)
        if cov is not None:
            return cov
    return _line_coverage_for_range(entry.lines, start_line, end_line)


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


def coverage_swift(xcresult_path: str) -> dict:
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


def function_coverage_swift(
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


def _to_result(fn, coverage_of, args) -> Optional[FunctionResult]:
    if fn.cc < args.min_cc:
        return None
    cov = 0.0 if args.no_coverage else coverage_of(fn)
    score = crap_score(fn.cc, cov if cov is not None else 0.0)
    grade = crap_grade(score, args.warn, args.threshold)
    return FunctionResult(fn.file, fn.name, fn.start, fn.cc, cov, score, grade)


def _coverage_lookup(args):
    if args.lang == "python":
        cov_py = coverage_python(args.coverage_json)[0] if args.coverage_json else {}
        return lambda fn: function_coverage_python(cov_py, fn.file, fn.start, fn.end)
    if args.lang == "swift":
        cov_swift = coverage_swift(args.xcresult) if args.xcresult else {}
        return lambda fn: function_coverage_swift(cov_swift, fn.file, fn.plain_name, fn.start)
    cov_ts = istanbul.load(args.istanbul_json) if args.istanbul_json else {}
    return lambda fn: istanbul.function_coverage(cov_ts, fn.file, fn.start, fn.end)


def analyse(args) -> tuple:
    found = complexity_scan.scan(args.paths, args.lang)
    coverage_of = _coverage_lookup(args)
    scored = (_to_result(fn, coverage_of, args) for fn in found.functions)
    results = sorted((r for r in scored if r is not None), key=lambda r: r.crap, reverse=True)
    return results, found.skipped


_GRADE_EMOJI  = {"ok": "✅", "WARN": "⚠️ ", "FAIL": "❌"}
_GRADE_COLOR  = {"ok": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m"}
_RESET        = "\033[0m"


def _fmt_cov(cov: Optional[float]) -> str:
    return f"{cov * 100:5.1f}%" if cov is not None else "    ?"


def _print_row(r: FunctionResult, no_color: bool) -> None:
    color = "" if no_color else _GRADE_COLOR.get(r.grade, "")
    reset = "" if no_color else _RESET
    emoji = _GRADE_EMOJI.get(r.grade, "  ")
    label = f"{Path(r.file).name}:{r.line}  {r.name}"
    if len(label) > LABEL_WIDTH:
        label = label[:LABEL_WIDTH - 1] + "…"
    print(f"{color}{emoji} {r.grade:5}{reset}  {r.crap:6.1f}  {r.cc:3}  {_fmt_cov(r.coverage)}  {label}")


def print_table(results: list, no_color: bool, top: int) -> None:
    fails     = [r for r in results if r.grade == "FAIL"]
    non_fails = [r for r in results if r.grade != "FAIL"]
    capped    = non_fails[:top] if top else non_fails
    shown     = fails + capped
    print(f"{'GRADE':8}  {'CRAP':6}  {'CC':3}  {'COV':6}  FUNCTION")
    print("─" * 76)
    for r in shown:
        _print_row(r, no_color)
    hidden = len(non_fails) - len(capped)
    if hidden > 0:
        print(f"\n  … {hidden} more ok/WARN (pass --top 0 to show all)")


def print_summary(results: list, warn_threshold: float, fail_threshold: float) -> None:
    total  = len(results)
    n_fail = sum(1 for r in results if r.grade == "FAIL")
    n_warn = sum(1 for r in results if r.grade == "WARN")
    n_ok   = total - n_fail - n_warn
    if results:
        max_crap = max(r.crap for r in results)
        avg_crap = sum(r.crap for r in results) / total
    else:
        max_crap = avg_crap = 0.0
    print()
    print(f"  {total} function(s) · {n_ok} ok · {n_warn} warn · {n_fail} fail")
    print(f"  Max CRAP: {max_crap:.1f}  ·  Mean CRAP: {avg_crap:.1f}")
    print(f"  Thresholds: warn > {warn_threshold}  fail > {fail_threshold}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CRAP score checker — CRAP(f) = CC²(1−cov)³ + CC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=USAGE,
    )
    p.add_argument("--lang", choices=["python", "swift", "typescript"], required=True,
                   help="Language to analyse")
    p.add_argument("paths", nargs="*", default=["."],
                   help="Files or directories to scan (default: current dir)")

    cov = p.add_mutually_exclusive_group()
    cov.add_argument("--coverage-json", metavar="FILE",
                     help="Python: output of `coverage json`")
    cov.add_argument("--xcresult", metavar="FILE",
                     help="Swift: .xcresult bundle from xcodebuild "
                          "(not SwiftPM's swift test, which produces .profdata)")
    cov.add_argument("--istanbul-json", metavar="FILE",
                     help="TypeScript: Istanbul coverage-final.json from Vitest or Jest")
    cov.add_argument("--no-coverage", action="store_true",
                     help="Assume 0%% coverage (worst-case scores)")

    p.add_argument("--threshold", type=float, default=FAIL_THRESHOLD,
                   help="CRAP score that fails the build (default: %(default)g, per ADR-001)")
    p.add_argument("--warn", type=float, default=WARN_THRESHOLD,
                   help="CRAP score that triggers a warning (default: %(default)g)")
    p.add_argument("--min-cc", type=int, default=2,
                   help="Skip functions with CC < N (default: 2; omits trivial 1-branch functions)")
    p.add_argument("--top", type=int, default=20,
                   help="Show only the N worst ok/WARN functions; FAIL rows always shown; "
                        "0 = show all (default: 20)")
    p.add_argument("--json", dest="json_output", action="store_true",
                   help="Emit JSON for CI/tooling consumers")
    p.add_argument("--no-color", action="store_true",
                   help="Disable ANSI colour in table output")
    p.add_argument("--allow-empty", action="store_true",
                   help="Exit 0 when no functions are found (suppresses the empty-scan error)")
    p.add_argument("--strict-freshness", action="store_true",
                   help="Exit 2 (tool error) when coverage file is older than the newest source file")
    p.add_argument("--baseline", metavar="FILE",
                   help="Fail only on functions that are new or worse than this file; needs coverage")
    p.add_argument("--update", action="store_true",
                   help="Lower the baseline to match the tree")
    return p


COVERAGE_FLAGS = {
    "python": ("coverage_json", "--coverage-json", "Python-only"),
    "swift": ("xcresult", "--xcresult", "Swift-only"),
    "typescript": ("istanbul_json", "--istanbul-json", "TypeScript-only"),
}


def _check_coverage_flag(args) -> None:
    own = COVERAGE_FLAGS[args.lang][1]
    for lang, (attr, flag, scope) in COVERAGE_FLAGS.items():
        if lang != args.lang and getattr(args, attr):
            raise ToolError(f"{flag} is {scope}; use {own} for {args.lang}")


def _validate_args(args) -> None:
    if args.warn >= args.threshold:
        raise ToolError(f"--warn ({args.warn}) must be less than --threshold ({args.threshold})")
    _check_coverage_flag(args)


def _check_coverage_source(args) -> None:
    if _coverage_path(args) or args.no_coverage:
        return
    args.no_coverage = True
    if not args.json_output:
        print(
            "[crap] No coverage source given — computing worst-case scores "
            "(0% coverage assumed).\n",
            file=sys.stderr,
        )


def _newest_source_mtime(source_paths: list) -> Optional[float]:
    newest = 0.0
    for root in source_paths:
        p = Path(root)
        files = p.rglob("*.*") if p.is_dir() else [p]
        for f in files:
            try:
                mt = f.stat().st_mtime
                if mt > newest:
                    newest = mt
            except OSError:
                continue
    return newest if newest > 0 else None


def _check_staleness(coverage_path: str, source_paths: list, strict: bool) -> None:
    try:
        cov_mtime = Path(coverage_path).stat().st_mtime
    except OSError:
        return
    newest = _newest_source_mtime(source_paths)
    if newest is None or newest <= cov_mtime:
        return
    message = f"⚠️  coverage file may be stale: {Path(coverage_path).name} is older than the newest source file"
    if strict:
        raise ToolError(message)
    print(f"{TAG}{message}", file=sys.stderr)


def _coverage_path(args) -> Optional[str]:
    return args.coverage_json or args.xcresult or args.istanbul_json


def _maybe_check_staleness(args) -> None:
    path = _coverage_path(args)
    if path:
        _check_staleness(path, args.paths, args.strict_freshness)


def _check_results_empty(results: list, args) -> None:
    if results:
        return
    message = (
        f"no functions analysed in: {', '.join(args.paths)}\n"
        "  Check that the paths contain source files for the chosen --lang.\n"
        "  Use --allow-empty to suppress this error."
    )
    if not args.allow_empty:
        raise ToolError(message)
    print(f"{TAG}{message}", file=sys.stderr)


def _coverage_source(args) -> Optional[str]:
    if args.coverage_json:
        return "coverage-json"
    if args.xcresult:
        return "xcresult"
    if args.istanbul_json:
        return "istanbul-json"
    if args.no_coverage:
        return "assumed-zero"
    return None


def _fn_to_dict(r: FunctionResult, cov_source: Optional[str]) -> dict:
    return {
        "file":            r.file,
        "name":            r.name,
        "line":            r.line,
        "cc":              r.cc,
        "coverage":        r.coverage,
        "crap":            round(r.crap, 2),
        "grade":           r.grade,
        "coverage_source": cov_source if r.coverage is not None else None,
    }


def _print_json(results: list, args, n_fail: int, skipped: list) -> None:
    cov_source = _coverage_source(args)
    payload = {
        "threshold":       args.threshold,
        "warn":            args.warn,
        "pass":            n_fail == 0,
        "coverage_source": cov_source,
        "functions":       [_fn_to_dict(r, cov_source) for r in results],
        "skipped":         skipped,
    }
    print(json.dumps(payload, indent=2))


def _emit_output(results: list, args, n_fail: int, skipped: list) -> None:
    if args.json_output:
        _print_json(results, args, n_fail, skipped)
        return
    print_table(results, no_color=args.no_color, top=args.top)
    print_summary(results, warn_threshold=args.warn, fail_threshold=args.threshold)
    line = complexity_scan.skipped_line(skipped)
    if line:
        print(line)


def _check_baseline_args(args) -> None:
    if args.update and not args.baseline:
        raise ToolError("--update needs --baseline")
    if args.baseline and args.no_coverage:
        raise ToolError("--baseline needs coverage data. Worst-case scores are a ranking, not a gate (ADR-001).")


def _failing_scores(results: list, root) -> dict:
    scores: dict = {}
    for r in results:
        if r.grade == "FAIL":
            ratchet.record(scores, ratchet.key(root, r.file, r.name), round(r.crap, 2))
    return scores


def _enforce_baseline(results: list, args, root) -> int:
    out = sys.stderr if args.json_output else sys.stdout
    current = _failing_scores(results, root or ratchet.repo_root())
    return ratchet.enforce(current, Path(args.baseline), args.update, out)


def gate(argv, root) -> int:
    args = build_parser().parse_args(argv)
    _validate_args(args)
    _check_coverage_source(args)
    _check_baseline_args(args)
    _maybe_check_staleness(args)
    results, skipped = analyse(args)
    _check_results_empty(results, args)
    n_fail = sum(1 for r in results if r.grade == "FAIL")
    _emit_output(results, args, n_fail, skipped)
    if args.baseline:
        return _enforce_baseline(results, args, root)
    return 1 if n_fail > 0 else 0


def main(argv=None, root=None) -> None:
    try:
        code = gate(argv, root)
    except ToolError as error:
        print(f"{TAG}{error}", file=sys.stderr)
        code = 2
    sys.exit(code)


if __name__ == "__main__":
    main()
