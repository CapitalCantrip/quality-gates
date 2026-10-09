---
name: crap
description: >
  Quality gate for Python, Swift, TypeScript/JavaScript, or Rust: CRAP scores
  (CRAP > 8 = FAIL) for Python/Swift/TypeScript; cognitive-complexity gate via cargo clippy (CC > 10 = FAIL) for
  Rust. Use when asked about complexity, coverage, or whether code passes the gate.
---

# /crap — Quality Gate

**Python / Swift / TypeScript** — CRAP score: `CRAP(f) = CC(f)² × (1−cov)³ + CC(f)`.
Gate: CRAP > 8 = FAIL. Fully-covered collapses to CRAP = CC; uncovered scores CC² + CC.

**Rust** — no CRAP formula; `cargo clippy` enforces cognitive complexity directly.
Gate: CC > 10 = FAIL, function > 25 executable lines = FAIL.

## Invocation

```
/crap [--lang python|swift|typescript|rust] [paths] [coverage options]
```

## Steps

1. Detect language from project context (`Cargo.toml` → Rust; `.swift` files → Swift; `package.json` or `.ts`/`.tsx`/`.js`/`.jsx`/`.cjs`/`.mjs` files → TypeScript; else Python).
2. **Rust** — no coverage file needed; proceed to step 3.
   **Python** — look for `coverage.json` (`coverage run -m pytest && coverage json`).
   **Swift** — an Xcode project: look for an `.xcresult` bundle (`xcodebuild test -resultBundlePath ...`). A SwiftPM package (`Package.swift`): run `swift test --enable-code-coverage`; the report is at `swift test --show-codecov-path`.
   **TypeScript** — look for `coverage/coverage-final.json` (Istanbul's `json` reporter, written by Vitest and Jest).
3. Run the gate:

   **Rust:**
   ```bash
   cargo clippy --all-targets 2>&1
   ```
   Report every `cognitive_complexity` and `too_many_lines` violation: file, function, score.

   **Python — with coverage:**
   ```bash
   coverage run -m pytest && coverage json
   crap --lang python <dirs> --coverage-json coverage.json
   ```

   **Python — no tests yet:**
   ```bash
   crap --lang python <dirs> --no-coverage
   ```

   **Swift — with coverage, Xcode project:**
   ```bash
   crap --lang swift Sources/ --xcresult /tmp/out.xcresult
   ```

   **Swift — with coverage, SwiftPM package:**
   ```bash
   swift test --enable-code-coverage
   crap --lang swift Sources/ --llvm-cov-json "$(swift test --show-codecov-path)"
   ```
   Run both in the same checkout. A report file counts only at the exact path `crap` scans, so a report made in another checkout or container gives every function unknown coverage. A function sharing a line with another function's body also gets unknown coverage; put each on its own lines.

   **Swift — no tests yet:**
   ```bash
   crap --lang swift Sources/ --no-coverage
   ```

   **TypeScript — with coverage** (Vitest needs `@vitest/coverage-v8`; under Jest use `npx jest --coverage --coverageReporters=json`):
   ```bash
   npx vitest run --coverage --coverage.reporter=json
   crap --lang typescript src --istanbul-json coverage/coverage-final.json
   ```

   **JSON output (Python/Swift/TypeScript, for CI):**
   ```bash
   crap --lang python <dirs> --coverage-json coverage.json --json
   ```

4. With `--no-coverage`, every function at CC 3 or above scores FAIL. That mode is a risk ranking, not a gate: report the top rows and say no coverage was available, never "the gate failed".
   With coverage, report all FAIL rows in full; summarise WARN rows (CRAP 5–8 for Python/Swift/TypeScript; CC 11–15 for Rust).
   `crap` skips the folders ADR-001's 2026-10-09 addendum lists and names each one it found on a last `Skipped N folder(s):` line (the `skipped` list in `--json`); if it names a folder holding real source, report it.
5. For each FAIL, recommend the cheaper fix first:
   - CC is the driver (high CC, low coverage): reduce CC — extract sub-functions
   - Coverage is the driver (low coverage, moderate CC): add tests
   - Rust: extract private helpers; flatten control flow with early `return` or `?`

## TypeScript coverage matching

Functions that start on the same line are matched to their Istanbul entries by the rule in ADR-001's 2026-10-10 addendum on shared start lines, and coverage is still counted by line. When a figure for such a function looks too high or too low, check for a neighbour function on its line before adding tests.

## Adopting the gate in a repo with existing debt (Python / Swift / TypeScript)

The baseline needs coverage data; `crap` refuses `--baseline` with `--no-coverage` (exit 2).

1. Record the debt once: `crap --lang python <dirs> --coverage-json coverage.json --baseline crap-baseline.json --update`. Commit the file.
2. Add a test that runs after coverage is collected and calls `crap.main([...same flags without --update...])`, asserting `SystemExit` code 0, so CI enforces it.
3. Baseline keys follow ADR-001's ratchet section and its 2026-10-09 addendum.
4. A new or worse function fails; a lowered score fails until `--update` records it. `--update` never raises a score or adds a function.

## Exit codes (Python / Swift / TypeScript)

| Code | Meaning |
|------|---------|
| 0 | All functions pass |
| 1 | One or more FAILs |
| 2 | Tool error (missing dep, bad path) |

## Dependencies

```bash
pip3 install coverage               # Python coverage; radon and lizard ship with quality-gates
xcode-select --install               # xcrun xccov (Swift --xcresult coverage only; SwiftPM's --llvm-cov-json needs nothing extra)
rustup component add clippy          # Rust
```

## Installing the commands

`cc-check`, `crap` and `comment-debt` come from the quality-gates Python package. If one is missing:

```bash
uv tool install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.8.0"
# or, inside a project venv:
pip install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.8.0"
```
