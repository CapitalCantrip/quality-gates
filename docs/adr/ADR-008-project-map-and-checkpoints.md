---
status: accepted
date: 2026-11-01
---

# ADR-008: The project map and the checkpoints

## Context

ADR-005 § Four layers adds an Understanding layer with two core pieces: a
**project map**, created at ideation and scaled to the job, and a **checkpoint**
at each stage boundary. ADR-006 sends every new gate's result to the builder
through the "proven" checkpoint, and its 2026-10-31 addendum makes that
checkpoint a prerequisite for the first new gate. Neither says where the map
lives, who writes a checkpoint, or how the builder can trust it.

The builder settled it in a grilling session on 2026-11-01 (quality-gates#112,
with #115), after reacting to a hand-made map of this repo. #28's questions
about the gate report were folded into #112 on 2026-10-30.

## Decision

### The project map

One map per project, committed as `PROJECT-MAP.md` at the root. It is created
at setup or at the first idea, and each job adds to it in proportion to its
size: a bug fix adds nothing, a feature adds its stage and its choices.

It always has five headings:

1. **Outcome**: the picture of what the project is for.
2. **Shape**: its features or components, placed along the stages, each marked
   shipped, decided, planned or missing.
3. **Route**: the stages, with "you are here".
4. **Choices**: open ones, ordered by what they block, and settled ones with
   where each is written.
5. **Loose ends**.

A heading with nothing under it yet says "nothing yet"; a missing heading is a
failure, never a short map.

A CI check fails when the map is missing or lacks a heading. For an existing
project, the first `/setup-standards` run after the release drafts the map from
the repo, its issues and its ADRs. A rendered view of the map is left to the UI
(ADR-005 rollout step 3); the Markdown stays the lasting copy and is never
generated from the view.

### Checkpoints

A checkpoint is given at each of five stage boundaries: idea settled, spec
agreed, built, proven, released. It goes to the builder in chat and in the pull
request or issue the stage belongs to, and says what was decided, what it cost
and what is next. Its lasting effect is the update it makes to the map; no
checkpoint file is kept.

Idea, spec and built are given through one rule and a template in the
`standards` workflow. The copied upstream skills (`wayfinder`,
`grill-with-docs`, `to-spec`, `implement-spec`) are not changed, so re-copying
them never drops the step. "Released" waits on the release stage (#144).

### The "proven" checkpoint

A command builds it from the gates' recorded results (the runner, ADR-007), so
the agent passes it on word for word and cannot soften a failure. The agent
runs it before opening the pull request and puts it in chat and in the pull
request's Evidence. CI builds its own copy in the job summary; when the two
differ, CI's copy holds.

One report serves both readers. The builder's part comes first: pass, fail or
could not check for each gate, then each failure as what is wrong, why it
matters, and the sentence to give the agent. A gate that did not run never
reads as a pass. Below it, a detail section holds scores, limits and paths for
the agent.

It also shows, from ADR-006 and ADR-009:

- every active recorded reason and the trend in their number, with "reason
  unknown" records flagged separately;
- any loosening new since the last checkpoint, first;
- each reason the agent renewed: what, why, and the new date;
- the extra items each gate's issue agreed (#29, #30, #31).

## Consequences

- Every consumer gains one committed file, `PROJECT-MAP.md`, and a CI check on
  its headings.
- The first new gate waits on the runner (ADR-007 build B) and this command.
- Agents carry the map forward at each stage boundary; small jobs cost little,
  because they add little.
- ADR-002's three-layer rule is amended when this ships, and the release
  restates it with four layers.

## Rejected

- **The rendered page as the map.** It lives outside the repo, other sessions
  cannot reliably update it, and nothing can check it.
- **A pinned GitHub issue.** It drifts from the code and needs GitHub.
- **One map per job.** It loses the picture of the whole project, the gap the
  map exists to close.
- **A dated file per checkpoint.** It piles up and repeats the map and the pull
  requests.
- **Optional headings.** A missing heading cannot be told apart from a
  forgotten one.
- **A `qg status` warning instead of a CI check.** A warning nobody runs is a
  silent pass (ADR-006).
- **Checking the map on every commit.** It fails commits during setup, and the
  map changes at stage boundaries, not per commit.
- **The agent writing "proven" from a template.** An agent can misreport a
  failure, the silent pass ADR-006 forbids.
- **"Proven" as a CI comment only.** The builder sees it only after pushing,
  and only on GitHub.
- **Two views of one run.** Twice the text to keep in agreement.
- **Editing each copied skill for its checkpoint.** Four adaptations to redo on
  every upstream re-copy.
