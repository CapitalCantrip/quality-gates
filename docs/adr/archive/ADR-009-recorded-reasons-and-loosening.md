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

Amended by: [Addendum 2026-11-23: warn before a review date; reasons count as tolerated growth](#addendum-2026-11-23-warn-before-a-review-date-reasons-count-as-tolerated-growth)

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

Amended by: [Addendum 2026-11-23: warn before a review date; reasons count as tolerated growth](#addendum-2026-11-23-warn-before-a-review-date-reasons-count-as-tolerated-growth)

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

## Addendum 2026-11-23: warn before a review date; reasons count as tolerated growth

Amends: [Who writes them](#who-writes-them), [Review dates](#review-dates)

Amended by: [Addendum 2026-11-26: the tolerated check as built; `--update` will not recreate main's baseline](#addendum-2026-11-26-the-tolerated-check-as-built---update-will-not-recreate-mains-baseline)

The builder decided both in a grilling session on #115 (2026-11-23). The
design review of 2026-11-11 asked for them (section 9, the comment on #115).

**A passed review date warns on commit and fails on the pull request.** A
commit is often unrelated work, and a date passing looks to the agent like a
gate failing at random. So:

- The review date is the last day a record holds, compared in UTC so a laptop
  and CI agree on the day.
- From 14 days before the date, `qg run commit` and `qg status` warn. A record
  allowed fewer than 14 days, such as a critical dependency flaw at 7, warns
  from the day it is written.
- After the date, `qg run commit` still only warns. `qg run ci` on a pull
  request fails until the record is renewed or removed. CI on the main branch
  warns, so a merge that lands just after midnight does not turn main red.
- The agent may renew or remove a reason for one case in the same pull
  request. A lapsed loosening blocks every pull request until the builder
  merges its own renewal pull request, which is how the builder is asked.

**Triggers are unchanged.** A dependency version and a function edited (#134)
fire on the change that caused them; an issue closing fires in CI only. None
of them lands on unrelated work, and none can be warned about ahead.

**Recorded reasons are part of the tolerated list (#192).** #192 fails CI when
the tolerated list grows without the builder's label. The reasons file is in
that list, so:

- A new record, including "reason unknown" at setup, is growth and needs the
  builder's label. The agent still writes it; the label is the yes. This
  replaces "the agent may write a recorded reason for one case" without asking.
- A renewal is not growth and needs no label. #192's one line names it, such
  as "1 reason renewed to 2027-02-20", and the next checkpoint lists it as
  before.
- On a loosening pull request, the `loosening` label counts as the builder's
  label for #192.
- #192 ships first; #115 adds the reasons file to its check.

Rejected:

- **Failing the commit once a date passes.** It stops unrelated work and looks
  random.
- **A warning period set as a share of each record's life.** Harder to
  predict, and `qg status` already flags 14 days.
- **Every renewal in a pull request of its own.** Unrelated work would stall on
  a separate pull request each time.
- **Treating triggers like dates.** They already fire on related work.
- **Reasons counted but never failing #192.** A well-worded reason would stay
  a quiet way past a gate.
- **A renewal needing the builder's label.** Every lapsed single-case reason
  would wait on the builder.
- **Both labels on a loosening pull request.** The loosening route is already
  stricter.

## Addendum 2026-11-26: the tolerated check as built; `--update` will not recreate main's baseline

Amends: [Addendum 2026-11-23: warn before a review date; reasons count as tolerated growth](#addendum-2026-11-23-warn-before-a-review-date-reasons-count-as-tolerated-growth), and ADR-001's [baseline ratchet](ADR-001-complexity-standards.md#addendum-2026-10-04-the-baseline-ratchet-v030)

Built in sprint 3a (quality-gates#192, #193), following the builder's
decisions on #232 (2026-11-25: the label is a record, not a lock; 2026-11-26:
setup never edits a workflow). Before it, a baseline could grow three ways
without anyone seeing it: delete it and run `--update`, type an entry in, or
add a folder to `exclude`.

**`qg tolerated --against <ref>` fails a pull request whose tolerated list
grew without the builder's label.** It compares the working tree with
`<ref>`, the pull request's base, and prints one line: what grew and whether a
label allows it, or "the tolerated list did not grow".

- The list: every baseline the project module names (`cc-baseline.json`,
  `crap-baseline.json`, `comment-debt.json`, `silencer-baseline.json`), the
  choice file's top-level `exclude`, and `settings.no-comments.exclude`.
  Recorded reasons join when #115 lands them.
- Growth: a baseline entry that is new or higher, or an exclude prefix that
  covers a path no prefix at `<ref>` covered. A prefix in
  `settings.no-comments.exclude` is new only when neither list at `<ref>`
  covered it, because the top-level list already skips the comment gate.
  Lowering or removing entries or prefixes, or deleting a baseline, is not
  growth.
- First adoption: a baseline for a gate that has none at `<ref>`, and a choice
  file when `<ref>` has none, are not growth. Problems found at adoption are
  debt (ADR-006). When `<ref>` has the file, a re-created one is compared entry
  by entry.
- With growth the check exits 1, unless the pull request carries
  `tolerated-growth`, or `loosening` on a loosening pull request; then it
  exits 0 and still prints the line. It reads the labels from `QG_PR_LABELS`,
  which the CI step fills from the pull request's labels, comma-separated. The
  workflow's `pull_request` trigger lists `labeled` and `unlabeled`, so adding
  the label runs the check again.
- An agent never applies either label itself. The label is the builder's yes
  on record, not a lock: one GitHub account cannot tell the two apart, and an
  agent's label is an escape.

**`--update` will not recreate a baseline that main has.** When the baseline
file is missing and the default branch of the repository holding it has the
file committed, `--update` writes nothing, exits 2 and says in one line to
restore it with `git checkout <branch> -- <file>` and update from there. With
no such copy, no default branch, or a baseline outside any repository, it
records a new one as before. This holds for `cc-check`, `crap` and
`comment-debt` through the one ratchet.

Rejected:

- **Labels passed as a flag.** An agent types flags; CI reads the labels from
  the pull request.
- **Every new baseline file counted in full.** Adopting a gate would always
  need the builder's label, though adoption debt is the expected case.
- **Asking the GitHub API for the labels.** It needs a token and the network
  in every consumer's CI, for the same list the event already holds.
- **Refusing `--update` for a baseline outside the repository.** Main cannot
  hold such a file, so there is nothing to restore.
