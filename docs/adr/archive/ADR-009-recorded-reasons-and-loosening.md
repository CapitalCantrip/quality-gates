---
status: accepted
date: 2026-11-01
---

# ADR-009: Recorded reasons and loosening

## Context

ADR-001 lets a project tighten a standard and never loosen it. ADR-005 §
Loosening a standard allows loosening once it can be recorded, and shown as a
warning. ADR-006 sends every deliberate gate exception through a **recorded
reason** and lists what the record must support. ADR-007 makes switching off a
gate, raising the commit time limit and removing a language with code into
loosening, refused until this ships.

The builder settled it in a grilling session on 2026-11-01 (quality-gates#115,
with #112). The requirements from #26, #27, #29, #30, #31 and #135 are on
#115.

## Decision

### Two kinds of record

A **recorded reason** relaxes a gate for one case: a skipped test, a secret
false alarm, an accepted planted bug. A **loosening** relaxes a standard for
the whole project: switching off a gate the project has, raising a limit such
as CC 8 to 10, raising the commit time limit, or removing a language that
still has code. A loosening is a recorded reason that always shows as a
warning.

Both live in one committed file at the project root,
`quality-gates-reasons.json`, so there is one count, one history and one place
to look. Where a tool keeps its own list, such as `.gitleaksignore`, the runner
checks that the two agree; an entry in the tool's list with no reason fails.

Each record holds what ADR-006 and the gate issues require: why, what would
let the case come back, and a review date or trigger where the gate asks for
one. "Reason unknown" is allowed at setup and flagged separately.

### Who writes them

The agent may write and renew a recorded reason for one case. A renewal is
never silent: the next checkpoint lists what was renewed, why, and the new
date (ADR-008).

A loosening needs the builder's yes, asked by the asking rule, and the yes is
the builder's merge:

- A loosening arrives in a pull request on its own, labelled `loosening`. CI
  fails a pull request that adds a loosening alongside any other change.
- Every skill forbids an agent to merge a `loosening` pull request, and a
  guard, like the stage guard, refuses an agent's `gh pr merge` on one.
- The record notes the date and the pull request.
- The next checkpoint opens with any loosening new since the last one, so a
  merge that slips past the guard is still shown.

This is a rule with visibility, not a lock: GitHub cannot tell the builder's
merge from an agent's under the same account.

### Review dates

A loosening needs a review date at most 90 days away, renewed only by the
builder's yes through the same route. When a date passes or a trigger fires,
the gate fails until the record is renewed or removed (ADR-006).

### The trend

The count of active records over time comes from the file's git history;
nothing extra is stored.

### Release order

This ships after the choice file and the runner (ADR-007 builds A and B) and
before the project map and checkpoints (ADR-008). Until ADR-008 ships,
recorded reasons for one case are allowed and loosenings are still refused, so
nothing project-wide is loosened before the checkpoint can show it.

## Consequences

- ADR-001's tighten-only wording is amended when the loosening part ships, and
  the README's "never loosen" line changes with it.
- Every consumer gains one committed file, `quality-gates-reasons.json`.
- Each loosening costs the builder a separate pull request, and a renewal one
  every 90 days at most.
- A project that finds a limit too strict can raise it instead of switching the
  whole gate off.

## Rejected

- **One term with a scope field.** A gate switched off would sit in the same
  list as one false alarm.
- **The agent writing loosenings, seen afterwards as warnings.** An agent could
  switch off a gate it keeps failing, against ADR-005.
- **The builder confirming every record.** Setup work on skips and leaked keys
  would stall on the builder.
- **Fixed limits, only switching off allowed.** A project that finds 8 too
  strict would switch the gate off, which is worse.
- **Reasons inside the choice file.** It would mix what is switched on with a
  long, growing list of cases.
- **Reasons kept per gate.** No single count for the checkpoint.
- **An approval line in the record.** An agent can type it as easily as the
  builder.
- **A separate GitHub account for agents with branch protection.** A real
  lock, but setup per project and machine; the builder chose the rule and
  visibility instead.
- **An optional review date for loosening.** A gate switched off "for now"
  would stay off.
- **Shipping both ADRs in one release.** Loosening would be allowed before
  anything shows it to the builder.
