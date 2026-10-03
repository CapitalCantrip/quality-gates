#!/usr/bin/env python3
"""
quality_check.py — Cyclomatic complexity reporter for Python code.

Uses radon to compute per-function cyclomatic complexity (CC).
Flags functions above a threshold. Used by the Cleaner agent pipeline stage.

Usage:
    python3 quality_check.py <path> [--threshold N] [--format text|json]

    <path>       File or directory to analyse (recursively for directories)
    --threshold  CC score above which functions are flagged (default: 8)
    --format     Output format: 'text' (default) or 'json'

Exit codes:
    0  All functions at or below threshold (or --format json regardless)
    1  One or more functions exceed threshold
    2  No Python files found / bad arguments

Cyclomatic Complexity scale (McCabe / radon):
    1-5  (A) Simple, low risk
    6-10 (B) Moderate — acceptable for agent-maintained code up to ~8
    11+  (C-F) Complex — refactor required

Uncle Bob / Martin guidance (from 2026-09-06 interview):
    Human-maintained code: target CC <= 5
    Agent-maintained code: target CC <= 8 (agents have exact short-term memory,
    so some cognitive-load constraints that drive human thresholds can be relaxed)
"""

import sys
import json
import argparse
from pathlib import Path

AGENT_CC_CEILING = 8


def main():
    parser = argparse.ArgumentParser(
        description="Cyclomatic complexity reporter (Cleaner pipeline stage)"
    )
    parser.add_argument("path", help="File or directory to analyse")
    parser.add_argument(
        "--threshold",
        type=int,
        default=AGENT_CC_CEILING,
        help="CC score above which functions are flagged (default: 8)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    try:
        from radon.complexity import cc_visit, cc_rank
    except ImportError:
        print("ERROR: radon not installed. Run: pip install radon", file=sys.stderr)
        sys.exit(2)

    target = Path(args.path)
    if not target.exists():
        print(f"ERROR: path not found: {target}", file=sys.stderr)
        sys.exit(2)

    # Collect Python files
    if target.is_file():
        files = [target] if target.suffix == ".py" else []
    else:
        files = sorted(target.rglob("*.py"))

    # Exclude non-project paths
    excluded = {"__pycache__", ".git", "backups", "venv", ".venv", "node_modules"}
    files = [f for f in files if not any(part in excluded for part in f.parts)]

    if not files:
        print("No Python files found.", file=sys.stderr)
        sys.exit(2)

    results = []
    for filepath in files:
        try:
            source = filepath.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            blocks = cc_visit(source)
        except SyntaxError:
            continue
        for block in blocks:
            results.append(
                {
                    "file": str(filepath),
                    "name": block.name,
                    "type": block.__class__.__name__,
                    "complexity": block.complexity,
                    "rank": cc_rank(block.complexity),
                    "line": block.lineno,
                    "above_threshold": block.complexity > args.threshold,
                }
            )

    if args.format == "json":
        print(json.dumps(results, indent=2))
        sys.exit(0)

    # Text output
    flagged = [r for r in results if r["above_threshold"]]
    ok = [r for r in results if not r["above_threshold"]]

    print(f"\n=== Cyclomatic Complexity Report (threshold: CC > {args.threshold}) ===\n")

    if flagged:
        print(f"FLAGGED — {len(flagged)} function(s) above threshold:\n")
        for r in sorted(flagged, key=lambda x: -x["complexity"]):
            rel = Path(r["file"]).relative_to(Path.cwd()) if Path(r["file"]).is_relative_to(Path.cwd()) else Path(r["file"]).name
            print(f"  [{r['rank']}] CC={r['complexity']:>3}  {rel}:{r['line']}  {r['name']}")
    else:
        print("  All functions at or below threshold. ✓")

    print(f"\nSUMMARY:")
    print(f"  Files analysed:     {len(files)}")
    print(f"  Functions checked:  {len(results)}")
    print(f"  Above threshold:    {len(flagged)}")
    print(f"  At/below threshold: {len(ok)}")

    if flagged:
        print(f"\n  → Refactoring needed. Exit 1.")
        sys.exit(1)
    else:
        print(f"\n  → Clean. Exit 0.")
        sys.exit(0)


if __name__ == "__main__":
    main()
