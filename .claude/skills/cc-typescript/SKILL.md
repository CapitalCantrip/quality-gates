---
name: cc-typescript
description: >
  Cyclomatic complexity check for TypeScript and JavaScript via cc-check --lang typescript (lizard); flags functions above CC 8 and proposes refactors. Use when asked to check TypeScript or JavaScript complexity.
---

# /cc-typescript — TypeScript and JavaScript Cyclomatic Complexity Check

Runs `cc-check --lang typescript` against `.ts`, `.tsx`, `.js` and `.jsx` files
and reports functions above the complexity threshold. lizard counts; the reasons
are in ADR-001's TypeScript addendum.

## Invocation

```
/cc-typescript [path] [--threshold N]
```

- `path` — file or directory (default: `src`)
- `--threshold N` — flag CC > N (default: 8). A project may pass a lower number, never a higher one

## Steps

1. Identify the source directories. The tool skips the folders ADR-001's 2026-10-09 addendum lists and names each one it found on a last `Skipped N folder(s):` line; if that line names a folder holding real source, report it.
2. Run:
   ```bash
   cc-check --lang typescript <dirs> --threshold 8
   ```
   If the repo has a CC baseline (e.g. `cc-baseline.json`), add `--baseline <file>`: it then fails only on new or worse functions.
   Use `cc-check` as the gate rather than ESLint's `complexity` rule, so CC and CRAP share one counter.
3. Report every flagged function with file, line and CC.
4. For each violation propose a concrete refactor: extract named helpers, replace `switch` or `if/else if` chains with a lookup object, return early instead of nesting.

Done when every flagged function is reported with a refactor, or the run is clean.

## What counts

ADR-001's TypeScript addendum lists what lizard counts, including its one known miscount.

## Baseline keys

A name that repeats in a file is keyed with its order, `path::(anonymous)#2`; ADR-001's TypeScript addendum gives the rule and the reason.

## Dependencies

lizard ships with quality-gates. No Node packages are needed for CC.

## Installing the commands

`cc-check`, `crap` and `comment-debt` come from the quality-gates Python package. If one is missing:

```bash
uv tool install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.7.0"
```
