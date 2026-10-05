# Changelog

## 0.4.0 — 2026-10-06

The workflow and principles layers of ADR-002, now accepted.

- New skill `standards`: the size rule and 13 principles, one file each, with
  an index the agent reads to pick the one that applies.
- New skill `/setup-standards`: sets up or upgrades a project for all three
  layers (agent docs, glossary, gates, baselines, hooks, CI, asking rule) and
  ends with a plain report.
- `qg-skills` also installs the stage guard (a Claude Code hook refusing
  `git add -A`, `git add .`, `git commit -a`) and the asking-rule line in
  `CLAUDE.md`. `qg-skills --check` fails when either is missing or stale, and
  exits 2 when `.claude/settings.json` is not valid JSON.
- New command `qg-agent-docs`: writes `docs/agents/` from Matt Pocock's setup
  templates without overwriting your edits.
- New command `qg-upstream`, run monthly by a workflow in this repo: reports
  upstream changes to the files copied from Pocock and pstack.

**When you bump the pin:** run `/setup-standards`, or at least `qg-skills`, and
commit what it writes (`.claude/skills/`, `.claude/hooks/`,
`.claude/settings.json`, `CLAUDE.md`). Until you do, a test calling
`skills_sync.main(["--check"])` fails.

## 0.3.2 — 2026-10-04

No comment debt left in the repo (#1).

- `crap --help` is rewritten: the epilog came from the module docstring and
  named a `../crap.py` path and a SwiftLint install that no longer apply. It
  now lists the languages, examples, exit codes and dependencies. Defaults and
  flags are unchanged.
- `crap` has its own test suite covering the formula, coverage parsing for both
  languages, the `--top` cap and every tool-error exit.

**When you bump the pin:** run `qg-skills` and commit `.claude/skills/`; nothing
else changes.

## 0.3.1 — 2026-10-04

Skills for cloud sessions. A cloud session doesn't install plugins a repo
enables in `.claude/settings.json`, so the skills never loaded there.

- The skills ship inside the Python package (`src/quality_gates/skills/`); the
  plugin manifest points there.
- New command `qg-skills` copies them into `.claude/skills/`; `--check` exits 1
  when the copies differ from the installed version.

**When you bump the pin:** run `qg-skills`, commit `.claude/skills/`, add a test
calling `skills_sync.main(["--check"])`, and remove the `quality-gates` entries
from `extraKnownMarketplaces` and `enabledPlugins` so skills aren't listed twice.

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
