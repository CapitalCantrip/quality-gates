---
status: accepted
date: 2026-10-31
---

# ADR-006: The gates beyond complexity, and the order they ship in

## Context

CC and CRAP measure how complex code is and whether tests run it. ADR-002 named
four things a builder who cannot read a diff is blind to, and the bigger risks
in agent-written code sit there: tests that check nothing, tests weakened to get
green, errors swallowed silently, leaked secrets, vulnerable or invented
dependencies, and type checks switched off.

quality-gates#22 mapped those gates. Three research tickets measured the tools
(#23 mutation testing, #24 swallowed errors, #25 secrets and dependencies), and
the builder decided each gate in grilling sessions on 2026-10-31: #26 test
weakening, #27 escape hatches (with #3, the comment gate in more languages), #29
mutation testing, #30 swallowed errors, #31 secrets and dependencies, and #32
the order. Each issue's closing comment holds the full decision; this ADR is
the one place they are read together.

ADR-005 frames all of it. Each gate is a component, says how it keeps the
builder informed, and reaches the builder through the "proven" checkpoint
(#112). Exceptions use recorded loosening (#115), not one mechanism per gate.
Outside tools are admitted under #114.

## Decision

### Two kinds of exception: debt and recorded reasons

Amended by: [ADR-009: recorded reasons and loosening](ADR-009-recorded-reasons-and-loosening.md)

Existing violations found when a gate is adopted are **debt**, recorded in a
baseline as every gate does today (ADR-001 addendum). They gain reasons or are
paid down, busiest files first, through the debt-audit route (#42).

A deliberate exception is a **recorded reason** (#115): why the standard is
relaxed for this case and what would let it come back, with a review date or a
trigger where the gate asks for one. The checkpoint lists every active reason.
When a date passes or a trigger fires, the gate fails until the reason is
renewed or removed.

Two gates do not let existing cases become debt. A test switched off at
adoption (#26) and a key found in history at adoption (#31) each need a reason
before the gate is switched on. A skip is a choice to stop checking, and a
leaked key is a live risk; neither is debt that was merely found.

No gate uses an in-code marker as its exception route (`gitleaks:allow`,
`# pragma: no mutate`, `// Stryker disable`, `// muter:disable`). Such markers
are comments, which `comment-debt` forbids, and they cannot be reviewed in one
place.

### The gates

| Gate | Catches | How | Runs |
|---|---|---|---|
| Comment gate, more languages (#3) | comments in Rust, TypeScript, Swift and shell | `comment-debt`'s lexer, extended | every commit and CI |
| Secret check (#31) | passwords, keys and tokens | gitleaks | every commit and CI |
| Dependency check (#31) | known flaws and malicious packages in dependencies | osv-scanner | ticket end and CI |
| Test weakening (#26) | switched-off tests, run-only markers, net test deletions | our own stored test list | every commit and CI |
| Swallowed errors (#30) | errors caught and ignored, or thrown away | our own spotting plus each language's type-aware tools | text shapes every commit; type-aware shapes ticket end and CI |
| Escape hatches (#27) | type escapes, crash-if-wrong shortcuts, warning silencers | our own spotting | every commit and CI |
| Mutation testing (#29) | tests that run code without checking it | mutmut, StrykerJS, cargo-mutants | ticket end and CI, changed functions |

**Comment gate (#3).** `comment-debt` grows from Python to Rust, TypeScript,
Swift and shell. It ships ahead of the rest of this ADR, with its own ADR.

**Secret check (#31).** Every commit and CI, so a key is stopped before the
push; a pushed key must be replaced, not just deleted. At setup, one scan of the
whole history: the agent names each key's service and tells the builder how to
cancel it, the builder confirms, or the agent shows it was never a real key.
Each such finding gets a reason with no review date. The gate does not rewrite
history. A false alarm is a `.gitleaksignore` fingerprint backed by a reason;
`gitleaks:allow` fails the gate.

**Dependency check (#31).** Malicious packages always fail, with no exception
route. High and critical flaws fail, including in build and test-only
packages; a flaw with no severity counts as high. Medium and low are reported in
the checkpoint. A new flaw in an untouched package still fails. A flaw with no
fix needs a reason with a review date of at most 90 days (high) or 7 days
(critical) and a "fix released" trigger checked in CI. A plain command runs the
check on demand so the builder's own scheduler can run it weekly; scheduling
stays outside quality-gates (ADR-005). It needs the network: in CI "could not
check" fails, and offline on the builder's machine it shows "could not check"
without blocking the commit. osv-scanner's exit codes 127 and 128 are never a
pass. A check for brand-new or barely used packages is a later component
(#126).

**Test weakening (#26).** A stored list of the project's tests, found by
reading the code, compared on every run. Skip and expected-to-fail markers need
a reason with a review date of at most 90 days or a trigger. Run-only markers
(`.only`, `fit`) always fail. A net drop in the test count needs a reason.
Reorganised tests need a commit-message note and a reviewer check, not a lasting
record. Loosened assertions are left to the review check (#125) and mutation
testing.

**Swallowed errors (#30).** Its own command. Each shape has exactly one owner,
so each case is counted once and ADR-001's one-counter-per-measure rule holds:

- Shapes that need types go to the language's own tools: TypeScript promises
  nobody waits on (typescript-eslint `no-floating-promises`), Rust results
  thrown away (rustc `unused_must_use`, clippy `let_underscore_must_use` and
  `unused_result_ok`), and an unused Swift `try?` result (the compiler).
- Shapes visible in the text are ours, sharing `comment-debt`'s code reader:
  empty handlers including ones holding only a comment, catch-everything
  handlers that return a default or only log, Swift `_ = try?`, Python
  `contextlib.suppress(Exception)`, and shell `|| true`, `set +e` and
  `2>/dev/null` on a command that matters. Python uses its own parser.
- A narrow catch that returns a default is not counted.
- A test in this repo runs ruff, ESLint, clippy and SwiftLint beside our
  spotting on the same samples, and fails if a linter catches a case we miss.

A new case needs a reason, with a review date only when it names a trigger.
The agent is told: let the error rise to where it can be reported, or handle it
where it happens; logging alone is not handling; a reason comes last.

**Escape hatches (#27).** Its own command, sharing the code reader. Counts type
escapes, crash-if-wrong shortcuts outside tests, warning silencers, and
TypeScript `strict` off; the table is on #27. A new hatch needs a reason, with a
review date only when it names a trigger.

**Mutation testing (#29).** Never per commit. At ticket end and in CI on the
changed functions, with no survivor allowed: each survivor gets a test that
catches it, or a reason that the mutant changes nothing. That reason is kept
outside the code, tied to the function and the exact change, and lapses when
the function is edited; the reviewer checks it. Unchanged code is not gated: a
full-run command, for the builder's own scheduler, reports the weakest
functions, paid down through #42. Mutation results stay separate from CRAP. A
run that cannot complete or gives an implausible score is "could not check". A
flaky test gets one rerun.

### Order

1. Secret check and dependency check, in one release. A leaked key is the
   costliest mistake and cannot be undone, both wrap existing tools, and they
   share the download-and-verify machinery.
2. Test weakening: the shortcut agents take most.
3. Swallowed errors, reusing #3's code reader.
4. Escape hatches, reusing the same reader.
5. Mutation testing: the heaviest to build and run, and covered meanwhile by
   test weakening on every commit and the review check (#125).

If the admission rule (#114) is late when a slot comes up, the next gate that
does not need it moves up. Every other gate ships in a release of its own.

### The commit budget

Amended by: [ADR-007 § The commit time limit](ADR-007-component-install.md#the-commit-time-limit)

All gates that run on a commit stay under about 2 seconds together on a normal
commit. A check that is slower runs at ticket end and in CI instead; this moves
the type-aware parts of the swallowed-error gate there. An agent routes around
a slow hook.

### Languages

| Gate | Python | TypeScript | Rust | Swift | Shell |
|---|---|---|---|---|---|
| Secret check | yes | yes | yes | yes | yes |
| Dependency check | yes | yes | yes | if the build proves `Package.resolved`, else named here | n/a |
| Test weakening | yes | yes | yes | yes | n/a |
| Swallowed errors | yes | yes | yes | yes | yes |
| Escape hatches | yes | yes | yes | yes | none to count |
| Mutation testing | yes | yes | yes | after a trial run (#127) | n/a |

### Reaching the builder

Amended by: [ADR-008 § The "proven" checkpoint](ADR-008-project-map-and-checkpoints.md#the-proven-checkpoint)

Each gate shows in the "proven" checkpoint (#112) as pass, fail or could not
check, never letting a gate that did not run read as a pass, then its open
reasons. A failure says what is wrong, why it matters and the sentence to give
the agent. Each gate's agent message says to fix the cause first and record a
reason last. The wording agreed for each gate is on its issue.

### Prerequisites

Amended by: [Addendum 2026-10-31: the "proven" checkpoint comes first](#addendum-2026-10-31-the-proven-checkpoint-comes-first)
Amended by: [ADR-010: admission and the comment gate's new languages](ADR-010-admission-and-recognised-conventions.md)

Every gate here except #3 waits on component install (ADR-005 rollout step 2)
and recorded loosening (#115). The secret, dependency and mutation gates, and
the TypeScript part of the swallowed-error gate, also wait on the admission
rule (#114). Each gate gets one build issue, blocked by these.

## Consequences

- Six more gates reach consumers over about six releases; each bump says what
  the consumer must do.
- #115 must support a review date, a dependency-version trigger, an
  issue-closing trigger, a "fix released" trigger, a lapse on editing a
  function, and records with no date; and it must flag "reason unknown".
- Swallowed errors and escape hatches depend on the code reader #3 builds.
- Some exceptions now need a reason that the builder sees counted in the
  checkpoint, which costs agent time at setup for skips and leaked keys.
- Weekly full runs depend on a scheduler outside quality-gates; without one,
  only changed code is checked.

## Rejected

- **Wrapping the linters alone for swallowed errors.** None catches "catch
  everything and return a default", the shape agents favour.
- **Running linters and our spotting over every shape.** One case would be
  counted twice and need two reasons, against ADR-001.
- **A percentage limit for mutation testing.** It hides the surviving weak
  spot the gate exists to show.
- **A mutation score baseline for unchanged code.** Mutant labels are not
  stable between runs, and setup would need a full run.
- **Recording leaked keys and existing skips as debt.** Both are choices or
  live risks, not found debt.
- **Rewriting history to remove a leaked key.** It is irreversible and does not
  make a copied key safe.
- **One ADR per gate.** Seven files to keep in agreement for decisions made
  together.
- **Shipping in shared-code order.** It is cheapest to build, but protection
  against leaked keys would arrive last.

## Addendum 2026-10-31: the "proven" checkpoint comes first

Amends: [Prerequisites](#prerequisites)

Every gate here except #3 also waits on the "proven" checkpoint (#112). Each
gate's failure wording, its open reasons and its "could not check" reach the
builder only through the checkpoint (§ Reaching the builder). Without it, a
gate that did not run is visible only to someone who runs `qg status`, which
is the silent pass this ADR forbids.

The builder chose this on 2026-10-31, after a hand-made project map showed the
gap: the gate issues required the checkpoint, but nothing here listed it.
Reporting through the runner and `qg status` until the checkpoint shipped was
rejected. The first gate would then reach the builder without the plain-words
report that keeps the builder in control (ADR-005).
