---
status: accepted
date: 2026-10-25
---

# ADR-005: From end-of-line gates to a guided framework from idea to release

## Context

quality-gates began as three gate commands and grew into a bundle: gates,
baselines and ratchets, a stage-guard hook, CI templates, vendored skills and
upstream watches, installed whole by `/setup-standards`. The README framed it as
the quality control station of a software factory: a check at the end of the
line.

That framing undersells what the builder wants. Catching bad code late does not
produce a well-designed outcome, and a builder who is not an engineer is not in
control just because a gate failed. The builder settled the goal and scope in a
grilling session on 2026-10-25; this ADR records the answers. quality-gates#102
holds the direction as an issue.

## Decision

### Goal

A guided framework that takes a non-technical builder from idea to release. It
produces well-thought-through, well-designed outcomes, uses resources
efficiently, and keeps the builder informed and in control, with strong
guidance from frontier models. Preventing poor output is a consequence, not the
aim.

Success for a project means, first, **the builder stays in control** and,
second, **the outcome is well designed**. Fewer bugs and less rework follow from
those two. The scarcest resource is **the builder's attention**, then money,
then time.

### Audience and boundary

Built for the builder first and for other non-technical builders. The repo is
public, so it is self-sufficient and internally consistent from a third party's
point of view: nothing in it depends on, or assumes knowledge of, any private
project. It owns the per-project method; the environment a builder runs projects
in is out of scope.

Claude Code comes first. Gates stay plain commands with exit codes, and required
documents stay plain Markdown, so other agent tools can use them.

Scheduling periodic jobs, such as the upstream skill checks, is out of scope.
quality-gates only needs those jobs to be runnable as commands.

### Stages

| # | Stage | In scope |
|---|---|---|
| 1 | Ideation: is it worth building, and what is it? | now |
| 2 | Spec and design | now |
| 3 | Planning: tickets and order | now |
| 4 | Building | now |
| 5 | Review and proof | now |
| 6 | Release | now: versions, changelogs, a release checklist and a checkpoint |
| 7 | In production: errors, usage, feedback | later, as optional components |

Deploy automation per platform comes later, as optional components.

Ideation challenges the idea: it always raises the strongest objections and the
simpler alternatives, and then the builder decides. It is not a gate.

### Four layers

Amended by: [ADR-008: the project map and the checkpoints](ADR-008-project-map-and-checkpoints.md)

ADR-002 set three layers: workflow, principles, gates. This ADR adds a fourth,
**Understanding**: what the builder knows about the project and the process.

- **Checks still win where they can.** Where quality is judgement, as in
  ideation and design, a stage produces a required document that later checks
  rely on; the document's presence and sections are checkable even when its
  content is not.
- **A project map** is a required core document, created at ideation and scaled
  to the job: the picture of the outcome, the major stages, the key forks where
  the builder's choices shape the project, and what is settled against what is
  open. Each checkpoint updates it.
- **A checkpoint** at each stage boundary tells the builder, in plain words,
  what was decided, what it cost, and what is next.
- **Teaching material** is fixed, reviewed and versioned with releases: a
  concept guide for non-technical builders, with plain-words explainers adapted
  from the principles the framework applies. The model links to it and explains
  what a concept means for the current project, instead of writing explanations
  fresh each time.
- **A learning record** per user, on their own computer and outside every repo,
  records what has been covered and which topics could come next. Explanations
  adapt to it, so nothing is explained twice and a new user starts from zero.
- **Teaching never goes into the code.** The no-comments rule stands; the
  Understanding layer lives in documents, skills and the UI.

The shipped three-layer rule in ADR-002 stays as it is until the first
Understanding component ships; that release amends ADR-002.

### Core and components

A small **core** is always on: the working method (size decides the starting
step), proving that work works, the asking rule, the project map and the
checkpoints.

Everything else is an optional **component**: one capability with all its
parts, switched on or off together. For example, the Python complexity gate is
its command, its skill, its CI job, its baseline and its explainer. Preset
bundles of components may come later.

### Outside material

The framework is a curated collection: some parts are built here, many come
from other open-source projects. Each outside tool is either copied in
(vendored) or declared as a dependency, decided per tool: small things such as
skills and documents are copied, large tools such as linters are dependencies.

An outside source is admitted only when it has an open licence that allows
adapting it, an author with real practice behind it, and is maintained or
stable, and it must not conflict with an accepted ADR unless a new ADR resolves
the conflict. Each source and its pinned version is recorded in the origin
manifest (quality-gates#104).

### Loosening a standard

Amended by: [ADR-009: recorded reasons and loosening](ADR-009-recorded-reasons-and-loosening.md)

Until recorded loosening ships, a project may tighten a standard and never
loosen it. Once it ships, a project may loosen one only through a recorded
project decision, which `qg status` and the UI show as a warning.

### Rollout

Amended by: [Addendum 2026-10-25: the component manifest and `qg status`](#addendum-2026-10-25-the-component-manifest-and-qg-status), [ADR-007: component install](ADR-007-component-install.md)

Staged, so no pinned project breaks:

1. `qg status`, read-only, built together with the origin manifest
   (quality-gates#104).
2. Components installed through `/setup-standards`, with today's set as the
   default.
3. The UI over the same component list: choose components, change settings and
   read each part's guidelines. How the UI is delivered gets its own ADR first.
4. The rename, with the old install line working for a transition period.

The new name is chosen in a separate session (quality-gates#111). The work
this ADR adds is tracked in quality-gates#112 to quality-gates#115.

## Consequences

- Every component has to answer how it keeps the builder informed, not only
  what it checks.
- The README's framing changes from end-of-line quality control to a framework
  across the whole workflow; the standards and gates sections are unchanged.
- The admission rule and the origin manifest become prerequisites for taking in
  more outside material.
- Required documents add a little work to small jobs; scaling them to the job
  keeps that small.

## Rejected

- **Keep it a gate bundle.** Gates alone cannot make an outcome well designed
  or keep the builder in control.
- **Everything optional, no core.** Nothing would hold the toolkit together, and
  the parts that keep the builder in control could be switched off.
- **Teaching generated fresh by the model each time.** It costs tokens, drifts
  between sessions and cannot be reviewed.
- **The learning record inside each project.** It describes a person, would
  leak into public repos, and would not carry across projects.
- **Free adjustment of thresholds.** It quietly removes the guarantee a pin
  gives. A total ban pushes users to fork.
- **A big-bang release or a fresh repo.** Both break or strand the projects
  that already pin quality-gates.

## Addendum 2026-10-25: the component manifest and `qg status`

Amends: [Rollout](#rollout)

Settled with the builder while specifying quality-gates#104 and `qg status`.

**Two files, two questions.** A new `components.json` ships with the package
and answers "what can a consumer install?": each component, its parts, a
one-line plain-words description, and its origin (ours, an upstream, or a
dependency). `upstream.json` stays the file-level record of which upstream
commit each copied file came from, which `qg-upstream` reads. A test fails when
the two disagree. Merging them was rejected: every upstream refresh would touch
the file the UI and outside readers depend on.

**The manifest is a contract.** It carries a format version; changing its shape
needs a new format version and a CHANGELOG note. A test fails when the README's
From column disagrees with it.

**`qg status` is a report, not a gate.** It is read-only, offline, and exits 0;
`qg-skills --check` stays the gate on copied files. Per component it reports
installed, missing, different or unknown, with the description and origin, and
it reports the consumer's pin against the installed version, or "pin not found".
Only copied files can be different; baselines, CI steps and the asking-rule line
are present or absent. When it cannot tell, it says unknown. `--json` gives the
same data for agents and the UI.
