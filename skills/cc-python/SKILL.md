---
name: cc-python
description: >
  Cyclomatic complexity check for Python via cc-check (radon); flags functions above CC 8 and proposes refactors. Use when asked to check Python complexity.
---

# /cc-python — Python Cyclomatic Complexity Check

Runs `cc-check` (quality_check.py) against Python source files and reports
functions above the complexity threshold.

## Invocation

```
/cc-python [path] [--threshold N]
```

- `path` — file or directory (default: `.`)
- `--threshold N` — flag CC > N (default: 8). A project may pass a lower number, never a higher one

## Steps

1. Identify Python source directories in the project (skip `venv`, `.venv`, `__pycache__`, `site-packages`)
2. Run:
   ```bash
   cc-check <dirs> --threshold 8 --format text
   ```
   8 is the agent-code ceiling (ADR-001); use a lower number only if the project sets one.
   `cc-check` takes one path per run: run it once per directory.
   Do not substitute `ruff --select C901`: ruff skips `and`/`or` and comprehension clauses and scores lower than radon, which CRAP also uses
3. Report all flagged functions with file, line, CC score
4. For each violation propose a concrete refactor: extract named sub-functions, replace long if/elif chains with dispatch dicts, simplify nested loops

## Thresholds (McCabe scale)

| CC  | Grade | Action |
|-----|-------|--------|
| 1–5 | A – simple | none |
| 6–8 | B – moderate | acceptable for agent code; needs tests to pass CRAP (62% at 6, 100% at 8) |
| 9+ | C–F | fails the gate; refactor before commit |

## Architectural constraints — apply when writing new Python in this session

- Maximum CC: 8 (agent ceiling)
- Deconstruct before implementing: identify branching paths first, extract each into a named helper before writing the main function body
- Flatten conditionals: dispatch dicts over long `if/elif` chains, early `return` over nested branches
- One loop level: extract the body of a nested loop into a named function

## Dependencies

```bash
pip3 install radon
```

## Installing the commands

`cc-check`, `crap` and `comment-debt` come from this plugin's Python package. If one is missing:

```bash
uv tool install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.2.0"
# or, inside a project venv:
pip install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.2.0"
```
