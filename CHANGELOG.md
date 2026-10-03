# Changelog

## 0.3.0 — 2026-10-04

A baseline ratchet for `cc-check` and `crap`, so a repo with existing debt can
put them in CI.

- `cc-check` and `crap` take `--baseline FILE` and `--update`. The baseline maps
  `path::function` to its score for functions over the threshold. The check
  fails on a new or worse function, and on a lowered score until `--update`
  records it. `--update` never raises a score or adds an entry. A missing
  baseline file is an error (exit 2) except with `--update`, which creates it.
- `crap --baseline` needs coverage: it exits 2 with `--no-coverage` or with no
  coverage source.
- `cc-check` takes several paths in one run: `cc-check src tests`.
- `cc-check --format json` rows carry `fullname` (`Class.method` for methods).
- `crap` names methods `Class.method` (was `method`).
- `cc-check` and `crap` `main` take an `argv` list, so a test can call them.
- `cc-check`'s `main` and `comment-debt`'s `status` are split to CC 8 or below.

**When you bump the pin:** nothing breaks. To gate CI on CC or CRAP in a repo
with existing debt, run the gate once with `--baseline <file> --update`, commit
the file, and add a test that calls `main` with `--baseline <file>`. Scripts
that ran `cc-check` once per directory can pass all the paths at once.

## 0.2.0 — 2026-10-04

One complexity standard across languages. See ADR-001.

- `cc-check` defaults to `--threshold 8`, the agent ceiling (was 5).
- The Python CC gate is `cc-check` (radon), not `ruff --select C901`: radon is
  the counter `crap` uses, ruff scores the same function lower.
- Swift: SwiftLint `cyclomatic_complexity` warns above 6 and fails above 8, with
  `ignores_case_statements: true`.
- `crap --no-coverage` is documented as a ranking, not a gate.
- MIT licence.

**When you bump the pin:** replace any `ruff --select C901` gate with
`cc-check <path>`, and expect it to flag more existing functions than ruff did;
remove a `[tool.ruff.lint.mccabe]` block that disagrees with 8; set
`ignores_case_statements: true` in `.swiftlint.yml`.

## 0.1.0 — 2026-09-28

First release: `comment-debt`, `cc-check`, `crap`, and the skills
`/no-comments`, `/cc-python`, `/cc-rust`, `/cc-swift`, `/crap`.
