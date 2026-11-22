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

Amended by: [Addendum 2026-11-10: a component per comment language, and a choice about existing debt](#addendum-2026-11-10-a-component-per-comment-language-and-a-choice-about-existing-debt)

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
checked; before, only tracked files were.

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
