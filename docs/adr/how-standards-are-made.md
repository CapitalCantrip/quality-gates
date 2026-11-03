# How standards are made

Read this when you add or change a standard, a principle, a skill's wording
or a gate on the roadmap, when you write a question for the builder, or when
you need to know what quality-gates is for and what is out of its scope.

## What quality-gates is for

- **A guided framework that takes a non-technical builder from idea to
  release.** Success means first that the builder stays in control, then that
  the outcome is well designed. The scarcest resource is the builder's
  attention, then money, then time. ([ADR-005](archive/ADR-005-direction-idea-to-release.md#goal))
- **The repo is public and self-sufficient:** nothing in it assumes a private
  project. Claude Code comes first, but gates stay plain commands with exit
  codes and documents stay plain Markdown. Scheduling periodic jobs is out of
  scope; quality-gates only needs them runnable as commands.
  ([ADR-005](archive/ADR-005-direction-idea-to-release.md#audience-and-boundary))
- **Stages one to six are in scope** (ideation, spec, planning, building,
  review and proof, release); production monitoring comes later as optional
  components. Ideation always raises the strongest objections and simpler
  alternatives, then the builder decides. ([ADR-005](archive/ADR-005-direction-idea-to-release.md#stages))

## The three layers

<!-- rule:three-layers -->
**Engineering standards come in three layers: Workflow, Principles and Gates.**

| Layer | Answers | Source | Form |
|---|---|---|---|
| Workflow | what order to work in, for the size of the work | Matt Pocock | a size rule plus his skills |
| Principles | how to judge each step, and how to ask | pstack, plus lessons from use | one skill: an index and one file per principle |
| Gates | what fails without anyone's cooperation | quality-gates | commands that exit non-zero |

The layers are ordered by how much they rely on the agent's cooperation. Gates
need none. Principles need the agent to read and apply them. The workflow
needs the builder to start at the right step. Where a standard can move from
the workflow toward the gates, it does.
<!-- /rule:three-layers -->

- **Decided, not built yet: a fourth layer, Understanding** — a project map,
  a checkpoint at each stage boundary, fixed teaching material and a per-user
  learning record. Teaching never goes into the code.
  ([ADR-005](archive/ADR-005-direction-idea-to-release.md#four-layers))
- **Decided, not built yet: the project map and checkpoints.** One
  `PROJECT-MAP.md` per project with five fixed headings (Outcome, Shape, Route,
  Choices, Loose ends), and five checkpoints (idea settled, spec agreed,
  built, proven, released). The "proven" checkpoint is built by a command from
  the gates' recorded results, so a gate that did not run never reads as a
  pass. ([ADR-008](archive/ADR-008-project-map-and-checkpoints.md))

## Principles from use

<!-- rule:principles-from-use -->
Two principles come from use rather than from pstack.

- *Date every "this can't be done"*. A negative finding ("this API can't be
  interrupted") records when and on what version it was observed, so it is
  re-tested instead of inherited.
- *Stop and report when a loop runs on*. After an hour, or three review rounds,
  without a commit, the agent reports what is done, what is left, and what it
  decided that nobody asked for. Those numbers are a starting point, to be
  revised from use.
<!-- /rule:principles-from-use -->

## The promotion path

<!-- rule:promotion-path -->
**A principle that can become a check, does.** When a class of mistake
recurs, the fix goes in the strongest place available. Architecture comes
first, then a gate in quality-gates, then a behaviour test, and prose comes last.
The principle file then names the gate that replaced it. A principle with
nothing enforcing it is either a judgement call or a gate that hasn't been
built yet.

**A lesson becomes a standard when it has happened at least twice and would
recur in another project.** One-off and project-specific lessons stay in their
project.
<!-- /rule:promotion-path -->

## Asking the builder

<!-- rule:asking-the-builder -->
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
<!-- /rule:asking-the-builder -->

## Writing for agents

Every skill, `CLAUDE.md` line and principle file follows Pocock's
`writing-for-agents`: principle names are leading words, index lines are
context pointers, steps end on a checkable completion criterion, rules are
stated as the behaviour wanted, and each meaning has one home. A new or
changed skill is reviewed against that list before release. Adapted text keeps
its MIT notice. ([ADR-002](archive/ADR-002-engineering-standards.md#writing-for-agents))

## Where a rule lives

- **This compendium is the home of every current rule.** A rule a skill
  depends on is tagged on its page, and `qg-references` writes it into each
  skill that links it, so a consumer gets the rule with the skill.
  ([ADR-012](archive/ADR-012-decisions-compendium.md),
  [ADR-004](archive/ADR-004-reference-files.md) for the tagging and
  link checks, which are unchanged)
- **The README links reference files instead of restating rules.** A test
  fails when a README paragraph shares eight words in a row with a tagged rule.

## The gates beyond complexity

Source: [ADR-006](archive/ADR-006-gates-beyond-complexity.md) and
[ADR-010](archive/ADR-010-admission-and-recognised-conventions.md). Only the
comment gate in Python ships today.

- **Planned, in this order:** secret check and dependency check (one release),
  test weakening, swallowed errors, escape hatches, mutation testing. Each
  waits on the runner, recorded loosening and the "proven" checkpoint; the
  comment gate in more languages ships first, after the choice file.
- **The comment gate in more languages** (quality-gates#3): Rust, TypeScript,
  Swift and shell join Python, with one baseline, `comment-debt.json`. Every
  comment counts, documentation comments included; bare tool pragmas stay
  exempt. A **recognised convention**, such as Rust's `// SAFETY:` above an
  `unsafe` block, is a comment form a language's community requires; a project
  may switch it on in its choice file, and each one is argued in
  `docs/recognised-conventions.md`.
- **All commit-time gates together stay under about 2 seconds;** slower checks
  run at ticket end and in CI. An agent routes around a slow hook.
