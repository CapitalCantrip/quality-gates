# Changelog

## 0.7.3 — 2026-10-10

`crap --lang typescript` now scores each function that shares a start line with
another over its own lines (#41, ADR-001 addendum of 2026-10-10). lizard gives
no column, so in `const f = () => xs.map(x => x ? 1 : 2)` both functions start
on line 1, and the first Istanbul entry on that line was taken for both: a
callback on the first line of a multi-line function was scored over the whole
function. Each lizard function now takes the entry that ends where it ends,
else the narrowest entry that contains its end, else the one that ends
last. TypeScript and JavaScript CRAP scores may change for functions that
share a start line with another, up or down; a function that is the only one
starting on its line scores as in 0.7.2. Coverage is still counted by line, so
a callback sharing a line with its holder still counts that line's branches
and statements. `cc-check` and Python and Swift scores do not change.

**When you bump the pin:** run `qg-skills`. A project with a TypeScript or
JavaScript `crap-baseline.json`: on the bump commit, with the gates passing on
the commit before, collect coverage as your CI does, delete
`crap-baseline.json`, run `crap` with `--update` exactly as your hook and CI
call it, and commit. Review the diff in the pull request: an entry that rose
or is new is a callback, or a function declared after another on the same line,
that was scored over a range with fewer or better tested branches than its
own. `--update` only lowers scores, so do not run it
against the old baseline. Other projects: nothing else.

## 0.7.2 — 2026-10-10

A method of a class defined inside a function is now scored on its own (#44).
radon drops a class defined in a function body, so neither `cc-check` nor `crap`
ever listed its methods. They are now listed under the dotted name `f.K.m`, at
any depth: a class in a method of a class in a function, a nested class in that
class, and closures inside such a method. The enclosing function's own score is
unchanged and nothing is counted twice. In a rare case a newly scored method
takes a name an existing function had; the existing function, if it comes
later in the file, is then keyed `#2`. This is a bug fix: ADR-001 already says
every method is scored.

**When you bump the pin:** run `qg-skills`. Then, on the bump commit, with the
gates passing on the commit before, delete `cc-baseline.json` and
`crap-baseline.json`, run each gate with `--update` exactly as your hook and
CI call it, and commit. Review the new entries in the pull request diff: they
are methods of classes defined inside functions that were over the limit all
along. Python reports may gain functions that were never scored before.

## 0.7.1 — 2026-10-10

One coverage seam in `crap` (#46, architecture review change 2; the review is
now in `docs/reviews/`). Each language is one record that both gates read: its
counting tool, its coverage flag and reader, and its "nothing found" message.
Every coverage reader answers the same question, the coverage of one function,
and `crap` scores every language through one path. No behaviour changes: the
output of `crap` and `cc-check`, text and JSON, is the same as in 0.7.0.

**When you bump the pin:** run `qg-skills`. Nothing else.

## 0.7.0 — 2026-10-09

One complexity scan for both gates (#43, ADR-001 addendum of 2026-10-09).
`cc-check` and `crap` now take their functions from one module, so they always
list the same functions under the same names.

- Classes are no longer scored by `cc-check`; `crap` never scored them.
- Python closures and methods of nested classes are scored on their own, named
  `outer.inner` and `K.Inner.deep`. A Python name that repeats in a file gets
  `#2`, `#3`, as TypeScript and Swift names already did.
- One skip list for both gates and every language: `.git`, `.venv`, `venv`,
  `.direnv`, `node_modules`, `__pycache__`, `backups`, `build`, `dist`, `.tox`,
  `.mypy_cache`, `.pytest_cache`, `.worktrees`, `.claude/worktrees`. `crap` now
  skips `venv` and scans hidden folders such as `.claude/hooks`; `cc-check` now
  skips `build`, `dist` and the tool caches.
- Both gates end their report with `Skipped N folder(s): ...` naming every
  skipped folder found inside the scanned paths. `crap --json` has it as a
  `skipped` list; `cc-check --format json` writes the line to stderr. When
  every file was skipped, the line comes before the "nothing found" error.
- TypeScript and Swift scans read only the files under the given paths, so a
  `build` or `dist` folder above the scanned path no longer hides the whole
  project. A scan of `.` reports `src/a.ts`, not `./src/a.ts`.
- `cc-check` drops the A–F letter. Its JSON loses `rank`, and `name` now holds
  the full name (`K.m`), the same as `fullname`.
- Error messages from radon and lizard now carry the tag of the gate that
  printed them (`ERROR:` in `cc-check`, `[crap]` in `crap`) instead of
  `[lizard]`. A missing radon reads the same in both gates. Exit codes are
  unchanged.

**When you bump the pin:** run `qg-skills`. Then, on the bump commit, with the
gates passing on the commit before, delete `cc-baseline.json` and
`crap-baseline.json`, run each gate with `--update` exactly as your hook and
CI call it, and commit. Review the new entries in the pull request diff: they
are closures, nested-class methods and functions in hidden folders that were
over the limit all along. Anything that reads `cc-check --format json` must
stop reading `rank`, and gets the full name (`K.m`) from `name`.

## 0.6.0 — 2026-10-08

CC and CRAP gates for TypeScript and JavaScript (#21, ADR-001 addendum of
2026-10-07, now accepted).

- `cc-check --lang typescript PATHS` counts `.ts`, `.tsx`, `.js` and `.jsx`
  with lizard and fails above 8, with `--baseline` as for Python. `--lang`
  defaults to `python`, so existing calls are unchanged.
- `crap --lang typescript PATHS --istanbul-json coverage/coverage-final.json`
  takes per-function coverage from Istanbul's JSON report (Vitest, Jest).
  `--no-coverage` and `--baseline` work as for the other languages.
- A new `/cc-typescript` skill; `/crap` and `/setup-standards` cover
  TypeScript, and `/setup-standards` has CI steps for it.
- Baseline keys: a function name that repeats in a file is keyed with its
  order, `path::(anonymous)#2`. This also applies to Swift.
- lizard is now a core dependency; the `[swift]` extra is gone.

**When you bump the pin:** run `qg-skills`. If you installed
`quality-gates[swift]`, drop `[swift]`. A Swift project with a
`crap-baseline.json` whose functions share a name in one file: run its
`crap --lang swift ... --update` once, as the second and later of those
entries are now keyed `name#2`, `#3`. A TypeScript or JavaScript project:
run `/setup-standards` to add the gates.

## 0.5.3 — 2026-10-07

Documentation only: the README's *Releasing* section says to push the release
tag from a local session, because a cloud session's GitHub proxy refuses tag
pushes.

**When you bump the pin:** nothing to do beyond `qg-skills`.

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
- PR bodies go through the `pr` skill. `qg-agent-docs` now writes
  `.github/pull_request_template.md` with its Summary / Evidence / Merge
  Danger headings, and adds a *Pull requests* section to the Agent skills
  block in `CLAUDE.md`, even when the block is already there. Before this,
  nothing pointed an agent at the skill, so PR bodies came out freehand.
- This repo only: a SessionStart hook installs `.venv` in cloud sessions (#36),
  and its own pre-commit hook finds `.venv/bin` (#33).

**When you bump the pin:** run `qg-skills` to get the new stage guard, and
`qg-agent-docs --tracker <yours>` (or `/setup-standards`) for the PR template
and the *Pull requests* section; if you already have a PR template, it is kept
and the tool shows the difference. If your
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
