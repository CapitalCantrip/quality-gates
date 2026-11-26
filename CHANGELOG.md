# Changelog

## Unreleased

**On bumping the pin,** do these in order; each step applies only to a project
that uses what it names, and one pull request can carry them all.

1. Run `qg-skills` and commit `.claude/` (the skills and `.claude/agents/`).
2. Run `qg-agent-docs --tracker <github|gitlab|local>` (or `/setup-standards`),
   and on a GitHub tracker `gh label create escaped`; commit
   `.github/ISSUE_TEMPLATE/` and `docs/agents/.base/escaped.md`.
3. Paste the step from the `setup-standards` skill's `ci-tolerated.md` at the
   end of the steps of the job that runs the gates, in a workflow that runs on
   pull requests, add `types: [opened, synchronize, reopened, labeled,
   unlabeled]` to that workflow's `pull_request` trigger, and commit it.
4. Run `comment-debt --update` once and commit `silencer-baseline.json` and
   `comment-debt.json`: it records every language's silencers at once (Python's
   pragmas; Swift's disable lines, TypeScript's ignore markers, Rust's allow
   attributes and lizard's forgive marker, for each comment row the project
   chose). Where main
   already has `silencer-baseline.json`, `--update` records no new silencer: run
   `comment-debt --rerecord` instead, check that `git diff comment-debt.json`
   shows no count that grew, and ask the builder for the `tolerated-growth`
   label on that pull request (an agent never applies it). Where an entry of an
   earlier release says to delete a baseline and run `--update`, run
   `--rerecord` and ask for the label the same way.
5. For TypeScript, JavaScript and Swift, run `cc-check --lang typescript
   --baseline <file>` and `crap`: a baseline that reports entries as PAID takes
   `--update`; one that reports a function as new or worse takes `--rerecord`,
   and the builder's `tolerated-growth` label. Fix or exclude each file shown
   as `UNMEASURED`.

- **An escape log: an `escaped` label and a four-question issue template
  (#196).** An escape is a problem that got past every gate and was found
  later. `/setup-standards` now creates the `escaped` label, and
  on a GitHub tracker `qg-agent-docs` writes `.github/ISSUE_TEMPLATE/escaped.md`: what happened,
  how it was found, the earliest point it could have been stopped (idea, spec,
  module map, ticket brief, build, review, gate), and which gate should have
  caught it, the fourth question listing the gates in `quality-gates.json` plus
  "none could". `docs/agents/escape-log.md` counts escapes by stage and by gate,
  each with `unanswered`. A template named
  `escaped` that it did not write is kept and reported, with no second one
  written; a path that leads outside the project, or a template it cannot read,
  is reported and left alone; a GitLab or local tracker gets no GitHub issue
  template. `qg-agent-docs` now exits 3 on a malformed `quality-gates.json`.
  If `docs/agents` is a link outside the repo, `qg-agent-docs` now updates none
  of its files nor the PR template; replace the link with a folder to get
  updates. The `standards` skill gains *file an escape*: an agent files one when
  it fixes a problem a merged change introduced, and never applies
  `tolerated-growth` or `loosening`. No score, threshold or scanned file
  changes.
- **radon and lizard are pinned to exact versions, and TypeScript and Swift
  counts move (#198, #123, #173).** The package asks for `radon==6.0.1` and
  `lizard==1.26.1`, so the date of an install no longer chooses the counter; it
  used to ask for `radon>=6` and `lizard>=1.24.2`. lizard 1.25.0 to 1.26.1 split
  TypeScript functions that 1.24.x had merged with their neighbour, count the
  `?` of a ternary between comparisons, and stop counting words in JSX text.
  They also count `guard` and `if` condition-list commas and string
  interpolation in Swift, and report computed properties as functions, so some
  functions appear that no baseline holds, some disappear, and some score higher
  or lower. On a public Swift project, rows above CC 8 went from 73 to 96. This
  is the last time a counter moves without a release saying so. A project that
  adds quality-gates to its dev dependencies and needs another radon or lizard
  now gets a resolver conflict: move its own requirement, or install with
  `uv tool install`.
- **A file the complexity gates cannot read now fails as unmeasured (#212).**
  `cc-check` and `crap` used to pass a Python file that did not parse or was
  not UTF-8 as clean; each now names it as `UNMEASURED` in the ratchet's
  wording and exits 1, with no traceback, and `crap --json` lists it under
  `"unmeasured"`. A baselined function in such a file keeps its entry.
  lizard still scores malformed TypeScript and Swift leniently.
- **Four agents ship (ADR-013):** `implementer`, `reviewer`, `debt-payer` and
  `diagnoser`. `qg-skills` copies them into `.claude/agents/` and
  `qg-skills --check` fails on a stale copy. If the project already has its own
  agent with one of those names, as its filename or the `name:` in its
  frontmatter, `qg-skills` stops, changes nothing and names
  the file: rename or remove it, then rerun. An orchestration prompt that
  names the `builder` agent now names `implementer`. No score, threshold or
  scanned file changes.
- **`qg status` lists each agent under the core** as installed, missing or
  different, and `components.json` gains the part kind `agent`.
- **`/setup-standards` asks you** whether to rename or remove a project agent
  that has a shipped agent's name.
- **`qg-skills` reads `.claude/settings.json` before copying anything.** A
  broken or wrongly shaped one used to stop it after the skills were already
  overwritten; now nothing changes until you fix it.
- **A `qg tolerated` CI step fails a pull request that grows the tolerated
  list without the builder's label** (ADR-011 addenda 2026-11-25 and
  2026-11-26, ADR-009 addendum 2026-11-26). Growth is a baseline entry that is
  new or higher, or a new or wider prefix in `exclude` or
  `settings.no-comments.exclude`; adopting a gate with no baseline on the
  base is not growth. The step prints one line saying what grew; the builder
  applies `tolerated-growth` (or `loosening` on a loosening pull request) to
  say yes, and an agent never applies either. `qg setup` never
  edits a workflow: when no such workflow runs `qg tolerated`, it prints the
  step to paste, and when the step does not pass `QG_PR_LABELS` or the
  trigger lacks those types, it says what to add; `qg setup --json` lists the
  same under `notes`. No score, threshold or scanned file changes.
- **`--update` will not recreate a baseline that main has; `--rerecord`
  records one afresh** (`cc-check`, `crap`, `comment-debt`; ADR-009 addendum
  2026-11-26). Deleting a committed baseline and running `--update` used to
  record every new and worse function; now it exits 2 and says to restore the
  file with `git checkout <branch> -- <file>`, or to run `--rerecord`. A first
  baseline, where the default branch has none, is recorded as before.
  `--rerecord` records measured entries afresh and keeps unmeasured ones; in
  `comment-debt` it records the silencer baseline too. An unreadable baseline
  stops it: delete the file first. Only `comment-debt` keeps the entries of a
  language it did not choose; `cc-check` and `crap` drop the entries of a file
  outside their scan, so a baseline file shared by Python and TypeScript loses
  the other language's entries (#263).
- **Python's `# pragma: no cover` and `# pragma: no branch` are silencers
  (ADR-010 addendum 2026-11-26).** `comment-debt` now reports a marker that
  switches off one of our own gates as its own finding, held in
  `silencer-baseline.json` (a count per file that only shrinks) and no longer
  counted as a comment line. A function over the limit could pass `crap` by
  hiding its untested branches under the pragma; now each pragma fails the
  gate unless it is recorded. The pragma counts wherever it sits on a line, a
  string or docstring included, as coverage.py reads the line. `# noqa`, `# type: ignore` and `# fmt:` are
  neither comment lines nor silencers. Until `silencer-baseline.json` exists
  `comment-debt` exits 2. Your comment-debt count drops by any pragma that
  carried prose. `qg setup` now records `silencer-baseline.json` beside
  `comment-debt.json` when it switches a comment language on.
- **Swift's `// swiftlint:disable` is a silencer (ADR-010 addendum 2026-11-26,
  #235).** `swiftlint:disable` switches off SwiftLint's `cyclomatic_complexity`,
  and the comment gate used to exempt it, so a failing function passed with one
  above it. With `no-comments-swift` chosen, `comment-debt` now reports it at
  its file and line, in every form (plain, `:next`, `:this` and `:previous`,
  with or without rule names, whatever rule it names), held in
  `silencer-baseline.json` and no longer exempt. Only a `//` line comment
  counts: SwiftLint ignores a disable in a block or doc comment, so there it
  stays an ordinary comment line. `swiftlint:enable` in every form stays
  exempt; a `swiftlint:disable` in a string literal is neither a silencer nor
  comment debt. A disable that carried prose used to count as a comment line and
  no longer does. `/cc-swift` and `/setup-standards` now say to record the
  disable lines they tell a consumer to add.
- **TypeScript's `istanbul ignore`, `c8 ignore` and `v8 ignore` comments are
  silencers (ADR-010 addendum 2026-11-26, #236).** They take lines and branches
  out of the coverage report `crap --lang typescript` reads, and the comment
  gate counted each as an ordinary comment line, so a function over the limit
  passed with its untested branches hidden. With `no-comments-typescript`
  chosen, `comment-debt` now reports a `//`, `/* */` or `/** */` comment that
  opens with `istanbul`, `c8` or `v8`, then `ignore` and `if`, `else`, `next`,
  `file`, `start` or `stop` (a reason or a count after it), at its file and
  line, held in `silencer-baseline.json` and no longer a comment line. It counts
  a form any one of the coverage tools reads (nyc and `istanbul-lib-instrument`,
  `c8`, Vitest's `v8` provider), checked against the real tools. A multi-line
  marker is a silencer on the line its marker word sits on, and no other: its
  reason lines stay comment debt. A marker in a string, template or regex
  literal is neither a silencer nor comment debt, though a coverage tool may
  still read it there: `c8` matches `/* c8 ignore start */` anywhere on a line,
  Vitest's `v8` provider matches `istanbul`, `c8` or `v8` then `ignore start`
  or `stop` on any raw source line, and its `istanbul` provider matches
  `istanbul ignore start` or `stop` the same way, so `const s = 'v8 ignore start';`
  hides the code below it and the gate counts it nowhere (a known gap, ADR-010 addendum); `eslint-disable`, `@ts-expect-error`, `@ts-ignore` and
  `prettier-ignore` stay exempt. A TypeScript consumer's comment debt falls and
  its silencer baseline records the markers, by the same lines. `/no-comments`
  and `/setup-standards` now say so.
- **Rust's complexity `allow` attributes are silencers (ADR-010 addendum
  2026-11-26, #237).** `#[allow(clippy::cognitive_complexity)]` and
  `#[allow(clippy::too_many_lines)]` switch off the two lints `cc-rust` denies,
  and nothing counted them, so a failing function passed with one above it. With
  `no-comments-rust` chosen, `comment-debt` now reports each at its file and
  line, held in `silencer-baseline.json`. Outer and inner attributes count, each
  lint alone or in a longer list (`allow(dead_code, clippy::too_many_lines)`),
  inside `cfg_attr` too, and `#[expect(…)]` of either lint counts as `allow`
  does, since clippy stops reporting under it; so does the old name
  `clippy::cyclomatic_complexity`. An `allow` inside another macro's attribute
  (`#[my_macro(allow(…))]`) does not. The attribute is code, so a comment on its
  line still counts as a comment line. An attribute split over several
  lines is found at its first line; one attribute naming both lints is one
  silencer. The attributes are read from the code, so a lint name in a string,
  raw string or comment is not a silencer, nor is `allow` of any other lint or
  `deny` of these two. Under `cc-rust setup`'s deny attributes, clippy also stops
  reporting under `#[allow(clippy::pedantic)]` and `#[allow(clippy::restriction)]`,
  a per-function `#[clippy::cognitive_complexity = "N"]` and a raised threshold in
  `clippy.toml`; `#[warn(clippy::cognitive_complexity)]` (or `too_many_lines`)
  downgrades the deny to a warning, so plain `cargo clippy --all-targets` exits 0
  (checked with clippy 0.1.98). None is counted yet (#255), and a Rust consumer without
  `no-comments-rust` still has its allow attributes uncounted. `/cc-rust` and
  `/setup-standards` now say to record the attributes they tell a consumer to
  add.
- **lizard's `#lizard forgive` comment is a silencer (ADR-010 addendum
  2026-11-26, #244).** lizard drops the next function that ends, so `cc-check
  --lang typescript` and `crap` for TypeScript, JavaScript and Swift never scored
  that function, and `comment-debt` counted the comment as an ordinary comment
  line. With `no-comments-typescript` or `no-comments-swift` chosen,
  `comment-debt` now reports a `//` or `/* */` comment that opens with
  `#lizard forgive` (lower case; white space or a line break may come before it;
  any text may follow) at its file and line, held in `silencer-baseline.json` and
  no longer a comment line. It counts what lizard 1.26.1 honours, checked
  against the real tool: `#lizard forgive global`, `#lizard forgives(metric)`,
  `/** */` and `///` forms drop no function and stay comment lines. The function
  stays unscored, as before: the marker is how it is counted, and `qg
  tolerated` counts growth. TypeScript's `istanbul`, `c8` and `v8 ignore`
  markers and Swift's `swiftlint:disable` count as before, with the forgive
  marker beside them. This replaces the one criterion #212 left open (scoring a
  forgiven function): it is not scored. Two reader limits are filed:
  a `/` after `of`, `await` or a generic's `>` is taken for a regex start, so a
  trailing forgive there is not counted though lizard honours it (#260), and a
  forgive in JSX text, a template literal's `${ }`, after `//` and U+2028, U+2029
  or a lone carriage return, in a Swift extended regex, or above an expression
  lizard abandons is counted though lizard ignores it. lizard stops reading a
  file at any comment containing `GENERATED CODE`, so no function after it is
  scored (#261). A TypeScript, JavaScript or Swift consumer with the comment row
  chosen and a `#lizard forgive` in its code sees its comment debt fall and its
  silencer baseline record the markers, by the same lines. `/no-comments`,
  `/setup-standards`, `/cc-swift` and `/cc-typescript` now say so.

## 0.14.2 — 2026-11-26

- **Three more principles in `standards` (ADR-002 addendum 2026-11-26):**
  *fix root causes*, *guard the context window* and *sequence verifiable
  units*, adapted from Lauren Tan's pstack. No score, threshold or scanned
  file changes. On bumping the pin, run `qg-skills`.

## 0.14.1 — 2026-11-25

Six more of Matt Pocock's skills ship. No score, threshold or scanned file
changes. On bumping the pin, run `qg-skills`.

- **`grilling`, `research` and `prototype` ship (ADR-003 addendum
  2026-11-25).** `grill-with-docs`, `wayfinder`, `triage` and
  `improve-codebase-architecture` call them by name; without the copies those
  calls failed in cloud sessions and wherever Pocock's plugin was not
  installed. On bumping the pin, run `qg-skills`. A project that kept his
  plugin only for these three can turn it off.
- **`grill-me`, `wait-what` and `wizard` ship.** The first two run only when
  you type them, so they add nothing to a session's context. `wizard` writes a
  script that walks you through steps only a person can do. With these, a
  project that used his plugin for the skills quality-gates did not copy can
  check whether it still needs it.

## 0.14.0 — 2026-11-24

The comment gate reads Rust fully and now TypeScript, Swift and shell, and
setup shows each language's debt before offering to record it or clean it
first (#185 to #189, #210, #213 to #215). On bumping the pin, run
`qg-skills`, then `/setup-standards`: it moves any `--exclude` patterns from
the pre-commit hook into the choice file (`comment-debt` now refuses
`--exclude`) and offers the comment languages your project uses. The gate
now also checks untracked files, and one it cannot read fails as
`UNMEASURED`. Commit the smaller baseline if `--update` drops zero entries.

- **Clean first is built (#189).** A comment language can now be accepted by
  paying down a scope you pick before the rest is recorded as debt; the
  `no-comments` skill's *Clean first* section has the steps, and an issue for
  what is left opens only if you ask. `comment-debt --report <language>` ends
  with every file that has comment lines, so that issue names them all.
  `/setup-standards` asks whether to switch on `rust-safety` when Rust code
  has `// SAFETY:` lines, and if you say yes it writes `quality-gates.json`,
  adds the convention, then chooses Rust. `qg explain no-comments` explains
  the gate. On bumping the pin, run `qg-skills`, then `/setup-standards` and
  accept the comment languages you want. As the #185 entry says,
  `comment-debt --exclude` is gone.
- **`comment-debt --report` counts what `qg setup` counts.** It now leaves out
  what a hook or CI `--exclude` flag leaves out, as setup's report and
  choosing already did. Nothing to do on bumping the pin.
- **No write keeps a zero baseline entry.** The first `--update` with no
  baseline file no longer writes `0` for a file both counted zero and
  unmeasured, and the next `--update`, or `qg setup --go` switching a comment
  language on, removes any stored entry of `0`, including one for a language
  not chosen. A zero entry allowed nothing, so the gate's verdicts do not
  change; commit the smaller baseline.
- **`comment-debt --status` lists an area's files with the most comment lines
  first** among those with equal rationale lines, then by path, so "pick the
  top file" picks the biggest, and lists areas with equal totals by name.
  Nothing to do on bumping the pin.
- **`qg status` with no choice file lists `no-comments`' missing parts under
  "Needs attention".** With no choice file the comment gate checks Python, so
  a missing hook, CI step or baseline is a real gap. The exit code is
  unchanged. Nothing to do on bumping the pin.
- **`comment-debt` reads TypeScript, Swift and shell (#187).** Three new
  components, `no-comments-typescript`, `no-comments-swift` and
  `no-comments-shell`, are offered by the next `/setup-standards` run to a
  project with that language. Each is off until chosen; choosing it with
  `qg setup --go --choose <id>` records that language's comments as debt, so
  only new ones fail. A comment marker inside a string, template literal,
  regex literal, interpolation or heredoc does not count; bare tool pragmas
  (`eslint-disable`, `eslint-enable`, `@ts-expect-error`, `@ts-ignore`,
  `prettier-ignore`, `swiftlint:disable`, `swiftlint:enable`,
  `# shellcheck disable=`) and a shell shebang on line 1 are exempt, and
  `/// <reference … />` counts as a doc comment. Shell covers `.sh`, `.bash`
  and `.zsh` files and files with no suffix whose first line is a shell
  shebang. Nothing to do on the bump unless you choose one; run
  `comment-debt --report <language>` first to see what choosing it records.
  A project that chooses one of them without `no-comments` reruns
  `/setup-standards`, which adds `comment-debt` to the pre-commit hook and CI
  when either lacks it.
  A file whose whole name is a suffix, such as `scripts/.sh` or `pkg/.py`,
  now counts as that language when `qg setup` and `qg status` find the
  languages a project uses, and in the comment gate for every language, as
  it already did there for Python.
- **`comment-debt` reads Rust fully (#186).** With `no-comments-rust`
  chosen, every Rust comment counts once per line: block comments and doc
  comments (`///`, `//!`, `/** */`) as well as `//` lines. A `//` inside a
  string, raw string or char literal no longer counts, and a bare
  `// @generated` is exempt. `rust-safety` in
  `settings.no-comments.conventions` now takes effect: `// SAFETY:` and the
  `//` lines after it, directly above an `unsafe` block or `unsafe impl`, do
  not count. A Rust project with `// SAFETY:` comments adds `rust-safety` to
  the choice file before it chooses `no-comments-rust`, so those comments are
  not recorded as debt.
- **`comment-debt` reads its exclusions from the choice file (#185, #210).**
  It now checks untracked files as well as tracked ones, reads
  `settings.no-comments.exclude` from `quality-gates.json`, and refuses
  `--exclude`. A project whose pre-commit hook passes `--exclude` must run
  `/setup-standards` on the bump, which moves the patterns into the choice
  file.
- **An untracked file the comment gate cannot read fails as `UNMEASURED`
  (#210).** Make the file readable, or list it in
  `settings.no-comments.exclude`.
- **`/implement-spec` re-checks its review fixes before it marks the PR
  ready.** A new step 8 runs `/code-review high` over only the fix commits,
  checking that every finding from both reviews is resolved and that the
  fixes brought in nothing new. It repeats until a re-check is clean; after
  three that are not, it asks the builder and leaves the PR in draft. When a
  re-check finds a regression the fixes themselves brought in, it reverts
  that fix round and files an issue for the finding instead of fixing
  forward. Nothing to do beyond the pin bump and `qg-skills`.
- **`qg setup` shows a comment language's debt before it asks (#188).**
  For each comment language it offers, setup prints that language's report:
  the total, the count by kind and by area, and the five files with the most
  comment lines and the most rationale lines (workaround, deliberately, for
  now, TODO ...), and the areas with the most rationale lines. The report
  counts the files choosing would record. It comes with the two ways to
  accept: record as debt, or clean first by paying comments down with the
  `no-comments` skill and then choosing. Python docstrings and bare strings
  count as kind `string`. `comment-debt --report <language>` prints the same
  report, and
  `qg setup --json` carries it under `debt_reports`. Nothing to do beyond the
  pin bump and `qg-skills`.
- **The report and `--status` name the files they could not read (#214).**
  `comment-debt --report` and `comment-debt --status` add one line, for
  example `# 1 file could not be read: scratch.py`, so the builder sees a
  file before choosing that the gate would fail as `UNMEASURED`. Their totals
  are unchanged. Rationale lines are now found on the right line in a file
  with a form feed or a Unicode line separator. Nothing to do on bumping the
  pin.
- **`qg status` no longer calls a comment language installed that was never
  chosen (#213).** The hook, CI step and baseline that `no-comments-rust`
  shares with `no-comments` used to show it as installed or partly installed
  with no choice file. Status now shows it as missing until the choice file
  chooses it, the same rule setup uses. Nothing to do on bumping the pin.
- **`/implement-spec` also runs Claude Code's `/code-review high` before it
  hands back.** Step 7 now runs `review-against-spec` and then the built-in
  correctness review, and one implementer fixes the findings of both. A sprint
  takes longer, and the builder starts fewer review rounds after it. Nothing
  to do beyond the pin bump and `qg-skills`.
- **Decisions are a compendium over an archive (ADR-012).** The numbered ADRs
  moved to `docs/adr/archive/`; `docs/adr/` now holds one page per question,
  which is where the current rules live. Every generated reference file's
  second line now names its compendium page instead of an ADR. Nothing to do
  beyond the pin bump.
- **A broken baseline no longer crashes a gate (#174).** A baseline that is
  not valid JSON, is not an object, holds a value that is not a number, or
  cannot be reached, read or written now makes `comment-debt`, `cc-check` and
  `crap` exit 2 with one line naming the file, instead of a traceback or, for
  a `null` or `NaN` value, a wrong verdict. `comment-debt` no longer crashes when the
  terminal's encoding is plain ASCII. Nothing to do on bumping the pin.

## 0.13.0 — 2026-11-04

The choice file, explainers and admission records (#137, #139, #114). The gates
now score only the files git would commit, each once, and stop outside a git
repo (#87, #120). Baselines may show `PAID` after the bump; the steps below say
what to do.

- **Admission records (#114, ADR-010).** `components.json` is now
  `format_version` 2. A new top-level `admissions` list records each outside
  source once: radon, lizard, `mattpocock/skills`, `cursor/plugins`, and the
  test-only ruff, ESLint and SwiftLint. Each has a name, a kind (`upstream`,
  `dependency` or `test-only`), a licence, one sentence on the author's
  practice, and either a last release date or a `stable` reason; radon and
  lizard also keep the minimum version and the version CI tested. Loading
  fails, on every run, when a record lacks a field, when an upstream is not
  MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause or ISC, when a dependency's
  licence is not OSI-approved, when an `origin` or `adapts` entry names a
  source with no admission, or when a source in `upstream.json` has none.
- **Quiet sources are flagged (#114).** `qg-upstream --upkeep` reports any
  source whose recorded `last_release` is over 12 months old and that is not
  marked stable, and the monthly `upstream` workflow opens or updates one issue
  for them. It reads the recorded date and never asks the source, so renewing
  means looking up the real newest release and updating `last_release`.
- **If you read `components.json`:** accept `format_version` 2 and read
  `admissions` and each component's optional `explainer` (README § The component
  manifest). A dependency part's `origin` no longer carries `version`: take it
  from its admission's `minimum_version`, as `>=` that version. Read through
  quality-gates, the origin still has `version`, so `qg status` prints the same
  origins.
- **If you read `qg status --json`:** `format_version` is 2; the report adds
  `languages`, `languages_from` and `unrecorded_languages`; a component's
  `status` may now be `offered, declined` or `not yet offered` (below); and
  each component adds `install_status`, what is installed whatever the choice,
  and `needs_attention`, the part lines the table prints.
- **`qg explain <name>` prints a component's explainer (#139, ADR-007).**
  `qg explain crap` prints the plain-words page for the `crap` gate from the
  installed package, offline (README § Explainers). A component names its
  explainer in `components.json`. Exit 0 when it printed one; 1 for a name that
  is not a component, or a component with no explainer yet; 2 for a usage error;
  3 when the manifest or the explainer cannot be read. Nothing to do beyond the
  pin bump steps below.
- **The choice file (#137, ADR-007, ADR-010).** A committed
  `quality-gates.json` at the project root records the languages, the chosen
  and declined components, the excluded paths, the commit time limit
  (2 seconds) and the comment gate's `exclude` and `conventions`
  (README § The choice file). The new `qg setup` proposes them in one table
  (component, description, cost) and writes the file on `--go`, and nothing
  else. It refuses to switch off the core or a gate the project has, or to
  remove a language that still has code, until recorded reasons ship (#115).
  Without a choice file, `--go` records what is installed as chosen; a gate
  whose only part present is the skill `qg-skills` copied does not count as
  installed, so it is offered and can be declined freely. Every
  other component that applies and that the file does not list is offered,
  whatever is installed, such as one whose skill `qg-skills` copied: an offer
  is recorded only when `--choose` or `--decline` names it, and setup names
  the offers not yet answered. With nothing to record and no offer open, it
  says the file is up to date. A recorded choice or decline is kept
  while its component does not apply. One id given to both `--choose` and
  `--decline` exits 3.
  It copies `--exclude` prefixes from the `comment-debt` commands of the hook
  and CI into the file and leaves the flags; a command chained to it with
  `&&`, `||`, `|` or `;` keeps its own flags, and a `\` continuation line
  counts. A language name it does not know,
  given to `--add-language` or `--remove-language` or written in the file,
  exits 3 with one line listing the names it knows. Test folders count toward
  the proposed languages; fixture folders do not (ADR-007 addendum
  2026-11-01).
- **`qg status` reads the choice file.** Languages come from the file, with a
  warning naming the files in any language it does not record; without the
  file, from detection. A component the file declines shows *offered,
  declined*, and one it does not list shows *not yet offered*; either has
  what is installed beside it when anything is, such as *offered, declined
  (partly installed)*. *Needs attention* shows for the core, a chosen component or one with
  some part installed, never for a declined or offered one with nothing
  installed. `--json` adds `languages`, `languages_from` and
  `unrecorded_languages`, and each component's `install_status` and
  `needs_attention`. A malformed choice file exits 3.
- **Shell and Rust are detected from files** (#137, ADR-010): `.sh`, `.bash`,
  `.zsh` and a shell first line such as `#!/bin/sh`, and `.rs`. Detection
  leaves out the skills, hooks and pre-commit hook quality-gates keeps.
- **The gates look at the files git would commit (#87, #120, ADR-011,
  ADR-001 addendum 2026-11-01).** Tracked files plus untracked files the
  `.gitignore` does not ignore; the skip list is gone. Each file is scored
  once, even when named twice or reached through a link. Fixture folders
  (`fixtures`, `fixture`, `__fixtures__`, `testdata`, in any case) are excluded by default,
  and setup writes that default into the choice file. Outside a git repo every
  command that looks for the project's root exits 2 with one line saying so,
  instead of using the current folder: the gates, `comment-debt`, `qg status`,
  `qg setup`, `qg-agent-docs` without `--root`, and `qg-skills` without
  `--dest`, which now writes `.claude/skills` at the top of the git repo even
  when run from a subfolder. `qg explain`, `qg-upstream` and `qg-references`
  read no project and run anywhere. A malformed `quality-gates.json` stops the
  gates with exit 2 and one line naming the problem. The gates take the repo
  from the first path given, so scanning another repo's folder follows that
  repo's `.gitignore` and `quality-gates.json`, and `--baseline` keys are
  written relative to that repo too. Outside the repo, through a link or a
  scanned path in no repo, `node_modules`, `.venv`, `build`, `.git` and the
  other dependency and build folders are still never walked. A path named on the command
  line that git ignores is not scored, and the gate names it in one line on
  stderr; `--json` output stays valid and exit codes are unchanged. On a
  case-insensitive filesystem, as on macOS, a path typed in another case, such
  as `SRC` for `src`, is scanned under the spelling on disk. A git submodule
  is scanned from inside it, by its own git: a scan from the superproject
  scores none of its files and names it on the *Skipped* line, marked
  `(a submodule: scan it from inside)`. Before this release its files were
  scored with the superproject's.
- **`exclude` entries match whole path segments.** `build` leaves out the
  folder or file `build`, never `buildscripts/` or `build_utils.py`; a
  trailing `/` changes nothing. Each entry is a path from the repo root: one
  starting with `/`, `./` or `../`, or with an empty, `.` or `..` segment,
  makes `quality-gates.json` malformed (exit 2 from the gates, 3 from
  `qg setup`). Root marker files such as `package.json` go
  through the same scope, so an excluded or git-ignored one adds no language.
  `comment-debt --exclude` keeps matching plain prefixes.
- **The `qg` entry point moved** from `quality_gates.status:main` to
  `quality_gates.qg:main` (sprint 1, ADR-011).
- **Manifests are validated on load** (sprint 1, ADR-011): a malformed
  `components.json` or `upstream.json` stops `qg status` and `qg-upstream`
  with one plain line and a non-zero exit, never a traceback.
- **When you bump the pin:**
  1. Reinstall the commands with `uv tool install --force` and the new install
     line, so `qg` points at its new entry point.
  2. Run `/setup-standards`. Its new step shows the table; say "go" and it
     writes `quality-gates.json` from what is installed. Commit it. From
     this release on, a component a release adds stays off after the bump,
     even when `qg-skills` copied its skill: `/setup-standards` offers it,
     and "go" or a decline records your answer.
  3. Run the gates. A file that was scored twice or a fixture folder that was
     scanned now shows `PAID`: lower the baseline with `--update` and commit
     it. A build or vendored folder that git would commit is now scored: add
     it to `.gitignore` or to `exclude` in `quality-gates.json`.
  4. Run the gates inside the git repo; outside one they stop with exit 2.

## 0.12.0 — 2026-10-25

No threshold or scanned file changes. `crap` now grades a function with no
coverage figure `UNMEASURED` instead of scoring it worst case, and the install
ships coverage (#104, #118, #75, #76, #77, #78, #81, #85, #105; ADR-005 addendum
2026-10-25, ADR-001 addendum 2026-10-25).

- **`UNMEASURED` grade (#81, #105).** A function the coverage report holds no
  usable figure for (a file the report never saw, a null xccov figure, a
  SwiftPM function sharing a line with another's opening) gets no CRAP score:
  `—` in the table, `"crap": null` and `"grade": "UNMEASURED"` in `--json`. It
  fails the gate (exit 1). The table lists it after the FAIL rows and `--top`
  never hides it; the summary adds "N unmeasured in F file(s): …"; `--json`
  adds a top-level `"unmeasured"` file list and sets `"pass"` to false.
  `--no-coverage` and `cc-check` are unchanged.
- **The baseline never records or loses an unmeasured function.** `--update`
  lowers and removes measured entries as before, adds none for an unmeasured
  function and keeps an existing entry as it is, writes the file, then exits 1
  listing `UNMEASURED` keys. A check run does not report a baselined unmeasured
  function as `PAID`. A report made in another checkout can no longer put every
  function into the baseline as accepted debt.
- **A coverage report of the wrong shape exits 2** in the coverage.py,
  Istanbul and xccov readers, as llvm-cov already did, naming the reader's
  input, never a traceback (#75).
- **xccov output is read as UTF-8 whatever the locale,** and output that is not
  UTF-8 exits 2 (#76). A report key that cannot be resolved (a NUL byte, a
  symlink loop, a path the locale cannot encode) exits 2 (#85, tests only).
- **`crap` and `cc-check` write UTF-8 whatever the locale,** so the table
  prints under `LC_ALL=C` (#78).
- **An empty or whitespace-only `--baseline` exits 2 naming the flag** in
  `crap`, `cc-check` and `comment-debt` (#77).
- **New extra: `quality-gates[coverage]`.** The install line adds it and
  `--with-executables-from coverage`, so `coverage` is on PATH beside the gates.
  README § Setup details says when to install coverage in the project's own
  environment instead, how to measure child processes
  (`[tool.coverage.run] patch = ["subprocess"]`) and why to clear data with
  `coverage erase`.

- **New contract: `components.json`.** The package ships a component manifest,
  `format_version` 1: every component, its parts (down to each gate's settings
  file, CI step and pre-commit step), a one-line description, its languages and
  its origin (ours, an upstream or a dependency). A tool that
  reads it should check `format_version`; a change of shape raises it and gets
  a note here. README § The component manifest documents the fields. Tests
  keep it in step with the shipped skills, `upstream.json` and the README's
  *From* column.
- **New command: `qg status`.** Run in a project, it prints each component as
  installed, missing, different, partly installed, unknown or not applicable,
  with what it does and where it came from, and the project's pin beside the
  installed version (or *pin not found*). `qg status --json` gives the same
  report for agents. It only reads, works offline and always exits 0;
  `qg-skills --check` stays the gate.

**When you bump the pin:**

1. Reinstall with the new line:
   `uv tool install --with-executables-from coverage "quality-gates[coverage] @ git+https://github.com/CapitalCantrip/quality-gates@v0.12.0"`.
   A project that pins `quality-gates` in its dev dependencies needs no extra;
   its own `coverage` stays.
2. Run `qg-skills`.
3. Run the CRAP gate. A function that used to score worst case for want of a
   figure now shows `UNMEASURED` and fails, even if the baseline holds it. Fix
   the measuring (run the tests and `crap` in the same checkout, coverage in
   the tests' environment) or take the file out of the scan. A Swift function
   under `#if os(macOS)` or `canImport(UIKit)` has no figure on Linux, so a
   Linux CRAP job now fails on it: run that job on macOS, or leave the file out
   of the Linux scan. Do not re-record
   the baseline for this: its entries stay while the function is unmeasured and
   are lowered or removed once it is measured.
4. A tool that reads `crap --json` must accept `"crap": null`, the
   `UNMEASURED` grade and the new `"unmeasured"` list.

`qg status` is there when you want to see what the project has.

## 0.11.1 — 2026-10-22

No score, threshold or scanned file changes.

- The install line lives only in `/setup-standards`. `/crap`, `/cc-python`,
  `/cc-swift`, `/cc-typescript` and `/no-comments` point to it instead of each
  carrying a pinned copy, and a test checks that every pin in the shipped
  skills matches the package version.
- `/crap` no longer has a Rust section. It told agents to run `crap --lang
  rust`, which `crap` has never accepted; Rust has no CRAP score, and `/crap`
  now says to use `/cc-rust`. `/cc-rust` has one threshold table (cognitive
  complexity over 10 fails, a function over 25 lines fails), dropping a second
  table whose warning band the deny attributes never allowed.

**When you bump the pin:** run `qg-skills`. In a Rust project, use `/cc-rust`
where you used `/crap`. Nothing else.

## 0.11.0 — 2026-10-22

lizard 1.24.2 is the new floor, and it changes some scores (#108; ADR-001
addendum "lizard 1.24.2 is the floor and the Swift workaround is gone
(v0.11.0)"). Fresh installs of earlier versions already pick up 1.24.2, so
this release makes every install count the same way.

- **Swift:** lizard 1.24.2 fixes terryyin/lizard#516, so the Swift workaround
  is deleted and Swift scans run plain `lizard` (closes #71 and #89). 1.24.2
  also gets right what the workaround missed: a `.init(set)`, `self.init(set)`,
  `super.init(set)` or `Foo.init(set)` call, or a bare `set` word such as
  `max(set, 1)`, no longer swallows the function after it into an `init` or
  `set` row. Macros such as `#Preview`, raw and multi-line strings and nested
  block comments are read correctly too.
- **TypeScript and JavaScript:** `??` and `??=` now count one path each, not
  two (the known miscount is gone). Each default parameter, and each default
  in a destructuring pattern, now counts one path: `function f(a = 1, b = 2)`
  is CC 3. An unnamed function in an array literal is named `(anonymous)`, not
  after the variable that holds the array.
- **Python:** unchanged; radon counts it.
- The `lizard` workflow now watches for any lizard release after 1.24.2 and
  asks for its score changes to be checked, since #516 is fixed.
- The `/cc-swift` and `/crap` skills link a new reference, *how lizard reads
  Swift*, in place of the workaround's. `/cc-typescript` drops the
  known-miscount reference.
- The stage guard's refusal now lists the changed files the blocked command
  would have staged: only those under the folders it named, or every changed
  file for a whole-tree add or `commit -a`, cut at 30 with a count of the rest.
  It reads the repo the command would have run in, following an earlier `cd`
  in the same command and `git -C`.
  Agents in a consuming project retried the same folder-wide add in five
  sessions; with the list in front of them, the next attempt names files.

**When you bump the pin:** reinstall quality-gates so lizard 1.24.2 or newer
is installed, then run `qg-skills`, which also copies the new
`.claude/hooks/stage_guard.py`. Rerun the Swift and TypeScript gates and
re-record their baselines (`--update`). Expect TypeScript scores to go down
where `??` is used and up where default values are used; a function that now
fails the gate needs a split or a baseline entry. A Swift baseline may gain
rows for functions that were swallowed before, and lose `init` or `set` rows
that held them. Python baselines do not change.

## 0.10.1 — 2026-10-12

No score, threshold or scanned file changes.

- A `lizard` workflow checks PyPI every Monday and opens an issue when a lizard
  release newer than 1.24.1 appears, so the wait on terryyin/lizard#516 (#71,
  #89) no longer depends on someone remembering at release time.
- `/setup-standards` now reports CRAP as not done for a project in any language
  with no tests, with the reason and what it takes, instead of getting stuck at
  the CRAP step (#94; ADR-002 addendum "a project with no tests (v0.10.1)").
- The GLOSSARY and `/cc-swift` say that a Swift closure no function holds (file
  scope, a stored property, a `lazy var`) is not scored at all (#95; ADR-001
  addendum "a closure outside any function is not scored (v0.10.1)").
- The README prose had a light pass for readability. No rule, number, command or
  link changed.

**When you bump the pin:** run `qg-skills`. The skills' install lines now name
`v0.10.1`, and `/setup-standards` and `/cc-swift` have new text. Nothing else.

## 0.10.0 — 2026-10-12

The rules the skills cite now ship inside the skills, as generated reference
files (#62; ADR-004), and the README links them instead of restating them
(#63). No threshold, counting tool or gate coverage changes.

- Each gate skill and the `standards` skill has a `references/` folder holding
  the rules it cites: the complexity ceiling, the skip list, symlinked folders,
  baseline keys, the baseline ratchet, how Functions are named, repeated names,
  TypeScript counting, TypeScript's known miscount, functions that share a
  start line, the lizard Swift
  workaround, the three layers, the principles from use, the promotion path,
  the asking rule and the vendored skills. A skill no longer points at an ADR
  file a consumer does not have.
- The ADRs keep their history as accepted. Each cited rule is restated in full
  in a dated section at the end of its ADR, and every addendum links the text it
  amends, and back.
- `qg-references` (this repo only) writes the reference files from those
  sections, and `qg-references --check` fails on drift, on tagged text that
  points outside its file, and on an amendment that does not link both ways.

**When you bump the pin:** run `qg-skills` and commit the new `references/`
folders under `.claude/skills/`. Until you do, `qg-skills --check` fails, so
CI catches a project that bumped without rerunning it. Nothing else changes.

## 0.9.1 — 2026-10-12

The Swift scan's `(set)` workaround no longer depends on the word before `(set)`
(#89; ADR-001 addendum "the `(set)` rule no longer depends on the word before
it, except `init` (v0.9.1)"). No threshold changes.

- `package(set)`, a comment between a modifier and `(set)`
  (`private /* why */ (set)`), and a line break inside the parens
  (`private(\n set)`) no longer create a Function named `set` that takes the
  next declaration's body. That declaration, such as `init() {}`, is scored
  under its own name.
- A local or parameter named `set` passed to a call, `foo(set)`, no longer
  opens a `set` Function that takes `{...}` and moves the enclosing function's
  `if`s into it; the function is scored whole, as lizard master does.
- Line numbers after a wrapped `private(\n set)` are unchanged: only the three
  tokens `(`, `set`, `)` are dropped, and the newlines stay. Function names,
  start and end lines and CCN match lizard master 9a63062 on these cases.
- `.init(set)`, `self.init(set)` and `super.init(set)` keep their tokens, as
  before, and match lizard master.
- Not covered: a bare `set` word that is not inside `(set)`, such as a local,
  parameter or property named `set` in `max(set, 1)` or `set.count`, or a label
  `g(set: 1)`; it still makes a `set` Function that takes the enclosing
  function's CC. It waits for #71. Also `.init(set)`, `self.init(set)`,
  `super.init(set)` and `Foo.init(set)` in a function body, where the next
  function scores as part of an `init` row; lizard master does the same.

**When you bump the pin:** run `qg-skills`. These Swift projects see rows move
in `crap --lang swift`: one that wrote `package(set)`, one that put a comment or
line break before or inside `(set)`, and one that passes a local or parameter
named `set` to a call (`foo(set)`, or `foo(\n set\n)`). A `set` row goes away
and the code after it is scored under its own name, as lizard master does. If
your crap baseline holds such a `set` entry, or fails after the bump, delete
`crap-baseline.json` and re-record it with `crap --lang swift <source dirs>
<coverage flag> --baseline crap-baseline.json --update`. Explain or fix every
row that shows `?` in the coverage column before you commit it. Python and
TypeScript scores are unchanged.

## 0.9.0 — 2026-10-12

What the scan covers (#54, #58, #51, #59; ADR-001 addenda "skip SwiftPM's
.build (v0.9.0)", "follow symlinked folders (v0.9.0)", "the freshness check
reads the scan's files (v0.9.0)", "Python end lines from the AST (v0.9.0)" and
"baseline keys use the real path (v0.9.0)"). No threshold changes.

- `.build`, SwiftPM's build folder, joins the skip list of both gates in every
  language and is named on the *Skipped N folder(s)* line (#54). A scan of a
  package root no longer returns functions from `.build/debug` or from
  checked-out dependencies under `.build/checkouts`.
- The shared walk follows symlinked folders (#58). A function in
  `Sources/Shop -> ../shared/Shop` is now scanned by both gates; before, the
  linked folder was left out without a word. The same real folder is walked once
  per scan: a link to an ancestor (a loop), a second link to one folder, and a
  folder reached from two scanned paths each give their repeat a place on the
  *Skipped* line, marked `(already scanned)` because its files were scanned once
  and are not lost. Two links that spell one folder in different case on a
  case-insensitive volume count as one folder, since folders are told apart by
  device and inode, not by path text. File names in the report keep the link path
  as scanned, but a baseline key is the file's real path, as before 0.9.0: a file behind `src/Shop -> ../shared/Shop` is keyed
  `shared/Shop/shop.py::f`, and one file gets one key whatever spelling or
  argument order reached it (`crap src/app src` and `crap src` agree). A link to
  a folder outside the repo gives a `../` key that depends on where that folder
  sits relative to the repo on each machine (ADR-001's addendum "baseline keys
  use the real path"). A link named on the
  skip list is still skipped, a dangling link is ignored. The skip list checks a
  link's own name, not its target, so a link into `node_modules` or `.build`, or
  to a parent folder, widens the scan: name it on the skip list or remove it.
  Scanned folders that overlap (`src src/pkg`) now list the inner folder's
  functions once, where they were listed twice, the second numbered `#2`. Only
  folders are deduplicated, not files named twice.
- `crap`'s coverage freshness check reads the files the scan reads (#51). A
  newer file under a skipped folder (`node_modules`, `.git`, `.venv`, build
  output) or of another language no longer makes the report stale, with or
  without `--strict-freshness`; a newer source file of the chosen language still
  does. The check uses the scan's own file list, so a symlinked folder counts. It
  runs after the walk and before the count, so a missing path is reported first
  and a stale report under `--strict-freshness` exits 2 without paying for the
  counting run. No score changes.
- A Python function's end line comes from the AST (#59). A function ending in a
  nested `def`, a method ending in a nested `class`, or a closure ending in a
  nested `def` is now measured over its whole body; before, the range stopped
  before the nested definition and `crap` read coverage from the `def` line
  alone, which always runs. Python `crap` scores can rise for these functions
  and a new failure can appear. Start lines, CC and `cc-check` are unchanged.
- On a case-insensitive macOS volume, the real path takes the case stored on
  disk. `pa/x -> ../shared/Shop` and `pb/x -> ../shared/shop` now key one file
  one way whatever the argument order, and the coverage.json and Istanbul readers
  find its figures through either link, as the llvm-cov and xccov readers
  already did. Elsewhere the real path is the resolved path.
- Internal: `complexity_scan.find_sources` walks and `count_functions` counts; `scan` does
  both, and `Scan.sources` is gone. Folders in the walk are compared by device and
  inode.

**When you bump the pin:** run `qg-skills`. Re-record the baselines whose scan
changed, once: delete the baseline file, then run the gate with `--update`.

- `cc-check` baseline (`cc-check <dirs> --baseline cc-baseline.json --update`),
  for Python and TypeScript, if you scan a SwiftPM package root, a folder that
  contains a symlinked source folder, or overlapping folders (`src src/pkg`):
  functions under `.build` drop out, functions behind a link come in under their
  real path, and an inner folder's functions are listed once, where they were
  listed twice with the second numbered `#2`. Swift is not a `cc-check`
  language, so a SwiftPM-only project has no `cc-check` baseline to re-record.
- `crap` baseline (`crap --lang <lang> <dirs> <coverage flag> --baseline
  crap-baseline.json --update`), for every language, under the same conditions
  (a SwiftPM package root, a symlinked source folder, or overlapping folders).
  A Python project also re-records it when a function ends in a nested `def` or
  `class`: its CRAP score can rise.
- A project with none of these has nothing to re-record.

Before you commit a re-recorded baseline, explain or fix every row that shows `?`
in the coverage column: each is a worst-case score the baseline will exempt
(#81); a function that now comes in through a symlinked folder shows `?` when
the coverage report has no figure for it. If you stopped passing
`--strict-freshness` because a newer file under `node_modules`, `.venv` or build
output raised a false stale warning, you can pass it again.

A baseline recorded before 0.9.0 holds real-path keys for ordinary files, and
0.9.0 keys them the same way, with one exception. On macOS, if you ran a gate
with a path typed in a different case from the one on disk (`crap SRC` for a
folder named `src`), 0.9.0 gives true-case keys, so that baseline shows every
function as new: delete it and record it once more with `--update`. A symlinked
source folder whose target lies outside the repo gives `../` keys, so record
that baseline on a checkout laid out as CI's is.

## 0.8.4 — 2026-10-11

Skills and docs only: no score, threshold or scanned file changes (#67, #70).

`/setup-standards` now finishes for a SwiftPM package with no test target.
Before, its CRAP steps assumed `swift test --enable-code-coverage` succeeds, so
such a package had no way through. Now it sets up no CRAP baseline or CI step
for it and reports CRAP as **not done**, with the reason (no test target, so no
coverage) and what it takes (add a test target with tests, then rerun the
skill). A project on `node --test`, which the skill already told to report CRAP
as not done, can now finish setup too. ADR-002 addendum "a SwiftPM package with
no test target (v0.8.4)".

`cc-swift` has a review rule: a new or changed Swift closure (including a
trailing closure or a nested `func`) that contains a branch has a test that
runs it. It is a judgement call in review, not a gate. A closure needs it
because the CRAP gate does not count a closure's lines against the function
that holds it (#53). A nested `func` is scored on its own, but a small one can
pass the gate untested. ADR-001 addendum "a review rule covers the closure gap
(v0.8.4)".

**When you bump the pin:** run `qg-skills`. A SwiftPM package with no test
target removes the CRAP CI step that 0.8.0 told it to add, because
`swift test --enable-code-coverage` finds no tests there, and reports CRAP as
not done. A SwiftPM package with tests and an Xcode project see no difference.

## 0.8.3 — 2026-10-11

The Swift scan works around two lizard Swift bugs (#69; ADR-001 addendum "a
workaround for two lizard Swift bugs (v0.8.3)"). No threshold changes.

- A failable initialiser, `init?(...)` or `init!(...)`, is now scored as a
  Function named `init` with its own CC and lines. lizard 1.24.1 did not report
  it, so it was never scored.
- `private(set)`, `fileprivate(set)`, `internal(set)` and `public(set)` no
  longer create a Function named `set` that takes the next declaration's body.
  That declaration, such as `init() {}`, is scored under its own name.
- A property's own `get`, `set`, `willSet` and `didSet` blocks are scored as
  before, and line numbers and file paths are unchanged.
- Swift projects may see new `init` Functions and fewer `set` ones in `crap
  --lang swift`, with either coverage flag. `cc-check` does not count Swift, so
  it is unaffected; Python and TypeScript scores are unchanged.
- `package(set)`, and a comment or line break between a modifier and `(set)`,
  are not covered and still make a `set` Function.
- A lizard run that fails, such as a crash in the workaround, now stops `crap`
  and `cc-check` with lizard's error output. Before, an exit of 1 was taken as
  lizard's warning exit, but lizard's CSV output never gives one, so only a
  crash exited 1 and it read as a scan that found no functions.
- The bugs are reported upstream as terryyin/lizard#516. The workaround is
  removed once the lizard floor reaches a release that fixes them (#71).

**When you bump the pin:** run `qg-skills`. Re-record the crap baseline of
every Swift project: delete `crap-baseline.json`, then run `crap --lang swift
<source dirs> <coverage flag> --baseline crap-baseline.json --update`. Before
you commit it, explain or fix every row that shows `?` in the coverage column:
each is a worst-case score the baseline will exempt (#81). There is no Swift
`cc-check` baseline to re-record, since `cc-check` does not count Swift; cc and
crap baselines of Python and TypeScript projects are unaffected.

## 0.8.2 — 2026-10-11

`--xcresult` matches exact paths (#49; ADR-001 addendum "xccov matches exact
paths (v0.8.2)"). No threshold changes.

- The xccov reader matches a scanned file to a report file only when both
  resolve to the same real path, as `--llvm-cov-json` has since 0.8.0. It no
  longer falls back to the file name or stem, which let two files with the same
  name in different folders share the first one's coverage and let an untested
  function pass. Swift `--xcresult` scores can change: a function that took
  another file's figure by name now gets its own, or scores worst case.
- A `.xcresult` bundle made in another checkout or container now gives every
  function unknown coverage (`?`, `null` in JSON), scored worst case, and
  `crap` prints the line about no scored function getting a figure. A report
  file with no `path` is not matched. A scanned or report path that cannot be
  resolved (a symlink loop, a NUL byte) exits 2, as `--llvm-cov-json` does.
- Matching within one file (`(name, line)`, then the bare name) is unchanged.
- Internal: the llvm-cov and xccov readers share one path resolver.

**When you bump the pin:** run `qg-skills`. In a Swift project that uses
`--xcresult`, run the tests in the checkout where `crap` runs. Re-record the
crap baseline of every such project: delete `crap-baseline.json`, then run
`crap --lang swift <source dirs> --xcresult <bundle> --baseline
crap-baseline.json --update`. Before you commit it, check that `crap` did not
print the line about no scored function getting a figure, and explain or fix
every row that shows `?` in the coverage column: each is a worst-case score the
baseline will exempt (#81). Baselines of
Python, TypeScript and SwiftPM (`--llvm-cov-json`) projects are unaffected.

## 0.8.1 — 2026-10-11

Coverage readers fail loudly (#50, #55, #56, #65, #66; ADR-001 addendum
"Coverage readers fail loudly (v0.8.1)"). No threshold changes, and a report
that works scores as before.

- A coverage flag given an empty or whitespace-only path, such as
  `--llvm-cov-json "$(swift test --show-codecov-path)"` when the path command
  fails (a broken `Package.swift`, or no package in the directory), now exits 2
  with `[crap] --llvm-cov-json was given an empty path`. Before, it printed the
  worst-case note and exited 0 or 1 by score, so a CI step could pass without
  coverage. Failing tests do not empty the path, since `--show-codecov-path`
  runs no tests; the `swift test --enable-code-coverage` step must fail the
  job.
- A coverage file that is not UTF-8 now exits 2 with the reader's "bad ...
  JSON" message, in the coverage.py and Istanbul readers as in the llvm-cov
  one. Before, they crashed with a traceback and exit 1. The coverage.py reader
  opens its file as UTF-8 whatever the locale.
- An xccov function with a null, missing or non-numeric `lineCoverage` has
  unknown coverage (`?`, `null` in JSON) and scores worst case. Before, null
  crashed the run and a missing figure counted as 0% covered. A same-named
  entry is no longer borrowed for it.
- When a coverage report was given and no scored function got a figure from
  it, `crap` prints `[crap] no scored function got a figure from the coverage
  report; it may have been made elsewhere or hold no figures for the scanned
  files` to stderr, in `--json` mode too. Scores and exit codes are unchanged.
- Internal: the three JSON coverage readers share one loader, and the llvm-cov
  reader names its region fields.

**When you bump the pin:** run `qg-skills`. A CI step that builds a coverage
flag with `$(...)` now fails the build when the path command inside `$(...)`
fails or prints nothing, where it used to pass as a worst-case ranking; fix
that path command, not the flag, and make sure the step that runs the tests
fails the job. If the new stderr line appears, the report was made somewhere
else (another checkout or a container), or holds no figures for the scanned
files: measure coverage in the checkout where `crap` runs, for the files it
scans. No baseline needs re-recording.

## 0.8.0 — 2026-10-10

`crap --lang swift` reads SwiftPM coverage (#6, ADR-001 addendum "SwiftPM
coverage (v0.8.0)"). The new `--llvm-cov-json FILE` takes the llvm-cov export
JSON that `swift test --enable-code-coverage` writes, so a SwiftPM package with
tests gets a Swift CRAP gate instead of worst-case scores. It needs neither
Xcode nor `xcrun`, so it runs on Linux too. A function's coverage is the line
figure `llvm-cov report --show-functions` prints for it. A report file matches
only lizard's exact path, so coverage must be measured in the same checkout
where `crap` runs; a report made in another checkout or container gives unknown
coverage. A function whose lines hold the opening of another function's body
gets unknown coverage rather than borrow it: two functions on one line both do,
and so does a function that ends on the line where the next one opens, while
that next one keeps its own figure. A closure or autoclosure default argument
on the line of the function's `{` gives unknown coverage too; move it to a line
above the `{`. `--xcresult` is unchanged. Giving another language's
coverage flag now names both Swift flags in the error.

**When you bump the pin:** run `qg-skills`. In a SwiftPM package, replace
`--no-coverage` in CI with these two commands, run in the same checkout:

```bash
swift test --enable-code-coverage
crap --lang swift Sources/ --llvm-cov-json "$(swift test --show-codecov-path)" --baseline crap-baseline.json
```

Record the baseline once by running the same two commands with `--update`
added, on the platform CI runs on, and commit `crap-baseline.json`. An Xcode
project needs to do nothing else.

## 0.7.4 — 2026-10-10

Housekeeping: no score, threshold or scanned file changes (#47, #48).

The two `--help` texts, the README and the skills listed four TypeScript and
JavaScript suffixes, but `.cjs` and `.mjs` have been counted since 0.7.0. The
help is now generated from the language records, and all of them name the six.
ADR-001 has a 2026-10-10 addendum for the list. Internally, the two gates share
one error wrapper, and crap's two strict-or-print checks share one helper.

**When you bump the pin:** run `qg-skills`, because the skill text changed. Other
projects: nothing else.

## 0.7.3 — 2026-10-10

`crap --lang typescript` now scores each function that shares a start line with
another over its own lines (#41, ADR-001 addendum of 2026-10-10). lizard gives
no column, so in `const f = () => xs.map(x => x ? 1 : 2)` both functions start
on line 1, and the first Istanbul entry on that line was taken for both: a
callback on the first line of a multi-line function was scored over the whole
function. Each lizard function now takes the entry that ends where it ends,
else the narrowest entry that contains its end, else the one that ends
last. TypeScript and JavaScript CRAP scores may change for functions that
share a start line with another, up or down; a function that is the only one
starting on its line scores as in 0.7.2. Coverage is still counted by line, so
a callback sharing a line with its holder still counts that line's branches
and statements. `cc-check` and Python and Swift scores do not change.

**When you bump the pin:** run `qg-skills`. A project with a TypeScript or
JavaScript `crap-baseline.json`: on the bump commit, with the gates passing on
the commit before, collect coverage as your CI does, delete
`crap-baseline.json`, run `crap` with `--update` exactly as your hook and CI
call it, and commit. Review the diff in the pull request: an entry that rose
or is new is a callback, or a function declared after another on the same line,
that was scored over a range with fewer or better tested branches than its
own. `--update` only lowers scores, so do not run it
against the old baseline. Other projects: nothing else.

## 0.7.2 — 2026-10-10

A method of a class defined inside a function is now scored on its own (#44).
radon drops a class defined in a function body, so neither `cc-check` nor `crap`
ever listed its methods. They are now listed under the dotted name `f.K.m`, at
any depth: a class in a method of a class in a function, a nested class in that
class, and closures inside such a method. The enclosing function's own score is
unchanged and nothing is counted twice. In a rare case a newly scored method
takes a name an existing function had; the existing function, if it comes
later in the file, is then keyed `#2`. This is a bug fix: ADR-001 already says
every method is scored.

**When you bump the pin:** run `qg-skills`. Then, on the bump commit, with the
gates passing on the commit before, delete `cc-baseline.json` and
`crap-baseline.json`, run each gate with `--update` exactly as your hook and
CI call it, and commit. Review the new entries in the pull request diff: they
are methods of classes defined inside functions that were over the limit all
along. Python reports may gain functions that were never scored before.

## 0.7.1 — 2026-10-10

One coverage seam in `crap` (#46, architecture review change 2; the review is
now in `docs/reviews/`). Each language is one record that both gates read: its
counting tool, its coverage flag and reader, and its "nothing found" message.
Every coverage reader answers the same question, the coverage of one function,
and `crap` scores every language through one path. No behaviour changes: the
output of `crap` and `cc-check`, text and JSON, is the same as in 0.7.0.

**When you bump the pin:** run `qg-skills`. Nothing else.

## 0.7.0 — 2026-10-09

One complexity scan for both gates (#43, ADR-001 addendum of 2026-10-09).
`cc-check` and `crap` now take their functions from one module, so they always
list the same functions under the same names.

- Classes are no longer scored by `cc-check`; `crap` never scored them.
- Python closures and methods of nested classes are scored on their own, named
  `outer.inner` and `K.Inner.deep`. A Python name that repeats in a file gets
  `#2`, `#3`, as TypeScript and Swift names already did.
- One skip list for both gates and every language: `.git`, `.venv`, `venv`,
  `.direnv`, `node_modules`, `__pycache__`, `backups`, `build`, `dist`, `.tox`,
  `.mypy_cache`, `.pytest_cache`, `.worktrees`, `.claude/worktrees`. `crap` now
  skips `venv` and scans hidden folders such as `.claude/hooks`; `cc-check` now
  skips `build`, `dist` and the tool caches.
- Both gates end their report with `Skipped N folder(s): ...` naming every
  skipped folder found inside the scanned paths. `crap --json` has it as a
  `skipped` list; `cc-check --format json` writes the line to stderr. When
  every file was skipped, the line comes before the "nothing found" error.
- TypeScript and Swift scans read only the files under the given paths, so a
  `build` or `dist` folder above the scanned path no longer hides the whole
  project. A scan of `.` reports `src/a.ts`, not `./src/a.ts`.
- `cc-check` drops the A–F letter. Its JSON loses `rank`, and `name` now holds
  the full name (`K.m`), the same as `fullname`.
- Error messages from radon and lizard now carry the tag of the gate that
  printed them (`ERROR:` in `cc-check`, `[crap]` in `crap`) instead of
  `[lizard]`. A missing radon reads the same in both gates. Exit codes are
  unchanged.

**When you bump the pin:** run `qg-skills`. Then, on the bump commit, with the
gates passing on the commit before, delete `cc-baseline.json` and
`crap-baseline.json`, run each gate with `--update` exactly as your hook and
CI call it, and commit. Review the new entries in the pull request diff: they
are closures, nested-class methods and functions in hidden folders that were
over the limit all along. Anything that reads `cc-check --format json` must
stop reading `rank`, and gets the full name (`K.m`) from `name`.

## 0.6.0 — 2026-10-08

CC and CRAP gates for TypeScript and JavaScript (#21, ADR-001 addendum of
2026-10-07, now accepted).

- `cc-check --lang typescript PATHS` counts `.ts`, `.tsx`, `.js` and `.jsx`
  with lizard and fails above 8, with `--baseline` as for Python. `--lang`
  defaults to `python`, so existing calls are unchanged.
- `crap --lang typescript PATHS --istanbul-json coverage/coverage-final.json`
  takes per-function coverage from Istanbul's JSON report (Vitest, Jest).
  `--no-coverage` and `--baseline` work as for the other languages.
- A new `/cc-typescript` skill; `/crap` and `/setup-standards` cover
  TypeScript, and `/setup-standards` has CI steps for it.
- Baseline keys: a function name that repeats in a file is keyed with its
  order, `path::(anonymous)#2`. This also applies to Swift.
- lizard is now a core dependency; the `[swift]` extra is gone.

**When you bump the pin:** run `qg-skills`. If you installed
`quality-gates[swift]`, drop `[swift]`. A Swift project with a
`crap-baseline.json` whose functions share a name in one file: run its
`crap --lang swift ... --update` once, as the second and later of those
entries are now keyed `name#2`, `#3`. A TypeScript or JavaScript project:
run `/setup-standards` to add the gates.

## 0.5.3 — 2026-10-07

Documentation only: the README's *Releasing* section says to push the release
tag from a local session, because a cloud session's GitHub proxy refuses tag
pushes.

**When you bump the pin:** nothing to do beyond `qg-skills`.

## 0.5.2 — 2026-10-07

Moving freely between local and cloud sessions.

- The stage guard refuses `git add :.`, which stages the whole tree like
  `git add .` (#16).
- `/setup-standards` writes a pre-commit hook that puts `.venv/bin` on PATH
  when the project has a `.venv`, so a commit from VS Code or a cloud shell
  finds `comment-debt` and `cc-check` (#33).
- The issue-tracker template has an *In a cloud session* section: there
  `gh issue`, `gh pr` and `gh label` fail with HTTP 403, so use the GitHub MCP
  tools or `gh api` REST calls (#35).
- PR bodies go through the `pr` skill. `qg-agent-docs` now writes
  `.github/pull_request_template.md` with its Summary / Evidence / Merge
  Danger headings, and adds a *Pull requests* section to the Agent skills
  block in `CLAUDE.md`, even when the block is already there. Before this,
  nothing pointed an agent at the skill, so PR bodies came out freehand.
- This repo only: a SessionStart hook installs `.venv` in cloud sessions (#36),
  and its own pre-commit hook finds `.venv/bin` (#33).

**When you bump the pin:** run `qg-skills` to get the new stage guard, and
`qg-agent-docs --tracker <yours>` (or `/setup-standards`) for the PR template
and the *Pull requests* section; if you already have a PR template, it is kept
and the tool shows the difference. If your
`.githooks/pre-commit` calls the gates by bare name and you use a `.venv`, add
`[ -d .venv/bin ] && PATH="$PWD/.venv/bin:$PATH"` after its shebang. If you
copied the issue-tracker doc from the template, add its *In a cloud session*
section.

## 0.5.1 — 2026-10-07

Documentation only: the README describes the package as it is since 0.5.0.

- A *Get started* section near the top gives the steps to set up a project
  on your computer or from a cloud session, to use it in a cloud session,
  and to keep it up to date.
  The older *Use it in a project* section becomes *Setup details*.
- The skills table lists every shipped skill, grouped by the step it serves,
  and says which are ours, which are Matt Pocock's word for word, and which
  are his with changes.
- The workflow table gives each route's later steps, as the size rule does.
- A fresh cloud session lists the project's skills only after its first
  message; *Get started* says so.
- A new maintainer section, *Keeping the copied skills current*, gives the
  monthly upstream routine.
- The licence section names the two upstream MIT works and where their
  notices are.
- The plugin manifests describe all three layers, not only the gates.

**When you bump the pin:** nothing to do beyond `qg-skills`.

## 0.5.0 — 2026-10-07

Matt Pocock's workflow skills ship with the package, so cloud sessions have
them ([ADR-003](docs/adr/archive/ADR-003-vendor-pocock-skills.md)).

- `qg-skills` now also copies 17 of his skills: `wayfinder`,
  `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `implement-spec`,
  `tdd`, `diagnosing-bugs`, `improve-codebase-architecture`,
  `codebase-design`, `domain-modeling`, `pr`, `triage`, `retro`,
  `writing-for-agents`, `handoff`, and his `code-review` as
  `/review-against-spec`, so it no longer hides Claude Code's `/code-review`.
- `setup-matt-pocock-skills` is a pointer to `/setup-standards`.
- The size rule ends every route with `/review-against-spec`, and the largest
  route builds its tickets with `/implement-spec`.
- Every change to a copied file is listed, with how to redo it, in
  `docs/upstream-adaptations.md`; `qg-upstream` points there.

**When you bump the pin:** run `qg-skills`, commit the new skill folders, and
start a new session. If his plugin is installed, his skills appear twice; the
unprefixed ones are the pinned copies. If your project has its own skill with
one of the names above, `qg-skills` replaces it: rename yours first.

## 0.4.1 — 2026-10-06

Fixes from the first run of `/setup-standards` on a real project (localbar).

- `/setup-standards` writes `CLAUDE.md` pointers that say what the file they
  name holds, not just its path, and on a re-run rewrites existing pointers
  that only name a file.
- The README says how to start: run `qg-skills` before the first Claude Code
  session, because a session loads skills only when it starts.

**When you bump the pin:** run `qg-skills`, start a new session, run
`/setup-standards`, and commit what changes.

## 0.4.0 — 2026-10-06

The workflow and principles layers of ADR-002, now accepted.

- New skill `standards`: the size rule and 13 principles, one file each, with
  an index the agent reads to pick the one that applies.
- New skill `/setup-standards`: sets up or upgrades a project for all three
  layers (agent docs, glossary, gates, baselines, hooks, CI, asking rule) and
  ends with a plain report.
- `qg-skills` also installs the stage guard (a Claude Code hook refusing
  `git add -A`, `git add .`, `git commit -a`) and the asking-rule line in
  `CLAUDE.md`. `qg-skills --check` fails when either is missing or stale, and
  exits 2 when `.claude/settings.json` is not valid JSON.
- New command `qg-agent-docs`: writes `docs/agents/` from Matt Pocock's setup
  templates without overwriting your edits.
- New command `qg-upstream`, run monthly by a workflow in this repo: reports
  upstream changes to the files copied from Pocock and pstack.

**When you bump the pin:** run `/setup-standards`, or at least `qg-skills`, and
commit what it writes (`.claude/skills/`, `.claude/hooks/`,
`.claude/settings.json`, `CLAUDE.md`). Until you do, a test calling
`skills_sync.main(["--check"])` fails.

## 0.3.2 — 2026-10-04

No comment debt left in the repo (#1).

- `crap --help` is rewritten: the epilog came from the module docstring and
  named a `../crap.py` path and a SwiftLint install that no longer apply. It
  now lists the languages, examples, exit codes and dependencies. Defaults and
  flags are unchanged.
- `crap` has its own test suite covering the formula, coverage parsing for both
  languages, the `--top` cap and every tool-error exit.

**When you bump the pin:** run `qg-skills` and commit `.claude/skills/`; nothing
else changes.

## 0.3.1 — 2026-10-04

Skills for cloud sessions. A cloud session doesn't install plugins a repo
enables in `.claude/settings.json`, so the skills never loaded there.

- The skills ship inside the Python package (`src/quality_gates/skills/`); the
  plugin manifest points there.
- New command `qg-skills` copies them into `.claude/skills/`; `--check` exits 1
  when the copies differ from the installed version.

**When you bump the pin:** run `qg-skills`, commit `.claude/skills/`, add a test
calling `skills_sync.main(["--check"])`, and remove the `quality-gates` entries
from `extraKnownMarketplaces` and `enabledPlugins` so skills aren't listed twice.

## 0.3.0 — 2026-10-04

A baseline ratchet for `cc-check` and `crap`, so a repo with existing debt can
put them in CI.

- `cc-check` and `crap` take `--baseline FILE` and `--update`. The baseline maps
  `path::function` to its score for functions over the threshold. The check
  fails on a new or worse function, and on a lowered score until `--update`
  records it. `--update` never raises a score or adds an entry. A missing
  baseline file is an error (exit 2) except with `--update`, which creates it.
- `crap --baseline` needs coverage: it exits 2 with `--no-coverage` or with no
  coverage source.
- `cc-check` takes several paths in one run: `cc-check src tests`.
- `cc-check --format json` rows carry `fullname` (`Class.method` for methods).
- `crap` names methods `Class.method` (was `method`).
- `cc-check` and `crap` `main` take an `argv` list, so a test can call them.
- `cc-check`'s `main` and `comment-debt`'s `status` are split to CC 8 or below.

**When you bump the pin:** nothing breaks. To gate CI on CC or CRAP in a repo
with existing debt, run the gate once with `--baseline <file> --update`, commit
the file, and add a test that calls `main` with `--baseline <file>`. Scripts
that ran `cc-check` once per directory can pass all the paths at once.

## 0.2.0 — 2026-10-04

One complexity standard across languages. See ADR-001.

- `cc-check` defaults to `--threshold 8`, the agent ceiling (was 5).
- The Python CC gate is `cc-check` (radon), not `ruff --select C901`: radon is
  the counter `crap` uses, ruff scores the same function lower.
- Swift: SwiftLint `cyclomatic_complexity` warns above 6 and fails above 8, with
  `ignores_case_statements: true`.
- `crap --no-coverage` is documented as a ranking, not a gate.
- MIT licence.

**When you bump the pin:** replace any `ruff --select C901` gate with
`cc-check <path>`, and expect it to flag more existing functions than ruff did;
remove a `[tool.ruff.lint.mccabe]` block that disagrees with 8; set
`ignores_case_statements: true` in `.swiftlint.yml`.

## 0.1.0 — 2026-09-28

First release: `comment-debt`, `cc-check`, `crap`, and the skills
`/no-comments`, `/cc-python`, `/cc-rust`, `/cc-swift`, `/crap`.
