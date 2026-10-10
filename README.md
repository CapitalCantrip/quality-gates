# quality-gates

Automated guardrails for software built with AI coding agents, for people who
can't review the code themselves. Checks fail the commit or the build when the
agent's code gets too complex, goes untested or adds comments, so problems are
caught without anyone reading a diff. Claude Code skills set a project up and
keep the agent to a working method that fits the size of the job. Each project
pins a version, so nothing changes until you update, and a fix reaches every
project when its pin is bumped.

## Get started

Install the commands, copy the skills into the project, then run
`/setup-standards`: it does the rest. You can do this on your computer or from
a cloud session on your phone. To update, install the new version and repeat.

### Set up a project, on your computer

You need [uv](https://docs.astral.sh/uv/) and Claude Code. In the project's
folder:

1. Install the commands, pinned to a version. This puts `qg-skills` and the
   gate commands on your computer:

   ```bash
   uv tool install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.8.1"
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

## As the quality control of a software factory

In a software factory, agents do most of the building, from plan to release,
and a person decides what to build and checks that it works. That only holds
up if the line has a quality control station that needs no one to read the
code. quality-gates can be that station:

- **It judges by numbers, not opinion.** Each gate is a command with a
  threshold and an exit code, so an agent running the line can act on the
  result without a person in the loop.
- **Every project gets the same standard.** Each one pins a tagged version, so
  every project on the line is checked the same way. The standard changes only
  through a written decision and a release, never by drift.
- **Old code doesn't stop the line, and no run makes it worse.** Existing debt
  is recorded once and can only shrink, so the factory can take on a project
  as it is.
- **It fails safe.** When a check can't tell, for example because it can't
  match test coverage to a file, it assumes the worst instead of guessing in
  the code's favour.
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
TypeScript and shell).

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
runs on Linux. The export records absolute paths and only an exact path
matches, so measure coverage and run `crap` in the same checkout (ADR-001's
addendum "SwiftPM coverage (v0.8.0)"). TypeScript and JavaScript coverage comes
from Istanbul's `coverage-final.json` (`--istanbul-json`), which Vitest and Jest
write. Functions that share a start line are matched to their Istanbul entries
by the rule in ADR-001's 2026-10-10 addendum on shared start lines. Without
coverage (`--no-coverage`) every function at CC 3 or above fails, so that mode
ranks functions by risk and is never read as pass/fail. `crap` takes
`--baseline FILE` too, and refuses it without coverage (exit 2). A
coverage flag given an empty path exits 2, so a path command that fails inside
`$(...)` fails the build instead of passing as a worst-case ranking.
When a report is given and none of the scored functions gets a figure from it,
`crap` prints one line to stderr saying so (ADR-001's addendum "Coverage
readers fail loudly").

### What both gates score

Both gates take their functions from one scan, so they always list the same
functions under the same names. A function, method, closure or method of a
nested class is scored on its own; a class is not. Both skip `.git`, `.venv`,
`venv`, `.direnv`, `node_modules`, `__pycache__`, `backups`, `build`, `dist`,
`.tox`, `.mypy_cache`, `.pytest_cache`, `.worktrees` and `.claude/worktrees`
wherever they appear below the scanned path, and scan every other hidden folder.
Each gate ends its report with a line naming the skipped folders it found, so a
real package called `build` or `dist` is never dropped silently. The reasons are
in ADR-001's 2026-10-09 addendum.

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

The baseline maps `path::function` to its score, and holds only functions over
the threshold. Paths are relative to the git root, so the file is the same on
every machine and in CI. Python names are dotted from the outside in:
`path::Class.method`, `path::outer.inner`, `path::K.Inner.deep`. lizard
(Swift, TypeScript) names a method without its class and an unnamed callback
`(anonymous)`. In every language a name that repeats in a file gets its order
as a suffix: `path::(anonymous)#2`.

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
| `/crap` | ours | Runs `crap` (Python, Swift, TypeScript) or `cargo clippy` (Rust) and says whether to add tests or reduce CC |
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

Two more commands support them:

- `qg-agent-docs --tracker github|gitlab|local` writes `docs/agents/` from
  Matt Pocock's setup templates, and `.github/pull_request_template.md` from
  the `pr` skill's headings. It never overwrites a file you edited; it
  shows the template's own change instead, so you can choose to adopt it.
- `qg-upstream` reports what changed upstream in the files this repo copies
  from Pocock and pstack; see
  [Keeping the copied skills current](#keeping-the-copied-skills-current).

## Setup details

[Get started](#get-started) covers the steps. The details behind them:

- Instead of `uv tool install`, you can add the same requirement to the
  project's dev dependencies; `/setup-standards` does this for a Python
  project. lizard, which counts Swift and TypeScript, installs with the package.
- Each command is a Python file in the package, linked to its name in
  [pyproject.toml](pyproject.toml); installing the package makes the link:

  | Command | Code |
  |---|---|
  | `qg-skills` | [src/quality_gates/skills_sync.py](src/quality_gates/skills_sync.py) |
  | `qg-agent-docs` | [src/quality_gates/agent_docs.py](src/quality_gates/agent_docs.py) |
  | `qg-upstream` | [src/quality_gates/upstream.py](src/quality_gates/upstream.py) |
  | `comment-debt` | [src/quality_gates/comment_debt.py](src/quality_gates/comment_debt.py) |
  | `cc-check` | [src/quality_gates/quality_check.py](src/quality_gates/quality_check.py) |
  | `crap` | [src/quality_gates/crap.py](src/quality_gates/crap.py) |

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
the pinned tag in the skills' install lines, tag `vX.Y.Z`, then bump the pin in
each consuming project.

Push the tag from a local session: a Claude Code cloud session's GitHub proxy
refuses tag pushes and the API call that creates a tag.

A change that alters no behaviour, such as a README fix, is still released.

## Keeping the copied skills current

The Pocock skills and the pstack principles are copies, so their authors'
updates reach a project only through a release here
([ADR-003](docs/adr/ADR-003-vendor-pocock-skills.md)).

1. On the 1st of each month the `upstream` workflow runs `qg-upstream` and, if
   a copied file changed upstream, opens an issue with the changes.
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

This repo gates itself, and carries no comment debt: `comment-debt.json` is
`{}`.

## Licence

MIT, in [LICENSE](LICENSE). The package also carries copies of two other MIT
works, each with its own notice:

- [Matt Pocock's skills](https://github.com/mattpocock/skills): the notice is
  `LICENSE-mattpocock` in each copied skill's folder, and
  `src/quality_gates/agent_doc_templates/LICENSE` for his setup templates.
- [Lauren Tan's pstack](https://github.com/cursor/plugins/tree/main/pstack):
  the notice is `LICENSE-pstack` in the `standards` skill's folder.

`qg-skills` copies each notice into the project with its skill.
