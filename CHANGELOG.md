# Changelog

## 0.5.2 — 2026-10-07

Moving freely between local and cloud sessions.

- The stage guard refuses `git add :.`, which stages the whole tree like
  `git add .` (#16).
- `/setup-standards` writes a pre-commit hook that puts `.venv/bin` on PATH
  when the project has a `.venv`, so a commit from VS Code or a cloud shell
  finds `comment-debt` and `cc-check` (#33).
- The issue-tracker template has an *In a cloud session* section: there
  `gh issue`, `gh pr` and `gh label` fail with HTTP 403, so use the GitHub MCP
  tools or `gh api` REST calls (#35).
- This repo only: a SessionStart hook installs `.venv` in cloud sessions (#36),
  and its own pre-commit hook finds `.venv/bin` (#33).

**When you bump the pin:** run `qg-skills` to get the new stage guard. If your
`.githooks/pre-commit` calls the gates by bare name and you use a `.venv`, add
`[ -d .venv/bin ] && PATH="$PWD/.venv/bin:$PATH"` after its shebang. If you
copied the issue-tracker doc from the template, add its *In a cloud session*
section.

## 0.5.1 — 2026-10-07

Documentation only: the README describes the package as it is since 0.5.0.

- A *Get started* section near the top gives the steps to set up a project
  on your computer or from a cloud session, to use it in a cloud session,
  and to keep it up to date.
  The older *Use it in a project* section becomes *Setup details*.
- The skills table lists every shipped skill, grouped by the step it serves,
  and says which are ours, which are Matt Pocock's word for word, and which
  are his with changes.
- The workflow table gives each route's later steps, as the size rule does.
- A fresh cloud session lists the project's skills only after its first
  message; *Get started* says so.
- A new maintainer section, *Keeping the copied skills current*, gives the
  monthly upstream routine.
- The licence section names the two upstream MIT works and where their
  notices are.
- The plugin manifests describe all three layers, not only the gates.

**When you bump the pin:** nothing to do beyond `qg-skills`.

## 0.5.0 — 2026-10-07

Matt Pocock's workflow skills ship with the package, so cloud sessions have
them ([ADR-003](docs/adr/ADR-003-vendor-pocock-skills.md)).

- `qg-skills` now also copies 17 of his skills: `wayfinder`,
  `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `implement-spec`,
  `tdd`, `diagnosing-bugs`, `improve-codebase-architecture`,
  `codebase-design`, `domain-modeling`, `pr`, `triage`, `retro`,
  `writing-for-agents`, `handoff`, and his `code-review` as
  `/review-against-spec`, so it no longer hides Claude Code's `/code-review`.
- `setup-matt-pocock-skills` is a pointer to `/setup-standards`.
- The size rule ends every route with `/review-against-spec`, and the largest
  route builds its tickets with `/implement-spec`.
- Every change to a copied file is listed, with how to redo it, in
  `docs/upstream-adaptations.md`; `qg-upstream` points there.

**When you bump the pin:** run `qg-skills`, commit the new skill folders, and
start a new session. If his plugin is installed, his skills appear twice; the
unprefixed ones are the pinned copies. If your project has its own skill with
one of the names above, `qg-skills` replaces it: rename yours first.

## 0.4.1 — 2026-10-06

Fixes from the first run of `/setup-standards` on a real project (localbar).

- `/setup-standards` writes `CLAUDE.md` pointers that say what the file they
  name holds, not just its path, and on a re-run rewrites existing pointers
  that only name a file.
- The README says how to start: run `qg-skills` before the first Claude Code
  session, because a session loads skills only when it starts.

**When you bump the pin:** run `qg-skills`, start a new session, run
`/setup-standards`, and commit what changes.

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
