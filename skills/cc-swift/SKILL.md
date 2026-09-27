---
name: cc-swift
description: >
  Swift complexity check via SwiftLint and crap --lang swift (lizard); flags functions above the threshold and proposes refactors.
---

# /cc-swift — Swift Cyclomatic Complexity Check

Runs SwiftLint (if configured) and/or `crap --lang swift` (lizard) against
Swift source files and reports functions above the complexity threshold.

## Invocation

```
/cc-swift [Sources dir]
```

## Steps

1. Locate the Swift source directory (typically `Sources/`)
2. **If a `.swiftlint.yml` is present**, run SwiftLint first:
   ```bash
   swiftlint lint --reporter emoji
   # or if Makefile has the target:
   make lint-swift
   ```
3. **Always** run lizard for raw CC numbers:
   ```bash
   crap --lang swift <Sources dir> --no-coverage
   ```
   (Use `--xcresult <path>` instead of `--no-coverage` when an `.xcresult` bundle is available)
4. Report all functions with CC ≥ 10 — the warning threshold. CRAP FAILs (score > 8) are always shown
5. For each violation propose: extract helper functions, break up long `switch` bodies, split large `body` computed properties into `@ViewBuilder` helpers

## Thresholds

| CC  | SwiftLint rule | Action |
|-----|----------------|--------|
| ≤ 10 | ok | none |
| 11–15 | warning | schedule refactor |
| > 15 | error — blocks build | fix now |

## Architectural constraints — apply when writing new Swift in this session

- Maximum CC: 10
- Deconstruct before implementing: break multi-step logic into private helpers before writing the main function body
- Flatten control flow: guard/early return over nested `if` branches
- SwiftUI views: split large `body` computed properties into focused `@ViewBuilder` helpers; break long `switch` arms into named view functions

## Dependencies

```bash
brew install swiftlint          # CC linting
pip3 install lizard             # CC measurement (used by crap)
xcode-select --install          # xcrun xccov for coverage (optional)
```

## Installing the commands

`cc-check`, `crap` and `comment-debt` come from this plugin's Python package. If one is missing:

```bash
uv tool install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.1.0"
# or, inside a project venv:
pip install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.1.0"
```
