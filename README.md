# quality-gates

A guided framework for building software with AI coding agents, from idea to
release, for people who can't review the code themselves. It aims for
well-designed outcomes, efficient use of resources, and a builder who stays
informed and in control ([ADR-005](docs/adr/ADR-005-direction-idea-to-release.md)).
Today it ships the gates and the working method; the rest is on the way.

Checks fail the commit or the build when the
agent's code gets too complex, goes untested or adds comments, so problems get
caught without anyone reading a diff. Claude Code skills set a project up and
keep the agent to a working method that fits the size of the job. Each project
pins a version, so nothing changes until you update, and a fix reaches every
project when its pin is bumped.

## Get started

Install the commands, copy the skills into the project, then run
`/setup-standards`: it does the rest. You can do this on your computer or from
a cloud session on your phone. To update, install the new version and repeat.

The project must be a git repository. Git keeps its history on your computer
and needs no cloud copy, so the commit hook and the gates work in a project
that never leaves your machine. The full feature set also needs GitHub: CI,
the issue tracker, recorded reasons that wait on an issue, and the route for
loosening a standard all run there. A local-only route for each is on the
roadmap ([#150](https://github.com/CapitalCantrip/quality-gates/issues/150)).

### Set up a project, on your computer

You need [uv](https://docs.astral.sh/uv/) and Claude Code. In the project's
folder:

1. Install the commands, pinned to a version. This puts `qg-skills`, the
   gate commands and `coverage` on your computer:

   ```bash
   uv tool install --with-executables-from coverage "quality-gates[coverage] @ git+https://github.com/CapitalCantrip/quality-gates@v0.12.0"
   ```

2. Run this command to copy the skills into the project:

   ```bash
   qg-skills
   ```

3. Start a new Claude Code session in the project and run `/setup-standards`.
   It sets up the issue tracker docs, the gates, the record of existing debt,
   the hooks and the CI checks, reports in plain words what it did, and
   commits.
4. Push.

Do step 2 before step 3: a session on your computer loads skills when it
starts, so a session started earlier has no `/setup-standards`.

### Set up a project, from a cloud session

Claude Code on the web, or the Code tab of the Claude mobile app:

1. Open a new session on the project.
2. Ask Claude to install quality-gates from GitHub with the line in step 1
   above, run `qg-skills`, open a pull request and merge it.
3. In the same session, run `/setup-standards`, then ask Claude to open a pull
   request and merge it.

### Use it in a cloud session

Once the project is set up, a cloud session has the skills from the project's
files; it needs no install of its own.

1. Open a session on the project.
2. Send a first message, such as "hi". The session fetches the project only
   when it gets one, so before that the `/` menu lists none of its skills.
3. Use the `/` commands.

### Keep it up to date

Each [CHANGELOG.md](CHANGELOG.md) entry ends with what to do for that version.
In general, on your computer or by asking Claude in a cloud session:

1. Install quality-gates again with the new version number in the line from
   step 1.
2. Run `qg-skills` and commit.
3. Run `/setup-standards` (on your computer, in a new session). It moves the
   project to the new version and adds anything the release brought.
4. Push, or open a pull request and merge it.

## Who this is for

You can describe what you want and tell whether the result works. You can't
read a diff and spot a design flaw, an untested path or an error that is
silently swallowed. That leaves four gaps:

| The gap | What goes wrong | What this repo does |
|---|---|---|
| Nobody reviews the code | The agent's bad habits ship | Gates: commands that fail the commit or the build, with no expertise needed to read the result |
| Written rules fade | "Never do X again" goes in a notes file, and X happens again | Lessons that recur become checks, not paragraphs |
| Good process and busy process look alike | Hours of polish on a design nobody agreed, or no plan where one was needed | The size of the work picks the starting step |
| Questions arrive in jargon | You choose between options you can't weigh | Every question states the stakes plainly, gives two or three options and recommends one |

Agents follow a failing tool more reliably than a paragraph of guidance, so
wherever a standard can be a command that exits non-zero, it is one.

## From idea to release

Quality is built in from the first step, not only checked at the end. Each
stage, from testing the idea through spec, planning, building and review to
release, leaves the builder with a clearer picture of where the project is
going and what each choice trades off. The gates below are the part that needs
no judgement; the direction for the rest is in
[ADR-005](docs/adr/ADR-005-direction-idea-to-release.md).

In a software factory, agents do most of the building and a person decides what
to build and checks that it works. That only holds up when no step depends on
someone reading the code:

- **It judges by numbers, not opinion.** Each gate is a command with a
  threshold and an exit code, so an agent running the line can act on the
  result without a person in the loop.
- **Every project gets the same standard.** Each one pins a tagged version, so
  every project on the line is checked the same way. The standard changes only
  through a written decision and a release, never by drift.
- **Old code doesn't stop the line, and no run makes it worse.** Existing debt
  is recorded once and can only shrink, so the factory can take on a project
  as it is.
- **It fails safe, and says why.** When a check can't tell, for example
  because it can't match test coverage to a file, it fails instead of guessing
  in the code's favour, and names the gap rather than dressing it up as a
  failing score.
- **The line learns once.** A mistake that keeps coming back becomes a check
  or a review rule, and it reaches every project at the next release.
- **People steer without reading code.** When an agent needs a decision, it
  gives the stakes in plain words, two or three options and a recommendation.

## Three layers

| Layer | Answers | Relies on |
|---|---|---|
| Workflow | what order to work in, for the size of the work | you picking the right starting step |
| Principles | how to judge each step, what counts as proof, how to ask you | the agent reading and applying them |
| Gates | what fails, whatever anyone intended | nothing |

A standard moves down this table whenever it can. The workflow is
[Matt Pocock's engineering skills](https://github.com/mattpocock/skills) and
many principles come from [Lauren Tan's pstack](https://github.com/cursor/plugins/tree/main/pstack).
All three layers ship in this package, so neither Pocock's plugin nor pstack needs installing. Why it
is shaped this way: [ADR-002](docs/adr/ADR-002-engineering-standards.md).

A fourth layer, **Understanding**, is planned: a project map of the outcome and
the key forks, a plain-words checkpoint at each stage boundary, fixed teaching
material, and a personal learning record kept outside the repo
([ADR-005](docs/adr/ADR-005-direction-idea-to-release.md)).

### Workflow: size decides where to start

| The work... | Start with | Then |
|---|---|---|
| won't fit in one agent session | `/wayfinder` | `/grill-with-docs`, `/to-spec`, `/to-tickets`, `/implement-spec` |
| fits in one session but touches several parts of the code | `/grill-with-docs` | `/to-spec`, `/implement` |
| is smaller than that | `/tdd`, or `/diagnosing-bugs` for a defect | |

Every route ends with `/review-against-spec`, then the gates. The size rule and
the principles ship as the `standards` skill, and Matt Pocock's skills for each
step ship beside it, so a cloud session has them too
([ADR-003](docs/adr/ADR-003-vendor-pocock-skills.md)). The full list is under
[Skills](#skills).

## Standards

Agent-written code is held to these. A project may tighten them, never loosen
them. Why each number is what it is: [ADR-001](docs/adr/ADR-001-complexity-standards.md).

| Gate | Language | Tool | Fails above | Warns above |
|---|---|---|---|---|
| No new comments | Python | `comment-debt` | the file's baseline | — |
| Cyclomatic complexity | Python | `cc-check` (radon) | 8 | — |
| Cyclomatic complexity | TypeScript, JavaScript | `cc-check --lang typescript` (lizard) | 8 | — |
| Cyclomatic complexity | Swift | SwiftLint, `ignores_case_statements: true` | 8 | 6 |
| Cognitive complexity | Rust | `cargo clippy` | 10 | — |
| Function length | Rust | `cargo clippy` | 25 lines | — |
| CRAP | Python, Swift, TypeScript, JavaScript | `crap` | 8 | 5 |

Human-maintained code targets CC 5.

Which gates score each language, and which components install for it:
[the languages-by-gates table](docs/languages-by-gates.md).

## The gates

### `comment-debt`: no new comments

Code carries no comments, docstrings or strings used as comments; bare pragmas
such as `# noqa` are exempt. Comments drift from the code and agents copy them as
permission. Put the knowledge where it shows when it stops being true: a test,
a named constant, an ADR or an issue. Existing comments are debt, held in
`comment-debt.json` as a line count per file. The gate fails if a file gains a
comment, and also if it loses one without the baseline being lowered, so paid
debt is always recorded. Python only for now
([#3](../../issues/3) adds Rust,
TypeScript, Swift and shell:
[ADR-010](docs/adr/ADR-010-admission-and-recognised-conventions.md)).

### `cc-check`: cyclomatic complexity

Counts the independent paths through each Python function: one, plus one for each
`if`, loop, `except`, boolean operator and comprehension clause. It is fast enough
to run after each function is written. It counts with radon, the same counter
CRAP uses, so the two numbers agree. ruff's C901 skips boolean operators and
comprehensions and can score the same function several points lower; don't use
it as the gate. Takes any number of files and directories in one run:
`cc-check src tests`. `--lang typescript` counts `.ts`, `.tsx`, `.js`, `.jsx`,
`.cjs` and `.mjs` with lizard instead. With `--baseline FILE` it fails only on
functions that are new or worse than the baseline; see
[Adopting the ratchet](#adopting-the-ratchet).

### `crap`: complexity weighted by missing tests

```
CRAP = CC² × (1 − coverage)³ + CC
```

Complex code is acceptable in proportion to how well it is tested. Fully covered,
a function scores its CC; uncovered, CC² + CC. Coverage needed to pass at 8:

| CC | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|
| Coverage | 0% | 18% | 37% | 51% | 62% | 73% | 100% |

It runs once per ticket, after the functions are written and their tests exist.
Python coverage comes from `coverage json`. Swift coverage comes from an Xcode
`.xcresult` bundle (`--xcresult`) or, in a SwiftPM package, from the llvm-cov
export JSON that `swift test --enable-code-coverage` writes, passed as
`--llvm-cov-json "$(swift test --show-codecov-path)"`; that needs no Xcode and
runs on Linux. Both Swift reports record absolute paths and only an exact
resolved path matches, so measure coverage and run `crap` in the same checkout
(ADR-001's addenda "SwiftPM coverage (v0.8.0)" and "xccov matches exact paths
(v0.8.2)"). TypeScript and JavaScript coverage comes
from Istanbul's `coverage-final.json` (`--istanbul-json`), which Vitest and Jest
write. Functions that share a start line are matched to their Istanbul entries
by the [shared start line rule](src/quality_gates/skills/crap/references/shared-start-line.md). Without
coverage (`--no-coverage`) every function at CC 3 or above fails, so that mode
ranks functions by risk and is never read as pass/fail. `crap` takes
`--baseline FILE` too, and refuses it without coverage (exit 2). A
coverage flag given an empty path exits 2, so a path command that fails inside
`$(...)` fails the build instead of passing as a worst-case ranking.
A coverage report of the wrong shape (a list where an object belongs, an xccov
`path` or `name` that is not text) exits 2 too.
When the report has no usable figure for a function, `crap` grades it `UNMEASURED`: no
CRAP score (`—` in the table, `"crap": null` in `--json`), a failing gate,
and the summary names its file. `--baseline --update` records none and keeps
any entry it already has, so a coverage outage can neither add debt nor drop it
(ADR-001's addendum "unmeasured functions (v0.12.0)").
When a report is given and none of the scored functions gets a figure from it,
`crap` prints one line to stderr saying so (ADR-001's addendum "Coverage
readers fail loudly").
`crap` warns when the coverage file is older than the newest source file the
scan read, and `--strict-freshness` makes that exit 2; files under a skipped
folder and files of another language do not count (ADR-001's addendum "the
freshness check reads the scan's files (v0.9.0)").

### What both gates score

Both gates take their functions from one scan, so they always list the same
functions under the same names. A function, method, closure or method of a
nested class is scored on its own; a class is not. A Swift closure is the
exception: its branches count in the function that holds it, and its untested
lines do not lower that function's coverage (#53). Both look only at the
[files in scope](src/quality_gates/skills/crap/references/files-in-scope.md): the files git would commit, so the
project's own `.gitignore` leaves out generated and installed folders, less the
`exclude` prefixes in `quality-gates.json` (test fixtures by default). Each file
is scored once, and a symlinked folder is scanned once, by the
[symlink rule](src/quality_gates/skills/crap/references/symlinked-folders.md). Outside a git repo, both stop with
exit 2 and say so.

A Python function's line range runs from its `def` line to the end of its last
statement, taken from the syntax tree, so a function whose body ends in a nested
`def` or `class` is measured, and `crap` reads its coverage, over the whole body
(ADR-001's addendum "Python end lines from the AST (v0.9.0)"). CC is still radon's.

### How they fit together

CC is the hard ceiling, checked function by function. CRAP is the sliding scale
below it, checked per ticket: the closer a function is to the ceiling, the more
tests it needs. Because both count CC the same way, they meet at the top: a CC 8
function passes only when fully covered. `comment-debt` is independent and runs
on every commit.

### Adopting the ratchet

A repo with existing debt cannot put `cc-check` or `crap` in CI as plain
pass/fail: every old function over the limit fails the build. `--baseline FILE`
turns either gate into a ratchet, the way `comment-debt` works:

```bash
cc-check src --baseline cc-baseline.json --update      # record today's debt once
cc-check src --baseline cc-baseline.json               # the check CI runs
```

The baseline maps each function to its score, and holds only functions over
the threshold. Each function is named so a baseline can tell it apart from every
other, the same on every machine and in CI. The details are in the
[naming rule](src/quality_gates/skills/crap/references/function-names.md), the
[repeated-names rule](src/quality_gates/skills/crap/references/repeated-names.md), the
[baseline key rule](src/quality_gates/skills/crap/references/baseline-keys.md) and, for Swift initialisers and
`private(set)`, [how lizard reads Swift](src/quality_gates/skills/crap/references/swift-reading.md).

- A function over the threshold that is not in the baseline fails. A renamed or
  moved function counts as new. So does a `name#2` entry whose number shifted because
  a function of the same name was added above it in the file.
- A baselined function whose score rose fails.
- A baselined function whose score fell, or that dropped to the threshold or
  below, also fails until `--update` records it, so paid debt cannot come back.
- `--update` only lowers scores and removes entries. It never raises a score or
  adds a function; it exits 1 and writes nothing if the tree has either.
- Without the baseline file, the check exits 2; `--update` creates it from the
  current tree.

Commit the baseline, then add a test that calls the gate's `main` with it so CI
enforces it:

```python
def test_no_function_is_more_complex_than_the_baseline_allows(self):
    with self.assertRaises(SystemExit) as stop:
        quality_check.main(["src", "--baseline", "cc-baseline.json"])
    self.assertEqual(stop.exception.code, 0)
```

`crap.main([...])` takes the same flags, with a coverage source.

## Skills

The skills ship inside the Python package, so the pinned install carries the
matching ones, and `qg-skills` copies them into a project. In the *From*
column, **ours** was written here, **Pocock** is a word-for-word copy of Matt
Pocock's skill, and **Pocock, changed** is his skill with the changes listed,
with reasons, in [docs/upstream-adaptations.md](docs/upstream-adaptations.md).

### The component manifest

[components.json](src/quality_gates/components.json) ships in the package and
lists every component: what it is made of, what it does in one line, and where
it came from. It is readable from an installed copy without network access, and
it is a contract for `qg status`, the planned UI and any tool that reads it. A
test fails when the *From* column below disagrees with it, when a shipped skill
belongs to no component, when a component names a part that does not ship, or
when it disagrees with [upstream.json](src/quality_gates/upstream.json), the
file-level record `qg-upstream` reads.

- `format_version`: a whole number. A change to the shape below raises it and
  gets a CHANGELOG note; adding a component or a part does not. It is 2; version 2
  added `admissions`.
- `admissions`: a list with one record per outside source ([ADR-010](docs/adr/ADR-010-admission-and-recognised-conventions.md)),
  each with `name` (the repo or tool name, as a component's `origin` spells it),
  `kind` (`upstream`, `dependency` or `test-only`), `licence` (an SPDX id: an
  upstream needs MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause or ISC, a
  dependency any OSI-approved licence, a test-only tool any), `practice` (one
  sentence on the author's practice, ending in a full stop), and either
  `last_release` (a date like `2026-10-29`) or `stable` (the reason it needs no
  releases), never both. A Python package this package installs also has
  `minimum_version` and `tested_version`, the version CI ran. An admission holds no repo
  or commit: those stay in `upstream.json`, whose `sources` each need an
  `upstream` admission. Loading fails when any is missing or breaks the rule,
  and when an `origin` name or an `adapts` entry has no admission, or an
  `origin` `type` differs from the `kind` of the source it names.
- `components`: a list. Each has `id`, `name`, `description` (one line, plain
  words), `core` (true for the parts every project has and cannot switch off),
  `languages` (empty when the component has none), `origin` and `parts`.
- `origin`: `{"type": "ours"}`, `{"type": "upstream", "name": "<repo>"}` (with
  `"changed": true` when the copy is adapted), or `{"type": "dependency",
  "name": "<tool>", "version": "<requirement>"}`. A component's origin is the
  one most of its parts have; a part with a different one carries its own. An
  `ours` part may list `"adapts": ["<repo>"]` for files it takes from an
  upstream.
- `parts`: each has a `kind` and an `id`, unique for its kind within the
  component. The kinds are `skill`, `hook`, `command`, `baseline`, `config`,
  `ci_step`, `precommit_step`, `claude_md_line` and `dependency`. A `config` is
  a settings file the gate reads, such as `.swiftlint.yml`, and is present or
  absent like a baseline. A `precommit_step` must have `marker`, the command
  `/setup-standards` puts in `.githooks/pre-commit`. A `ci_step` has `file`, the setup example
  it comes from, and must have `marker`, the text that example puts in a CI workflow; with
  `found_in`, the marker is looked for in that project file instead, such as the
  test file `cc-check` runs inside for Python. A part for only some of its
  component's languages lists them in `languages`; in a project that uses none
  of them the part is *not applicable* and does not count toward the
  component's status.

**Set up and standards**

| Skill | From | Does |
|---|---|---|
| `/setup-standards` | ours | Sets up or upgrades a project for all three layers and reports what it did |
| `standards` | ours | The size rule and the principles, one file each; the agent opens one when its trigger matches |
| `/setup-matt-pocock-skills` | ours | Points to `/setup-standards`, for his skills that ask for his setup |

**Plan: work too big for one session, or touching several parts**

| Skill | From | Does |
|---|---|---|
| `/wayfinder` | Pocock | Maps work too big for one session as decision tickets and settles them one at a time |
| `/grill-with-docs` | Pocock | Questions you about a plan until it is sharp, writing ADRs and the glossary as it goes |
| `/to-spec` | Pocock | Turns the conversation into a spec on the issue tracker |
| `/to-tickets` | Pocock | Breaks a spec into tickets, each saying what it waits on |

**Build**

| Skill | From | Does |
|---|---|---|
| `/implement-spec` | Pocock, changed | Builds all of a spec's tickets, each after the ones it waits on |
| `/implement` | Pocock, changed | Builds one piece of work from a spec or tickets |
| `/tdd` | Pocock, changed | Builds test first: a failing test, then the code that passes it |
| `/diagnosing-bugs` | Pocock | Finds the cause of a hard bug or slowdown before fixing it |

**Check**

| Skill | From | Does |
|---|---|---|
| `/review-against-spec` | Pocock, changed | Checks a change against the project's standards and the issue or spec it came from; his `code-review`, renamed so Claude Code's own `/code-review` still works |
| `/no-comments` | ours | Sets up `comment-debt` in a repo, or pays down one file's debt |
| `/cc-python` | ours | Runs `cc-check` at 8 and proposes refactors |
| `/cc-typescript` | ours | Runs `cc-check --lang typescript` at 8 and proposes refactors |
| `/cc-swift` | ours | Runs SwiftLint and lizard and proposes refactors |
| `/cc-rust` | ours | Runs `cargo clippy`; `setup` scaffolds `clippy.toml` and deny attributes |
| `/crap` | ours | Runs `crap` (Python, Swift, TypeScript) and says whether to add tests or reduce CC |
| `/improve-codebase-architecture` | Pocock | Finds code that resists change and proposes how to reshape it |

**Used by the steps above, or beside them**

| Skill | From | Does |
|---|---|---|
| `codebase-design` | Pocock | Shared terms for designing parts of the code that are simple to use |
| `domain-modeling` | Pocock | Keeps the project's glossary and ADRs |
| `/pr` | Pocock | Writes a pull request description |
| `/triage` | Pocock | Sorts issues and labels them ready for an agent or a person |
| `/retro` | Pocock | Looks back on a session for what to change next time |
| `writing-for-agents` | Pocock | How to write skills, `CLAUDE.md` and other text an agent reads |
| `/handoff` | Pocock | Writes a summary so another session can pick up the work; it is saved in a temporary folder, which a cloud session loses when it ends |

Three more commands support them:

- `qg-agent-docs --tracker github|gitlab|local` writes `docs/agents/` from
  Matt Pocock's setup templates, and `.github/pull_request_template.md` from
  the `pr` skill's headings. It never overwrites a file you edited; it
  shows the template's own change instead, so you can choose to adopt it.
- `qg-upstream` reports what changed upstream in the files this repo copies
  from Pocock and pstack; see
  [Keeping the copied skills current](#keeping-the-copied-skills-current).
  Exit 0: nothing changed. Exit 1: changes, printed as Markdown. Exit 2:
  GitHub unreachable. Exit 3: `upstream.json` is missing or malformed.
  `--upkeep` instead checks `components.json` for outside sources with no
  release in 12 months that are not marked stable: exit 0 none, exit 1 some,
  exit 3 the manifest is malformed.
- `qg-references` writes the rules the skills cite into each skill's
  `references/` folder, from the restated rules tagged in the ADRs
  ([ADR-004](docs/adr/ADR-004-reference-files.md)). `qg-references --check` also
  fails when an ADR amendment and the text it amends do not link to each other.
  It runs in this repo at each release; a consumer gets the files through
  `qg-skills`.

### The choice file

`quality-gates.json` sits at the project root and is committed. It records what
the builder chose ([ADR-007](docs/adr/ADR-007-component-install.md)), and
`qg setup` writes it. It is a contract for `qg status`, setup and the planned
runner. Loading fails, and `qg status` and `qg setup` exit 3 with one line
naming the problem, when a field is missing, has the wrong type or names
something quality-gates does not know.

```json
{
  "format_version": 1,
  "languages": ["python", "shell"],
  "exclude": ["tests/fixtures/"],
  "components": {"chosen": ["crap", "no-comments"], "declined": ["design-helpers"]},
  "commit_time_limit_seconds": 2,
  "settings": {"no-comments": {"exclude": ["gen/"], "conventions": ["rust-safety"]}}
}
```

- `format_version`: a whole number, 1. A change to the shape raises it and
  gets a CHANGELOG note.
- `languages`: the project's languages, each a name the language registry
  knows: `python`, `typescript`, `swift`, `rust` or `shell`. It replaces
  detection as the source of truth; `qg status` warns about code in a language
  the list leaves out. A language may be listed before it has code.
- `exclude`: path prefixes from the repo root that detection and the gates
  leave out, on top of what `.gitignore` ignores. Setup writes the default
  fixture folders here (every outermost `fixtures`, `fixture`, `__fixtures__`
  or `testdata` folder).
- `components`: `chosen` and `declined`, each a list of component ids from
  `components.json`; no id may be in both. A component in neither list has
  not been offered yet. The core is never listed: every project has it.
- `commit_time_limit_seconds`: a number above 0, 2 by default (ADR-006).
- `settings`: per-component settings. Only `no-comments` has any so far:
  `exclude`, path prefixes the comment gate leaves out, and `conventions`, the
  ids of the [recognised conventions](docs/recognised-conventions.md) the
  project has switched on. Both default to empty. `comment-debt` does not read
  them yet (#3), so keep its `--exclude` flags until then.

## Setup details

[Get started](#get-started) covers the steps. The details behind them:

- Instead of `uv tool install`, you can add the same requirement to the
  project's dev dependencies; `/setup-standards` does this for a Python
  project. lizard, which counts Swift and TypeScript, installs with the package.
- The `coverage` extra installs coverage.py beside the gates, and
  `--with-executables-from coverage` puts its command on your PATH. That
  `coverage` runs tests with the tool's own Python, so it suits a project whose
  tests need only the standard library. A project whose tests import its own
  dependencies installs coverage in the environment the tests run in.
  Child processes the tests start are measured only with
  `[tool.coverage.run] patch = ["subprocess"]` in `pyproject.toml` (coverage
  7.10 or later). Clear old data with `coverage erase`: `rm .coverage*` also
  deletes `.coveragerc`.
- Each command is a Python file in the package, linked to its name in
  [pyproject.toml](pyproject.toml); installing the package makes the link:

  | Command | Code |
  |---|---|
  | `qg` | [src/quality_gates/qg.py](src/quality_gates/qg.py), which hands each subcommand to its own file |
  | `qg status` | [src/quality_gates/status.py](src/quality_gates/status.py) |
  | `qg setup` | [src/quality_gates/setup_choices.py](src/quality_gates/setup_choices.py) |
  | `qg-skills` | [src/quality_gates/skills_sync.py](src/quality_gates/skills_sync.py) |
  | `qg-agent-docs` | [src/quality_gates/agent_docs.py](src/quality_gates/agent_docs.py) |
  | `qg-upstream` | [src/quality_gates/upstream.py](src/quality_gates/upstream.py) |
  | `qg-references` | [src/quality_gates/references.py](src/quality_gates/references.py) |
  | `comment-debt` | [src/quality_gates/comment_debt.py](src/quality_gates/comment_debt.py) |
  | `cc-check` | [src/quality_gates/quality_check.py](src/quality_gates/quality_check.py) |
  | `crap` | [src/quality_gates/crap.py](src/quality_gates/crap.py) |

- `qg status` shows what quality-gates has installed in the project you are in.
  It lists every component with one of these words, a line on what it does and
  where it came from: *installed*, *missing*, *different* (a copied file was
  edited, so it no longer matches the release), *partly installed*, *unknown*
  (it could not read something), *not applicable* (the component is for a
  language the project does not use), *offered, declined* or *not yet offered*
  (the choice file lists the component as declined, or not at all). Core
  components come first. The project's languages come from the
  [choice file](#the-choice-file); without one, from detection over the files
  git would commit. With a choice file, it warns about code in a language the
  file does not record, naming the files. It also shows
  the version the project pins next to the version installed, or *pin not
  found*. It only reads, works offline and exits 0 whatever it finds, so it
  never blocks a commit; `qg-skills --check` stays the check that fails. It
  exits 3, with one line on stderr naming the problem, only when the
  `components.json` shipped inside quality-gates or the project's
  `quality-gates.json` is malformed, and 2 outside a git repo. `qg status --json`
  prints the same report for an agent, with the component list's format
  version, `languages`, `languages_from` (`choice file` or `detection`),
  `unrecorded_languages` (each with its files), and for each component its id,
  status and parts. The commands and
  tools quality-gates itself installs, such as `cc-check` or `radon`, have no
  status of their own: they are listed as *provided by quality-gates* and do
  not count toward a component's status, and neither does a part for a language
  the project does not use. *Needs attention* names only the parts that count.

  ```text
  $ qg status
  Pin: v0.12.0. Installed quality-gates: 0.12.0 (matches).

  Core components (every project has these)
    core                     installed          upstream: mattpocock/skills
      The workflow from idea to merged change, ...

  Optional components
    crap                     partly installed   ours
      Flags code that is both tangled and untested, ...
      Needs attention: baseline crap-baseline.json: missing
    complexity-python        different          ours
      Flags Python functions that are too tangled to follow, ...
      Needs attention: skill cc-python: different

  Not applicable to this project
    complexity-swift         not applicable     ours
      Flags Swift functions that are too tangled to follow, ...
  ```

- `qg setup` proposes the project's languages and one row per component, with
  its description, its cost (commit delay, CI time, outside tools) and a tick
  on the recommended set, and lists the files it would change. It writes
  nothing until `--go`, and then only `quality-gates.json`. Without a choice
  file it ticks what is installed, or every component that applies when
  nothing is. A component the file does not list is offered, ticked. Change the
  proposal with `--add-language`, `--remove-language`, `--choose` and
  `--decline`, each repeatable. It refuses, with exit 1 and nothing written,
  to switch off the core or a gate the project has, or to remove a language
  that still has code: both wait on recorded reasons (#115). It copies the
  `--exclude` prefixes of the `comment-debt` lines in `.githooks/pre-commit`
  and the CI workflows into `settings` › `no-comments` › `exclude`, and leaves
  the flags in place. Run again, it changes nothing. `--json` prints the
  proposal for an agent.

- `qg-skills` copies from the installed package, not from GitHub, so the
  version you installed decides which skills a project gets. It writes
  `.claude/skills/`, the stage guard and the asking-rule line in `CLAUDE.md`. It touches only the skills it ships; the project's own
  skills are left alone. `qg-skills --check` exits 1 if any copy differs from
  the installed version, and `/setup-standards` adds a test that runs it, so CI
  catches a stale copy.
- The stage guard is a hook in `.claude/hooks/`, registered in
  `.claude/settings.json`, that refuses `git add -A`, `git add .` and
  `git commit -a`.
- `/setup-standards` adopts the gates with a baseline each; to do it by hand,
  see `/no-comments` and [Adopting the ratchet](#adopting-the-ratchet).
- This repo is also a Claude Code plugin, for use outside any one project. A
  cloud session does not install plugins, so committed copies are the route
  that works everywhere. Don't enable the plugin in a project that ran
  `qg-skills`, or every skill is listed twice. The same goes for Matt Pocock's
  plugin: with it installed, his skills appear twice, once under its prefix.
  That is harmless; the unprefixed copies are the pinned ones.

## Releasing

Bump `version` in `pyproject.toml`, `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` together, add a `CHANGELOG.md` entry, update
the pinned tag in the skills' install lines, run the reference generator
(`.venv/bin/qg-references`, then `.venv/bin/qg-skills` to refresh
`.claude/skills`), tag `vX.Y.Z`, then bump the pin in each consuming project.

Push the tag from a local session: a Claude Code cloud session's GitHub proxy
refuses tag pushes and the API call that creates a tag.

What a consumer receives is released: code, commands, skills, templates and
reference files. A change only this repo sees (the README, ADRs, CLAUDE.md,
tests, or a refactor with no change in behaviour) waits for the next release.
Release at most once a day: tag that day's merged changes together.

The `lizard` workflow checks PyPI every Monday and opens an issue when it
finds a lizard release newer than the last one checked. A lizard release can
change scores, so read its changelog for Swift and TypeScript changes, run the
tests against it, and record any counting change in ADR-001 before raising the
floor.

## Keeping the copied skills current

The Pocock skills and the pstack principles are copies, so their authors'
updates reach a project only through a release here
([ADR-003](docs/adr/ADR-003-vendor-pocock-skills.md)).

1. On the 1st of each month the `upstream` workflow runs `qg-upstream` and, if
   a copied file changed upstream, opens an issue with the changes. It also
   runs `qg-upstream --upkeep`, which opens or updates one issue naming every
   outside source in `components.json` with no release in 12 months that is
   not marked `stable`; renew its `last_release` or mark it stable with the
   reason.
2. Replace each word-for-word copy with the new upstream file.
3. For each changed file, take the new upstream version and redo every change
   [docs/upstream-adaptations.md](docs/upstream-adaptations.md) lists for it.
4. Move `commit` in `src/quality_gates/upstream.json` to the upstream commit
   you copied from.
5. Release, as above.

A project gets the update when it bumps its pin and reruns `qg-skills`. Until
then its `qg-skills --check` test fails, so a stale copy cannot pass CI.

## Development

```bash
uv venv && uv pip install -e .
.venv/bin/python -m unittest discover -s tests
.venv/bin/comment-debt
```

This repo runs its own gates and carries no comment debt: `comment-debt.json` is
`{}`.

How the code is laid out, and where each new piece belongs:
[ADR-011](docs/adr/ADR-011-code-structure.md).

[docs/languages-by-gates.md](docs/languages-by-gates.md) is generated from the
language registry and each gate's language table. After changing either, run
`.venv/bin/python -m quality_gates.languages_table`; a test fails while the
table is out of date, and `--check` reports the drift without writing. It exits
1 on drift, 2 when asked to write outside the quality-gates checkout, and 3
when `components.json` is missing or malformed.

## Decisions

Every standard and design choice is recorded in an ADR in
[docs/adr/](docs/adr/), and changes only through a new ADR or a dated addendum.

| ADR | Decides |
|---|---|
| [ADR-001](docs/adr/ADR-001-complexity-standards.md) | The complexity and CRAP thresholds, and the tool that counts them |
| [ADR-002](docs/adr/ADR-002-engineering-standards.md) | The three layers: workflow, principles, gates |
| [ADR-003](docs/adr/ADR-003-vendor-pocock-skills.md) | Shipping Matt Pocock's skills through `qg-skills` |
| [ADR-004](docs/adr/ADR-004-reference-files.md) | Rules shipped with the skills as generated reference files |
| [ADR-005](docs/adr/ADR-005-direction-idea-to-release.md) | The direction: a guided framework from idea to release |
| [ADR-006](docs/adr/ADR-006-gates-beyond-complexity.md) | The gates beyond complexity, and the order they ship in |
| [ADR-007](docs/adr/ADR-007-component-install.md) | Choosing, switching and upgrading components |
| [ADR-008](docs/adr/ADR-008-project-map-and-checkpoints.md) | The project map and the checkpoints |
| [ADR-009](docs/adr/ADR-009-recorded-reasons-and-loosening.md) | Recorded reasons and loosening |
| [ADR-010](docs/adr/ADR-010-admission-and-recognised-conventions.md) | Admitting outside sources, and the comment gate's new languages |
| [ADR-011](docs/adr/ADR-011-code-structure.md) | The code's structure |

## Licence

MIT, in [LICENSE](LICENSE). The package also carries copies of two other MIT
works, each with its own notice:

- [Matt Pocock's skills](https://github.com/mattpocock/skills): the notice is
  `LICENSE-mattpocock` in each copied skill's folder, and
  `src/quality_gates/agent_doc_templates/LICENSE` for his setup templates.
- [Lauren Tan's pstack](https://github.com/cursor/plugins/tree/main/pstack):
  the notice is `LICENSE-pstack` in the `standards` skill's folder.

`qg-skills` copies each notice into the project with its skill.
