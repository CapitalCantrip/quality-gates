# Design review of quality-gates, 2026-11-11

A living document. Sections are written in the order the review ran, so the
early sections were written before the later evidence was read.

Method: the architecture review protocol (problem first, then a
boring-default sketch, then the documents, then checks and bad-day
simulations). The design under review is the decisions compendium in
`docs/adr/`.

## Start here

Written last (2026-11-14), for the builder. It explains the whole review in
plain words. The numbered sections below it are the working, in the order
the review ran; open them when you want the evidence.

### What the review found, in five sentences

1. The gates you have today catch tangled code, untested code and comments.
   Those matter, but they are not the main ways agent-written code goes
   wrong.
2. The main ways (tests that check nothing, errors hidden so a failure looks
   like success, leaked keys) are all decided and all still waiting to be
   built.
3. An agent can make a failing gate pass without fixing the code, in five
   ways, and today nothing would tell you.
4. Nobody writes down the problems that got past the gates, so there is no
   way to know whether the gates are worth their cost.
5. A lot of effort has gone into making two numbers exact, and that is where
   most of the upkeep comes from.

### What was decided

On 2026-11-14 the builder chose to add one short sprint, called **honest
gates**, before the runner. It makes cheating visible and starts the record
of misses, so everything built afterwards rests on numbers that can be
trusted. The runner is delayed by about one sprint.

### Words used below

- **Baseline:** the saved list of old problems a gate agrees to ignore.
- **Tolerated list:** every place a problem can be excused: the baselines,
  the list of files the gates skip, and lines in the code that switch a
  check off.
- **Escape:** a problem that got past the gates and was found later.
- **Pin:** the version of quality-gates a project uses.
- **Runner:** the planned single command that runs all of a project's gates
  (#138).

### The fourteen proposed issues, in plain words

Each row says what is wrong today, what changes, and what you would notice.

| # | Today | After | What you notice |
|---|---|---|---|
| 1 | An agent can add to the tolerated list and no check sees it | CI fails when the list grows, unless you label the pull request | One line on each pull request: "the tolerated list grew by 3", or nothing |
| 2 | Deleting a baseline and making a fresh one records new problems as old | The command refuses when a baseline already exists on the main branch | Nothing, unless an agent tries it |
| 3 | When a function is renamed or moved, the only fix is typing into the baseline by hand | One command moves the entry and refuses if the code got worse | Fewer hand edits, so a suspicious one stands out |
| 4 | A one-line note in the code tells the coverage tool to ignore untested lines, and no gate counts it | Those notes are counted, and a new one fails | Agents write a test where they used to write the note |
| 5 | Problems found after merging are fixed and forgotten | Each gets a label and three lines: what happened, how it was found, which gate should have caught it | A count by kind, between sprints, that shows which gate to build next |
| 6 | The next six gates are in an order set before any evidence | The order is decided again with the escape count in hand | One decision, at the end of the foundations |
| 7 | A counting tool can update by itself and change scores with no code change | Each version of quality-gates fixes the exact counting tools | No more builds failing on a day when nothing changed |
| 8 | A laptop can run one version of the gates against a project that pins another, silently | The gate stops and says which version to install | A clear message instead of a confusing failure |
| 9 | Code that can only be measured on a Mac fails on Linux CI, or CRAP is left out of CI | A project records "measured on a Mac"; Linux says so and moves on; merging still needs a Mac result | Mac-only projects stop failing CI for the wrong reason |
| 10 | The `crap` skill tells agents that splitting a function is the cheap fix | It tells them to test first, and split only when the code is hard to follow | More tests, fewer piles of tiny untested functions |
| 11 | Duplicate code, dead code and changes outside the task have no check and no decision | A trial on two projects reports what each check finds and how many false alarms | A recommendation you can say yes or no to (settles #22) |
| 12 | When an agent improves a function, the build fails until the baseline is updated | Improving code never fails; the better score is saved automatically | Fewer pointless failures |
| 13 | In Swift and Rust, old problems are excused by a line in the code that nothing counts | They go in a baseline that can only shrink, like Python | The same standard in every language |
| 14 | Setting up a project is 274 lines of instructions an agent follows by hand | One command installs the hook, the CI steps and the baselines | Setup and upgrades are quicker and the same in every project |

### The plan, sprint by sprint

| When | What happens | Your part |
|---|---|---|
| Sprint 3, running now | The comment gate learns four more languages (#185 to #189). Unchanged | The usual review and merge |
| Sprint 3a, honest gates (new) | Issues 1, 2, 4, 5, 7, 10 and the weaker-test review rule (#125). One release | Review and merge; each project adds one CI check on its next update |
| Beside 3a (new) | A research run: could two of the gates compare against the main branch and need no baseline file at all? | Nothing yet |
| Before sprint 4 (new) | A decision session, about 30 minutes | Three choices: keep baseline files or not; how "measured on a Mac" should work; whether the secret check may ship right after the runner |
| Sprint 4 | The runner (#138), now also carrying issues 3, 8, 9, 12, 13 and 14 | Each project re-runs setup once, as already planned |
| Sprint 5 | Explainers, recorded reasons, the track record (#140, #115, #141), with the track record also counting escapes | The usual |
| Sprint 6 | The project map and checkpoints (#112); the "proven" checkpoint shows tolerated-list growth and escapes | The usual |
| End of foundations | The planned architecture pass and the gate-order decision in issue 6. Issue 11 was placed here and is closed (see below) | One decision session |
| After | The new gates, one release each | One release at a time |

### Why this order

- **Issue 1 first** because every later number (reasons, the checkpoint, six
  new gates) is only as trustworthy as the tolerated list.
- **Issue 5 early** because it costs almost nothing and is worth more the
  longer it has run.
- **The research before the runner** because the runner fixes how baselines
  are stored in every project, and changing that afterwards means every
  project re-records them again.
- **Issues 3, 8, 9, 12, 13 and 14 inside the runner release** because
  projects re-run setup once for that release anyway.

### What has happened since

On 2026-11-14 the builder approved filing. The fourteen issues are #192 to
#205, in the order of the table above (row 1 is #192, row 14 is #205). Each
still needs its check against the code before an agent takes it. The new
sprint order is a comment on the build plan (#37), and notes are on #141,
#115 and #173. The builder's answers to the review's six questions are in
section 8.

Two of those answers changed the picture.

- **The one thing that has visibly gone wrong is duplicate code written by
  separate subagents.** The review proposed a finder for it; the builder
  said no, and issue 11 (#202) is closed. The fix belongs at the front of
  the process: settle the shape of the code before tickets are cut (#122).
  The review missed this because it looked only at gates. Section 13 says
  what it missed and what it now recommends.
- **Mac CI is free on public repos** (`2026-11-14-github-macos-ci.md`), so
  a public Swift project can add a Mac job, and the "measured on" setting
  (#200) shrinks to two narrower cases.

Later the same day the protocol retro (section 12) was acted on. The
review skill was rewritten from it, and the drafts in section 12 are now
history. The builder also agreed to two more design reviews: the runner's
spec before its tickets are cut, and the whole package at the end of
foundations. Whether the review ships with this package as a step every
project gets is decided then; the note is a comment on #37.

## 1. Written before reading the ADRs

The only project text seen at this point is `CLAUDE.md`, which loads
automatically. It names the gates (`comment-debt`, `cc-check` at 8, `crap`
at 8), says standards change only through an ADR, and says consumers pin
tags. Nothing else had been read.

### 1.1 The problem, in one sentence

A builder who cannot judge code by reading it directs AI agents across five
repos, and needs a mechanical, trustworthy signal that the code those agents
write is not quietly getting worse, without the signal itself becoming a
second job.

### 1.2 Hard constraints I expect

- The builder is not a software engineer. A failing gate has to say what is
  wrong and what to do in plain words, or it only makes sense to the agent
  that caused it.
- The author of the code and the reader of the gate output are usually the
  same agent. A gate an agent can satisfy without improving the code will be
  satisfied that way.
- Five repos, more than one language, at least one Mac-only toolchain.
  Laptop and CI will not always be able to run the same measurement.
- One person maintains this. Upkeep has to be near zero in a normal week.
- Existing code predates the standards. It cannot all be fixed first.

### 1.3 What a good solution would need

1. **Measures tied to how agent-written code actually goes wrong.** My list,
   most damaging first:
   - code that does the wrong thing while tests pass, because the agent wrote
     the test to match the code
   - tests that run code but assert nothing, or tests weakened or deleted to
     get to green
   - errors swallowed so a failure looks like success
   - a second copy of something that already exists, so the two drift apart
   - changes far outside what was asked
   - leftover dead code, unused flags and half-finished paths
   - invented or needless dependencies
   - functions that grow until nobody can reason about them
   - comments and docs that go stale and are then treated as permission
2. **Tamper evidence.** An agent must not be able to move a threshold, grow
   a baseline or add an exemption without a trace the builder sees.
3. **Old code tolerated, new code held.** Without making the tolerated list a
   thing that needs constant upkeep.
4. **The same answer on the laptop and in CI,** or an explicit rule for when
   they cannot agree.
5. **One source of truth, cheap to upgrade.** A change to a standard reaches
   five repos without five hand edits.
6. **Low false-alarm rate.** A gate that fails for reasons unrelated to the
   change teaches agents and the builder to route around it.
7. **A view for the builder.** Is each repo getting better or worse, in one
   place, without reading code.
8. **A way to tell whether the gates work.** Some record of defects that
   got through, so thresholds are tuned on evidence.

### 1.4 The boring default this design must beat

- Off-the-shelf linters with their built-in complexity rule (ruff C901,
  eslint `complexity`, swiftlint `cyclomatic_complexity`), configured per repo.
- Coverage judged on changed lines only (`diff-cover` style), so no baseline
  file exists at all: old code is never measured, new lines must be covered.
- Old lint violations tolerated with the linter's own ignore list or by
  linting only changed files.
- The `pre-commit` framework with a shared hooks repo pinned by revision,
  plus one required CI check.
- A short shared instructions file for agents.

What this default lacks, and so what a custom package has to earn its keep
on: a combined complexity-and-coverage measure (CRAP), a no-comments rule,
tamper evidence on the tolerated list, and one consistent report across
languages.

### 1.5 Numbers I will look for

- how many gates, how many languages, how many consumer repos
- thresholds and where they came from
- size of each baseline, and whether it is shrinking
- how long the gates take per commit and per CI run
- how often a gate failed for a reason unrelated to the change
- how many defects reached main that a gate should have caught, and how
  many that no gate could have caught
- hours spent on gate upkeep against hours of product work

## 2. Verdict

**Keep the direction. Fix three things before building more gates on top.**
(In the protocol's words: approve direction, gate further implementation on
M1, M2 and M3 below. Stage reviewed: a design already in use, partly built.)

The short version, in plain words:

- The gates that ship measure tangled functions, untested functions and
  comments. Those are real problems, and they are also the easy ones to count.
  The design itself says the bigger risks are elsewhere (weak tests, hidden
  errors, leaked keys), has the right list, and has put every one of them
  behind four pieces of plumbing that are not built yet.
- The promise "old debt is recorded once and can only shrink" is not true
  today. I found five ways an agent can make a failing gate pass without
  improving the code, ran each one, and none leaves a trace the builder would
  see.
- Nothing records what got *past* the gates. So there is no way to tell
  whether threshold 8, or any gate, is earning its keep.
- A large share of the work so far went into making two numbers exact. That
  work was done carefully. It is also where most of the upkeep and most of
  the false alarms come from.

What is good and should not be lost: a gate that could not measure fails
instead of passing; one counter per measure so two gates never disagree; the
word "catch" instead of "bug"; honest wording that loosening is "a rule with
visibility, not a lock"; test code is gated like any other code; a consumer
only changes when its pin moves.

## 3. The design's problem statement against mine

The design's goal ([how-standards-are-made](../adr/how-standards-are-made.md),
from ADR-005): a guided framework from idea to release; success is first that
the builder stays in control, then that the outcome is well designed.

Mine (1.1): a trustworthy signal that agent-written code is not quietly
getting worse.

The two differ in a way that matters. Mine can be checked: did the signal
miss something, did it cry wolf. The design's cannot: no page says what
measurement, taken later, would show that the builder was *not* in control or
that an outcome was *not* well designed. The design broadened the problem
(from gates to a whole framework) on 2026-10-25 without adding a way to tell
whether either the narrow or the broad version is working.

From my list in 1.3, how the design does:

| What a good solution needs | In the design? |
|---|---|
| Measures tied to real failure modes | Partly. See section 7, question 1 |
| Tamper evidence | No. See M1 |
| Old code tolerated, new code held | Yes, with upkeep costs. See question 2 |
| Same answer on laptop and CI | Partly. See M4 and M5 |
| One source of truth, cheap upgrade | Source of truth yes; upgrade is 20 manual steps per release |
| Low false-alarm rate | Not measured; several known sources |
| A view for the builder | Decided, not built (the "proven" checkpoint, `qg tally`) |
| A way to tell whether the gates work | No. See M2 |

## 4. Arithmetic

Every number here I computed or measured myself on 2026-11-14.

1. **The CRAP table closes.** Recomputing `CC² × (1 − coverage)³ + CC ≤ 8`
   gives 0%, 18%, 37%, 51%, 62%, 73%, 100% for CC 2 to 8, matching the README.
   The consequence the table does not spell out: **a function with CC 1 or 2
   needs no tests at all**, ever.
2. **So splitting beats testing.** A function with nine `if` branches (CC 10)
   fails both gates. I split it into nine two-path helpers and wrote no tests.
   `crap` reported nine functions, all ok, exit 0. The same nine untested
   decisions exist; the gate no longer sees them.
3. **Where the work went.** 30 releases in 38 days (2026-09-28 to
   2026-11-04). By my reading of the CHANGELOG: about 4 added protection a
   consumer did not have (the first three gates, the ratchet, TypeScript,
   SwiftPM coverage), about 14 made the two complexity numbers more exact
   (counting, coverage readers, which files, baseline keys), about 12 were
   workflow, skills, setup and docs. ADR-001 is 1,586 lines with 20 addenda.
   Roughly 55 of 136 issues are about measuring those two numbers (matched
   by title, so approximate). **No new kind of defect has been caught since
   the first release.**
4. **The commit budget.** On this repo `comment-debt` takes 0.33 s and
   `cc-check` 0.33 s: 0.66 s of the 2 s limit, most of it Python starting up.
   ADR-006 adds four more commit-time gates. As separate commands that is
   about 6 × 0.33 = 2.0 s before any of them does real work. The limit only
   holds if the runner runs them in one process.
5. **Cost of a release to consumers.** The update is 4 steps per repo
   (install, `qg-skills`, `/setup-standards`, push): 20 steps across five
   repos, each needing an agent session. At least 4 of the 30 releases also
   changed scores or keys, so baselines had to be recorded again.
6. **Loosening renewals.** Each loosening needs the builder's own merge at
   least every 90 days: 4 a year each. Two loosenings per repo across five
   repos is 40 builder merges a year for renewals alone.
7. **This repo cannot show the ratchet working.** All three of its baselines
   are empty (`{}`). Evidence of how the ratchet behaves on real debt exists
   only in the consumers, and nothing collects it.

## 5. Four bad days

The protocol's simulations are written for online services. I translated
each to this design; the retro (section 12) says how.

- **Peak day: several agents building at once in every repo.** Commit speed
  holds. What gives first is the builder's attention: each agent that hits a
  gate resolves it itself, and the routes in M1 are the quickest. Agents
  working in linked worktrees also hit two open bugs (#190, #191) where every
  known function is reported as new, so the gate fails for a reason unrelated
  to the change on exactly the day there are most changes.
- **Dependency-change day: the counting tool releases a new version.** This
  has happened (#173). `lizard` is required as "at least" a version, so a
  fresh install on an unchanged tag picked up a release that counts
  TypeScript differently. Main failed with no code change. `--update` refuses
  to add entries, so the fix was a hand edit of the baseline. At recovery,
  every TypeScript and Swift consumer needs the same hand edit.
- **Halfway day: two repos bumped, three not.** Non-Python projects use one
  machine-wide install (`uv tool install`). The laptop then runs one version
  against five pins. `qg status` reports the mismatch and exits 0; no gate
  checks it. The laptop and CI can score the same code differently, and a
  baseline recorded on the laptop fails in CI.
- **Eighteen months on.** Six more gates, each with exceptions that carry
  review dates. A date passing makes a gate fail with no code change
  (ADR-009), and a newly published flaw in an untouched dependency fails CI
  (ADR-006). Both are correct by the design and both look, to an agent in the
  middle of a ticket, like a gate failing at random. ADR-001 keeps growing
  an addendum for each edge of each coverage format; eight are already
  listed as "not folded in yet".

## 6. Findings

Confidence: **high** means I ran it; **medium** means I reasoned from the
documents; **low** means it needs someone who has seen the consumers.

### Major

**M1. An agent can grow the tolerated list, and nothing shows it.**
(High. Baselines and loosening; README "can only shrink"; Three layers table,
"Gates rely on: nothing".) I ran each of these in a scratch repo:

| Route | Result |
|---|---|
| Delete the baseline, run `--update` | New over-limit function recorded as old debt, check exits 0 |
| Type the entry into the baseline by hand | Check exits 0 |
| Add the file to `exclude` in the choice file | Function is no longer scored, check exits 0 |
| Add `# pragma: no cover` to untested branches | Comment gate allows it; coverage reads 100%; a CC 7 function with six untested branches passes CRAP |
| Swift and Rust: add the silencing line above the function | That line *is* the baseline entry (setup step 3), and nothing counts them |

`--update` refuses to add or raise, which is the right instinct, but the
file it protects is a plain file the agent can write. The design also has no
legitimate way to move an entry when a function is renamed, moved or
re-counted, so hand edits are already the normal fix (#173). When hand edits
are normal, a bad one cannot stand out. ADR-009 designs visibility for
*loosening*; these five routes are loosening by another door and are not
covered. *Fix:* a CI check that compares the baselines, `exclude` and the
count of in-code silencers with the main branch, fails when any grew unless
the pull request is labelled for it, and prints one line for the builder
("the tolerated list grew by 3"). Add a real "re-key" command so hand edits
are never needed.

**M2. Nothing records what got past the gates.**
(Medium. Components and setup, track record; ADR-007.) `qg tally` will count
catches: things a gate stopped. ADR-007 itself says many catches are "an
agent's own first draft being corrected". That number goes up when gates are
noisy as well as when they are useful. The number that tells you whether the
gates work is the opposite one: problems found later (by the builder using
the product, by a review, by a crash) and, for each, which gate should have
caught it or that none could. Without it, threshold 8, the order of the next
six gates and the value of CRAP are all opinion. The planned log also lives
inside git's private folder, which a cloud session throws away at the end.
*Fix:* an `escaped` label and a three-line template in each consumer; the
between-sprints routine counts them by kind; a threshold or gate order
changes only with that count in hand.

**M3. The protection that matters most is queued behind plumbing.**
(Medium. How standards are made, "The gates beyond complexity"; ADR-006
Prerequisites.) ADR-006 says plainly that the bigger risks are tests that
check nothing, weakened tests, swallowed errors, leaked keys and bad
dependencies. Every one waits on the runner, recorded loosening and the
"proven" checkpoint, and the comment gate in four more languages ships
first. The stated reason is that each gate needs a proper exception route.
The strongest case against: a leaked key needs no exception route to be
worth stopping, and the weakened-test review rule (#125) needs no code at
all. In 38 days and 30 releases, none of these shipped. *Fix:* re-open the
order. Ship the cheap, high-value ones in their simplest form now (secret
check, the review rule, switched-off and deleted tests) and let them adopt
the runner and recorded reasons when those exist.

**M4. A tag does not fix what the counters count.**
(High for the event, it is #173; medium for the general case.) Admission
gives a Python dependency "a minimum version plus the version CI tested".
So the date of an install, not the tag, decides how complexity is counted.
This breaks the README's promise that "nothing changes until you update".
*Fix:* each tag pins its counters to exact versions; moving one is a release
with consumer steps.

**M5. The machine-wide install and the per-repo pin can disagree silently.**
(Medium.) See "Halfway day". *Fix:* each gate compares the installed version
with the project's pin and stops with "could not run" on a mismatch.

**M6. CRAP rewards the wrong two moves.**
(High.) Coverage means "a test ran this line", not "a test checked it". One
call with no assertions gave 100%. And small functions need no tests
(arithmetic 1 and 2). The `crap` skill then tells the agent which to pick:

> For each FAIL, recommend the cheaper fix first: CC is the driver (high CC,
> low coverage): reduce CC — extract sub-functions

Splitting is often good design. Splitting *instead of* testing is the gate
being gamed, and the skill recommends it as the cheap option. Mutation
testing is the design's answer and is last in the queue. *Fix:* until then,
(a) reword the skill so an untested function gets tests before it gets
split, and (b) decide whether changed code needs a plain coverage floor that
splitting cannot dodge.

**M7. Three failure modes have no decision.**
(Medium. Corrected 2026-11-14 after reading the build plan: duplicated and
dead code are listed there as an open choice, #22, with no decision and no
date. Changes outside the task are listed nowhere.) Against my list in 1.3:
a second copy of something that exists, leftover dead code, and changes far
outside what was asked. None is in ADR-006. The first is handled in this repo by a sentence in `CLAUDE.md`
("stop and ask rather than add a second copy"), which the design's own
promotion path says is the weakest place for a rule. All three are also
cheap to count with existing tools. *Fix:* one research ticket that runs a
duplicate finder and a dead-code finder over the consumers and reports
findings and false alarms, before deciding.
(Added 2026-11-14, confidence now high for duplicates: the builder reports
that this is what went wrong in this repo. Tickets built by separate
subagents produced near-duplicate components and functions, and several
refactor rounds followed. See section 8, answer 1.)

**M8. The strongest simpler alternative was never weighed.**
(Medium. ADR-001 rejects ruff, with a number, which is good.) The option
missing from every page: judge only what the branch changed, by scoring the
main branch and the branch and comparing, with no stored baseline file. The
case for it: no baseline to tamper with, no keys, no "paid debt" failures,
no re-recording after a counting change, and about half of ADR-001's addenda
would not exist. The case against: CRAP needs coverage for both sides, which
doubles the test run, so it suits `cc-check` and `comment-debt` better than
`crap`. Hosted services that do "new code only" checks were not weighed
either. I am not saying switch. I am saying the committed-baseline design
was chosen without this comparison, and baselines now sit in five repos.

### Minor

**m1. Paying debt breaks the build.** A function that got better fails until
`--update` runs. The reason given (paid debt cannot return) is sound, but
the effect is that agents run `--update` many times a week, so "the agent
changed the baseline" is routine and M1 hides inside it. Let the hook lower
entries by itself.

**m2. A rename or a file move turns old debt into new failures.** Deliberate
(no laundering by renaming), but it taxes exactly the tidy-up work
`/improve-codebase-architecture` proposes, and the only ways through are to
pay all the debt in the moved file or hand-edit (M1).

**m3. Mac-only measuring has no honest state in CI.** See question 2.

**m4. Swift and Rust are held to a weaker standard than Python.** Their debt
is recorded as in-code silencers, which Baselines and loosening says no gate
accepts ("No gate accepts an in-code marker"). The two pages disagree.

**m5. The comment gate covers one of five languages after 38 days,** and
exempts every tool pragma, including the two that switch coverage off.

**m6. Setup is 274 lines of prose an agent follows,** copied into each repo
with the version typed into it. `qg setup` writes only the choice file;
hooks, CI and baselines are done by hand each time. See question 4.

**m7. Eight ADR-001 addenda are "not folded in yet".** The compendium's
promise is that each rule has one home; for coverage readers the home is
still the archive.

### Suggestions

- Mark each planned gate with what it would have caught in the escape log
  (M2) before it is built.
- One `cc` skill with a language section each, in place of four.
- Say in the README which promises are true today and which arrive with the
  runner; "relies on: nothing" and "can only shrink" currently overstate.

## 7. The four questions

### 1. Do the gates measure what makes agent code go wrong, or what is easy?

Mostly what is easy, and the design knows it. Tangled functions and missing
test runs are real but are low on my list of how agent code fails. Top of
that list is code that is wrong while tests pass, tests that check nothing,
and hidden errors. I wrote a function that swallows every error and returns
an empty string, called it once with no assertion, and all three gates
passed.

Missing and planned: weak or weakened tests, swallowed errors, escape
hatches, secrets, bad dependencies (M3). Missing and not planned: duplicate
code, dead code, changes outside the task, anything about the shape of
files and modules rather than single functions (M7). Missing and probably
not gateable: "does the thing actually work when used", which stays with
the *prove it works* principle and the builder.

### 2. Do baselines and ratchets create work that does not pay off?

Yes, in four places, and one of them is the Mac example.

- **Mac-only measuring.** The design's rule is that a function with no
  coverage figure fails, on the laptop and in CI alike. For Swift that means:
  code under `#if os(macOS)` is unmeasured on Linux and fails there; an
  Xcode coverage bundle only exists on a Mac and only matches in the same
  checkout. The setup skill's answer is "run it where the baseline was
  recorded, or report CRAP as not done". So a Mac-only project either pays
  for Mac CI, or has no CRAP in CI, in which case CRAP is checked only when
  an agent chooses to run it. There is no state for "this is measured on the
  Mac on purpose; Linux should say so and move on". The planned "Can't run
  here" block is a line in the setup report, not that state.
- **Counting changes.** Each time a counter or a key rule changed, every
  consumer recorded baselines again. At least four times so far.
- **Paid debt failing** (m1) and **renames counting as new** (m2).
- **Exactness for its own sake.** Much of ADR-001 exists so that a baseline
  key and a coverage figure match to the function on every machine. The
  alternative in M8 needs almost none of it.

What does pay off: the idea itself. Recording debt once and failing only on
new problems is what lets a gate be switched on in an old repo at all.

### 3. Where do the gates push agents into gaming?

| Pressure | The gamed move | Seen by a gate? |
|---|---|---|
| CRAP fails | Split into tiny functions, write no tests | No |
| CRAP fails | Call the function in a test, assert nothing | No |
| CRAP fails | `# pragma: no cover` on the untested lines | No |
| CC fails | Move branches into a lookup table or chained helpers nobody can follow | No |
| Any ratchet fails | Edit the baseline, or delete and re-create it | No |
| A file keeps failing | Add it to `exclude` | No |
| Swift or Rust fails | Add the silencing line | No |
| Comment gate fails | Move the comment into a log message, a long name or a test title | Partly |
| Hook is in the way | Commit without the hook | Only later, in CI |

The first three rows are the ones to worry about, because the agent ends up
believing it did the right thing: the skill told it to (M6).

### 4. Is the split between package, repo setup and skills right?

The package boundary is right: counting, comparing and the manifest live in
code, are tested, and travel by pin. Two parts of the split are off.

- **Setup lives in the wrong layer.** The design's own rule is that a
  standard moves from prose toward commands whenever it can. Installing the
  hook, writing CI and recording baselines are mechanical, yet they are 274
  lines of instructions an agent re-reads and re-does in each repo. That is
  where repos drift apart. `qg setup --go` should do them; the skill should
  shrink to the conversation with the builder and the report. The runner
  (#138) does part of this.
- **Skills carry facts that belong to the tool.** `crap` and `no-comments`
  each explain flags, exit codes and coverage quirks ("a closure default
  argument on the line of the `{` leaves its function unmeasured"). When the
  tool's output says what to do next, the skill can be a few lines. Today a
  change to a reader means a change to a skill, a release and five copies.
- **`standards` is the right shape**: an index and one file per principle.
  It is also the layer with no enforcement, so it should hold only what
  cannot be a gate. *Stop and ask rather than add a second copy* does not
  meet that test (M7).
- **Bundling the workflow skills with the gates** means a wording fix and a
  counting change share a version. The CHANGELOG's "no score, threshold or
  scanned file changes" line handles this well enough. Leave it.

## 8. Questions for the builder

Answered by the builder on 2026-11-14. Each answer is followed by what it
changes.

1. **Since the gates went in, what has gone wrong in the five repos that you
   noticed as a user?**
   Answer: on quality-gates itself, tickets built by separate subagents,
   in parallel and also one after another, produced duplicate components
   and functions with slightly different names and small variations. Each
   subagent started fresh, with no scaffold and no view of the others' work.
   A small refactor was needed straight after the parallel run, and several
   refactor rounds were needed to bring the build to acceptable quality.
   That experience is one of the main reasons the project map and the
   module map are being built.
   What it changes: this is the first recorded escape, and no gate, shipped
   or planned, looks for it. The review first answered with a finder (the
   trial in issue 11, #202). The builder rejected that on 2026-11-14 and
   #202 is closed: the review cycle already catches duplicates after the
   fact, and the aim is to stop them being written. See section 13.
2. **Do the agents and you act under one GitHub account in every repo?**
   Answer: yes, one account.
   So the label in #192 cannot be a lock, because an agent could apply it.
   It is a visible record: the growth line prints on the pull request either
   way.
3. **Do the five pins move together, or one at a time?**
   Answer: "What five pins? Across the five consumers?"
   Yes: each project that uses quality-gates records which version it uses,
   so there are five. The project map shows they move one at a time (one
   project sat at v0.3.2 while another was on v0.12.0). So one laptop often
   holds a newer install than a project expects, which is the case #199
   handles.
4. **Is there Mac CI for the Swift project, and is its cost acceptable?**
   Answer: there is none yet. Mac CI should be free on a public repo; the
   builder commissioned `docs/research/2026-11-14-github-macos-ci.md` to
   check.
   What the research found: GitHub's standard Mac machines are free and
   unlimited on public repos. On a private repo they cost $0.062 a minute
   from a monthly allowance of $12 on the free plan, about 193 minutes.
   GitHub says its own machines should "almost never" be replaced by a
   self-hosted one on a public repo. An earlier draft of this answer said
   Mac minutes use the allowance ten times faster; GitHub no longer states
   that figure, and the dollar rates above replace it.
   What it changes: for a public Swift project the first answer to "Mac-only
   measuring" is a Mac job in CI, which costs nothing and needs no new
   setting. The "measured on" setting (#200) is still needed, for two
   narrower cases: the Linux job in the same project has to say "not
   measured here, by choice" and pass, and a private project may not want to
   spend its allowance on every push. A self-hosted Mac drops off the list
   of options for public repos. One practical catch from the research:
   Python 3.9 is not preinstalled on the Mac machines, so a Mac job installs
   its own Python, and should name a fixed machine label, not "latest".
5. **Has anyone looked at a baseline file's history in a consumer? Do
   entries ever go up?**
   Answer: once, from an error; it was noticed and fixed.
   So M1 has happened in practice, and it was caught by attention, not by a
   check. #192 makes the catch automatic.
6. **Is there any record of functions between 6 and 8 causing trouble, or
   between 9 and 12 being fine?**
   Answer: not that the builder knows of.
   The threshold stays at 8. It becomes a question again only when the
   escape count (#196) gives a reason.

## 9. Proposed issues

Filed on 2026-11-14 as #192 to #205, in the order of this table (row 1
is #192, row 14 is #205), each labelled `needs-triage`. Models: haiku for housekeeping, sonnet by default, opus where a
decision has to be designed.

| # | Title | Acceptance criteria | Model |
|---|---|---|---|
| 1 | CI fails when the tolerated list grows without the builder's label | The five routes in M1 each fail CI on a pull request without the label; with it, CI passes and prints one plain line with the growth; covers all three baselines, `exclude`, and a count of in-code silencers; ADR addendum and compendium page updated | opus |
| 2 | `--update` will not re-create a baseline that the main branch already has | Deleting a baseline and running `--update` exits non-zero and writes nothing; first adoption still works | sonnet |
| 3 | A re-key command for renamed, moved or re-counted functions | Moves an entry without raising its score; refuses when the score rose; prints what moved; no consumer step in any CHANGELOG entry asks for a hand edit afterwards | sonnet |
| 4 | Coverage-off pragmas are counted, not exempt | `# pragma: no cover` and `no branch` are findings with a baseline; a new one fails; the CC 7 example in this review fails | sonnet |
| 5 | Escape log: record problems that got past the gates | An `escaped` label and a three-line template ship through setup; the between-sprints routine reports the count by kind; the ADR says a threshold or gate order changes only with that count cited | sonnet |
| 6 | Decide the order of the next gates again, with the cheap ones first | An ADR-006 addendum that either ships secret check, the weakened-test review rule (#125) and switched-off/deleted tests before the runner, or says with reasons why each must wait | opus |
| 7 | Each tag pins its counting tools exactly (decides #173) | radon and lizard have exact versions per tag; a fresh install of an old tag gives the same scores as on release day; admission rule and CHANGELOG updated | sonnet |
| 8 | Gates stop when the installed version is not the project's pin | A mismatch exits 2 with one line naming both versions and the fix; `qg status` unchanged | sonnet |
| 9 | A "measured on" setting for gates that can only measure on one system | A project can record that a gate measures on macOS; elsewhere it reports "not measured here, by choice" and does not fail; the gate fails anywhere if no result from the named system exists for the commit being merged; ADR-007 addendum | opus |
| 10 | `crap` skill: tests before splitting | The quoted line is replaced so an untested function gets tests first and is split only when it is hard to follow; reviewed against `writing-for-agents` | haiku |
| 11 | Research: duplicate, dead-code and out-of-scope-change checks | One finder for each is run on at least two consumers; the write-up gives findings, false alarms and run time, and recommends gate, review rule or neither | sonnet |
| 12 | Paying debt never fails a commit | A function that improved passes; the lower score is recorded before merge without the agent running `--update`; paid debt still cannot return | sonnet |
| 13 | Swift and Rust debt moves from in-code silencers to a baseline | New silencing lines fail; existing ones are counted in a baseline that only shrinks; the two compendium pages agree | sonnet |
| 14 | `qg setup --go` installs the hook, CI steps and baselines | Running it twice changes nothing; `/setup-standards` no longer contains shell commands for those steps; one consumer set up from scratch with it | opus |

Comments posted on existing issues instead of new ones: on #141, that a log inside
git's folder is lost in cloud sessions and counts the wrong thing alone (M2);
on #115, that an expiring review date should warn ahead and not fail in the
middle of unrelated work.

## 10. Areas for a later `/improve-codebase-architecture` pass

1. **Coverage readers and the matcher.** Four formats, the most addenda, the
   most open bugs (#83, #90, #124), and a design already decided but not
   built (code structure, "coverage matching in one place").
2. **Finding the project root and making baseline keys.** Real paths,
   symlinks, case, worktrees and hooks (#190, #191). If M8's comparison
   leads anywhere, much of this could go.
3. **Setup across three places:** the skill's prose, `qg setup`, and the
   coming runner. Do this pass before #138 is built, not after.
4. **The shared code reader for comments,** before four languages and two
   more gates (swallowed errors, escape hatches) are built on it.

## 11. Fit with the build plan

Added 2026-11-14. Sections 1 to 10 were written without the build plan
(#37), its side lane (#149) or the hand-made project map. This section reads
them and merges the review into them. The plan's state: sprints 1 and 2 and
the gate-interface refactor are merged; the comment gate in more languages
(#185 to #189) is running; then the runner (#138), then #140, #115 and #141,
then #112, then the six new gates.

### What the plan already covers

- Duplicated and dead code is a known open choice (#22). M7 is corrected.
- The coverage matcher (section 10, area 1) is the plan's R4, in the side
  lane.
- A full `/improve-codebase-architecture` pass is already set for the end of
  the foundations.
- #138 already asks every consumer to re-run setup and moves every baseline
  to one format. That is the one planned moment when changing how baselines
  work is cheap. Anything in this review that touches baselines or setup
  should ship in that release or wait a long time.

### What the plan does not cover

- Nothing in it makes the tolerated list tamper-evident (M1). The plan adds
  a reasons file, six gates and a checkpoint on top of baselines an agent
  can edit unseen.
- Nothing records misses (M2). #141 counts catches only.
- The baseline design is about to be fixed in one format without the
  comparison in M8.
- The `crap` skill's advice (M6) and the weaker-test review rule (#125,
  "ready, unscheduled") cost almost nothing and are not scheduled.

### Order, by leverage

1. **The tolerated-list check (issue 1).** Every later part of the plan
   (reasons, loosening, the "proven" checkpoint, six gates) reports numbers
   that rest on it.
2. **The escape log (issue 5).** Nearly free, and its value grows with every
   week it has been running. Started now, it has two months of evidence by
   the time the order of the new gates matters.
3. **The baseline comparison (M8), before #138's tickets are cut.** A short
   research run, because after #138 the answer is expensive to change.
4. **Setup and "measured on" inside the runner release (issues 14, 9, 3, 8,
   12, 13).** These decide how much upkeep five repos cost for years, and
   consumers re-run setup once either way.
5. **The cheap fixes to CRAP gaming (issues 10, 4, #125).**
6. **Gate order (issue 6) and the missing checks (issue 11).** Decide with
   the escape log in hand, when the foundations finish.

### Sprints

Decided 2026-11-14: the builder chose to insert sprint 3a before the runner.
Changes from the plan are marked **new** or **added**. Nothing running is
interrupted.

| Sprint | Work | Release and what consumers do |
|---|---|---|
| 3 (running) | #185 to #189, unchanged | as planned |
| 3a **new**: honest gates | issue 1 tolerated-list check (opus); issue 2 no re-create (sonnet); issue 4 coverage-off pragmas counted (sonnet); issue 7 exact counter versions, deciding #173, with side-lane batch 1 (#103, #123) (sonnet); issue 10 `crap` skill wording (haiku); #125 weaker-test review rule (sonnet); issue 5 escape log label and template (sonnet) | minor; consumers add one CI check and record a pragma baseline |
| research **new**, beside 3a | the M8 comparison: `cc-check` and `comment-debt` judged against the main branch with no stored file, tried on one consumer; reports run time, what breaks, what it would remove (opus) | none |
| decision session **new**, before sprint 4's tickets | about 30 minutes of the builder's time: keep stored baselines or not (from the research); how "measured on" should work (issue 9); whether the secret check may ship straight after the runner | none |
| 4 | #138 the runner, **added**: issue 3 re-key command; issue 12 paying debt never fails; issue 8 gates stop on a pin mismatch; issue 14 `qg setup --go` installs hook, CI and baselines; issue 9 "measured on"; issue 13 Swift and Rust silencers into the baseline. Two pull requests, one tag | as planned: consumers re-run setup once |
| 5 | #140, #115, #141, **amended**: #141 also counts escapes and survives cloud sessions; #115 warns before a review date and the tolerated-list check covers the reasons file | as planned |
| 6 | #112, **amended**: the "proven" checkpoint shows growth of the tolerated list and the escape count | as planned |
| side | R4, then batch 2, unchanged | as planned |
| end of foundations | the planned architecture pass; issue 6 gate order, decided with the escape log. Issue 11 was placed here and is closed (section 13) | none |
| stage 5 | the new gates. Recommended order, for the decision: secrets and dependencies, test weakening, swallowed errors, mutation testing, escape hatches. Mutation testing moves up one place because it is the only thing that closes the tests-that-check-nothing gap in M6 | one release each |

Sprint 4 grows. The plan's rule to keep #138 alone is about consumers
re-running setup once, and that still holds with one tag. If the ticket cut
shows it is too big, issues 9 and 13 move to sprint 5; issues 3, 12 and 14
should not, because they change what setup writes.

## 12. Protocol retro

How the review protocol did on this job. Each item quotes the passage and
drafts a replacement.

### Where it helped

**Writing the problem first.**

> You cannot review a design by reading it and reacting — you must
> independently reconstruct the decision problem *before* reading the
> proposal

M7 exists because of this. Duplicate code, dead code and out-of-scope
changes were on my list and on no page; had I read ADR-006's list first, I
would have judged it complete. Keep as is.

**Doing the arithmetic.**

> Extract every number, multiply them together yourself

Recomputing the CRAP table is what showed that CC 2 needs no tests, which
led to the splitting experiment (M6). Keep as is.

**Simulate, do not pattern-match.** Running the five tamper routes turned
"an agent could probably edit the file" into M1 with results. Keep.

**The missing-alternative check.**

> if your sketch is not in the alternatives section and is not obviously
> dominated, that is a Major finding

Produced M8. Keep.

### Where it misled

**The bad-day simulations assume an online service.**

> **Peak day:** stated peak (or 10× today's) arrives. What saturates first?
> … **Dependency-down day:** the single most critical dependency is down 30
> min, then returns.

A tool that runs on a laptop has no peak traffic and no outage. I had to
invent the translation, and a reviewer who did not would write "not
applicable" four times. Replacement:

> For each, write 2–4 sentences of what mechanically happens. If the design
> is not a running service (a tool, a library, a policy, a process),
> translate before you simulate, and say how you translated:
> - **Peak day:** the heaviest realistic use. For a tool: many users or
>   agents at once, the largest input, the busiest week.
> - **Dependency-change day:** the thing it leans on most goes away *or
>   changes behaviour without warning*. For a tool: a library releases a
>   version that gives different answers.
> - **Halfway day:** some users are on the new version and some are not.
>   What do they share, and what disagrees?
> - **Eighteen-months day:** unchanged.

**Five of the twelve category checks had nothing to grip.** 3.3 (load), 3.4
(consistency), 3.8 (tenancy) and parts of 3.5 and 3.9 are written in terms
of QPS, shards, replicas and tenants. The index says "check a box only after
performing that section's full How steps", which cannot be done here.
Replacement for the line above the checklist:

> For each category, first ask what it means for this kind of design. If it
> has a meaning, run it in that meaning and say so (for a developer tool,
> "load" is run time against the time budget and "state ownership" is which
> file is the source of truth). If it has none, write one line saying why.
> Never tick a box by analogy alone, and never skip one silently.

**The verdict words assume nothing is built yet.**

> Lead with: **APPROVE / APPROVE DIRECTION, GATE IMPLEMENTATION ON [list] /
> BLOCKED / ESCALATE**

This design is in use in five repos. "Blocked" would mean nothing.
Replacement, added after that sentence:

> For a design already in use, lead instead with **KEEP / KEEP, FIX [list]
> BEFORE EXTENDING / RECONSIDER**, and judge a Blocker as "do not build
> further on this until resolved".

**Step 2 assumes the document has a problem section to stop at.**

> Read ONLY the problem/context/requirements sections. Stop before the
> proposal.

A compendium of decisions has none, and the project's instruction file had
already loaded. Replacement:

> If the artefact has no separate problem section, write the problem from
> the request alone, and note anything about the design you had already
> seen so the reader can discount it.

### Where it missed

**Nothing asks whether the design can be gamed by whoever it measures.**
This was the most important question here (M1, M6, question 3) and the
protocol has no step for it. Security (3.8) is about outside attackers, not
about the measured party steering the measure. Draft of a new check:

> **3.13 Incentives and gaming.** *Check:* when the design measures or
> limits someone (a user, a team, an agent), does the cheapest way to
> satisfy it also serve the goal?
> *How:* list each measure and limit. For each, write the cheapest move
> that satisfies it, then say whether that move serves the goal. Try each
> such move for real where you can. List every file, flag or setting that
> relaxes the measure and who can change it; a control the measured party
> can edit unseen is a finding. Ask what the design's own instructions
> recommend when the measure fails, and whether that is the gamed move.
> *Add a fifth bad day:* **adversary day**: whoever is measured does the
> least work that turns the result green. What did they do, and who sees
> it?

**Nothing asks whether a measure measures the thing.** 3.1 asks whether
goals are measurable, not whether the chosen measure tracks the goal. Add
to 3.1's "How":

> For each number the design enforces, name the harm it stands in for and
> one case where the number is good and the harm is present. If that case
> is easy to produce, the measure is a proxy and the design must say what
> covers the gap.

**Nothing asks for evidence of misses.** 3.12 comes close with "what
detects quiet wrongness" but is about data flows. Add:

> For a design whose job is to catch problems, ask where the problems it
> missed are recorded. A count of what it caught, without a count of what
> it missed, cannot show that it works.

**Nothing says who reads the report.** The format leads with bracketed
severity tags and assumes an engineer. This review was for a builder who is
not one. Add to the report format:

> Before writing, name the reader. For a reader who is not an engineer,
> open with the verdict and what to do in plain sentences, explain each
> severity word once, and put the tags second.

## 13. What this review under-weighted: prevention

Added 2026-11-14, after the builder's feedback.

### The blind spot

The brief was about the gates, and the review stayed there. For every
problem it asked "which check would catch this?" and proposed fourteen
issues, thirteen of them checks or plumbing for checks. It did not ask
"where could this have been stopped before it was written?". The builder
named the gap: a check can only report what is easy to count, after the
work is done, and the expensive part is the refactor that follows.

The evidence was in front of the review. Its own pre-registered list in 1.3
had "a second copy of something that exists", and finding M7 noted that the
only guard was a sentence in `CLAUDE.md`. Its answer was still a finder.
Even the escape log's template asked "which gate should have caught it".

### What was decided

- No finder for duplicate, dead or out-of-task code. Issue 11 (#202) is
  closed. The review cycle catches these after the fact: the two-axis
  review against the spec, the bug-hunting code review, the architecture
  pass and the retro.
- The escape log (#196) now asks for the earliest point a miss could have
  been stopped: idea, spec, module map, ticket brief, build, review or
  gate. Its count then says whether to improve the planning or add a gate.

### Why separate subagents write duplicates

Each builder starts with only its ticket. It cannot see what the builder
beside it is adding, and nothing tells it what already exists or what the
new parts should be called. So each one invents its own. Three things would
have to be true before the tickets start for this not to happen:

1. The shape is settled: which modules exist, what each one hides, what the
   new ones are called.
2. The shape exists in the code, as empty modules with their interfaces, so
   a builder fills in a place that is already there.
3. Each ticket says what it builds on and what it must not re-create.

### What the plan already has, and the gap

| Piece | What it does | State |
|---|---|---|
| #122 module map, scaffold ticket, shape checkpoints | All three points above, plus a pause every four tickets to compare the build with the map | Designed in detail; no sprint; listed as "grill when its stage comes up" |
| ADR-011 and the *Code structure* section in each brief | Point 3, for the modules ADR-011 names | In use |
| #101 ship the builder and reviewer agents | Every project's builders carry the rule "check the map before adding a module" | Open choice, no sprint |
| #92 check a brief's claims before an agent takes it | Stops a builder finding out mid-build that its brief was wrong | Tried locally; not shipped |
| #145 challenge the idea; #112 project map | The same thinking one stage earlier | #145 undecided; #112 in sprint 6 |

The gap is timing. The largest multi-ticket builds in the plan, the runner
(#138, now with six added tickets) and the project map (#112), come before
#122. Sprint 3a adds seven tickets, most of them touching the ratchet and
the baselines. The plan's stand-in is one line telling the session to run
`/improve-codebase-architecture` on the modules first.

### Decided

The builder agreed to all of this on 2026-11-14.

1. **Sprint 3a's ticket cut writes a module map and a scaffold ticket by
   hand.** One comment listing the modules the seven tickets touch, what is
   new, and its names; one first ticket that puts the empty pieces in
   place; the other tickets blocked on it. This is a stopgap for building
   quality-gates and the dry run #122 asks for.
2. **#122 is built beside sprint 3a,** so the runner's ticket cut uses the
   real skill and the shape checkpoints. The aim is a shipped part of the
   framework, so every consumer project follows the practice the same way
   at low cost.
3. **#101, shipping the builder and reviewer agents, is built with #122,**
   because the rule "check the map before adding a module" lives in them.
4. **Tickets run in parallel only when four things hold.** The module map
   is agreed, so every builder knows which modules exist and how they
   connect. The scaffold ticket is merged, so the modules, their interfaces
   and the wiring between them exist in the code. The tickets fill in
   different modules. None of them changes an interface or the wiring; a
   ticket that must change either runs alone, and the map is updated before
   the next one starts. The second condition is the builder's addition: a
   map on paper is not enough, because two builders can still wire the same
   two modules together in two different ways.
5. **The between-sprints routine counts review rounds and rework commits
   for each build.** A review round is one time a reviewer sent the work
   back. A rework commit is a change made after the build was first
   reported done, to fix its shape, not to add anything. Together they are
   the price paid for what was not prevented. They do three jobs: they show
   whether the module map is working (R3 took four review rounds; the
   builds after #122 should take fewer); they warn early when a sprint went
   badly, while the cause is fresh; and they show if the map ever becomes
   paperwork that changes nothing. The numbers are small and uneven, so
   they are read as a trend over several builds. They are for the builder
   to read and are never a target given to agents, because an agent told to
   lower them would skip review findings.
