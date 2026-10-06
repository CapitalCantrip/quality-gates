---
status: accepted
date: 2026-10-07
---

# ADR-003: Ship Matt Pocock's workflow skills through `qg-skills`

## Context

ADR-002's workflow layer is Matt Pocock's skills: the size rule names
`/wayfinder`, `/grill-with-docs`, `/to-spec`, `/tdd` and the rest. Those reach a
session only through his Claude Code plugin, and a cloud session (Claude Code on
the web, including the Code tab of the Claude mobile app) does not install
plugins. ADR-002 left this open under Consequences: vendoring would fix it, at
the cost of tracking his upstream.

The builder works from a phone often enough that the workflow layer missing in
those sessions is the common case, not the edge. Tested 2026-10-07: a fresh
cloud session from the iOS app had none of Pocock's skills.

## Decision

`qg-skills` ships 17 of Pocock's skills beside the standards skills, copied from
`mattpocock/skills` at the commit `upstream.json` records:

- every step the size rule names: `wayfinder`, `grill-with-docs`, `to-spec`,
  `to-tickets`, `implement`, `implement-spec`, `tdd`, `diagnosing-bugs`,
  `improve-codebase-architecture`, and his `code-review` as
  `review-against-spec`;
- what those steps call or the builder uses beside them: `codebase-design`,
  `domain-modeling`, `pr`, `triage`, `retro`, `writing-for-agents`, `handoff`.

Each copied skill carries his MIT notice as `LICENSE-mattpocock`.

**Copied word for word, except where a change is listed.** Every change is an
entry in `docs/upstream-adaptations.md`: what changed, why, and how to redo it
on a newer upstream file. `upstream.json` records the copied files under one
source and the changed ones under a second, so `qg-upstream` labels each
reported diff as one to replace or one to redo by hand.

**`code-review` ships as `review-against-spec`.** As a project skill named
`code-review` it would hide Claude Code's own `/code-review`, which does a
different job: it hunts for bugs, where Pocock's checks the change against the
project's written standards and the issue or spec it came from. The builder
wants both. The three skills that call it by name are changed to match.

**`setup-matt-pocock-skills` is replaced by a pointer skill** of the same name
that sends the builder to `/setup-standards`. Six of the copied skills tell the
builder to run his setup when `docs/agents/` is missing; `/setup-standards`
already writes those files from his templates (ADR-002 addendum). A pointer
keeps those skills word for word.

**The size rule's largest route ends in `/implement-spec`** rather than
`/implement` per ticket. It is Pocock's step for building a spec's tickets as a
task graph, and it is what his `/to-tickets` hands to.

**An update is a release.** The monthly upstream workflow opens an issue when a
watched file changes. Adopting it means replacing the word-for-word copies,
redoing each listed change, moving `commit`, and releasing. Consumers get it by
bumping their pin; their `qg-skills --check` test fails until they rerun
`qg-skills`, so a stale copy cannot pass CI.

## Consequences

- Every project on quality-gates gets the whole workflow layer in every
  session, local or cloud, at the pinned version.
- Pocock's updates reach a project only through a quality-gates release. A fix
  he ships waits for that release; in exchange, no project's workflow changes
  under it without a pin bump.
- A builder with Pocock's plugin installed sees his skills twice, once under
  the plugin's prefix. Skills that call another by name get the pinned copy.
- `handoff` writes to the machine's temporary folder, which a cloud session
  discards when it ends. A handoff that survives the session is a separate
  skill, built in the builder's public skills repo and shipped here as a second
  upstream source once it exists.
- His other skills (`grill-me`, `prototype`, `teach` and the rest) stay
  plugin-only. Adding one is an entry in this ADR's list, not a new ADR.

## Rejected

- **Copying the skills into each project by hand.** Nothing would report his
  updates, and each project would drift on its own schedule.
- **Leaving his `code-review` out.** Claude Code's `/code-review` does not check
  the change against the spec or the project's standards.
- **Editing the six skills that name his setup.** Six changes to redo on every
  update, where one pointer skill needs none.
