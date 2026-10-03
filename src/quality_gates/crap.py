#!/usr/bin/env python3
"""
crap.py — CRAP (Change Risk Anti-Patterns) score checker.

  CRAP(f) = CC(f)² × (1 − cov(f))³ + CC(f)

  cov(f) ∈ [0, 1];  CC = cyclomatic complexity.
  Score ≤ 30 was an early human-coder rule of thumb.
  Uncle Bob's crap4j/crap4java spec tightened that to 8 as the automated gate;
  this project follows that spec.

  A fully-covered function collapses to CRAP = CC.
  An uncovered function scores CRAP = CC² + CC (maximum penalty).

Languages:
  python — CC via radon, coverage via coverage.py JSON
  swift  — CC via lizard, coverage via xcrun xccov

Usage examples:

  # Python — with coverage:
  coverage run -m pytest && coverage json
  crap --lang python src/ \\
      --coverage-json coverage.json

  # Python — worst-case (no test suite yet):
  crap --lang python src/ --no-coverage

  # Swift — with coverage (xcodebuild produces .xcresult bundles):
  xcodebuild test -scheme MyScheme -resultBundlePath /tmp/MyScheme.xcresult
  python3 ../crap.py --lang swift Sources/ \\
      --xcresult /tmp/MyScheme.xcresult

  # Swift — SwiftPM note: `swift test --enable-code-coverage` writes .profdata,
  #   not .xcresult. Use --no-coverage or convert via llvm-cov export first.

  # Swift — worst-case:
  python3 ../crap.py --lang swift Sources/ --no-coverage

Exit codes:
  0  all functions below --threshold
  1  one or more functions exceed --threshold
  2  tool error (missing dependency, bad input)

Dependencies:
  pip3 install radon            # Python CC
  pip3 install coverage         # Python per-line/branch coverage
  pip3 install lizard           # Swift (and Python, Java, …) CC
  brew install swiftlint        # Swift CC (already installed)
  xcode-select --install        # xcrun xccov for Swift coverage
"""

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from subprocess import run, PIPE
from typing import Optional

from quality_gates import ratchet


# ── Core formula ─────────────────────────────────────────────────────────────

def crap_score(cc: float, coverage: float) -> float:
    """CRAP(f) = CC(f)² × (1 − cov)³ + CC(f).  cov ∈ [0, 1]."""
    coverage = min(1.0, max(0.0, coverage))  # guard: out-of-range flips sign
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
    coverage: Optional[float]   # None = no data available
    crap: float
    grade: str


@dataclass
class FileCoverage:
    """Per-file coverage data parsed from coverage.py JSON."""
    lines: dict          # {line_number: bool}  True=executed, False=missed
    branches: dict       # {from_line: [covered, total]}; empty when no branch data
    has_branches: bool


# ── Python mode ───────────────────────────────────────────────────────────────

def _build_branch_map(exec_b: list, miss_b: list) -> dict:
    """Build {from_line: [covered, total]} from executed/missing branch lists."""
    bmap: dict = {}
    for from_ln, _ in miss_b:
        bmap.setdefault(from_ln, [0, 0])[1] += 1
    for from_ln, _ in exec_b:
        entry = bmap.setdefault(from_ln, [0, 0])
        entry[0] += 1
        entry[1] += 1
    return bmap


def _parse_file_coverage(fd: dict) -> FileCoverage:
    """Parse one file's entry from coverage.py JSON into a FileCoverage."""
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
    """Fraction of branches in [start, end] that were taken."""
    in_range = {ln: v for ln, v in branches.items() if start <= ln <= end}
    if not in_range:
        return None
    total = sum(v[1] for v in in_range.values())
    return (sum(v[0] for v in in_range.values()) / total) if total else None


def _line_coverage_for_range(lines: dict, start: int, end: int) -> Optional[float]:
    """Fraction of tracked lines in [start, end] that were executed."""
    in_range = {ln: hit for ln, hit in lines.items() if start <= ln <= end}
    if not in_range:
        return None
    return sum(1 for hit in in_range.values() if hit) / len(in_range)


def cc_python(paths: list) -> dict:
    """
    Run radon cc -j on *paths*.  Returns radon's JSON as a dict:
      { "filepath.py": [ { type, name, lineno, endline, complexity, … }, … ] }
    """
    if importlib.util.find_spec("radon") is None:
        print(
            "[crap] radon is not installed.\n"
            "  Install with: pip3 install radon",
            file=sys.stderr,
        )
        sys.exit(2)
    cmd = [sys.executable, "-m", "radon", "cc", "--json"] + paths
    result = run(cmd, stdout=PIPE, stderr=PIPE, text=True)
    if result.returncode != 0:
        print(f"[crap] radon failed:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"[crap] could not parse radon output: {exc}", file=sys.stderr)
        sys.exit(2)


def coverage_python(coverage_json_path: str) -> tuple:
    """
    Parse coverage.py JSON (generated by `coverage json`).
    Returns (cov_map, has_branches) where:
      cov_map  = { abspath: FileCoverage }
      has_branches = True when branch data is present in any file

    Warns on stderr when branch data is absent (run with branch=True
    in .coveragerc for more accurate per-branch scores).
    """
    try:
        with open(coverage_json_path) as fh:
            data = json.load(fh)
    except OSError as exc:
        print(f"[crap] cannot open coverage file: {exc}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"[crap] bad coverage JSON: {exc}", file=sys.stderr)
        sys.exit(2)

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
    """
    Coverage fraction for lines/branches in [start_line, end_line].
    Prefers branch coverage when available; falls back to line coverage.
    Returns None if the file isn't in the coverage map.
    """
    key = str(Path(filepath).resolve())
    entry = cov_map.get(key) or cov_map.get(filepath)
    if not entry:
        return None
    if entry.has_branches:
        cov = _branch_coverage_for_range(entry.branches, start_line, end_line)
        if cov is not None:
            return cov
    return _line_coverage_for_range(entry.lines, start_line, end_line)


def _qualified_name(block: dict) -> str:
    name = block.get("name", "?")
    return f"{block['classname']}.{name}" if block.get("classname") else name


def _py_block_to_result(
    block: dict,
    filepath: str,
    cov_data: dict,
    no_coverage: bool,
    min_cc: int,
    warn_threshold: float,
    fail_threshold: float,
) -> Optional[FunctionResult]:
    """Convert one radon block to a FunctionResult, or None to skip."""
    if block.get("type") not in ("function", "method"):
        return None
    cc = block.get("complexity", 1)
    if cc < min_cc:
        return None
    start = block.get("lineno", 0)
    end   = block.get("endline", start)
    name  = _qualified_name(block)
    if no_coverage:
        cov = 0.0
    elif cov_data:
        cov = function_coverage_python(cov_data, filepath, start, end)
    else:
        cov = None
    cov_calc = cov if cov is not None else 0.0
    score    = crap_score(cc, cov_calc)
    grade    = crap_grade(score, warn_threshold, fail_threshold)
    return FunctionResult(filepath, name, start, cc, cov, score, grade)


def analyse_python(
    paths: list,
    coverage_json: Optional[str],
    no_coverage: bool,
    min_cc: int,
    warn_threshold: float,
    fail_threshold: float,
) -> list:
    radon_data = cc_python(paths)
    cov_data: dict = {}
    if coverage_json:
        cov_data, _ = coverage_python(coverage_json)
    results = []
    for filepath, blocks in radon_data.items():
        for block in blocks:
            r = _py_block_to_result(
                block, filepath, cov_data, no_coverage,
                min_cc, warn_threshold, fail_threshold,
            )
            if r is not None:
                results.append(r)
    return sorted(results, key=lambda r: r.crap, reverse=True)


# ── Swift mode ────────────────────────────────────────────────────────────────

def _parse_lizard_row(row: list) -> Optional[dict]:
    """Parse one CSV row from lizard --csv. Returns None if malformed."""
    if len(row) < 11:
        return None
    try:
        return {
            "file":  row[6].strip(),
            "name":  row[7].strip(),
            "cc":    int(row[1]),
            "start": int(row[9]),
            "end":   int(row[10]),
        }
    except (ValueError, IndexError):
        return None


def cc_swift(paths: list) -> list:
    """
    Run lizard on Swift files; return list of dicts:
      { file, name, cc, start, end }

    lizard must be installed: pip3 install lizard

    CSV columns (no header row):
      NLOC, CCN, token, param, length, location, filepath,
      method_name, method_long_name, start_line, end_line
    """
    import csv, io

    try:
        result = run(
            ["lizard", "--language", "swift", "--csv"] + paths,
            stdout=PIPE, stderr=PIPE, text=True,
        )
    except FileNotFoundError:
        print(
            "[crap] lizard not found.\n"
            "  Install with: pip3 install lizard\n"
            "  lizard provides language-agnostic cyclomatic complexity for Swift.",
            file=sys.stderr,
        )
        sys.exit(2)

    if result.returncode not in (0, 1):
        print(f"[crap] lizard failed:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)

    raw = result.stdout.strip()
    if not raw:
        return []

    return [
        fn for fn in (
            _parse_lizard_row(row)
            for row in csv.reader(io.StringIO(raw))
        )
        if fn is not None
    ]


def _extract_file_funcs(file_data: dict) -> dict:
    """Build function coverage map for one source file from xccov JSON."""
    file_funcs: dict = {}
    for fn in file_data.get("functions", []):
        raw_name  = fn.get("name", "")
        base_name = raw_name.split("(")[0].strip()
        line_num  = fn.get("lineNumber", 0)
        cov_frac  = min(1.0, max(0.0, float(fn.get("lineCoverage", 0.0))))
        # Primary key: (base_name, line) — handles overloads
        file_funcs[(base_name, line_num)] = cov_frac
        # Fallback key: base_name alone (first occurrence wins)
        file_funcs.setdefault(base_name, cov_frac)
        # xccov reports "ClassName.methodName" but lizard reports "methodName".
        # Also index by the short name (after the last dot) so they match.
        short_name = base_name.rsplit(".", 1)[-1]
        if short_name != base_name:
            file_funcs.setdefault((short_name, line_num), cov_frac)
            file_funcs.setdefault(short_name, cov_frac)
    return file_funcs


def _register_file_coverage(cov_map: dict, filepath: str, file_funcs: dict) -> None:
    """Index file_funcs under filepath, filename, and stem."""
    for key in (filepath, Path(filepath).name, Path(filepath).stem):
        cov_map.setdefault(key, file_funcs)


def coverage_swift(xcresult_path: str) -> dict:
    """
    Run `xcrun xccov view --report <path> --json`.
    Returns { file_path: { (base_name, line_number): coverage_fraction } }

    Requires an .xcresult bundle produced by xcodebuild (not SwiftPM's
    swift test, which produces .profdata rather than .xcresult).

    xcov function names look like "initBuffers(_:capacity:)" — we also index by
    base name alone so lizard's plain "initBuffers" can match.
    """
    result = run(
        ["xcrun", "xccov", "view", "--report", xcresult_path, "--json"],
        stdout=PIPE, stderr=PIPE, text=True,
    )
    if result.returncode != 0:
        print(f"[crap] xcrun xccov failed:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"[crap] could not parse xccov output: {exc}", file=sys.stderr)
        sys.exit(2)

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
    """Look up per-function coverage; tries several key forms."""
    for key in (filepath, Path(filepath).name, Path(filepath).stem):
        file_funcs = cov_map.get(key)
        if file_funcs is None:
            continue
        val = file_funcs.get((name, start_line), file_funcs.get(name))
        if val is not None:
            return float(val)
    return None


def _swift_fn_to_result(
    fn: dict,
    cov_data: dict,
    no_coverage: bool,
    min_cc: int,
    warn_threshold: float,
    fail_threshold: float,
) -> Optional[FunctionResult]:
    """Convert one lizard function dict to a FunctionResult, or None to skip."""
    cc = fn["cc"]
    if cc < min_cc:
        return None
    if no_coverage:
        cov = 0.0
    elif cov_data:
        cov = function_coverage_swift(cov_data, fn["file"], fn["name"], fn["start"])
    else:
        cov = None
    cov_calc = cov if cov is not None else 0.0
    score    = crap_score(cc, cov_calc)
    grade    = crap_grade(score, warn_threshold, fail_threshold)
    return FunctionResult(fn["file"], fn["name"], fn["start"], cc, cov, score, grade)


def analyse_swift(
    paths: list,
    xcresult: Optional[str],
    no_coverage: bool,
    min_cc: int,
    warn_threshold: float,
    fail_threshold: float,
) -> list:
    functions = cc_swift(paths)
    cov_data: dict = {}
    if xcresult:
        cov_data = coverage_swift(xcresult)
    results = [
        r for r in (
            _swift_fn_to_result(fn, cov_data, no_coverage, min_cc, warn_threshold, fail_threshold)
            for fn in functions
        )
        if r is not None
    ]
    return sorted(results, key=lambda r: r.crap, reverse=True)


# ── Output ────────────────────────────────────────────────────────────────────

_GRADE_EMOJI  = {"ok": "✅", "WARN": "⚠️ ", "FAIL": "❌"}
_GRADE_COLOR  = {"ok": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m"}
_RESET        = "\033[0m"


def _fmt_cov(cov: Optional[float]) -> str:
    return f"{cov * 100:5.1f}%" if cov is not None else "    ?"


def _print_row(r: FunctionResult, no_color: bool) -> None:
    """Print one result row with ANSI colour and truncated label."""
    color = "" if no_color else _GRADE_COLOR.get(r.grade, "")
    reset = "" if no_color else _RESET
    emoji = _GRADE_EMOJI.get(r.grade, "  ")
    label = f"{Path(r.file).name}:{r.line}  {r.name}"
    if len(label) > 50:
        label = label[:47] + "…"
    print(f"{color}{emoji} {r.grade:5}{reset}  {r.crap:6.1f}  {r.cc:3}  {_fmt_cov(r.coverage)}  {label}")


def print_table(results: list, no_color: bool, top: int) -> None:
    # FAIL rows are always shown in full; --top applies only to ok/WARN rows.
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


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CRAP score checker — CRAP(f) = CC²(1−cov)³ + CC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--lang", choices=["python", "swift"], required=True,
                   help="Language to analyse")
    p.add_argument("paths", nargs="*", default=["."],
                   help="Files or directories to scan (default: current dir)")

    cov = p.add_mutually_exclusive_group()
    cov.add_argument("--coverage-json", metavar="FILE",
                     help="Python: output of `coverage json`")
    cov.add_argument("--xcresult", metavar="FILE",
                     help="Swift: .xcresult bundle from xcodebuild "
                          "(not SwiftPM's swift test, which produces .profdata)")
    cov.add_argument("--no-coverage", action="store_true",
                     help="Assume 0%% coverage (worst-case scores)")

    p.add_argument("--threshold", type=float, default=8.0,
                   help="CRAP score that fails the build "
                        "(default: 8, per Uncle Bob's crap4java spec)")
    p.add_argument("--warn", type=float, default=5.0,
                   help="CRAP score that triggers a warning (default: 5)")
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


# ── CLI helpers ───────────────────────────────────────────────────────────────

def _check_paths_exist(paths: list) -> None:
    for p in paths:
        if not Path(p).exists():
            print(f"[crap] path not found: {p}", file=sys.stderr)
            sys.exit(2)


def _validate_args(args) -> None:
    """Guard-clause validation; exits with code 2 on any problem."""
    if args.warn >= args.threshold:
        print(
            f"[crap] --warn ({args.warn}) must be less than --threshold ({args.threshold})",
            file=sys.stderr,
        )
        sys.exit(2)
    if args.lang == "python" and args.xcresult:
        print("[crap] --xcresult is Swift-only; use --coverage-json for Python", file=sys.stderr)
        sys.exit(2)
    if args.lang == "swift" and args.coverage_json:
        print("[crap] --coverage-json is Python-only; use --xcresult for Swift", file=sys.stderr)
        sys.exit(2)
    _check_paths_exist(args.paths)


def _check_coverage_source(args) -> None:
    """Default to worst-case when no coverage source is provided."""
    if args.coverage_json or args.xcresult or args.no_coverage:
        return
    args.no_coverage = True
    if not args.json_output:
        print(
            "[crap] No coverage source given — computing worst-case scores "
            "(0% coverage assumed).\n",
            file=sys.stderr,
        )


def _newest_source_mtime(source_paths: list) -> Optional[float]:
    """Return the mtime of the newest file under source_paths, or None."""
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
    """Warn (or fail) when the coverage file is older than the newest source."""
    try:
        cov_mtime = Path(coverage_path).stat().st_mtime
    except OSError:
        return  # file-not-found already handled by _check_paths_exist
    newest = _newest_source_mtime(source_paths)
    if newest is None or newest <= cov_mtime:
        return
    print(
        f"[crap] ⚠️  coverage file may be stale: "
        f"{Path(coverage_path).name} is older than the newest source file",
        file=sys.stderr,
    )
    if strict:
        sys.exit(2)


def _maybe_check_staleness(args) -> None:
    """Dispatch staleness check for whichever coverage file is in use."""
    if args.coverage_json:
        _check_staleness(args.coverage_json, args.paths, args.strict_freshness)
    elif args.xcresult:
        _check_staleness(args.xcresult, args.paths, args.strict_freshness)


def _run_analysis(args) -> list:
    if args.lang == "python":
        return analyse_python(
            args.paths,
            coverage_json=args.coverage_json,
            no_coverage=args.no_coverage,
            min_cc=args.min_cc,
            warn_threshold=args.warn,
            fail_threshold=args.threshold,
        )
    return analyse_swift(
        args.paths,
        xcresult=args.xcresult,
        no_coverage=args.no_coverage,
        min_cc=args.min_cc,
        warn_threshold=args.warn,
        fail_threshold=args.threshold,
    )


def _check_results_empty(results: list, args) -> None:
    if results:
        return
    print(
        f"[crap] no functions analysed in: {', '.join(args.paths)}\n"
        "  Check that the paths contain source files for the chosen --lang.\n"
        "  Use --allow-empty to suppress this error.",
        file=sys.stderr,
    )
    if not getattr(args, "allow_empty", False):
        sys.exit(2)


def _coverage_source(args) -> Optional[str]:
    """Return the coverage_source tag for JSON output."""
    if args.coverage_json:
        return "coverage-json"
    if args.xcresult:
        return "xcresult"
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


def _print_json(results: list, args, n_fail: int) -> None:
    cov_source = _coverage_source(args)
    payload = {
        "threshold":       args.threshold,
        "warn":            args.warn,
        "pass":            n_fail == 0,
        "coverage_source": cov_source,
        "functions":       [_fn_to_dict(r, cov_source) for r in results],
    }
    print(json.dumps(payload, indent=2))


def _emit_output(results: list, args, n_fail: int) -> None:
    if args.json_output:
        _print_json(results, args, n_fail)
    else:
        print_table(results, no_color=args.no_color, top=args.top)
        print_summary(results, warn_threshold=args.warn, fail_threshold=args.threshold)


def _check_baseline_args(args) -> None:
    if args.update and not args.baseline:
        print("[crap] --update needs --baseline", file=sys.stderr)
        sys.exit(2)
    if args.baseline and args.no_coverage:
        print(
            "[crap] --baseline needs coverage data. Worst-case scores are a ranking, not a gate (ADR-001).",
            file=sys.stderr,
        )
        sys.exit(2)


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


def main(argv=None, root=None) -> None:
    args = build_parser().parse_args(argv)
    _validate_args(args)
    _check_coverage_source(args)
    _check_baseline_args(args)
    _maybe_check_staleness(args)
    results = _run_analysis(args)
    _check_results_empty(results, args)
    n_fail = sum(1 for r in results if r.grade == "FAIL")
    _emit_output(results, args, n_fail)
    if args.baseline:
        sys.exit(_enforce_baseline(results, args, root))
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
