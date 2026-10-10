---
status: accepted
date: 2026-10-06
---

# ADR-002: Engineering standards in three layers: workflow, principles, gates

## Context

This repo was written for people who build software with AI coding agents but
are not software engineers themselves. That builder can describe what they want
and judge whether the result works for them. They usually cannot read a diff
and spot a design flaw, an untested path or a silent failure. Four problems
follow from that.

1. **Nobody reviews the code.** An engineer catches an agent's bad habits in
   review. Without one, the habits ship. The only reviewer that never gets
   tired and needs no expertise is a check that fails.
2. **Written rules fade.** An agent reads a long instruction file with uneven
   attention, and nothing happens when it skips a rule. A typical project
   collects a lessons file of the form "never do X again". Then X happens again.
   The commonest case: an agent commits every changed file at once, sweeping in
   a build artefact or another session's half-finished work. The lesson gets
   written down, and the same mistake recurs weeks later.
3. **The builder can't tell good process from busy process.** An agent can
   spend hours polishing a design nobody agreed to, or skip planning on work
   that needed it. The builder sees activity either way.
4. **Questions arrive in engineering terms.** An agent that asks "should this
   be a sidecar command or a shared module?" hands the decision to the one
   person least equipped to make it. One that never asks makes irreversible
   choices alone.

Until now this repo has addressed only the first problem, with gates: commands
that exit non-zero. Two published bodies of work address the others.

- **Lauren Tan's pstack** (MIT, github.com/cursor/plugins/tree/main/pstack)
  has 24 one-rule principles, such as *prove it works* and *subtract before you
  add*. Their names work as shorthand for steering an agent. It also has
  `/correct`, which turns a repeated correction into a check. It is built for
  Cursor and deliberately leaves out planning.
- **Matt Pocock's engineering skills** (MIT, github.com/mattpocock/skills) give
  a workflow from a vague idea to merged code: `/wayfinder`,
  `/grill-with-docs`, `/to-spec`, `/to-tickets`, `/implement`, `/tdd`,
  `/code-review` and `/retro`, plus `/improve-codebase-architecture` as a
  periodic audit.

The two overlap very little. Pocock says what order to work in, and Tan says
how to judge each step and what counts as proof. Pocock's `/retro` stops at
suggestions, and pstack has no planning. Neither one assumes the builder can't
review code.

## Decision

**This repo holds engineering standards in three layers.** It keeps the name
`quality-gates`; see Rejected.

| Layer | Answers | Solves | Source | Form |
|---|---|---|---|---|
| Workflow | what order to work in, for the size of the work | 3 | Matt Pocock | a size rule plus his skills |
| Principles | how to judge each step, and how to ask | 2, 4 | pstack, plus lessons from use | one skill: an index and one file per principle |
| Gates | what fails without anyone's cooperation | 1, 2 | this repo | commands that exit non-zero (ADR-001) |

The layers are ordered by how much they rely on the agent's cooperation. Gates
need none. Principles need the agent to read and apply them. The workflow
needs the builder to start at the right step. Where a standard can move down
that table, it does.

### Workflow: size decides the entry point

| The work... | Starts at | Then |
|---|---|---|
| will not fit in one agent session | `/wayfinder` | `/grill-with-docs`, `/to-spec`, `/to-tickets`, `/implement` per ticket |
| fits in one session but changes more than one module | `/grill-with-docs` | `/to-spec`, `/implement` |
| is smaller than that | `/tdd`, or `/diagnosing-bugs` for a defect | |

Every route ends with `/code-review`, then the project's gates. Run
`/improve-codebase-architecture` when a module starts resisting change, not on
a schedule.

The builder only has to judge one thing, the size of the work, and the table
does the rest.

**The project glossary file is `CONTEXT.md`.** Pocock's newer skills write
`GLOSSARY.md`. Projects that adopted his earlier convention use `CONTEXT.md`,
and a rename would change nothing about how they work.

### Principles: a vocabulary with a promotion path

The principles ship as one skill, `standards`, through `qg-skills` like the
gates' skills. Its `SKILL.md` is an index of one line per principle, saying
when it applies. Each principle has its own file, which an agent reads only
when it applies that principle. One skill keeps the space it takes in every
session's skill list to one line, where 24 separate skills would take 24.

The first set:

- From pstack: *prove it works*, *explain the number*, *build the lever*,
  *test behaviour not implementation*, *subtract before you add*, *boundary
  discipline*, *make operations idempotent*, *minimise reader load*, *attack
  the premise*, *encode lessons in structure*.
- From use: *date every "this can't be done"*. A negative finding ("this API
  can't be interrupted") records when and on what version it was observed, so
  it is re-tested instead of inherited. Also *stop and report when a loop runs
  on*: after a fixed time or number of review rounds without a commit, the
  agent reports what is done, what is left, and what it decided that nobody
  asked for.

**A principle that can become a check, does.** When a class of mistake
recurs, the fix goes in the strongest place available. Architecture comes
first, then a gate in this repo, then a behaviour test, and prose comes last.
The principle file then names the gate that replaced it. A principle with
nothing enforcing it is either a judgement call or a gate that hasn't been
built yet.

**A lesson becomes a standard when it has happened at least twice and would
recur in another project.** One-off and project-specific lessons stay in their
project.

### Asking the builder

**Ask when uncertain about anything irreversible, outward-facing or large in
scope. Proceed on reversible work with a stated default.** Every question
carries:

- what is at stake, in plain words;
- two or three options, with only the pros and cons the builder would notice:
  cost, risk, time, what changes for them;
- a recommendation and the reason for it.

The decision stays with the builder, and the analysis stays with the agent.

This is a principle in the `standards` skill. Each consuming project's
`CLAUDE.md` also carries a one-line pointer to it, because skills load only
when invoked and this rule must apply to every turn. `qg-skills --check` fails
when that line is missing.

### Setting up a project: one command

**A `/setup-standards` skill prepares a new or existing project for all three
layers.** A builder can't be expected to know that a project needs a
baseline file, a pre-commit hook and a test that makes CI enforce them, any
more than they can review the code. Pocock's `setup-matt-pocock-skills` does
this for his workflow. This skill calls it, then adds what is not his:

1. Runs Pocock's setup: the issue tracker, triage labels, `CONTEXT.md` and
   `docs/adr/`.
2. Detects the languages in the repo and installs the matching gates at the
   current pin, through `qg-skills`.
3. Records today's debt as baselines, so the gates fail only on new problems.
4. Installs the pre-commit hook and the hook that refuses bulk staging.
5. Adds the tests that make CI run the gates and `qg-skills --check`.
6. Adds the asking-rule pointer to the project's `CLAUDE.md`.
7. Ends with a plain report that accounts for every step above as done,
   already in place, or not done with the reason.

It asks only where a choice is the builder's, such as which issue tracker to
use, and in the asking-rule format. Run again on a set-up project, it changes
nothing that is already correct, so it doubles as the upgrade after a pin
bump.

### Writing for agents

Every skill, `CLAUDE.md` line and principle file in this repo follows Pocock's
`writing-for-agents`:

- **Principle names are leading words.** *Prove it works* or *subtract before
  you add* is a token the agent thinks with, so the file repeats the name
  rather than restating the rule in new words.
- **Index lines are context pointers.** Each line of the `standards` index
  leads with the principle's name and names the cases that should make the
  agent open its file, one trigger per case.
- **Steps end on a completion criterion** the agent can check, such as "every
  step accounted for", rather than "set up the project".
- **Rules are stated as the behaviour wanted.** A prohibition appears only as a
  hard guardrail, paired with what to do instead.
- **Each meaning has one home.** A skill points at the ADR or the gate's
  `--help` rather than copying them.

A new or changed skill is reviewed against that list before release.

### Attribution

Text adapted from pstack or from Pocock's skills keeps its MIT notice. Each
principle file names its source.

## Consequences

- The README leads with who this repo is for and the problems above. The
  standards table stays the gates table.
- A new gate needs no new ADR when it enforces an existing principle. A new
  principle, or a change to the size rule, does.
- Pocock's workflow needs his plugin, and cloud sessions don't install plugins,
  so it is unavailable there. Vendoring his skills through `qg-skills` would
  fix that, at the cost of tracking his upstream. That is a separate decision.
- Candidate gates that grew out of real repeated mistakes:
  - a hook that refuses bulk staging (`git add -A`, `git add .`,
    `git commit -a`);
  - one source of truth for version pins;
  - a smoke test that runs every command-line entry point once;
  - a test that no module shadows a standard-library name;
  - a ratchet against swallowed exceptions.

  Each is built in a consuming project first, and moves here once it has
  caught a real mistake.
- The five existing gate skills predate the writing checklist and are
  reviewed against it in their own release.
- Consumers bump their pin and rerun `qg-skills` to get the `standards` skill
  and the `CLAUDE.md` check.

## Rejected

- **Installing pstack whole.** It is Cursor-specific: its plugin format, the
  `Task` tool and model slugs. Its 23 playbooks would run beside each project's
  own process and contradict it, and it rejects planning outright.
- **pstack's *never block on the human*.** It assumes an operator who can
  review any decision after the fact and cheaply reverse it. A builder who
  can't read the code can't do either. The asking rule keeps the decision with
  them and keeps the cost of the question low.
- **The principles in a separate skills repo.** The name would fit better, but
  `qg-skills` already reaches every project and every cloud session. A second
  repo would need its own distribution.
- **Renaming this repo to `engineering-standards`.** Every consumer would have
  to update its pin for a label. Revisit once the principles layer is bigger
  than the gates layer.
- **One skill per principle, as pstack ships them.** Each skill costs a line in
  every session's skill list. One index costs one line.
- **`GLOSSARY.md`.** See Workflow.

## Addendum 2026-10-06: building the two skills (v0.4.0)

The three layers, the size rule, the principles and the asking rule are
unchanged. Building `standards` and `/setup-standards` changed five details of
the decision above; where this addendum and the text above disagree, this
addendum holds.

- **Pocock's setup templates are copied, not called.** His
  `setup-matt-pocock-skills` sets `disable-model-invocation`, so another skill
  cannot run it. `qg-agent-docs` writes `docs/agents/` from copies of his
  templates, with his MIT notice, and never overwrites a file the project
  edited: it shows the template's own change instead, so the builder can adopt
  it. `upstream.json` records the upstream commit every copied or adapted file
  came from, Pocock's and pstack's; `qg-upstream` reports what changed since,
  and a monthly workflow opens a `needs-triage` issue when it does. Adopting a
  change is a release like any other.
- **The glossary file is `GLOSSARY.md`.** This reverses the decision above and
  the last item under Rejected. Pocock's current skills read and write
  `GLOSSARY.md`, and a project on `CONTEXT.md` would have its glossary ignored
  by them. `/setup-standards` renames an existing `CONTEXT.md` and writes a
  starter glossary where there is none.
- **The stage guard ships now,** not after a consuming project. It was built
  and caught real mistakes in the project this ADR was written from, before
  that project's details were removed. `qg-skills` installs it as a Claude Code
  `PreToolUse` hook and registers it in `.claude/settings.json`; it refuses
  `git add -A`, `git add .`, `git add -u`, `git stage` with those, and
  `git commit -a`, and says to stage files by name.
- **`qg-skills` installs and checks the asking-rule line,** as well as the
  skills and the stage guard. `qg-skills --check` fails when any of them is
  missing or out of date.
- **Gate placement:** `cc-check` runs in the pre-commit hook and in CI; `crap`
  runs in CI only, because it needs coverage from the whole suite.
  `/setup-standards` covers Python, Swift and Rust. A SwiftPM-only package gets
  no CRAP gate until issue #6 is fixed, and the report says so.

*Stop and report when a loop runs on* uses an hour, or three review rounds,
without a commit. Those numbers are a starting point, to be revised from use.

## Addendum 2026-10-10: a CRAP gate for SwiftPM packages (#6)

The gate placement above still holds. `crap --lang swift` now reads a SwiftPM
package's coverage from the llvm-cov export JSON that
`swift test --enable-code-coverage` writes, through `--llvm-cov-json`. The
sentence above about SwiftPM getting no CRAP gate until issue #6 no longer
holds: `/setup-standards` gives a SwiftPM-only package a CRAP gate and a
baseline. Its CRAP step runs on Linux or macOS; put it on the one the
baseline was recorded on, because a function under `#if os(macOS)` or
`canImport(UIKit)` has no coverage record on Linux and scores worst case
there. The step measures coverage and runs `crap` in the same checkout, since
a report file counts only at `crap`'s exact path. ADR-001's "Addendum
2026-10-10: SwiftPM coverage (v0.8.0)" records how a Function's figure is
worked out and matched.

## Addendum 2026-10-11: a SwiftPM package with no test target (#67)

The addendum above holds for a SwiftPM package with a test target. A package
with no test target has no coverage to measure: `swift test
--enable-code-coverage` reports no tests found and `crap` exits 2. For such a
package `/setup-standards` sets up no CRAP baseline or CI step, still sets up
SwiftLint, Swift's complexity gate, and reports CRAP as not done, with the
reason and what it takes: add a test target with tests, then rerun the skill.
No threshold, counting tool or gate scope changes.
