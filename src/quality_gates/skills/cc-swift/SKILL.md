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

1. Locate the Swift source directory (typically `Sources/`). The tool skips the folders listed in ADR-001's addenda "one complexity scan for both gates" and "skip SwiftPM's .build". It follows symlinked folders by the rule in the addendum "follow symlinked folders". It names each skipped folder it found on a last `Skipped N folder(s):` line; if that line names a folder holding real source, report it. A folder marked `(already scanned)` was scanned once and is not lost source.
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
   With tests, swap `--no-coverage` for coverage so the CRAP column is a gate: `--xcresult <path>` for an Xcode project's `.xcresult` bundle, or, in a SwiftPM package, run `swift test --enable-code-coverage` and pass `--llvm-cov-json "$(swift test --show-codecov-path)"`; for either, measure coverage in the checkout where `crap` runs, since a report file counts only at the exact path `crap` scans
4. Report SwiftLint warnings (CC > 6) and errors (CC > 8). With `--no-coverage`, lizard's CRAP column is a worst-case ranking, not a gate: every function at CC 3 or above "fails" it
   Which Swift initialisers and accessors become Functions, including `init?` and `private(set)`: ADR-001 addenda "a workaround for two lizard Swift bugs (v0.8.3)" and "the `(set)` rule no longer depends on the word before it, except `init` (v0.9.1)".
5. For each violation propose: extract helper functions, break up long `switch` bodies, split large `body` computed properties into `@ViewBuilder` helpers

## Thresholds

| CC  | SwiftLint rule | Action |
|-----|----------------|--------|
| ≤ 6 | ok | none |
| 7–8 | warning | note it; refactor if you are in the function anyway |
| > 8 | error — blocks build | fix now |

The project's `.swiftlint.yml` should hold:

```yaml
cyclomatic_complexity:
  warning: 6
  error: 8
  ignores_case_statements: true
```

`ignores_case_statements: true` stops an exhaustive `switch` over an enum from
counting one per case (ADR-001). If a project's file disagrees, report it.

## Architectural constraints — apply when writing new Swift in this session

- Maximum CC: 8 (agent ceiling, ADR-001)
- Deconstruct before implementing: break multi-step logic into private helpers before writing the main function body
- Flatten control flow: guard/early return over nested `if` branches
- SwiftUI views: split large `body` computed properties into focused `@ViewBuilder` helpers; break long `switch` arms into named view functions

## Review rule

In Swift, a new or changed closure (including a trailing closure or a nested `func`) that contains a branch has a test that runs it. It is a judgement call in review, not a gate. The reason differs by kind:

- A closure: the CRAP gate does not count a closure's lines against the function that holds it, so an untested closure passes inside a tested holder (until quality-gates issue #53).
- A nested `func`: the CRAP gate scores it on its own and fails an untested one with two or more branches. A small one (a single branch, CRAP 6) can still pass untested, which is why the rule asks for a test for it too.

quality-gates ADR-001, addendum "a review rule covers the closure gap (v0.8.4)", records the decision.

## Dependencies

```bash
brew install swiftlint          # CC linting
xcode-select --install          # xcrun xccov for --xcresult coverage (optional); lizard ships with quality-gates
```

## Installing the commands

`cc-check`, `crap` and `comment-debt` come from the quality-gates Python package. If one is missing:

```bash
uv tool install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.9.0"
# or, inside a project venv:
pip install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.9.0"
```
