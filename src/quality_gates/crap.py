#!/usr/bin/env python3
import argparse
import json
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from quality_gates import complexity_scan, ratchet
from quality_gates.errors import ToolError, run_gate
from quality_gates.languages import COVERAGE_FORMATS, LANGUAGES, CoverageFormat, CoverageOf, Language

FAIL_THRESHOLD = 8.0
WARN_THRESHOLD = 5.0
LABEL_WIDTH = 50
TAG = "[crap] "
ASSUMED_ZERO = "assumed-zero"

USAGE_WIDTH = 79
USAGE_INDENT = "  "
LANGUAGE_NAME_WIDTH = 12


def _language_entry(name: str, language: Language) -> str:
    detail = f"CC from {language.counter} ({language.suffix_text}), coverage from {language.coverage_from}"
    return textwrap.fill(
        detail,
        width=USAGE_WIDTH,
        initial_indent=f"{USAGE_INDENT}{name:<{LANGUAGE_NAME_WIDTH}}",
        subsequent_indent=" " * (len(USAGE_INDENT) + LANGUAGE_NAME_WIDTH),
        break_on_hyphens=False,
    )


def _languages_usage() -> str:
    entries = [_language_entry(name, language) for name, language in LANGUAGES.items()]
    return "Languages:\n" + "\n".join(entries)


USAGE = f"""\
A fully covered function scores its CC; an uncovered one scores CC² + CC.

{_languages_usage()}

Examples:
  coverage run -m unittest && coverage json
  crap --lang python src/ --coverage-json coverage.json

  xcodebuild test -scheme MyScheme -resultBundlePath /tmp/MyScheme.xcresult
  crap --lang swift Sources/ --xcresult /tmp/MyScheme.xcresult

  swift test --enable-code-coverage
  crap --lang swift Sources/ --llvm-cov-json "$(swift test --show-codecov-path)"

  vitest run --coverage --coverage.reporter=json
  crap --lang typescript src/ --istanbul-json coverage/coverage-final.json

  crap --lang python src/ --no-coverage    worst-case ranking, not a gate

Exit codes:
  0  no function scores above --threshold
  1  one or more functions score above --threshold
  2  tool error: missing dependency, bad input, or no functions found

Dependencies: radon (Python CC), coverage (Python coverage), lizard (Swift and
TypeScript CC), xcrun xccov (Swift coverage from Xcode; not needed for
--llvm-cov-json).
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


@dataclass(frozen=True)
class Limits:
    min_cc: int
    warn: float
    threshold: float


def _to_result(fn: complexity_scan.Function, coverage_of: CoverageOf, limits: Limits) -> Optional[FunctionResult]:
    if fn.cc < limits.min_cc:
        return None
    cov = coverage_of(fn)
    score = crap_score(fn.cc, cov if cov is not None else 0.0)
    grade = crap_grade(score, limits.warn, limits.threshold)
    return FunctionResult(fn.file, fn.name, fn.start, fn.cc, cov, score, grade)


def score(functions: list, coverage_of: CoverageOf, limits: Limits) -> list:
    scored = (_to_result(fn, coverage_of, limits) for fn in functions)
    return sorted((r for r in scored if r is not None), key=lambda r: r.crap, reverse=True)


def _assume_zero(fn: complexity_scan.Function) -> float:
    return 0.0


@dataclass(frozen=True)
class CoverageReport:
    format: CoverageFormat
    path: str


def _given_report(args) -> Optional[CoverageReport]:
    for coverage in COVERAGE_FORMATS:
        path = getattr(args, coverage.dest)
        if path is None:
            continue
        if not path.strip():
            raise ToolError(f"{coverage.flag} was given an empty path")
        return CoverageReport(coverage, path)
    return None


def _coverage_of(report: Optional[CoverageReport]) -> CoverageOf:
    if report is None:
        return _assume_zero
    return report.format.read(report.path)


def _coverage_source(report: Optional[CoverageReport]) -> str:
    return report.format.source if report else ASSUMED_ZERO


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
    p.add_argument("--lang", choices=list(LANGUAGES), required=True,
                   help="Language to analyse")
    p.add_argument("paths", nargs="*", default=["."],
                   help="Files or directories to scan (default: current dir)")

    cov = p.add_mutually_exclusive_group()
    for coverage in COVERAGE_FORMATS:
        cov.add_argument(coverage.flag, dest=coverage.dest, metavar="FILE", help=coverage.help)
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


def _check_coverage_flag(args) -> None:
    own = " or ".join(coverage.flag for coverage in LANGUAGES[args.lang].coverage)
    for lang, language in LANGUAGES.items():
        for coverage in language.coverage:
            if lang != args.lang and getattr(args, coverage.dest):
                raise ToolError(f"{coverage.flag} is {language.scope}; use {own} for {args.lang}")


def _validate_args(args) -> None:
    if args.warn >= args.threshold:
        raise ToolError(f"--warn ({args.warn}) must be less than --threshold ({args.threshold})")
    _check_coverage_flag(args)


def _check_coverage_source(args, report: Optional[CoverageReport]) -> None:
    if report or args.no_coverage:
        return
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


def _fail_or_warn(message: str, strict: bool) -> None:
    if strict:
        raise ToolError(message)
    print(f"{TAG}{message}", file=sys.stderr)


def _check_staleness(coverage_path: str, source_paths: list, strict: bool) -> None:
    try:
        cov_mtime = Path(coverage_path).stat().st_mtime
    except OSError:
        return
    newest = _newest_source_mtime(source_paths)
    if newest is None or newest <= cov_mtime:
        return
    _fail_or_warn(
        f"⚠️  coverage file may be stale: {Path(coverage_path).name} is older than the newest source file",
        strict,
    )


def _maybe_check_staleness(args, report: Optional[CoverageReport]) -> None:
    if report:
        _check_staleness(report.path, args.paths, args.strict_freshness)


def _check_results_empty(results: list, args, skipped: list) -> None:
    if results:
        return
    complexity_scan.print_skipped(skipped, sys.stderr)
    message = (
        f"no functions analysed in: {', '.join(args.paths)}\n"
        "  Check that the paths contain source files for the chosen --lang.\n"
        "  Use --allow-empty to suppress this error."
    )
    _fail_or_warn(message, strict=not args.allow_empty)


def _fn_to_dict(r: FunctionResult, cov_source: str) -> dict:
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


def _print_json(results: list, args, n_fail: int, skipped: list, cov_source: str) -> None:
    payload = {
        "threshold":       args.threshold,
        "warn":            args.warn,
        "pass":            n_fail == 0,
        "coverage_source": cov_source,
        "functions":       [_fn_to_dict(r, cov_source) for r in results],
        "skipped":         skipped,
    }
    print(json.dumps(payload, indent=2))


def _emit_output(results: list, args, n_fail: int, skipped: list, cov_source: str) -> None:
    if args.json_output:
        _print_json(results, args, n_fail, skipped, cov_source)
        return
    print_table(results, no_color=args.no_color, top=args.top)
    print_summary(results, warn_threshold=args.warn, fail_threshold=args.threshold)
    complexity_scan.print_skipped(skipped, sys.stdout)


def _check_baseline_args(args, report: Optional[CoverageReport]) -> None:
    if args.update and not args.baseline:
        raise ToolError("--update needs --baseline")
    if args.baseline and report is None:
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
    report = _given_report(args)
    _check_coverage_source(args, report)
    _check_baseline_args(args, report)
    _maybe_check_staleness(args, report)
    found = complexity_scan.scan(args.paths, args.lang)
    results = score(found.functions, _coverage_of(report), Limits(args.min_cc, args.warn, args.threshold))
    _check_results_empty(results, args, found.skipped)
    n_fail = sum(1 for r in results if r.grade == "FAIL")
    _emit_output(results, args, n_fail, found.skipped, _coverage_source(report))
    if args.baseline:
        return _enforce_baseline(results, args, root)
    return 1 if n_fail > 0 else 0


def main(argv=None, root=None) -> None:
    sys.exit(run_gate(gate, argv, root, TAG))


if __name__ == "__main__":
    main()
