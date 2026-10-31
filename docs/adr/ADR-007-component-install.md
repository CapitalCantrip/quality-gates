---
status: accepted
date: 2026-10-31
---

# ADR-007: Component install: choosing, switching and upgrading components

## Context

ADR-005 made everything outside a small core an optional **component**, and set
rollout step 2: `/setup-standards` installs components instead of one fixed
set, with today's set as the default. `components.json` and `qg status`
(ADR-005 addendum, v0.12.0) say what can be installed and what is; nothing yet
says what the consumer chose, how the choice changes, or what a pin bump does to
it. Every gate in ADR-006 waits on this.

The builder settled it in a grilling session on 2026-10-31 (quality-gates#135),
checked against ADR-005, ADR-006 and the decisions on #115 (recorded
loosening), #114 (admission rule), #112 (the "proven" checkpoint) and #120
(language detection). The decision comment on #135 holds the full list.

## Decision

### Choosing

Setup shows one table: each component, its one-line description from
`components.json`, and what it costs the builder (commit delay, CI time,
outside tools fetched). The recommended set is ticked; the builder says "go" or
names what to change. The recommended set is today's set, so "go" changes
nothing for an existing project. Presets may come later (ADR-005).

### Explainers

Each component ships an **explainer**: a short page, versioned with the release,
saying what the component catches, why it matters to someone who cannot read
the code, what it will ask of the builder, and up to three outside links under
"Want to go deeper?". Each link says why it is worth the time and the date it
was last checked; links are free to view and come from someone with real
practice. The release checklist runs a link check.

The table stays clean: below it, one line says *"Ask me about any row, or run
`qg explain <name>`."* The agent reads the explainer and says what it means for
this project; it never writes an explanation fresh (ADR-005, Understanding).

### The choice file

Amended by: [ADR-010: admission and the comment gate's new languages](ADR-010-admission-and-recognised-conventions.md)

A committed `quality-gates.json` at the project root records the chosen
components, the ones offered and declined, the project's languages, and its
commit time limit. `qg status`, the runner and setup all read it. Without the
file, `qg status` falls back to working out what is installed.

**Languages.** Setup proposes them from project markers (`pyproject.toml`,
`package.json`, `Package.swift`, `Cargo.toml`) and source files outside test
and fixture folders. The builder confirms, adds or removes, and the list is
recorded. A language may be added before it has any code, as in a new repo or
ahead of a rewrite; its gates start with empty baselines. Removing a language
that still has code is loosening. `qg status` warns about code in a language the
file does not list. This replaces detection as the source of truth (#120).

### Switching off

The core never switches off. Switching off a gate the project has is loosening
(ADR-005): refused until recorded loosening (#115) ships, then allowed only with
a recorded reason, which `qg status` and the checkpoint show as a warning.
Helper components and components for languages the project does not use switch
off freely.

Switching off removes the copied skill and the runner entry and keeps the
baseline and config, so switching back on forgives nothing added in between.

### Pin bumps

A component that a release adds is off for existing consumers until accepted.
The next `/setup-standards` run offers it with a recommendation and records the
answer. Declining a gate the project never had is not loosening and needs no
reason, but `qg status` lists it as "offered, declined". New projects get it in
the recommended set. The CHANGELOG entry says: bump, then run
`/setup-standards`.

### The runner

The pre-commit hook holds one gate line, `qg run commit`, and CI holds
`qg run ci`. Each reads the choice file and runs the chosen components' steps
for that stage. Switching a component edits only the choice file, so it never
disturbs another component's lines, and running setup twice changes nothing.

An existing project moves over on its first setup run after the release: the
choice file is written from what is installed, and the gate lines in its hook
and CI are replaced by the runner lines; every other line is kept. Until that
run its hook and CI keep working unchanged.

### The commit time limit

The runner times the commit stage against the limit ADR-006 sets, 2 seconds,
recorded in the choice file. A project may lower it freely; raising it is
loosening and needs a recorded reason. Going over warns, in the checkpoint and
`qg status`, naming the slowest step. It never fails a commit: timing varies
between runs and machines, and a hook that fails at random teaches agents to
skip it.

### Prerequisites

A chosen component whose tool is missing fails with "could not check" and how
to fix it, on commit and in CI alike, so a gate that did not run never reads as
a pass (ADR-006). The one exception is the dependency check run offline on the
builder's machine (#31). Setup tries to install each prerequisite and reports
any it cannot as not done; `qg status` shows "chosen, can't run here: needs X".

### Track record

The runner records each **catch**: a problem a gate stopped, counted once by
gate, file, function or line, and kind, and ending as fixed, given a reason, or
accepted as debt. The record holds no finding content: a leaked key is "a key
in `config.py`", never the key.

The log lives in git's own folder and is never committed. `qg tally` totals it,
and each pull request's Evidence carries one line, worded like "quality-gates
stopped 4 problems on this branch: 3 fixed, 1 given a reason". The name comes
from one constant, so the rename (#111) changes it in one place. The word is
"problems", never "bugs".

Track record is an optional component, on by default. Switched off, the runner
still counts the current branch's catches for the pull request line and the
checkpoint, keeps no lasting log, and clears the count when the branch merges.

### Keeping the builder informed

The setup report keeps its table of steps and adds three blocks: **Your
components** (on, off, offered and declined, languages added by hand), **Can't
run here** (each missing prerequisite and what installing it takes), and
**Next** (at most three actions for the builder, then the `qg explain` line).

### Build

Five builds, each its own release:

| Build | Holds | Blocks the ADR-006 gates |
|---|---|---|
| A | The choice file, recorded languages, `qg status` reading it, the setup table, the offer on a bump | yes |
| B | The runner, the commit time limit, "could not check", moving existing projects over | yes |
| C | The explainer format, `qg explain`, the link check | yes |
| D | Explainers for today's components | no |
| E | Track record | no |

Switching off a gate is built with #115.

## Consequences

- Each consumer gains one committed file, `quality-gates.json`, and its hook and
  CI shrink to one gate line each, rewritten once at the upgrade.
- `qg status` stops guessing languages and choices once the file exists.
- Every new component must ship an explainer and say its cost in the setup
  table.
- New gates reach existing projects only when the builder reruns setup and
  accepts them; until then the bump changes nothing.
- The ADR-006 commit limit becomes a warning with a per-project setting,
  instead of a rule only reviewers apply.
- Pull requests carry evidence of what the gates stopped, at no cost to the
  builder's attention.

## Rejected

- **Asking about each component in turn.** Ten to sixteen questions the builder
  cannot weigh.
- **Presets now.** ADR-005 defers them, and someone must design and keep them.
- **Working the choice out from what is installed.** It cannot tell "chose not
  to" from "broken", and has nowhere to keep a reason.
- **Switching off as a plain choice.** It lets an agent turn off any gate it
  keeps failing, against ADR-005.
- **New gates on by default at a bump.** A bump could break every commit, as
  when the secret check finds an old key.
- **A managed block of lines in the hook and CI, or agent hand-edits.** Both
  drift, and neither gives one timing or result for the checkpoint.
- **Failing a commit that goes over the time limit.** The same commit would
  pass once and fail the next.
- **Warning and carrying on when a tool is missing.** A missing tool would
  become a free pass.
- **Better detection alone for languages.** Still a guess, and it cannot cover a
  language with no code yet.
- **A committed tally file updated by CI.** An automated commit to main on every
  merge.
- **"Bugs caught".** It overclaims; many catches are an agent's own first draft
  being corrected.
- **A link column in the table, or no explainers.** The first clutters the
  table; the second is the fresh-each-time teaching ADR-005 rejects.
