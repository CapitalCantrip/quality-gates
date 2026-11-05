#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from quality_gates import complexity_scan, languages, project_files, ratchet
from quality_gates.errors import given_path, run_gate

AGENT_CC_CEILING = 8
ERROR_TAG = "ERROR: "
DEFAULT_LANG = "python"
FINDING_KIND = "complexity"

LANGUAGES = {
    "python": "No Python files found.",
    "typescript": "No TypeScript or JavaScript functions found.",
}


def _description() -> str:
    labels = " and ".join(languages.LANGUAGES[name].label for name in LANGUAGES)
    return f"Cyclomatic complexity reporter for {labels} code"


def _lang_help() -> str:
    counts = "; ".join(
        f"{name} counts {languages.LANGUAGES[name].suffix_text} with {complexity_scan.COUNTERS[name].tool}"
        for name in LANGUAGES
    )
    return f"{counts} (default: {DEFAULT_LANG})"


def build_parser():
    parser = argparse.ArgumentParser(description=_description())
    parser.add_argument(
        "--lang", choices=list(LANGUAGES), default=DEFAULT_LANG,
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
    for finding in sorted(flagged, key=lambda f: -f.number):
        print(f"  {finding.display}")


def print_text(flagged, functions, files, threshold):
    print(f"\n=== Cyclomatic Complexity Report (threshold: CC > {threshold}) ===\n")
    print_flagged(flagged)
    print("\nSUMMARY:")
    print(f"  Files analysed:     {len(files)}")
    print(f"  Functions checked:  {len(functions)}")
    print(f"  Above threshold:    {len(flagged)}")
    print(f"  At/below threshold: {len(functions) - len(flagged)}")
    print("\n  → Refactoring needed. Exit 1." if flagged else "\n  → Clean. Exit 0.")


def to_finding(fn, root):
    shown = f"CC={fn.cc:>3}  {display_path(fn.file)}:{fn.start}  {fn.name}"
    return ratchet.Finding(ratchet.location(root, fn.file, fn.name), fn.cc, FINDING_KIND, shown)


def findings(functions, threshold, root):
    return [to_finding(fn, root) for fn in functions if fn.cc > threshold]


def report(found, flagged, args):
    if args.format == "json":
        print(json.dumps([to_result(fn, args.threshold) for fn in found.functions], indent=2))
    else:
        print_text(flagged, found.functions, found.files, args.threshold)


def gated(flagged, args):
    return [] if args.format == "json" else flagged


def parse_args(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.update and args.baseline is None:
        parser.error("--update needs --baseline")
    if args.baseline is not None:
        given_path("--baseline", args.baseline)
    return args


def gate(argv, root):
    args = parse_args(argv)
    found = complexity_scan.scan(args.paths, args.lang, root=root)
    if not found.files:
        complexity_scan.print_skipped(found.skipped, sys.stderr)
        print(LANGUAGES[args.lang], file=sys.stderr)
        return 2
    flagged = findings(found.functions, args.threshold, project_files.root_for(args.paths, root))
    report(found, flagged, args)
    out = sys.stderr if args.format == "json" else sys.stdout
    complexity_scan.print_skipped(found.skipped, out)
    if args.baseline is None:
        return ratchet.exit_code(ratchet.judge(gated(flagged, args), {}))
    return ratchet.enforce(flagged, Path(args.baseline), args.update, out)


def main(argv=None, root=None):
    sys.exit(run_gate(gate, argv, root, ERROR_TAG))


if __name__ == "__main__":
    main()
