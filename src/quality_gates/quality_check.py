#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from quality_gates import complexity_scan, languages, ratchet
from quality_gates.errors import run_gate

AGENT_CC_CEILING = 8
ERROR_TAG = "ERROR: "
DEFAULT_LANG = "python"


def _cc_check_items():
    return [(name, languages.LANGUAGES[name]) for name in languages.CC_CHECK_LANGUAGES]


def _description() -> str:
    labels = " and ".join(language.label for _, language in _cc_check_items())
    return f"Cyclomatic complexity reporter for {labels} code"


def _lang_help() -> str:
    counts = "; ".join(
        f"{name} counts {language.suffix_text} with {language.counter}"
        for name, language in _cc_check_items()
    )
    return f"{counts} (default: {DEFAULT_LANG})"


def build_parser():
    parser = argparse.ArgumentParser(description=_description())
    parser.add_argument(
        "--lang", choices=languages.CC_CHECK_LANGUAGES, default=DEFAULT_LANG,
        help=_lang_help(),
    )
    parser.add_argument("paths", nargs="+", metavar="path", help="files or directories to analyse")
    parser.add_argument(
        "--threshold", type=int, default=AGENT_CC_CEILING,
        help=f"CC score above which functions are flagged (default: {AGENT_CC_CEILING})",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="output format (default: text)")
    parser.add_argument("--baseline", metavar="FILE", help="fail only on functions that are new or worse than this file")
    parser.add_argument("--update", action="store_true", help="lower the baseline to match the tree")
    return parser


def to_result(fn, threshold):
    return {
        "file": fn.file,
        "name": fn.name,
        "fullname": fn.name,
        "type": "Function",
        "complexity": fn.cc,
        "line": fn.start,
        "above_threshold": fn.cc > threshold,
    }


def display_path(file):
    path = Path(file)
    return path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path.name


def print_flagged(flagged):
    if not flagged:
        print("  All functions at or below threshold. ✓")
        return
    print(f"FLAGGED — {len(flagged)} function(s) above threshold:\n")
    for r in sorted(flagged, key=lambda x: -x["complexity"]):
        print(f"  CC={r['complexity']:>3}  {display_path(r['file'])}:{r['line']}  {r['name']}")


def print_text(results, files, threshold):
    flagged = [r for r in results if r["above_threshold"]]
    print(f"\n=== Cyclomatic Complexity Report (threshold: CC > {threshold}) ===\n")
    print_flagged(flagged)
    print("\nSUMMARY:")
    print(f"  Files analysed:     {len(files)}")
    print(f"  Functions checked:  {len(results)}")
    print(f"  Above threshold:    {len(flagged)}")
    print(f"  At/below threshold: {len(results) - len(flagged)}")
    print("\n  → Refactoring needed. Exit 1." if flagged else "\n  → Clean. Exit 0.")
    return 1 if flagged else 0


def over_threshold(results, root):
    scores = {}
    for r in results:
        if r["above_threshold"]:
            ratchet.record(scores, ratchet.key(root, r["file"], r["fullname"]), r["complexity"])
    return scores


def report(results, files, args):
    if args.format == "json":
        print(json.dumps(results, indent=2))
        return 0
    return print_text(results, files, args.threshold)


def gate(argv, root):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.update and not args.baseline:
        parser.error("--update needs --baseline")
    found = complexity_scan.scan(args.paths, args.lang)
    if not found.files:
        complexity_scan.print_skipped(found.skipped, sys.stderr)
        print(languages.LANGUAGES[args.lang].cc_check_nothing_found, file=sys.stderr)
        return 2
    results = [to_result(fn, args.threshold) for fn in found.functions]
    code = report(results, found.files, args)
    out = sys.stderr if args.format == "json" else sys.stdout
    complexity_scan.print_skipped(found.skipped, out)
    if not args.baseline:
        return code
    current = over_threshold(results, root or ratchet.repo_root())
    return ratchet.enforce(current, Path(args.baseline), args.update, out)


def main(argv=None, root=None):
    sys.exit(run_gate(gate, argv, root, ERROR_TAG))


if __name__ == "__main__":
    main()
