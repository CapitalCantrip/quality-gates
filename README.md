# quality-gates

Engineering standards for software built with AI coding agents, by people who
are not software engineers. Each project pins a tag, so a fix lands everywhere
by bumping the pin.

## Who this is for

You can describe what you want and tell whether the result works. You can't
read a diff and spot a design flaw, an untested path or an error that is
silently swallowed. That leaves four gaps:

| The gap | What goes wrong | What this repo does |
|---|---|---|
| Nobody reviews the code | The agent's bad habits ship | Gates: commands that fail the commit or the build, with no expertise needed to read the result |
| Written rules fade | "Never do X again" goes in a notes file, and X happens again | Lessons that recur become checks, not paragraphs |
| Good process and busy process look alike | Hours of polish on a design nobody agreed, or no plan where one was needed | One question, how big is the work, picks the starting step |
| Questions arrive in jargon | You choose between options you can't weigh | Every question states the stakes plainly, gives two or three options and recommends one |

Agents follow a failing tool more reliably than a paragraph of guidance, so
wherever a standard can be a command that exits non-zero, it is one.

## Three layers

| Layer | Answers | Relies on |
|---|---|---|
| Workflow | what order to work in, for the size of the work | you picking the right starting step |
| Principles | how to judge each step, what counts as proof, how to ask you | the agent reading and applying them |
| Gates | what fails, whatever anyone intended | nothing |

A standard moves down this table whenever it can. The workflow comes from
[Matt Pocock's engineering skills](https://github.com/mattpocock/skills) and
many principles from [Lauren Tan's pstack](https://github.com/cursor/plugins/tree/main/pstack),
both MIT. Why it is shaped this way:
[ADR-002](docs/adr/ADR-002-engineering-standards.md). The workflow and
principles layers are proposed; the gates below ship today.

### Workflow: size decides where to start

| The work... | Start with |
|---|---|
| won't fit in one agent session | `/wayfinder` |
| fits in one session but touches several parts of the code | `/grill-with-docs` |
| is smaller than that | `/tdd` |

Every route ends with `/code-review`, then the gates.

To prepare a project for all three layers, run `/setup-standards` (proposed in
ADR-002): it installs the gates, records existing debt, adds the hooks and CI
tests, and reports in plain words what it did.

## Standards

Agent-written code is held to these. A project may tighten them, never loosen
them. Why each number is what it is: [ADR-001](docs/adr/ADR-001-complexity-standards.md).

| Gate | Language | Tool | Fails above | Warns above |
|---|---|---|---|---|
| No new comments | Python | `comment-debt` | the file's baseline | — |
| Cyclomatic complexity | Python | `cc-check` (radon) | 8 | — |
| Cyclomatic complexity | Swift | SwiftLint, `ignores_case_statements: true` | 8 | 6 |
| Cognitive complexity | Rust | `cargo clippy` | 10 | — |
| Function length | Rust | `cargo clippy` | 25 lines | — |
| CRAP | Python, Swift | `crap` | 8 | 5 |

Human-maintained code targets CC 5.

## The gates

### `comment-debt`: no new comments

Code carries no comments, docstrings or strings used as comments; bare pragmas
such as `# noqa` are exempt. Comments drift from the code and agents copy them as
permission, so the knowledge goes where it fails when it stops being true: a
test, a named constant, an ADR or an issue. Existing comments are debt, held in
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
`cc-check src tests`. With `--baseline FILE` it fails only on functions that are
new or worse than the baseline; see [Adopting the ratchet](#adopting-the-ratchet).

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
Python coverage comes from `coverage json`; Swift from an Xcode `.xcresult`
bundle. Without coverage (`--no-coverage`) every function at CC 3 or above fails,
so that mode ranks functions by risk and is never read as pass/fail. `crap`
takes `--baseline FILE` too, and refuses it without coverage (exit 2).

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
every machine and in CI. A method is keyed `path::Class.method`.

- A function over the threshold that is not in the baseline fails. A renamed or
  moved function counts as new.
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

Each skill runs its gate, reports the violations, proposes fixes, and gives the
agent the limits to write within. They ship inside the Python package, so the
pinned install carries the matching skills.

| Skill | Does |
|---|---|
| `/no-comments` | Sets up `comment-debt` in a repo, or pays down one file's debt |
| `/cc-python` | Runs `cc-check` at 8 and proposes refactors |
| `/cc-swift` | Runs SwiftLint and lizard and proposes refactors |
| `/cc-rust` | Runs `cargo clippy`; `setup` scaffolds `clippy.toml` and deny attributes |
| `/crap` | Runs `crap` (Python, Swift) or `cargo clippy` (Rust) and says whether to add tests or reduce CC |

## Use it in a project

Install the commands, pinned:

```bash
uv tool install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.3.2"
```

or add the same requirement to the project's dev dependencies. Swift support
needs `lizard`: install with the `[swift]` extra.

Copy the skills into the project and commit them:

```bash
qg-skills            # writes .claude/skills/<skill>/ for each skill
qg-skills --check    # exit 1 if the copies differ from the installed version
```

Committed copies load in local and cloud sessions alike. A cloud session does
not install plugins a repo enables in `.claude/settings.json`, so the plugin
route works only locally. Run `qg-skills` again after each pin bump, and add a
test that calls `skills_sync.main(["--check"])` so CI catches a stale copy.
`qg-skills` touches only the skills it ships; the repo's own skills are left
alone.

The repo is still a Claude Code plugin, for use outside any one project. Don't
enable both in one repo, or every skill is listed twice.

Then adopt the comment gate as the `/no-comments` skill describes: a
baseline, a pre-commit hook, and a test so CI enforces it. Adopt the CC and CRAP
gates the same way: see [Adopting the ratchet](#adopting-the-ratchet).

## Releasing

Bump `version` in `pyproject.toml`, `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` together, add a `CHANGELOG.md` entry, update
the pinned tag in the skills' install lines, tag `vX.Y.Z`, then bump the pin in
each consuming project.

## Development

```bash
uv venv && uv pip install -e .
.venv/bin/python -m unittest discover -s tests
.venv/bin/comment-debt
```

This repo gates itself, and carries no comment debt: `comment-debt.json` is
`{}`.

## Licence

MIT
