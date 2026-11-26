---
status: accepted
date: 2026-11-01
---

# ADR-010: Admission of outside sources, and the comment gate's new languages

## Context

ADR-005 § Outside material admits an outside tool, skill or reference only with
an open licence that allows adapting it, an author with real practice behind
it, upkeep or stability, and no conflict with an accepted ADR, recorded in the
origin manifest. It left open how each test is judged and recorded, and what
"pinned version" means for each kind of dependency. The manifest now exists
(`components.json` with `upstream.json`, quality-gates#104) and already says
whether each part is ours, copied from an upstream, or a dependency; it records
no licence and no judgement. The secret, dependency and mutation gates and the
TypeScript part of the swallowed-error gate wait on this (ADR-006).

ADR-006 grows `comment-debt` from Python to Rust, TypeScript, Swift and shell
(#3), with one shared code reader generalised from LocalBar's
`scripts/check-no-comments`, which the swallowed-error and escape-hatch gates
reuse. Decided on #3 (2026-10-31): extend `comment-debt` rather than add a
command; documentation comments count in every language; bare tool pragmas stay
exempt; a repo's own documented exceptions are declared by the project, not
built in.

Both questions share one idea: nothing comes in, whether an outside source or
an allowed comment form, without a written case that a reviewer can check. The
builder settled them together in a grilling session on 2026-11-01
(quality-gates#114, #3).

## Decision

### Admitting an outside source

Amended by: [Addendum 2026-11-26: counting tools are pinned exactly (#198)](#addendum-2026-11-26-counting-tools-are-pinned-exactly-198)

**Licence.** Material copied in needs a permissive licence (MIT, Apache-2.0,
BSD, ISC), because adapting it ships it under ours. A dependency, which runs as
a separate tool and is never copied, may have any OSI-approved licence.

**The record.** Each outside source is recorded once in the manifest with its
licence, one sentence on its author's practice, and either the date of its last
release or a "stable" verdict with its reason. A test fails when a source lacks
any of them. A source with no admission does not ship.

**Upkeep.** The monthly upstream workflow also flags a source with no release
in 12 months, unless its record says stable.

**Pinning, by kind.**

| Kind | Pinned as |
|---|---|
| A tool this repo downloads, such as gitleaks or osv-scanner | an exact version, verified against its published checksum |
| A Python package this package installs, such as radon or lizard | a minimum version, with the version CI tested recorded beside it |
| A tool setup installs into the consumer's project, such as mutmut, StrykerJS or typescript-eslint | an exact version written by setup and moved by a pin bump |

An exact pin on a package this package installs would clash with the
consumer's own installs.

**Conflict with an accepted ADR.** A conflict in text we copy is resolved by an
entry in `docs/upstream-adaptations.md`. A dependency whose behaviour conflicts
needs a new ADR or stays out.

**Sources already in use** (radon, lizard, `mattpocock/skills`,
`cursor/plugins`, pstack) are admitted with full records in the change that
builds this. Tools used only by this repo's tests (ruff, ESLint, SwiftLint in
the calibration test) get a licence check and a "test only" mark, since they
never reach a consumer.

### The comment gate in more languages

Amended by: [Addendum 2026-11-10: a component per comment language, and a choice about existing debt](#addendum-2026-11-10-a-component-per-comment-language-and-a-choice-about-existing-debt), [Addendum 2026-11-23: where `SAFETY:` applies, which pragmas are bare, and triple-slash references](#addendum-2026-11-23-where-safety-applies-which-pragmas-are-bare-and-triple-slash-references), [Addendum 2026-11-26: silencers, a second kind of finding](#addendum-2026-11-26-silencers-a-second-kind-of-finding), [Addendum 2026-11-26: Swift's `swiftlint:disable` is a silencer (#235)](#addendum-2026-11-26-swifts-swiftlintdisable-is-a-silencer-235), [Addendum 2026-11-26: TypeScript's `istanbul`, `c8` and `v8 ignore` markers are silencers (#236)](#addendum-2026-11-26-typescripts-istanbul-c8-and-v8-ignore-markers-are-silencers-236)

**Languages.** Rust, TypeScript (including `.tsx`, `.js`, `.jsx`, `.mjs` and
`.cjs`), Swift and shell join Python. Shell becomes a language in the choice
file (ADR-007): setup proposes it when the repo tracks `.sh`, `.bash` or `.zsh`
files, or files whose first line is a shell shebang.

**What counts.** Every comment, documentation comments included. A comment
over several lines counts once per line, as in Python. Swift's `// MARK:`
counts; an extension or a separate file does its job. Strings used as comments
count in Python only. Bare tool pragmas stay exempt, such as
`eslint-disable`, `@ts-expect-error`, `swiftlint:disable` and
`shellcheck disable=`; the escape-hatch gate counts the warning silencers among
them (ADR-006).

**The code reader.** Python keeps its own reader. The other languages share
one, which returns each comment with its kind, text and lines, and a copy of
the code with strings and comments blanked out, line numbers kept. The
swallowed-error and escape-hatch gates search that copy.

**One baseline,** `comment-debt.json`, for every language.

**On a pin bump,** each new language a project uses is offered by the next
`/setup-standards` run, as a component a release adds (ADR-007 § Pin bumps).
Accepting it records the comments already there as debt (ADR-006), paid down
through #42; only new comments fail.

**Exclusions move to the choice file,** so the hook, CI and `qg status` read
one list. `--exclude` is removed; setup moves a project's existing flags into
the choice file.

### Recognised conventions

Amended by: [Addendum 2026-11-23: where `SAFETY:` applies, which pragmas are bare, and triple-slash references](#addendum-2026-11-23-where-safety-applies-which-pragmas-are-bare-and-triple-slash-references)

A **recognised convention** is a comment form a language's own community
requires, which a project may switch on in its choice file as an ordinary
choice: off by default, listed by `qg status` among the project's choices, and
not a warning. Any other comment form a project wants is a loosening
(ADR-009).

Each one is recorded in `docs/recognised-conventions.md` with its full case:
what it is for, the arguments for and against, its impact on a project, its
sources, and the exact form the gate allows. A test fails when the gate allows
a form the file does not record, or the file records one the gate does not
allow.

The bar is set here once. Adding a convention is a pull request that adds its
case to the file and the form to the gate, reviewed against this bar and
released with a CHANGELOG line; it needs no addendum here.

The first is Rust's `// SAFETY:` directly above an `unsafe` block or
`unsafe impl`. The case is in the file.

### Release order

#3 ships in a release of its own, ahead of the other gates in ADR-006, but now
after the choice file (#137), which holds its exclusions, its conventions and
the shell language. #114's build ships before the first gate that needs an
outside tool.

## Consequences

- ADR-006's "every gate except #3" no longer frees #3 from component install:
  it waits on #137, though not on the runner or the explainers.
- Projects that pass `--exclude` break on the bump until setup has moved the
  flags; the CHANGELOG entry says so.
- A Rust project with `unsafe` code switches `SAFETY:` on once and sees no
  warning for it.
- Every outside source costs a short written record, and an old one is flagged
  each month until renewed or marked stable.
- The manifest's format version changes when it gains admission records; tools
  that read it are told in the CHANGELOG.

## Rejected

Amended by: [Addendum 2026-11-26: counting tools are pinned exactly (#198)](#addendum-2026-11-26-counting-tools-are-pinned-exactly-198)

- **Every allowed comment form as a loosening.** A Rust project with `unsafe`
  code would carry a permanent warning for what its community requires, and the
  builder would learn to ignore warnings.
- **Exclusions as hook and CI flags.** The two lists drift apart.
- **Shell always checked, outside the choice file.** The choice file would stop
  being the source of truth for languages.
- **New languages switched on by the bump.** A project that missed the
  record-the-debt step would have every commit blocked, which an agent routes
  around.
- **Permissive licences only, for dependencies too.** It would shut out a
  copyleft tool that never touches a project's code.
- **Exact pins for every dependency.** It breaks consumers' installs.
- **The admission judgement noted only in the pull request.** Tools cannot read
  it, and it is lost after the merge.
- **Each convention's case inside this ADR.** Each addition would need an
  addendum, and the case would sit in two places.
- **A separate ADR for each issue.** One rule, a written case before anything
  comes in, would be split in two.

## Addendum 2026-11-10: a component per comment language, and a choice about existing debt

Amends: [The comment gate in more languages](#the-comment-gate-in-more-languages)

The builder decided this on #3 (2026-11-10), when the brief was re-checked
against `main` after the choice file (#137) and the shared ratchet (#178) landed.

**Each new comment language is its own component.** `no-comments-rust`,
`no-comments-typescript`, `no-comments-swift` and `no-comments-shell` are
offered, chosen or declined like any other component, as a release adds them
(ADR-007 § Pin bumps). `no-comments` stays Python's, so its id does not change.
A language is checked only when its component is chosen in the choice file.
Python follows the same rule: it is checked only when `no-comments` is chosen,
and a project with no choice file is checked as before.

**Existing comments are the builder's choice, made after seeing them.** This
replaces "accepting it records the comments already there as debt". Before the
builder chooses, setup shows that language's debt report, computed by the
gate's own finder:

- the total, and the count by kind (line, block, doc) and by area;
- the top culprits: the files and folders with the most comment lines, and
  those with the most rationale lines (workaround, for now, TODO and the like).

The builder then chooses one of two:

- **Record as debt.** Every existing comment of that language goes into
  `comment-debt.json`; only new ones fail.
- **Clean first.** The builder picks a scope from the report (an area, a file
  or a kind), and may ask for an issue for the rest. The scope is paid down,
  whatever remains is recorded as debt, and the language is switched on once
  the paydown is done.

The gate never switches a language on with its comments unrecorded, so the
reason for rejecting "new languages switched on by the bump" stands.

**The comment gate checks the files in scope.** It takes them from the project
module, as `cc-check` and `crap` do (*What gets scored*): the files git would
commit, less the choice file's `exclude` and, without a choice file, the
default fixture folders. `settings.no-comments.exclude` applies on top and
matches whole path segments (ADR-001 addendum 2026-11-01), so `build` skips
`build/` and never `buildscripts/`. An untracked file that git would commit is
checked; before, only tracked files were. A file the gate cannot read, an
one it may not open, an unfinished one that does not parse or one that is
not UTF-8, is unmeasured, as
in the CRAP gate (ADR-001 addendum 2026-10-25): the gate names it and fails,
and the baseline keeps any entry it has and records none for it. Entries for
a language the gate does not check are not judged and `--update` keeps them,
so declining a language, or a choice file that does not choose `no-comments`,
never empties its recorded debt.

**`--exclude` is refused.** `comment-debt --exclude x` exits non-zero with a
message that says to run `/setup-standards`, which moves the prefixes into
`settings.no-comments.exclude`. A hook or CI line that still passes the flag
fails until setup has moved it.

**Left to a later build.** The one common baseline format and the gate flags
other than `--exclude` wait for the runner (#138): `comment-debt.json` stays a
per-file count, and `--update`, `--status` and `--baseline` stay. The shared
code reader is a module of its own, `code_reader` (#210 puts it in place);
the swallowed-error and escape-hatch gates (#132, #133) reuse it.

Rejected:

- **One component for all four languages.** A project that wants Rust but not
  Swift would take both, or neither.
- **Recording existing debt with no choice.** The builder would not see what
  the gate swallowed, and could not choose to pay a folder down first.
- **Cleaning first with the gate already on.** Every commit would fail until
  the paydown finished, which an agent routes around.
- **Counting only tracked files.** A new file could carry comments until its
  first commit, unlike every other gate.

## Addendum 2026-11-23: where `SAFETY:` applies, which pragmas are bare, and triple-slash references

Amends: [The comment gate in more languages](#the-comment-gate-in-more-languages), [Recognised conventions](#recognised-conventions)

Settled in review of the Rust, TypeScript, Swift and shell readers (#186,
#187, PR #219).

**The `unsafe` block under a `// SAFETY:` run may sit anywhere on the next
line,** as in `let ev = unsafe { event.as_ref() };`. Rust code takes the
result of an `unsafe` block in an assignment as often as it opens one on a
line of its own, and the reasoning belongs to that block either way.
`unsafe impl` still starts its line. `docs/recognised-conventions.md` gives
the form.

**These comments are bare tool pragmas, and exempt:** Rust's
`// @generated`; TypeScript's `eslint-disable`, `eslint-disable-line`,
`eslint-disable-next-line` and `eslint-enable`, each with or without rule
names, `@ts-expect-error`, `@ts-ignore` and `prettier-ignore`; Swift's
`swiftlint:enable`, with or without `:next`, `:this` or `:previous` and rule
names (its `swiftlint:disable` became a silencer, [addendum 2026-11-26,
Swift](#addendum-2026-11-26-swifts-swiftlintdisable-is-a-silencer-235)); shell's `# shellcheck disable=` with its
codes. A tool reads each of them and none can move into a name or a test; an
`enable` only closes what a `disable` opened. Any of them followed by prose
counts.

**`/// <reference … />` in TypeScript counts, as a doc comment.** An
`import` or the `types` list in `tsconfig.json` does its job, so it is not
a pragma a project has to keep; the report files it under kind `doc`
because it describes the file to the compiler.

## Addendum 2026-11-26: silencers, a second kind of finding

Amends: [The comment gate in more languages](#the-comment-gate-in-more-languages)

Settled at the 3a ticket cut (#195, plan #232) after the review of 2026-11-25
showed a function at CC 8 with six untested branches under `# pragma: no cover`
passing `crap`: the pragma took those lines out of the coverage report and the
comment gate exempted the pragma as a bare tool pragma.

**A silencer is an in-code marker that switches off one of quality-gates' own
gates.** `comment-debt` finds it at a file and line, as a finding of kind
`silencer` beside the comment lines. Silencers are not comment debt: a line
that holds a silencer is not also counted as a comment line, whatever prose
follows it. A tool still reads it, so prose does not take it out of the kind.

**The readers live in the comment gate's per-language table,** one per
language beside its comment syntax, and not in the language registry
(ADR-011 § 2). A reader is a function given the language's reading and the
source, and returns the lines that hold a silencer, so a language can look
at its comments or, as Rust's will, at the code with strings and comments
blanked out. Python's reads the physical source lines, as coverage.py matches
them: `# pragma: no cover` and `# pragma: no branch` are silencers wherever
they sit on a line, a string or a docstring included, since coverage.py
excludes that line all the same. The match is the word `pragma` after a `#`,
with or without the colon and spaces, in either case, then `no` and `cover`
or `branch`, with anything after. `# noqa`, `# type: ignore` and
`# fmt: on|off|skip` stay bare pragmas and exempt: they switch off no gate of
ours. Another tool's pragma,
such as `# pragma: no mutate`, is an ordinary comment line. The gate reads no
coverage configuration, so a project's own `exclude_lines` patterns are not
silencers.

**Silencers have their own baseline,** `silencer-baseline.json` at the repo
root under that fixed name, a count per file that only shrinks. It goes
through the same ratchet as every baseline: `new` and `worse` fail, a lower
count is `PAID` until `--update`, and a file that cannot be read is unmeasured
and keeps its entry. `--update` records every silencer when the file does not
exist yet, and only lowers it after that. A missing silencer baseline stops
the check with exit 2, as a missing `comment-debt.json` does. `--baseline`
moves the comment baseline only. The check reads the silencer baseline before
it judges or writes the comment baseline, so a broken one stops the run with
exit 2 and nothing written. `qg setup` records both baselines when it switches
a comment language on; when `silencer-baseline.json` does not exist yet it
records the silencers of every chosen comment language, not only the new
one, so `comment-debt` passes straight after. The silencer baseline is part of the tolerated
list (GLOSSARY); #192's `tolerated` module counts its growth (ADR-011 addendum
2026-11-25).

**Other languages follow in their own tickets:** TypeScript's `istanbul ignore`,
`c8 ignore` and `v8 ignore` (#236), Swift's `swiftlint:disable` in every form
(#235) and Rust's `#[allow(clippy::cognitive_complexity)]` and
`#[allow(clippy::too_many_lines)]`, which are code and not comments (#237).
Until each lands, its row matches nothing.

### Rejected

- **Keeping the pragma exempt but recording it in `comment-debt.json`.** Debt
  and silencers answer different questions: debt is paid by deleting a
  comment, a silencer by testing the code it hides.
- **Finding silencers only in the comment list.** coverage.py matches the raw
  line, so a pragma in a string or a docstring hides code from `crap` just as
  a comment does.
- **Counting only a bare `# pragma: no cover`.** coverage.py honours the
  pragma with prose after it, so a counted-only-when-bare rule lets a reason
  hide the silencer.

## Addendum 2026-11-26: Swift's `swiftlint:disable` is a silencer (#235)

Amends: [The comment gate in more languages](#the-comment-gate-in-more-languages)

Settled at the 3a ticket cut (#235, plan #232); it is the Swift row the silencers
addendum left to its own ticket, and with Rust's (#237) it closes #204.
`swiftlint:disable` switches off SwiftLint's `cyclomatic_complexity`, the Swift
complexity gate, and until now the comment gate exempted it as a bare tool pragma, so
adding one was how a failing function got to pass.

**Every `swiftlint:disable` is a silencer, and no longer a bare pragma.** The
forms are plain, `:next`, `:this` and `:previous`, with or without rule names and
whatever rule they name: the literal reading. A list of complexity rule names
would have to guess which names SwiftLint ties to complexity, and one miss lets
a failing function pass. The match is the word `swiftlint:disable` in a `//`
line comment, with anything after it. A block comment (`/* … */`) or a doc
comment (`///`, `/** … */`) is not read: SwiftLint 0.65.1 does not honour a
disable there, so it hides nothing and stays an ordinary comment line. A
silencer is not also a comment line, so a disable that carries prose is a
silencer and not comment debt. The reader looks only at comments, so a
`swiftlint:disable` inside a string literal is neither a silencer nor debt.

**`swiftlint:enable` stays a bare tool pragma, exempt,** in its plain, `:next`,
`:this` and `:previous` forms, with or without rule names. It only closes what
a `disable` opened and switches nothing off. Prose after it counts as before.

**The silencers are read only when `no-comments-swift` is chosen,** as the
comment gate reads nothing else of a language. Without it the disable lines go
uncounted.

**The silencer baseline holds the Swift ones** exactly as it holds Python's:
count per file, only shrinking, `--update` recording them when the file does
not exist yet. A consumer who records existing debt with a disable line (the
setup step for Swift) runs `comment-debt`. That step comes after `qg setup` has
written `silencer-baseline.json`, and `--update` records a silencer only when
the file does not exist, so where the default branch holds none the step
deletes the file and runs `--update`; otherwise it runs `--rerecord`, which
records the comment baseline afresh too and needs the builder's
`tolerated-growth` label. `/setup-standards` says so and `/cc-swift` points
there.

## Addendum 2026-11-26: counting tools are pinned exactly (#198)

Amends: [Admitting an outside source](#admitting-an-outside-source), [Rejected](#rejected)

Settled in the build plan (#232, 2026-11-25) and written up in #198. It closes
#173 and #123.

**Before this,** a Python package this package installs carried a minimum
version, with the version CI tested recorded beside it, and the *Rejected* list
turned down exact pins because they "break consumers' installs". The minimum
left the date of the install to choose which lizard counted. lizard 1.25.0 split
TypeScript functions that 1.24.x had merged, so a consumer's baseline failed on
an unchanged tag the day an install resolved the new release (#173).

**Now, a counting tool is pinned to an exact version.** radon 6.0.1 and lizard
1.26.1 are the only two packages this package installs, and both count code, so
`pyproject.toml` asks for `radon==6.0.1` and `lizard==1.26.1`. The admission
record's `minimum_version` and `tested_version` both name that same version, and
a test fails when the requirement is not `==`, or when either field disagrees
with it. The test holds every entry of `dependencies` to this rule, so a package
that counts nothing needs the rule and the test changed first.

**Moving a counting tool is a release.** The change that moves it:

- reads the tool's changelog for counting changes, and runs the full suite
  against the new version;
- records every counting change in ADR-001, and moves the admission record and
  `pyproject.toml` together;
- sets `LAST_SEEN` in `.github/workflows/lizard.yml`, for lizard;
- says in its CHANGELOG entry what a consumer re-keys after bumping the pin.

**radon is pinned at 6.0.1,** the version CI tests today: the workflows run
`pip install -e .`, which took the newest radon the old floor of 6 allowed, and
6.0.1 is the latest on PyPI and the admission record's `tested_version`. Pinning
it changes no score.

**Why the *Rejected* reason no longer holds for these two.** A consumer who
installs quality-gates with `uv tool install` gets its own environment, so the
pins touch nothing else. A project that adds quality-gates to its dev
dependencies can see a resolver conflict if its own requirements need another
radon or lizard; it then moves its own requirement or installs with
`uv tool install`. That cost is smaller than a score that changes with the day
of the install. Every other kind in the pinning table is unchanged.

## Addendum 2026-11-26: TypeScript's `istanbul`, `c8` and `v8 ignore` markers are silencers (#236)

Amends: [The comment gate in more languages](#the-comment-gate-in-more-languages)

Settled at the 3a ticket cut (#236, plan #232); it is the TypeScript row the
silencers addendum left to its own ticket. `/* istanbul ignore next */` and its
`c8` and `v8` forms take lines and branches out of the coverage report, and
`crap --lang typescript` reads that report, so a function over the limit passes
with its untested branches hidden. Until now each marker counted as one comment
line like any comment.

**What the tools honour,** run on 2026-11-26 against real reports, as #235 did
for SwiftLint. Each form was measured by whether the uncovered lines or branches
of the marked code left the Istanbul JSON.

| Tool (versions run) | Reads |
|---|---|
| `istanbul-lib-instrument` 6.0.3 (nyc, babel-plugin-istanbul, Jest's default) | the word `istanbul` only. `//` and `/* */`, where the comment text opens with `istanbul ignore` and `if`, `else`, `next` or `file`, with any whitespace. Not `/** */`. No `start` or `stop`. Whatever follows the hint is ignored |
| `v8-to-istanbul` 9.3.0 under `c8` 12.0.0 (Jest's `v8` provider) | the words `c8` and `v8`, line by line. `/* c8 ignore next [N]` with exactly one space after `/*`, and `start` and `stop`. Not `//`, not `/*c8`, not `/**`. No `if`, `else` or `file` |
| `ast-v8-to-istanbul` 1.0.8 under Vitest 5.1.2's `v8` provider | all three words, each hint (`if`, `else`, `next`, `file`, `start`, `stop`) and each form (`//`, `/* */`, `/** */`), with any whitespace; 54 of 54 combinations hid code or dropped the file |
| `@vitest/istanbul-lib-instrument` 2.1.1 under Vitest 5.1.2's `istanbul` provider | what `istanbul-lib-instrument` reads, and also `istanbul ignore start` or `stop` on any raw source line (it runs with `ignoreLines: true`), with no comment opener |

**The gate cannot tell which tool made the report,** since `crap` reads one
Istanbul JSON whatever wrote it. So the silencer is what any of the three reads,
under one pattern: a `//`, `/* */` or `/** */` comment whose text opens with
`istanbul`, `c8` or `v8`, then `ignore`, then one of `if`, `else`, `next`,
`file`, `start` or `stop` ending at a word boundary, with any whitespace between
the words. Whatever follows the hint, a reason or a count (`next 3`), is part of
the silencer. The three words are lower case, as the tools read them. A marker
that only one tool reads is counted: a marker no tool reads costs the consumer
one baseline entry, and a form that a tool reads and the gate does not count
lets code through.

**A comment that only looks like a marker is not a silencer** and stays an
ordinary comment line: `ignore` with no hint, `ignore nextx`, `ignore-next`,
capitals, a `@preserve` or other word before the marker, `nyc ignore next`, and
`/// istanbul ignore next`, which no tool reads. A marker that comes after other
text in its comment (`// why: c8 ignore next`, `/* why c8 ignore next */`, or a
later line of a block comment that opens with prose) is not read:
`istanbul-lib-instrument` and `v8-to-istanbul` do not honour it there. White
space, a line break included, may sit between the comment opener and the marker
and between its words (`/*\n   istanbul ignore next */`, `/* istanbul\n
ignore next */`): `istanbul-lib-instrument` and Vitest's `v8` provider honour
both, so both are read, and the silencer is reported on the line the marker
word `istanbul`, `c8` or `v8` sits on. The reader looks only at comments, so a
marker inside a string, template literal or regex literal is neither a silencer
nor comment debt.

**A silencer is the one line its marker word sits on, and no more.** In
`/* istanbul ignore next -- the reason\n continues */`, line 1 is the silencer
and the continuation lines stay comment debt; where the marker starts on the
second line, line 2 is the silencer and line 1 stays comment debt, as `#249` item 1 left to this
ticket. The alternative, taking the whole block into the silencer, would let any
length of reason leave the comment count by sitting under a marker, and the
reason is the prose the comment gate exists to count: agents copy a comment
that excuses a shortcut as permission to take it again. Counting the marker line
only keeps the silencer baseline a count of markers and the comment baseline a
count of prose, and the cost to a consumer is that each reason line stays debt
until deleted. It is also what a Python docstring holding a pragma does (the
other lines stay debt), so the two languages agree. A marker with its reason on
one line leaves no comment line.

**Known gaps, left open: a marker outside a comment hides code, and the gate
counts it nowhere.** The reader looks only at comments, as the ticket says, and
the tools read raw source lines, so each of these hides coverage from `crap`
and is neither a silencer nor comment debt (each run on 2026-11-26):

- `v8-to-istanbul` under `c8` matches `/* c8 ignore start */` anywhere on a
  line, a string or template literal included: `const s = '/* c8 ignore start */';`
  hides every line after it up to a `stop` or the end of the file. `/* c8
  ignore next */` in a string hides its own line.
- Vitest's `v8` provider matches `istanbul`, `c8` or `v8` then `ignore start`
  or `stop` on any raw source line, with no comment opener: `const s = 'v8
  ignore start';` hides the code below it to a `stop` or the end of the file.
- Vitest's `istanbul` provider matches `istanbul ignore start` or `stop` on any
  raw source line: `const s = "istanbul ignore start";` hides the code below it
  the same way.
- Vitest's `start` and `stop` are also read on any line of a block comment, where
  the gate reads only the line the marker opens.
- `node:coverage ignore next`, `disable` and `enable`, which Node's runner,
  `v8-to-istanbul` and Vitest read, are a fourth marker word this ticket does not
  name.

Two smaller points. A multi-line `c8 ignore next` hides only its own
continuation line under `c8` (the code below stays in the report) and is
counted all the same. Where a marker stands is not checked: one the tool cannot
attach to a node, such as a trailing `// istanbul ignore next` after a
statement's last token, hides nothing and is counted.

**`eslint-disable`, `@ts-expect-error`, `@ts-ignore` and `prettier-ignore` stay
bare tool pragmas, exempt,** since they switch off no gate of ours.

**The silencers are read only when `no-comments-typescript` is chosen,** as the
comment gate reads nothing else of a language: without it the markers go
uncounted. JavaScript files (`.js`, `.jsx`, `.mjs`, `.cjs`) read the same way.

**The silencer baseline holds them** exactly as it holds Python's and Swift's:
count per file, only shrinking, `--update` recording them when the file does not
exist yet. A consumer's comment debt falls and their silencer count rises by the
same lines, so they record once. Where `silencer-baseline.json` is not there yet
(a bump from before silencers), `comment-debt --update` writes it. Where it is,
`--update` records no new silencer, so the consumer runs `comment-debt
--rerecord` and asks the builder for the `tolerated-growth` label, as Swift's
step does.

**Rejected.**

- **Counting only `istanbul`.** `c8` and `v8` hide the same lines from the same
  report, and a project on Vitest or `c8` has no `istanbul` marker to count.
- **Counting only what every tool reads.** Almost nothing is read by all three,
  so a consumer would pick the form their tool alone reads.
- **The whole block comment as the silencer.** See above.
