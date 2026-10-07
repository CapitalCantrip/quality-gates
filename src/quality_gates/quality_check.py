#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from quality_gates import lizard_scan, ratchet

AGENT_CC_CEILING = 8
EXCLUDED_PARTS = {"__pycache__", ".git", "backups", "venv", ".venv", "node_modules"}


def build_parser():
    parser = argparse.ArgumentParser(description="Cyclomatic complexity reporter for Python and TypeScript code")
    parser.add_argument(
        "--lang", choices=["python", "typescript"], default="python",
        help="python counts with radon; typescript counts .ts .tsx .js .jsx with lizard (default: python)",
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


def load_radon():
    try:
        from radon.complexity import cc_visit, cc_rank
    except ImportError:
        print("ERROR: radon not installed. Run: pip install radon", file=sys.stderr)
        sys.exit(2)
    return cc_visit, cc_rank


def python_files(target):
    if not target.exists():
        print(f"ERROR: path not found: {target}", file=sys.stderr)
        sys.exit(2)
    if target.is_file():
        return [target] if target.suffix == ".py" else []
    return sorted(target.rglob("*.py"))


def collect_files(paths):
    files = []
    for path in paths:
        files.extend(f for f in python_files(Path(path)) if not EXCLUDED_PARTS.intersection(f.parts))
    if not files:
        print("No Python files found.", file=sys.stderr)
        sys.exit(2)
    return files


def read_blocks(filepath, cc_visit):
    try:
        return cc_visit(filepath.read_text(encoding="utf-8"))
    except (OSError, ValueError, SyntaxError):
        return []


def to_result(filepath, block, cc_rank, threshold):
    return {
        "file": str(filepath),
        "name": block.name,
        "fullname": block.fullname,
        "type": block.__class__.__name__,
        "complexity": block.complexity,
        "rank": cc_rank(block.complexity),
        "line": block.lineno,
        "above_threshold": block.complexity > threshold,
    }


def analyse(files, threshold):
    cc_visit, cc_rank = load_radon()
    return [
        to_result(filepath, block, cc_rank, threshold)
        for filepath in files
        for block in read_blocks(filepath, cc_visit)
    ]


def check_paths_exist(paths):
    for path in paths:
        if not Path(path).exists():
            print(f"ERROR: path not found: {path}", file=sys.stderr)
            sys.exit(2)


def lizard_to_result(fn, cc_rank, threshold):
    return {
        "file": fn["file"],
        "name": fn["name"],
        "fullname": fn["label"],
        "type": "Function",
        "complexity": fn["cc"],
        "rank": cc_rank(fn["cc"]),
        "line": fn["start"],
        "above_threshold": fn["cc"] > threshold,
    }


def analyse_typescript(paths, threshold):
    check_paths_exist(paths)
    _, cc_rank = load_radon()
    functions = lizard_scan.scan(paths, "typescript")
    if not functions:
        print("No TypeScript or JavaScript functions found.", file=sys.stderr)
        sys.exit(2)
    files = sorted({fn["file"] for fn in functions})
    return [lizard_to_result(fn, cc_rank, threshold) for fn in functions], files


def analyse_paths(args):
    if args.lang == "typescript":
        return analyse_typescript(args.paths, args.threshold)
    files = collect_files(args.paths)
    return analyse(files, args.threshold), files


def display_path(file):
    path = Path(file)
    return path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path.name


def print_flagged(flagged):
    if not flagged:
        print("  All functions at or below threshold. ✓")
        return
    print(f"FLAGGED — {len(flagged)} function(s) above threshold:\n")
    for r in sorted(flagged, key=lambda x: -x["complexity"]):
        print(f"  [{r['rank']}] CC={r['complexity']:>3}  {display_path(r['file'])}:{r['line']}  {r['name']}")


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


def run(argv, root):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.update and not args.baseline:
        parser.error("--update needs --baseline")
    results, files = analyse_paths(args)
    code = report(results, files, args)
    if not args.baseline:
        return code
    out = sys.stderr if args.format == "json" else sys.stdout
    current = over_threshold(results, root or ratchet.repo_root())
    return ratchet.enforce(current, Path(args.baseline), args.update, out)


def main(argv=None, root=None):
    sys.exit(run(argv, root))


if __name__ == "__main__":
    main()
