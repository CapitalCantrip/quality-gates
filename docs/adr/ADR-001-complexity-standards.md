---
status: accepted
date: 2026-10-04
---

# ADR-001: One complexity standard, counted by the tool CRAP uses

## Context

Before this decision the complexity limit was written down in five places with
four values. The first consuming project enforced Python CC 6 through ruff and Swift 6/8 through
SwiftLint, both set by a commit and not a decision. The `/cc-python` skill said
8. `cc-check` defaulted to 5. `/cc-swift` and that project's build checklist still
said 10/15.

The tools also disagree about what CC means. On the same function, one `if`
with four `and`-joined conditions plus a filtered list comprehension:

| Counter | CC |
|---|---|
| ruff C901 (McCabe) | 2 |
| radon (`cc-check`, and `crap --lang python`) | 7 |
| lizard (`crap --lang swift`) | 7 |

ruff ignores boolean operators and comprehension clauses; radon and lizard
count them. Gating with ruff while CRAP scores with radon meant a function
could pass the CC gate and still fail CRAP at 100% coverage.

## Decision

Amended by: [Addendum 2026-10-04: the baseline ratchet (v0.3.0)](#addendum-2026-10-04-the-baseline-ratchet-v030), [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08), [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070), [Addendum 2026-10-11: coverage readers fail loudly (v0.8.1)](#addendum-2026-10-11-coverage-readers-fail-loudly-v081), [Current rule, restated 2026-10-12: the complexity ceiling](#current-rule-restated-2026-10-12-the-complexity-ceiling)

**Agent-written code has a cyclomatic complexity ceiling of 8.** Human-maintained
code targets 5. Agents keep exact short-term memory, so some of the cognitive
load that drives the human limit does not apply (Robert C. Martin, interviewed
2026-09-06).

| Language | Gate | Tool | Limit |
|---|---|---|---|
| Python | CC | `cc-check` (radon) | fail above 8 |
| Swift | CC | SwiftLint `cyclomatic_complexity`, `ignores_case_statements: true` | warn above 6, fail above 8 |
| Rust | Cognitive complexity | `cargo clippy` | fail above 10; function length fail above 25 lines |
| Python, Swift | CRAP | `crap` | warn above 5, fail above 8 |

**Python CC is counted by radon, not ruff,** because CRAP counts with radon. With
one counter, a fully covered function's CRAP equals its CC, so the CC ceiling and
the CRAP ceiling meet at the same point: CC 8 passes CRAP only at 100% coverage.

**Swift ignores `switch` cases.** An exhaustive `switch` over an enum is flat and
readable at any length, and Swift requires every case to be listed. Counting each
case pushed idiomatic Swift above the limit for no gain in risk. `guard let` and
`if let` still count.

**Rust's 10 is a different measure,** not a looser one. Cognitive complexity
penalises nesting and ignores flat `match` arms. Do not align it with the CC
numbers.

**CRAP is a gate only with coverage data.** Without it every function scores
CC² + CC, which fails at CC 3. `crap --no-coverage` is a worst-case report, read
for the ranking, never a pass/fail result.

**A project may tighten these limits, never loosen them.**

## Consequences

Amended by: [Addendum 2026-10-10: SwiftPM coverage (v0.8.0)](#addendum-2026-10-10-swiftpm-coverage-v080)

- Consumers switch the Python CC gate from `ruff --select C901` to `cc-check`.
  radon flags roughly twice as many existing functions as ruff did; that is debt
  to pay down, not a reason to keep ruff.
- `cc-check` defaults to 8.
- Swift CRAP in a SwiftPM package has no coverage source: `swift test
  --enable-code-coverage` writes llvm-cov JSON, and `crap` reads only Xcode's
  `.xcresult`. Until `crap` reads llvm-cov JSON (#6), a SwiftPM project's Swift CRAP
  stays worst-case and informational.
- Swift has the same split Python had: SwiftLint gates CC, lizard scores CRAP,
  and they count differently. Left as is while the only Swift consumer is
  frozen.

## Rejected

- **ruff as the counter.** Fast and in every editor, but a different number from
  CRAP's for the same function, so the two gates could not be reasoned about
  together.
- **CC 6.** No recorded reason, and below 8 it leaves CRAP's range from 7 to 8
  unreachable even with full coverage.
- **Separate numbers per language.** Swift's higher scores came from counting
  `switch` cases; removing that removed the case for a different number.

## Addendum 2026-10-04: the baseline ratchet (v0.3.0)

Amends: [Decision](#decision)

Amended by: [Amended 2026-10-08, on acceptance](#amended-2026-10-08-on-acceptance), [Addendum 2026-10-12: baseline keys use the real path (v0.9.0)](#addendum-2026-10-12-baseline-keys-use-the-real-path-v090), [Current rule, restated 2026-10-12: the baseline ratchet](#current-rule-restated-2026-10-12-the-baseline-ratchet), [Current rule, restated 2026-10-12: baseline keys](#current-rule-restated-2026-10-12-baseline-keys)

The standards above are unchanged. `cc-check` and `crap` gained `--baseline` so a
repo with existing debt can enforce them in CI without first paying it all off.

- **Key format:** `path::function`, with methods as `path::Class.method` and the
  path relative to the git root (the working directory outside a git repo). A
  key carries no line number, so editing elsewhere in the file does not move it;
  a renamed or moved function is new, so debt cannot be laundered by renaming.
- **Only functions over the threshold are recorded.** A function that drops to
  the threshold leaves the baseline at the next `--update`, and cannot return.
- **A missing baseline is an error, except with `--update`.** Treating it as
  empty would fail every adopting repo on its first run; treating it as
  permissive would let a mistyped path pass CI.
- **CRAP baselines need coverage,** following the decision that CRAP without
  coverage is a ranking, not a gate.

## Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)

Amends: [Decision](#decision)

Amended by: [Amended 2026-10-08, on acceptance](#amended-2026-10-08-on-acceptance), [Addendum 2026-10-10: functions that share a start line (v0.7.3)](#addendum-2026-10-10-functions-that-share-a-start-line-v073), [Addendum 2026-10-10: the suffix list (v0.7.4)](#addendum-2026-10-10-the-suffix-list-v074), [Current rule, restated 2026-10-12: the complexity ceiling](#current-rule-restated-2026-10-12-the-complexity-ceiling), [Current rule, restated 2026-10-12: TypeScript and JavaScript counting](#current-rule-restated-2026-10-12-typescript-and-javascript-counting), [Current rule, restated 2026-10-12: TypeScript's known miscount](#current-rule-restated-2026-10-12-typescripts-known-miscount), [Addendum 2026-10-22: lizard 1.24.2 is the floor and the Swift workaround is gone (v0.11.0)](#addendum-2026-10-22-lizard-1242-is-the-floor-and-the-swift-workaround-is-gone-v0110), [Current rule, restated 2026-10-22: TypeScript and JavaScript counting](#current-rule-restated-2026-10-22-typescript-and-javascript-counting)

The standards above extend to `.ts`, `.tsx`, `.js`, `.jsx`, `.cjs` and `.mjs`
(`.cjs` and `.mjs` named by the 2026-10-10 addendum). Nothing changes for Python,
Swift or Rust.

| Gate | Tool | Limit |
|---|---|---|
| CC | `cc-check --lang typescript` (lizard) | fail above 8 |
| CRAP | `crap --lang typescript` (lizard, Istanbul coverage) | warn above 5, fail above 8 |

**lizard counts both gates,** for the reason radon counts both for Python: with
one counter a fully covered function's CRAP equals its CC, so the ceilings meet
at 8. On test functions lizard agrees with a hand count for `if`, loops, `case`,
`catch`, `&&`, `||` and `?:`, and gives a nested arrow function its own score.

**`switch` cases count.** Swift is exempt because its compiler requires an
exhaustive `switch`; TypeScript does not, so each `case` is a path that can go
untested. lizard runs without `-m`.

**Coverage comes from Istanbul's JSON report** (`coverage-final.json`, the
`json` reporter), which Vitest and Jest both write. A function's coverage is
its branch coverage within its lines, or its statement coverage when it has no
branches: the rule `crap` already applies to Python. The function's lines come
from Istanbul's `fnMap`, matched to lizard by start line, because lizard's end
line runs on into the next declaration when the code has type annotations.

**Known miscount:** lizard counts `??` as two paths, not one. That can only
raise a score, so the gate errs strict; it is left as is.

### Amended 2026-10-08, on acceptance

Amends: [Addendum 2026-10-04: the baseline ratchet (v0.3.0)](#addendum-2026-10-04-the-baseline-ratchet-v030), [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08)

Amended by: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070), [Current rule, restated 2026-10-12: repeated names](#current-rule-restated-2026-10-12-repeated-names)

**Repeated names get their order as a suffix in baseline keys.** lizard names a
method without its class and every unnamed callback `(anonymous)`, and the
ratchet keeps one score per key, so a new function could hide behind an old one
of the same name. The second and later functions of a name in a file are keyed
`path::name#2`, `#3`, in order of their start line. This applies to Swift too;
a Swift baseline with no repeated names is unchanged. Keying by the enclosing
named function was rejected: lizard does not report nesting.

**lizard is a core dependency,** no longer the `[swift]` extra: two languages
need it, and it is pure Python.

### Rejected

- **ESLint's `complexity` rule as the CC gate.** It is the usual choice and runs
  in the editor, but it is a second counter beside CRAP's: the split this ADR
  removed for Python.
- **A counter of our own on the TypeScript compiler API.** It would need Node
  inside a Python package and would still be a second counter.
- **`json-summary` coverage.** It holds totals per file; CRAP needs coverage per
  function.
- **lcov, for now.** Node's own test runner writes lcov, not Istanbul JSON. Add
  it when a project on `node --test` adopts the gates.

## Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)

Amends: [Decision](#decision), [Amended 2026-10-08, on acceptance](#amended-2026-10-08-on-acceptance)

Amended by: [Addendum 2026-10-11: a workaround for two lizard Swift bugs (v0.8.3)](#addendum-2026-10-11-a-workaround-for-two-lizard-swift-bugs-v083), [Addendum 2026-10-11: skip SwiftPM's .build (v0.9.0)](#addendum-2026-10-11-skip-swiftpms-build-v090), [Addendum 2026-10-11: follow symlinked folders (v0.9.0)](#addendum-2026-10-11-follow-symlinked-folders-v090), [Addendum 2026-10-11: the freshness check reads the scan's files (v0.9.0)](#addendum-2026-10-11-the-freshness-check-reads-the-scans-files-v090), [Addendum 2026-10-11: Python end lines from the AST (v0.9.0)](#addendum-2026-10-11-python-end-lines-from-the-ast-v090), [Current rule, restated 2026-10-12: repeated names](#current-rule-restated-2026-10-12-repeated-names), [Current rule, restated 2026-10-12: what a Function is](#current-rule-restated-2026-10-12-what-a-function-is), [Current rule, restated 2026-10-12: the skip list](#current-rule-restated-2026-10-12-the-skip-list)

The limits above are unchanged. What a gate scores, and where it looks, is now
decided in one module that both `cc-check` and `crap` take their functions from
(#43), so the promise that the two gates count the same way is kept by code
rather than by convention. Before this, Python was counted twice, classes were
scored by one gate only, and each gate had its own list of folders to skip.

**A Function is what is scored** (see `GLOSSARY.md`): a function, a method, a
closure, or a method of a nested class, each on its own.

- **Classes are not scored.** A class's radon score is built from its methods,
  which are already scored, so a class could fail for complexity its methods
  report.
- **Closures and nested-class methods are scored on their own,** with names
  dotted from the outside in: `outer.inner`, `K.Inner.deep`. Before, their
  complexity sat in the enclosing class, or nowhere. The `#2` suffix for a
  repeated name now applies to Python too. TypeScript and Swift names stay as
  lizard gives them, since lizard does not report nesting.
- **One skip list, for both gates and every language:** `.git`, `.venv`, `venv`,
  `.direnv`, `node_modules`, `__pycache__`, `backups`, `build`, `dist`, `.tox`,
  `.mypy_cache`, `.pytest_cache`, `.worktrees`, `.claude/worktrees`. Every other
  hidden folder is scanned, so agent-written hooks in `.claude/hooks` are held
  to the standard. An entry matches a folder of that name anywhere below the
  scanned path, so a real package called `build` or `dist` is skipped too; for
  that reason both gates end their report with a line naming every skipped
  folder they found. A folder above the scanned path never counts: a project
  checked out under `build/` is scanned in full, in every language.
- **An empty scan is not a scan error.** The scan raises only for a missing
  path, a missing tool or a crashed tool; a scan that finds nothing returns
  nothing. Each gate keeps its own wording for that case, and `crap
  --allow-empty` keeps working. This amends #43, which asked the scan to raise
  on an empty result: that would have changed both messages and removed
  `--allow-empty`, which the same issue asked to keep.
- **A missing radon reads the same in both gates:** `radon is not installed.`
  followed by `Install with: pip3 install radon`, the wording `crap` already
  used. This amends #43, which asked every message body to stay word for word:
  one scan raises one error, so `cc-check`'s old `radon not installed. Run:
  pip install radon` could not be kept without a second message for the same
  failure.
- **The A–F letter is gone** from `cc-check`. It never decided pass or fail.

### Rejected

- **Scoring classes in both gates.** A class's score double-counts its methods.
- **Skipping every hidden folder.** It hid `.claude/hooks`, which agents write.
- **Lizard's own `-x` exclude patterns.** They match the whole path as given,
  so `*/build/*` skipped every file of a project that sits under a `build`
  folder, and named nothing. Lizard now reads the list of files the shared walk
  found.
- **A flag to record new debt into a baseline on upgrade.** Consumers re-record
  their baselines once on the bump commit instead, so no flag exists that an
  agent could later use to accept debt quietly.

## Addendum 2026-10-10: functions that share a start line (v0.7.3)

Amends: [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08)

Amended by: [Current rule, restated 2026-10-12: functions that share a start line](#current-rule-restated-2026-10-12-functions-that-share-a-start-line)

The limits above are unchanged. This amends the TypeScript addendum's sentence
that a function's lines come from Istanbul's `fnMap`, *matched to lizard by
start line*. That rule is exact only when one function starts on a line. In
`const f = () => xs.map(x => x ? 1 : 2)` lizard reports two functions at line
1 and gives no column, so the first `fnMap` entry on that line was taken for
both: a callback on the first line of a multi-line holder was scored over the
holder's whole range, with the holder's branches and statements (#41).

**Matching rule.** Among the `fnMap` entries whose declaration starts on
lizard's start line, in this order:

1. the entry whose end line equals lizard's end line;
2. else the narrowest entry whose end line is at or after lizard's end line;
3. else, when no entry contains lizard's end line, the entry on that line that
   ends last. This is the case when lizard's end line runs past the real end
   because of type annotations, as when an `interface` follows the function.

A function that is the only one starting on its line matches the same entry
under all three, so its score is unchanged. Only the end lines of the entries
matter, so entries that tie on end line give the same range.

**The limit that remains.** Coverage is counted by line: a branch or statement
belongs to a function when it starts inside the function's lines. A callback
that shares a line with its holder, or with the function declared beside it,
still counts that line's branches and statements, and the holder still counts
the callback's. The rule fixes the range, not the overlap on a shared line.
Two functions that start and end on the same line get the same coverage.

**Effect.** TypeScript and JavaScript CRAP scores can change for functions that
share a start line with another. No threshold, counting tool or gate coverage
changes, and `cc-check` is untouched.

### Rejected

- **Matching by column.** lizard reports none, and Istanbul's columns are
  unreliable under some reporters (v8 coverage gives a null end column).
- **Attributing statements and branches to the narrowest enclosing function by
  position.** It would remove the shared-line overlap, but it needs each
  function's end column, and Istanbul's end columns can be null: nyc's
  remapping and Vitest both write `null` there.

## Addendum 2026-10-10: the suffix list (v0.7.4)

Amends: [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08)

Amended by: [Current rule, restated 2026-10-12: TypeScript and JavaScript counting](#current-rule-restated-2026-10-12-typescript-and-javascript-counting)

The limits and gates above are unchanged, and so is what each gate counts. The
TypeScript addendum named four suffixes until this note, but `languages.py` has
counted six since v0.7.0. The docs did not follow the code, and the `--help` text
was written by hand from the same stale list.

The TypeScript and JavaScript suffixes are `.ts`, `.tsx`, `.js`, `.jsx`, `.cjs`
and `.mjs`. `languages.py` holds that list, and the `--help` text of `crap` and
`cc-check` prints it from there. The README and the skills name the same six,
and a test fails when a paragraph names some of them but not all.

Nothing that is scanned or scored changes. The two suffixes the TypeScript addendum
did not name until this note have been counted since v0.7.0, so a consumer needs no
action when bumping the pin.

## Addendum 2026-10-10: SwiftPM coverage (v0.8.0)

Amends: [Consequences](#consequences)

Amended by: [Addendum 2026-10-11: xccov matches exact paths (v0.8.2)](#addendum-2026-10-11-xccov-matches-exact-paths-v082), [Addendum 2026-10-11: a review rule covers the closure gap (v0.8.4)](#addendum-2026-10-11-a-review-rule-covers-the-closure-gap-v084)

The limits above are unchanged. Swift CRAP now reads coverage from a SwiftPM
package as well as from an Xcode project, so a SwiftPM package with tests has a
CRAP gate rather than a worst-case ranking. This supersedes the Consequences
line that left SwiftPM's Swift CRAP worst-case and informational.

| Project | Flag | Coverage report |
|---|---|---|
| Xcode | `--xcresult` | `.xcresult` bundle, read through `xcrun xccov`; unchanged |
| SwiftPM | `--llvm-cov-json` | the llvm-cov export JSON that `swift test --enable-code-coverage` writes, at `swift test --show-codecov-path` |

The SwiftPM reader needs neither Xcode nor `xcrun`, so it also runs on Linux.
Its JSON `coverage_source` is `llvm-cov-json`.

**A Function's coverage is llvm-cov's per-function line figure,** the Lines
column `llvm-cov report --show-functions` prints for it. It is the share of the
executable lines in the function's body that ran, worked out from that
function's own regions by llvm-cov's own rules. On the committed fixture every
function's figure equals that column. It is the per-function line measure
xccov reports too; the two were not compared function by function.

**Matching a Function to its llvm-cov body:**

- **The file is the report file at lizard's exact resolved path,** with the
  report's paths resolved too, so a symlinked path still matches. Any other
  file has unknown coverage. llvm-cov records absolute paths, so coverage has
  to be measured in the same checkout where `crap` runs: a report made in
  another checkout or a container gives every function unknown coverage.
- **The body is the one that ends last among those opening within lizard's
  lines** for the Function, and of those the one that opens first. llvm-cov
  starts a body at its `{`, while lizard starts a Function at `func`. An
  attribute line above (`@discardableResult`) is outside both. A signature over
  several lines puts the `{` below lizard's start, still inside its lines.
  llvm-cov lists a closure or autoclosure as a function of its own. One inside
  the body ends before the body does. A closure default argument in a signature
  over several lines opens before the body's `{` but also ends before it. So
  neither is taken for its holder. No body inside the lines means unknown
  coverage.
- **A Function whose lines hold the opening of another function's body has
  unknown coverage,** when that body shares a line with its own. Two functions
  on one line both do. A function that ends on the line where the next one
  opens does, and the next one keeps its own figure, because the first body
  opens outside its lines. If another body within lizard's lines shares a line
  with the chosen one and does not nest inside it, the regions cannot say
  which body is this Function's. Two functions on one line are the common
  case. Taking the
  last-ending body there lends one function's coverage to the other: an
  untested function passes beside a tested one, as #49 showed for xccov.
  Unknown scores worst case, so the gate fails safe. A default argument that
  llvm-cov lists as a function of its own, a closure (`= { _ in }`, `= {}`) or
  an autoclosure (`= flagA && flagB`, `= x ?? nil`), also gives unknown
  coverage when it ends on the line its function's `{` opens on, because
  nothing in the regions tells it from a second function. The remedy is to put
  the default argument on a line above the `{`. A literal default (`= 0`,
  `= nil`, `= []`, `= .main`) has no body of its own and is unaffected.
- **A function listed more than once,** as a generic specialisation or in more
  than one export, is scored once. The listings are merged, and each line keeps
  its highest count, so a line ran if any listing ran it. Listings are the same
  body only when they open at the same line and column.
- **A closure or nested `func` is scored on its own regions,** and its own
  counts do not reach the function that holds it. In the holder's figure, its
  lines carry the holder's count, as they do in llvm-cov's figure.
  A nested `func` that never ran therefore scores 0 on its own and leaves its
  holder's figure unchanged.

### Rejected

- **Matching on llvm-cov's mangled name.** It needs a Swift demangler, and
  overloads and nested functions still have to be told apart by line.
- **Matching a file by its name, or by its trailing folders and name,** so that
  a report made in another checkout or container still matches. A report made
  elsewhere can then lend a tested target's coverage to an untested one with
  the same folder and file name, such as `Core/Models/Item.swift` and
  `Admin/Models/Item.swift`, and hide a FAIL: the bug #49 records for xccov,
  again. Measuring coverage and running `crap` in the same checkout costs
  nothing a consumer's CI does not already do.
- **Taking the body that opens first.** A closure default argument in a
  signature over several lines opens first, and would be scored as the
  function.
- **Region coverage,** llvm-cov's headline figure. The two Swift formats would
  then measure different things for the same code.
- **Counting a closure's own counts against the function that holds it,**
  because lizard counts a closure's branches in its holder's CC. llvm-cov's
  and xccov's per-function figures do not do this, so the two Swift flags
  would score the same code differently.
- **Running `llvm-cov export` inside `crap` from the `.profdata`.** It needs the
  test binary's path and the toolchain on the machine; `swift test` already
  writes the JSON.

## Addendum 2026-10-11: coverage readers fail loudly (v0.8.1)

Amends: [Decision](#decision)

The limits above are unchanged. Three behaviours of `crap` that let a gate pass
or fail without saying why now say so. They amend the rule that CRAP is a gate
only with coverage data: a coverage flag that is present but empty or
unreadable no longer degrades to a worst-case ranking.

- **A coverage flag given an empty or whitespace-only path is a tool error
  (exit 2)** naming the flag, such as `--llvm-cov-json was given an empty path`.
  Only an absent flag means no report. Before this, a flag whose
  value came from a command that printed nothing, such as `--llvm-cov-json
  "$(swift test --show-codecov-path)"` with a broken `Package.swift` or no
  package in the directory, printed the worst-case note and exited 0 or 1 by
  score, so a CI step whose path command failed could pass. It now fails the
  build. `--show-codecov-path` runs no tests and prints a path even after
  failing tests, so failing tests are caught at the `swift test
  --enable-code-coverage` step, which must fail the job.
- **A file that is not UTF-8 is a tool error (exit 2)** in every coverage
  reader that reads a JSON file, not a traceback with exit 1. The coverage.py
  reader opens its file as UTF-8 explicitly, so the result does not depend on
  the machine's locale. One loader, `json_report.load_json`, holds the three
  failures (missing file, not UTF-8, bad JSON); each reader keeps its own
  wording.
- **An xccov function whose `lineCoverage` is null, missing or not a number has
  unknown coverage,** the same answer #6 gives wherever a coverage reader is
  unsure, never borrowed coverage. It scores worst case, so the gate fails
  safe, and the other functions in the report score normally. A missing figure
  no longer reads as 0.0 covered, and the lookup returns unknown for it rather
  than falling through to a same-named entry. A present number is still
  clamped to 0 through 1.

When a coverage report was given, at least one function was scored and none got
a figure, `crap` also prints one line to stderr, `[crap] no scored function got
a figure from the coverage report; it may have been made elsewhere or hold no
figures for the scanned files`, for every coverage flag and in `--json` mode
too. The report may have been made in another checkout, may hold no figure for
the scanned files, or may carry no usable figures at all. Scores and the exit
code are unchanged.

## Addendum 2026-10-11: xccov matches exact paths (v0.8.2)

Amends: [Addendum 2026-10-10: SwiftPM coverage (v0.8.0)](#addendum-2026-10-10-swiftpm-coverage-v080)

The limits above are unchanged. The rule from the *SwiftPM coverage (v0.8.0)*
addendum, that a Function's file is the report file at lizard's exact resolved
path and any other file has unknown coverage, now holds for both Swift flags.
Before this, the `--xcresult` reader indexed each report file under its path,
its file name and its stem, and looked a Function up in that order. Two files
with the same name in different folders shared whichever the report listed
first, so an untested function passed on a tested one's coverage: the bug #49
records.

- **A Function's file matches an xccov file only when both paths resolve to the
  same real path,** symlinks resolved on both sides, so a relative path from
  lizard still matches the absolute path xccov records. There is no file-name or
  stem fallback, and a report file with no `path` cannot be matched. A file
  that is not in the report has unknown coverage and scores worst case.
- **`--xcresult` coverage, like `--llvm-cov-json`, must be measured in the
  checkout where `crap` runs.** xccov records absolute paths, so a bundle made
  in another checkout or container gives every function unknown coverage, and
  `crap` prints the line about no scored function getting a figure.
- **Matching within one file is unchanged:** the Function's `(name, line)`
  entry, then its bare name. That fallback can still lend a same-named
  overload's figure; that is #83.
- **Paths compare as text after resolving,** as for `--llvm-cov-json`. On a
  macOS volume that ignores case, a scan path typed in the wrong case
  (`twinapp/sources` for `TwinApp/Sources`) matches nothing and gives unknown
  coverage. The same happens when an Xcode project's file reference spells a
  file in another case than the disk (`model.swift` for `Model.swift`): xccov
  records the project's spelling, that file's functions score worst case, and
  the hint line does not appear if other files got figures. Both fail safe,
  since the function scores worst case, so they are accepted rather than
  matched by file identity; the fix is to correct the path or the reference.

Rejected, as in the SwiftPM addendum: matching by file name or trailing folders,
which lets a report made elsewhere lend one target's coverage to another.

**Effect on existing scores.** A Swift project whose `--xcresult` scores relied
on a name match, or on a bundle made in another checkout, now scores those
functions worst case. Where two same-named files shared one figure, each file
now has its own. A crap baseline recorded with `--xcresult` may therefore hold
stale scores and is re-recorded.

## Addendum 2026-10-11: a workaround for two lizard Swift bugs (v0.8.3)

Amends: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070)

Amended by: [Addendum 2026-10-12: the `(set)` rule no longer depends on the word before it, except `init` (v0.9.1)](#addendum-2026-10-12-the-set-rule-no-longer-depends-on-the-word-before-it-except-init-v091), [Current rule, restated 2026-10-12: the lizard Swift workaround](#current-rule-restated-2026-10-12-the-lizard-swift-workaround), [Addendum 2026-10-22: lizard 1.24.2 is the floor and the Swift workaround is gone (v0.11.0)](#addendum-2026-10-22-lizard-1242-is-the-floor-and-the-swift-workaround-is-gone-v0110), [Current rule, restated 2026-10-22: how lizard reads Swift](#current-rule-restated-2026-10-22-how-lizard-reads-swift)

The limits and the counting tool are unchanged: lizard still counts Swift.
lizard 1.24.1, the latest release, misreads two Swift constructs (#69), and the
scan now corrects both before lizard's state machine sees them.

- **A failable initialiser was not scored.** lizard's tokenizer makes `init?`
  and `init!` single tokens, so they never match `init`. A failable `init?` with
  two `if`s (CC 3) was not reported, and so was never scored.
- **`private(set)` made a Function named `set`.** The `set` inside an access
  modifier (`private(set)`, `fileprivate(set)`, `internal(set)`,
  `public(set)`) opened a setter accessor, which took the next `{...}` as its
  body. The declaration after it, such as `init() {}`, was swallowed into a
  `set` Function and not scored under its own name.

**The workaround.** A Swift scan runs lizard through
`quality_gates.lizard_swift_workaround`, which puts a subclass of lizard's Swift
reader in place and then calls lizard as before; a TypeScript scan runs plain
`lizard`. The subclass rewrites the
token stream in lizard's preprocessing step: `init?` and `init!` become `init`,
and the `(set)` after one of those four modifiers is dropped. A failable
initialiser is then a Function named `init` with its own CC and lines; its `?`
or `!` is not counted as a condition. A property's own `get`, `set`, `willSet`
and `didSet` blocks are still Functions, as before. No token that holds a line
break is touched, so line numbers and file paths are those of the source file
and coverage matching is unchanged. Source files on disk are never rewritten.

Not covered: `package(set)`, and a comment or line break between the modifier
and `(set)`. Each still makes a `set` Function that swallows the next
declaration; both are filed as #89 and fixed in v0.9.1 (addendum "the `(set)`
rule no longer depends on the word before it, except `init` (v0.9.1)").

**A failing lizard stops the gate.** lizard's CSV output counts no warnings, so
the scan's lizard run exits 0 however many functions exceed lizard's own warning
limit (checked on 1.17.0, 1.17.10 and 1.24.1); the scan also passes `-i -1` in
case a lizard release starts counting them. Any other exit, such as a crash in the workaround when a lizard
release renames what it patches, is a tool error that shows lizard's error
output. Before this, an exit of 1 was taken as lizard's warning exit, which CSV
output never gives, so the only exit 1 was a crash, and it read as a scan that
found no functions.

`crap --lang swift` sees the fix with either coverage flag, since it reads the
shared scan. `cc-check` does not count Swift (SwiftLint does, with its own
parser), so it is unaffected. Running `lizard` directly still shows both bugs.

**Upstream and removal.** Both bugs are reported as terryyin/lizard#516, fixed
on lizard's master after 1.24.1. The workaround is removed, not kept, once the
lizard floor in `pyproject.toml` reaches a release with the fix: delete the
workaround module and its test file, and run Swift scans as `-m lizard` again
(#71).
Every release checks terryyin/lizard#516 (README § Releasing).

Rejected:
- Rewriting source files on disk before scanning. The scan would read copies,
  so file paths would no longer match the coverage report.
- Patching lizard inside the gates' own process. The swapped reader would stay
  in place for everything else that process does with lizard; the wrapper
  confines it to a lizard subprocess that only Swift scans start.
- Waiting for a lizard release. Until then a failable initialiser of any CC
  passes the gate unscored.

**Effect on existing scores.** A Swift project may see new `init` Functions
and fewer `set` ones, and a declaration that was swallowed by a `set` is now
scored under its own name. A Swift crap baseline may therefore hold stale or
missing entries and is re-recorded. Python and TypeScript scans are unchanged.

## Addendum 2026-10-11: a review rule covers the closure gap (v0.8.4)

Amends: [Addendum 2026-10-10: SwiftPM coverage (v0.8.0)](#addendum-2026-10-10-swiftpm-coverage-v080)

Amended by: [Addendum 2026-10-12: a closure outside any function is not scored (v0.10.1)](#addendum-2026-10-12-a-closure-outside-any-function-is-not-scored-v0101)

`/cc-swift` carries a review rule. In Swift, a new or changed closure (including
a trailing closure or a nested `func`) that contains a branch has a test that
runs it. It is a judgement call in review, not a gate. The reason differs by
kind:

- A closure: the CRAP gate does not count a closure's lines against the
  function that holds it, so an untested closure passes inside a tested holder
  (until quality-gates issue #53).
- A nested `func`: the CRAP gate scores it on its own and fails an untested one
  with two or more branches. A small one (a single branch, CRAP 6) can still
  pass untested, which is why the rule asks for a test for it too.

No threshold, counting tool or gate scope changes.

## Addendum 2026-10-11: skip SwiftPM's .build (v0.9.0)

Amends: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070)

Amended by: [Current rule, restated 2026-10-12: the skip list](#current-rule-restated-2026-10-12-the-skip-list)

The limits above are unchanged. This adds one folder to the skip list of the
2026-10-09 addendum. A scan of a SwiftPM package root with `--lang swift`
returned functions from `.build/debug/test_entry_point.swift`, and would also
have scored checked-out dependencies under `.build/checkouts`, none of which the
project wrote (#54).

**The skip list** is now `.git`, `.venv`, `venv`, `.direnv`, `node_modules`,
`__pycache__`, `backups`, `build`, `.build`, `dist`, `.tox`, `.mypy_cache`,
`.pytest_cache`, `.worktrees`, `.claude/worktrees`. It stays one list for both
gates and every language, matches a folder of that name anywhere below the
scanned path, and `.build` is named on the *Skipped N folder(s)* line like the
others. A project checked out under a `.build` folder is still scanned in full,
since only folders below the scanned path count.

**Effect on existing scores.** A scan that reached `.build` finds fewer
functions, so its baselines hold rows for files that are no longer scanned.
`cc-check` and `crap` baselines of a scan that includes a SwiftPM package root
are re-recorded.

### Rejected

- **Skipping every hidden folder.** Already rejected on 2026-10-09: it hides
  `.claude/hooks`, which agents write.
- **A Swift-only skip list.** `.build` is generated output wherever it appears,
  and the one list is what keeps the two gates and every language counting the
  same way.

## Addendum 2026-10-11: follow symlinked folders (v0.9.0)

Amends: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070)

Amended by: [Addendum 2026-10-12: baseline keys use the real path (v0.9.0)](#addendum-2026-10-12-baseline-keys-use-the-real-path-v090), [Current rule, restated 2026-10-12: baseline keys](#current-rule-restated-2026-10-12-baseline-keys), [Current rule, restated 2026-10-12: symlinked folders](#current-rule-restated-2026-10-12-symlinked-folders)

The limits above are unchanged. The shared walk of the 2026-10-09 addendum did
not follow symlinks, so with `Sources/Shop -> ../shared/Shop` a scan of
`Sources/` returned functions from `Sources/A` only and left the linked folder
out of both gates, silently (#58). A symlinked source folder is source the
project ships, and a gate that covers less than it appears to is the failure
mode these standards guard against.

**The rule.** The walk follows a symlinked folder unless its name is on the skip
list, and never walks the same real folder twice in one scan:

- **Once each, across the whole scan.** A folder's identity, its device and
  inode, is recorded when the walk enters it, including each scanned path
  itself. Path text cannot tell folders apart: on a case-insensitive volume
  `shared/Shop` and `shared/shop` are one folder under two spellings. A folder
  whose identity was already entered is not walked again, which covers a link to an ancestor
  (a loop), two links to one folder, a link beside the real folder, and a folder
  reached from two scanned paths. The second visit is named on the *Skipped N
  folder(s)* line, like a skip-list folder, but marked: `src/Shop (already
  scanned)`. The mark says the folder's files were scanned once, through the
  first visit, so it is not lost source; a skip-list folder carries no mark and
  was not scanned.
- **Which visit wins is fixed.** Among the folders under one parent, real
  folders are entered before links, then by name; the walk is depth first in
  that order. The first visit is scanned, so the same arguments on the same checkout
  always yield the same file names. The order holds among siblings only, and
  scanned paths are entered in the order given, so a different argument order can
  change which spelling a file shows on screen; its baseline key does not change
  (see the addendum "baseline keys use the real path"). A link in an earlier
  subtree (`src/A/link`) reaches a real folder in a later one (`src/Z/real`)
  first, so the files are named by the link path and the real folder is the one
  marked already scanned.
- **File names on screen keep the link path as scanned.** A file reached through
  a link is reported as `Sources/Shop/Shop.swift`, not its real path, and the
  coverage readers (which already resolve both sides to a real path) still match
  it. The baseline key does not follow this rule: the addendum "baseline keys use
  the real path" overrides the triage default of #58 that keys follow the typed
  path.
- **The skip list still applies by name.** A link called `build` is skipped and
  named, as a real folder of that name would be. A link to a folder that does not
  exist is ignored. A scanned path that is itself a link is followed.
- **The skip list checks a link's own name, not its target.** A link into
  `node_modules` or `.build`, or to a parent folder, is followed, and so widens
  the scan. Name such a link on the skip list or remove it.

**Effect on existing scores.** A repo with a symlinked source folder gains the
functions in it, so a crap or cc baseline recorded before may lack their rows
and is re-recorded. A repo with no such links scans as before. A scan given
overlapping folders (`src src/pkg`) used to list the inner folder's functions
twice, the second copy numbered `#2`; it now lists them once and marks the
repeat as already scanned. Only folders are deduplicated: the same file named
twice on the command line, or once inside a folder that is also scanned, is
still listed twice.

### Rejected

- **Not following links.** It leaves shipped source out of the gates without a
  word, which is the failure the standards guard against.
- **Following links with no guard.** A link to a parent never ends, and two
  links to one folder double its functions.
- **Reporting the real path of a linked file on screen.** It would rename every
  function in the folder in the report if the link target moves, and the names
  would no longer match what the builder passes on the command line.
- **Counting a repeated visit under its link path as well.** The same function
  would be scored, and baselined, twice.

## Addendum 2026-10-11: the freshness check reads the scan's files (v0.9.0)

Amends: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070)

The limits above are unchanged, and so is what each gate scores. `crap` warns
when the coverage file is older than the newest source file, and
`--strict-freshness` turns the warning into exit 2. That check walked every file
with a dot in its name under each scanned path on its own, so it counted the
folders the scan skips (`node_modules`, `.git`, `.venv`, build output) and the
files of other languages: in a package whose Swift sources were older than the
coverage file, one newer file under `node_modules/` raised *coverage file may be
stale* (#51).

**The rule.** The newest modification time is taken over the source files of the
scan itself: the shared walk, with its skip list and its symlink rule, filtered
to the chosen language's suffixes. `find_sources` returns that list, and
`crap` reads it; there is no second walk and no second copy of the skip rules. A
path given as a single file counts if its suffix is the language's, as it does
for the scan. A file that cannot be read for its time is ignored, as before.

`crap` walks before it checks freshness and counts after it. A missing path is
reported ahead of a stale coverage file, which is reported ahead of a missing
counting tool, and `--strict-freshness` stops with exit 2 before the counting
tool runs, so a stale report does not pay for the count.

**Effect on existing scores.** None: no function is scored differently. A report
that was called stale only because of a skipped folder or another language no
longer is, so any workaround for that false warning can go. A newer source file of the
chosen language still makes the report stale, with and without the flag. No
baseline is re-recorded for this change.

### Rejected

- **Keeping a freshness walk with a copy of the skip list.** The two would
  drift; the first fault was that they already had.
- **Comparing against only the files that hold scored functions.** A newer file
  with no function above the minimum CC can still have changed the tests that
  the report was made from, so the check keeps every source file of the language.

## Addendum 2026-10-11: Python end lines from the AST (v0.9.0)

Amends: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070)

The limits above are unchanged, and so is the counting tool: a Python function's
CC is still radon's, and its start line is still radon's. This replaces where
the end line comes from. Radon's `endline` ignores a trailing nested `def` or
`class`, so `def h(x)` whose body ends in a nested `def tail()` scanned as a
range that stopped before `tail`, and method `K.m` ending in a nested `class
Inner` stopped before `Inner`. `crap` reads Python coverage over a function's
line range, so it read the `def` line alone, which always runs, and scored a
function with an untested branch as fully covered (#59).

**The rule.** Every Python Function's end line is the `end_lineno` of its AST
node (Python 3.8 and later, so inside the 3.9 floor). The node is found by the
same `(name, line, column)` key the scan already uses to index function nodes, so
methods, closures and functions in nested classes get the rule alike. A node
is looked up without a fallback, since radon and the scan read the same tree. The
nested function or class is still scored on its own range, inside the holder's.

**Effect on existing scores.** CC and `cc-check` are unchanged. A Python
function that ends in a nested `def` or `class` is now measured over its whole
body, so its coverage can fall and its CRAP score can rise, past the threshold
for a function with untested code before the nested definition. A crap baseline
that holds such a function may hold a lower score than it now earns and is
re-recorded. Functions that do not end in a nested definition keep their scores.
The closing lines of a multi-line last statement (a closing bracket, the tail of
a multi-line string) now fall inside the range, and coverage.py counts no
statement there.

### Rejected

- **Patching radon's `endline` with the largest end line among the function's
  closures and nested classes.** It repeats in a second place what the AST
  already states, and needs a rule for each kind of statement that can close a
  body.
- **Taking the start line from the AST too.** Start lines stay radon's, so
  baseline keys and the `#N` labels do not move.

## Addendum 2026-10-12: baseline keys use the real path (v0.9.0)

Amends: [Addendum 2026-10-04: the baseline ratchet (v0.3.0)](#addendum-2026-10-04-the-baseline-ratchet-v030), [Addendum 2026-10-11: follow symlinked folders (v0.9.0)](#addendum-2026-10-11-follow-symlinked-folders-v090)

Amended by: [Current rule, restated 2026-10-12: baseline keys](#current-rule-restated-2026-10-12-baseline-keys), [Current rule, restated 2026-10-12: symlinked folders](#current-rule-restated-2026-10-12-symlinked-folders)

The limits above are unchanged. This amends one rule of the addendum "follow
symlinked folders", which took the triage default of #58 that baseline keys
follow the path the builder typed. Review of that rule found two faults that
share one cause, rebuilding a key from typed path text:

- Typing the scanned folder through a symlinked prefix (`crap "$PWD/src"` with a
  logical `$PWD`, a CI workspace that is a symlink, `/tmp` on macOS) flipped
  every key behind a link back to a real path, so the ratchet reported those
  functions as new.
- Argument order changed the keys: with `src/app` a link to `src/real`,
  `crap src/app src` keyed the files `src/app/x.py` and `crap src` keyed them
  `src/real/x.py`.

The builder chose, on #72 (2026-10-11), to key by the real path as every release
before 0.9.0 did. This overrides the triage default of #58.

**The rule.** A baseline key is the file's real path relative to the real path of
the repo root, followed by `::` and the function name: symlinks are resolved and
a `..` step lands where it really lands, so `src/Shop/../up.py` is keyed by the
folder `src/Shop` links to, not by `src`. One file gets one key whatever spelling
or argument order reached it. File names on screen, in the table and in `--json`,
keep the link path as scanned.

**The real path has the case stored on disk.** On a case-insensitive volume a
link keeps its own spelling when resolved, so `pa/x -> ../shared/Shop` and
`pb/x -> ../shared/shop` would key one file two ways, and one run would miss the
coverage the other found. On macOS the real path is therefore read back from the
filesystem (`F_GETPATH`), which gives `shared/Shop`; elsewhere, or when that read
fails, it is the resolved path. The key and every coverage reader (coverage.json,
Istanbul, llvm-cov, xccov) use the same function.

**A link to a folder outside the repo** gives a key that starts with `../` and
depends on where that folder sits relative to the repo on each machine. A
checkout whose shared folder lies elsewhere sees those functions as new and their
old rows as paid. This is accepted: such links are rare, and the alternative
(below) fails more often.

**Effect on existing scores.** A file that no link reaches keeps the key it had
before 0.9.0, and so does a scanned path that is itself a link, with one
exception: on macOS, a gate run with a path typed in a different case from the
one on disk gets true-case keys from 0.9.0. A baseline recorded that way before
0.9.0 must be recorded once more (delete it, then run with `--update`).
Functions behind a symlinked folder came into the scan with v0.9.0 and are
recorded under their real path when the baseline is re-recorded. No release
carried link-path keys.

### Rejected

- **Keeping link-path keys and patching the triggers** (walk up the typed path to
  find the repo root, mark every typed folder as seen before the walk). The class
  of fault had already come back once in other words, and every way of typing a
  path would stay a possible new trigger.
- **Releasing #54, #51 and #59 without #58.** It is the fastest route, but a
  symlinked source folder would stay unscanned.

## Addendum 2026-10-12: the `(set)` rule no longer depends on the word before it, except `init` (v0.9.1)

Amends: [Addendum 2026-10-11: a workaround for two lizard Swift bugs (v0.8.3)](#addendum-2026-10-11-a-workaround-for-two-lizard-swift-bugs-v083)

Amended by: [Current rule, restated 2026-10-12: the lizard Swift workaround](#current-rule-restated-2026-10-12-the-lizard-swift-workaround), [Addendum 2026-10-22: lizard 1.24.2 is the floor and the Swift workaround is gone (v0.11.0)](#addendum-2026-10-22-lizard-1242-is-the-floor-and-the-swift-workaround-is-gone-v0110), [Current rule, restated 2026-10-22: how lizard reads Swift](#current-rule-restated-2026-10-22-how-lizard-reads-swift)

The limits and the counting tool are unchanged. The v0.8.3 workaround dropped
`(set)` only straight after `private`, `fileprivate`, `internal` or `public`.
The builder decided (2026-10-11, #89) to widen it now rather than wait for a
lizard release (#71) or copy the ~160-line reader rewrite on lizard's master
(commits 2d38691 and 4af401c).

**The rule.** In the token stream, when a `)` arrives and the last three
significant tokens are `(`, `set`, `)`, those three are dropped, whatever word
comes before them, except `init`. Whitespace, newline and comment (`//`, `/*`)
tokens are skipped when looking for the significant ones. Only the three
significant tokens are deleted: every newline and comment token stays, so no
later line number moves. This covers `package(set)`, a comment between the
modifier and `(set)`, and a line break inside the parens (`private(\n set)`). It
also drops a `(set)` that follows any other word, such as `foo(set)` with a
local or parameter named `set`, which opened the same fake `set` Function.

**The `init` exception.** `.init(set)`, `self.init(set)` and `super.init(set)`
keep their tokens, which is how lizard master reads them. Master takes such a
call for an initialiser declaration, so the function after it, or the rest of
the convenience initialiser, scores as part of an `init` row. Dropping the
tokens instead would make results differ from master here, and master is the
reference.

**Checked against lizard master.** lizard master 9a63062 and the workaround
give the same function names, start and end lines and CCN on `package(set) var
x = 0` then `init() {}`, on `private /* why */ (set) var z`, on `private(\n
set)`, on a function with one `if` after a wrapped `private(\n set)` (lines
5-7, CCN 2), on `let x: Foo = .init(set)` at type scope, on `self.init(set)`
inside a convenience initialiser, and on `let t = foo(set)` inside a function
with an `if`.

**Not covered.**
- A bare `set` word that is not inside `(set)`: a local, parameter or property
  named `set` used as `max(set, 1)` or `set.count`, or a label as in
  `g(set: 1)`. Each still opens a `set` Function, which takes the `{...}` after
  it and moves the enclosing function's CC into that row. A property declared
  `static let set = 1` opens none until it is used this way. lizard master does
  not open the row, so this gap ends when the lizard floor reaches a release
  with its fix (#71).
- `.init(set)`, `self.init(set)` and `super.init(set)`: the next function scores
  as part of an `init` row, in the workaround and in lizard master alike. So does
  `Foo.init(set)` inside a function body, where the row takes the enclosing
  function's `if`s.

Fixing the first needs lizard's deeper reader rewrite. Both are rare.

**Effect on existing scores.** A Swift project sees rows move if it wrote
`package(set)`, put a comment or line break before or inside `(set)`, or passes
a local or parameter named `set` to a call (`foo(set)`, or `foo(\n set\n)`). A
`set` row disappears and the code after it is scored under its own name, as
lizard master does. A crap baseline that holds such a `set` entry, or lacks the
row for a declaration that was swallowed, is stale and is re-recorded. Python
and TypeScript scans are unchanged.

## Addendum 2026-10-12: a closure outside any function is not scored (v0.10.1)

Amends: [Addendum 2026-10-11: a review rule covers the closure gap (v0.8.4)](#addendum-2026-10-11-a-review-rule-covers-the-closure-gap-v084)

The closure bullet above assumes a function holds the closure. A closure that
no function holds, such as a file-scope closure, a stored-property closure or a
`lazy var` closure, is not scored by any gate: `crap --lang swift` reports "no
functions analysed" for it. The review rule covers it all the same, so a
consumer loses nothing today. No threshold, counting tool or gate scope
changes.


## Addendum 2026-10-22: lizard 1.24.2 is the floor and the Swift workaround is gone (v0.11.0)

Amends: [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08), [Addendum 2026-10-11: a workaround for two lizard Swift bugs (v0.8.3)](#addendum-2026-10-11-a-workaround-for-two-lizard-swift-bugs-v083), [Addendum 2026-10-12: the `(set)` rule no longer depends on the word before it, except `init` (v0.9.1)](#addendum-2026-10-12-the-set-rule-no-longer-depends-on-the-word-before-it-except-init-v091), [Current rule, restated 2026-10-12: TypeScript's known miscount](#current-rule-restated-2026-10-12-typescripts-known-miscount)

Amended by: [Current rule, restated 2026-10-22: TypeScript and JavaScript counting](#current-rule-restated-2026-10-22-typescript-and-javascript-counting), [Current rule, restated 2026-10-22: how lizard reads Swift](#current-rule-restated-2026-10-22-how-lizard-reads-swift)

lizard 1.24.2 (released 2026-10-22) fixes terryyin/lizard#516 and reads Swift
better than the workaround did. The lizard floor in `pyproject.toml` is now
1.24.2, the workaround module and its rewriting are deleted, and a Swift scan
runs plain `lizard`, as a TypeScript scan does (#71, #89, #108). The limits are
unchanged; the counting tool is the same, at a newer floor.

**Swift, against the fixtures the workaround was tested on.** 1.24.2 with no
correction gives the rows lizard master 9a63062 gave for every case the
workaround covered, and also reads correctly the cases the workaround and master
both got wrong:

- `.init(set)`, `self.init(set)`, `super.init(set)` and `Foo.init(set)` are
  calls. The function after one, or the one holding it, keeps its own row and
  CC instead of scoring as part of an `init` row.
- A bare `set` word (`max(set, 1)`, `set.count`, `g(set: 1)`) opens no `set`
  Function.

The release also tokenizes Swift macros such as `#Preview` so their braces
count, scans raw, multi-line and interpolated strings and nested block comments
as single tokens, and stops `.type` and `type(of:)` from reading as a type
declaration. Each of these can move a Swift function's lines or CC.

**TypeScript and JavaScript counting changes with the release.** The builder
chose to take it as lizard counts it, over capping lizard at 1.24.1 or patching
the default-value count back out:

- `??` and `??=` count one path each, not two. The known miscount is gone, and
  scores that held it go down.
- Each default parameter, and each default inside a destructuring pattern,
  counts one path. `function f(a = 1, b = 2)` is CC 3. Scores with defaults go
  up, and a function near 8 may now fail.
- Optional chaining (`?.`) still counts nothing.
- An unnamed function inside an array literal, as in
  `const p = [function () {}]`, is named `(anonymous)`, not `p`, which is the
  name every other unnamed callback already had.

Python is unaffected: radon counts it.

**Why now.** The old floor was `lizard>=1.17` with no cap, so any project
installing quality-gates fresh already ran 1.24.2 and its counts. Raising the
floor makes every install count the same way and lets the workaround go.

Rejected:
- Capping lizard below 1.24.2. It freezes today's scores, but keeps the
  workaround, its known gaps and the `??` miscount, and the same decision comes
  back with the next release.
- Taking 1.24.2 but not counting default values. That is a new patch on
  lizard's TypeScript reader, the kind of workaround this release lets us
  delete.

**Effect on existing scores.** A Swift baseline may gain rows for functions
that a `.init(set)` call or a bare `set` used to swallow, and lose `init` or
`set` rows that held them. A TypeScript baseline may see scores fall where `??`
is used and rise where defaults are used, and a function in an array literal
changes key from its holder's name to `(anonymous)`. Re-record both baselines
when bumping the pin, and fix or baseline any function that newly fails.

## Current rule, restated 2026-10-12: the complexity ceiling

Amends: [Decision](#decision), [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08)

<!-- rule:complexity-ceiling -->
**Agent-written code has a cyclomatic complexity ceiling of 8.** Human-maintained
code targets 5. Agents keep exact short-term memory, so some of the cognitive
load that drives the human limit does not apply (Robert C. Martin, interviewed
2026-09-06).

| Language | Gate | Tool | Limit |
|---|---|---|---|
| Python | CC | `cc-check` (radon) | fail above 8 |
| TypeScript, JavaScript | CC | `cc-check --lang typescript` (lizard) | fail above 8 |
| Swift | CC | SwiftLint `cyclomatic_complexity`, `ignores_case_statements: true` | warn above 6, fail above 8 |
| Rust | Cognitive complexity | `cargo clippy` | fail above 10; function length fail above 25 lines |
| Python, TypeScript, JavaScript, Swift | CRAP | `crap` | warn above 5, fail above 8 |

**Python CC is counted by radon, not ruff,** because CRAP counts with radon. With
one counter, a fully covered function's CRAP equals its CC, so the CC ceiling and
the CRAP ceiling meet at the same point: CC 8 passes CRAP only at 100% coverage.

**Swift ignores `switch` cases.** An exhaustive `switch` over an enum is flat and
readable at any length, and Swift requires every case to be listed. Counting each
case pushed idiomatic Swift above the limit for no gain in risk. `guard let` and
`if let` still count.

**Rust's 10 is a different measure,** not a looser one. Cognitive complexity
penalises nesting and ignores flat `match` arms. Do not align it with the CC
numbers.

**CRAP is a gate only with coverage data.** Without it every function scores
CC² + CC, which fails at CC 3. `crap --no-coverage` is a worst-case report, read
for the ranking, never a pass/fail result. A coverage flag that is given must
work: an empty or whitespace-only path, a missing file, a file that is not UTF-8
or one that is not valid JSON is a tool error (exit 2) naming the problem, never
a quiet fall back to the worst-case ranking. A function the report holds no
usable figure for has unknown coverage and scores worst case, so the gate fails
safe. When a report was given, at least one function was scored and none got a
figure, `crap` also prints a line to stderr saying the report may have been made
elsewhere or hold no figures for the scanned files.

**A project may tighten these limits, never loosen them.**
<!-- /rule:complexity-ceiling -->

## Current rule, restated 2026-10-12: the baseline ratchet

Amends: [Addendum 2026-10-04: the baseline ratchet (v0.3.0)](#addendum-2026-10-04-the-baseline-ratchet-v030)

<!-- rule:baseline-ratchet -->
`cc-check` and `crap` take `--baseline`, so a repo with existing debt can
enforce the limits in CI without first paying it all off.

- **Only functions over the threshold are recorded.** A function that drops to
  the threshold leaves the baseline at the next `--update`, and cannot return.
- **A missing baseline is an error, except with `--update`.** Treating it as
  empty would fail every adopting repo on its first run; treating it as
  permissive would let a mistyped path pass CI.
- **CRAP baselines need coverage,** because CRAP without coverage is a ranking,
  not a gate.
<!-- /rule:baseline-ratchet -->

## Current rule, restated 2026-10-12: baseline keys

Amends: [Addendum 2026-10-04: the baseline ratchet (v0.3.0)](#addendum-2026-10-04-the-baseline-ratchet-v030), [Addendum 2026-10-11: follow symlinked folders (v0.9.0)](#addendum-2026-10-11-follow-symlinked-folders-v090), [Addendum 2026-10-12: baseline keys use the real path (v0.9.0)](#addendum-2026-10-12-baseline-keys-use-the-real-path-v090)

<!-- rule:baseline-keys -->
**The rule.** A baseline key is the file's real path relative to the real path of
the repo root (the working directory outside a git repo), followed by `::` and
the function name, with a method as `Class.method`. Symlinks are resolved and a
`..` step lands where it really lands, so `src/Shop/../up.py` is keyed by the
folder `src/Shop` links to, not by `src`. One file gets one key whatever spelling
or argument order reached it. File names on screen, in the table and in `--json`,
keep the link path as scanned.

**A key carries no line number,** so editing elsewhere in the file does not move
it. A renamed or moved function counts as new, so debt cannot be laundered by
renaming.

**The real path has the case stored on disk.** On a case-insensitive volume a
link keeps its own spelling when resolved, so `pa/x -> ../shared/Shop` and
`pb/x -> ../shared/shop` would key one file two ways, and one run would miss the
coverage the other found. On macOS the real path is therefore read back from the
filesystem (`F_GETPATH`), which gives `shared/Shop`; elsewhere, or when that read
fails, it is the resolved path. The key and every coverage reader (coverage.json,
Istanbul, llvm-cov, xccov) use the same function.

**A link to a folder outside the repo** gives a key that starts with `../` and
depends on where that folder sits relative to the repo on each machine. A
checkout whose shared folder lies elsewhere sees those functions as new and their
old rows as paid. This is accepted: such links are rare, and the alternative,
keeping link-path keys and patching each way a path can be typed, fails more
often.
<!-- /rule:baseline-keys -->

## Current rule, restated 2026-10-12: TypeScript and JavaScript counting

Amends: [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08), [Addendum 2026-10-10: the suffix list (v0.7.4)](#addendum-2026-10-10-the-suffix-list-v074)

Amended by: [Current rule, restated 2026-10-22: TypeScript and JavaScript counting](#current-rule-restated-2026-10-22-typescript-and-javascript-counting)

**TypeScript and JavaScript are the files ending in `.ts`, `.tsx`, `.js`, `.jsx`,
`.cjs` and `.mjs`.** `languages.py` holds that list, and the `--help` text of
`crap` and `cc-check` prints it from there.

**lizard counts both gates,** for the reason radon counts both for Python: with
one counter a fully covered function's CRAP equals its CC, so the ceilings meet
at 8. On test functions lizard agrees with a hand count for `if`, loops, `case`,
`catch`, `&&`, `||` and `?:`, and gives a nested arrow function its own score.

**`switch` cases count.** Swift is exempt because its compiler requires an
exhaustive `switch`; TypeScript does not, so each `case` is a path that can go
untested. lizard runs without `-m`.

## Current rule, restated 2026-10-12: TypeScript's known miscount

Amends: [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08)

Amended by: [Addendum 2026-10-22: lizard 1.24.2 is the floor and the Swift workaround is gone (v0.11.0)](#addendum-2026-10-22-lizard-1242-is-the-floor-and-the-swift-workaround-is-gone-v0110)

**Known miscount:** lizard counts `??` as two paths, not one. That can only
raise a score, so the gate errs strict; it is left as is.

## Current rule, restated 2026-10-12: repeated names

Amends: [Amended 2026-10-08, on acceptance](#amended-2026-10-08-on-acceptance), [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070)

<!-- rule:repeated-names -->
**Repeated names get their order as a suffix in baseline keys,** in every
language: Python, TypeScript, JavaScript and Swift. lizard names a method without
its class and every unnamed callback `(anonymous)`, and the ratchet keeps one
score per key, so a new function could hide behind an old one of the same name.
The second and later functions of a name in a file are keyed `path::name#2`,
`#3`, in order of their start line. A file with no repeated names has no
suffixed keys. Keying by the enclosing named function was rejected: lizard does not
report nesting.
<!-- /rule:repeated-names -->

## Current rule, restated 2026-10-12: what a Function is

Amends: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070)

<!-- rule:function-names -->
**A Function is what is scored:** a function, a method, a closure, or a method
of a nested class, each on its own. Both gates take their Functions from one
scan, so they score the same Functions.

- **Classes are not scored.** A class's radon score is built from its methods,
  which are already scored, so a class could fail for complexity its methods
  report.
- **Python closures and nested-class methods are scored on their own,** with
  names dotted from the outside in: `outer.inner`, `K.Inner.deep`.
- **TypeScript, JavaScript and Swift names stay as lizard gives them,** since
  lizard does not report nesting: a method without its class, and an unnamed
  callback as `(anonymous)`.
- **A repeated name gets its order as a suffix,** `name#2`, `name#3`, in every
  language.
<!-- /rule:function-names -->

## Current rule, restated 2026-10-12: functions that share a start line

Amends: [Addendum 2026-10-10: functions that share a start line (v0.7.3)](#addendum-2026-10-10-functions-that-share-a-start-line-v073)

<!-- rule:shared-start-line -->
A TypeScript or JavaScript Function's lines come from Istanbul's `fnMap`,
matched to lizard by start line, because lizard's end line runs on into the next
declaration when the code has type annotations. lizard gives no column, so in
`const f = () => xs.map(x => x ? 1 : 2)` two functions start on line 1, and the
end line decides which `fnMap` entry each one gets.

**Matching rule.** Among the `fnMap` entries whose declaration starts on
lizard's start line, in this order:

1. the entry whose end line equals lizard's end line;
2. else the narrowest entry whose end line is at or after lizard's end line;
3. else, when no entry contains lizard's end line, the entry on that line that
   ends last. This is the case when lizard's end line runs past the real end
   because of type annotations, as when an `interface` follows the function.

A function that is the only one starting on its line matches the same entry
under all three. Only the end lines of the entries matter, so entries that tie
on end line give the same range.

**The limit that remains.** Coverage is counted by line: a branch or statement
belongs to a function when it starts inside the function's lines. A callback
that shares a line with its holder, or with the function declared beside it,
still counts that line's branches and statements, and the holder still counts
the callback's. The rule fixes the range, not the overlap on a shared line.
Two functions that start and end on the same line get the same coverage.
<!-- /rule:shared-start-line -->

## Current rule, restated 2026-10-12: the lizard Swift workaround

Amends: [Addendum 2026-10-11: a workaround for two lizard Swift bugs (v0.8.3)](#addendum-2026-10-11-a-workaround-for-two-lizard-swift-bugs-v083), [Addendum 2026-10-12: the `(set)` rule no longer depends on the word before it, except `init` (v0.9.1)](#addendum-2026-10-12-the-set-rule-no-longer-depends-on-the-word-before-it-except-init-v091)

Amended by: [Current rule, restated 2026-10-22: how lizard reads Swift](#current-rule-restated-2026-10-22-how-lizard-reads-swift)

lizard 1.24.1, the latest release, misreads two Swift constructs, and the scan
corrects both before lizard's state machine sees them.

- **lizard does not score a failable initialiser.** lizard's tokenizer makes `init?`
  and `init!` single tokens, so they never match `init`. A failable `init?` with
  two `if`s (CC 3) is not reported, and so is never scored.
- **lizard reads `(set)` as a Function named `set`.** The `set` in an access modifier
  (`private(set)`, `package(set)`) or in a call passing a local named `set`
  (`foo(set)`) opens a setter accessor, which takes the next `{...}` as its
  body. The declaration after it, such as `init() {}`, is swallowed into a
  `set` Function and not scored under its own name.

**The workaround.** A Swift scan runs lizard through
`quality_gates.lizard_swift_workaround`, which puts a subclass of lizard's Swift
reader in place and then runs lizard's own command-line entry point; a
TypeScript scan runs plain `lizard`. The subclass rewrites the token stream in
lizard's preprocessing step:

- `init?` and `init!` become `init`. A failable initialiser is then a Function
  named `init` with its own CC and lines; its `?` or `!` is not counted as a
  condition.
- When a `)` arrives and the last three significant tokens are `(`, `set`, `)`,
  those three are dropped, whatever word comes before them, except `init`.
  Whitespace, newline and comment (`//`, `/*`) tokens are skipped when looking
  for the significant ones, so a comment or line break before or inside `(set)`
  makes no difference.

A property's own `get`, `set`, `willSet` and `didSet` blocks are Functions.
Every newline and comment token stays, so line numbers and file paths are those
of the source file, and coverage is matched to the source file's own lines.
Source files on disk are never rewritten. Only the gates' scan is corrected:
running `lizard` directly shows both bugs.

**A failing lizard stops the gate.** lizard's CSV output counts no warnings, so
the scan's lizard run exits 0 however many functions exceed lizard's own warning
limit; the scan also passes `-i -1` in case a lizard release starts counting
them. Any other exit, such as a crash in the workaround when a lizard release
renames what it patches, is a tool error that shows lizard's error output.

**The `init` exception.** `.init(set)`, `self.init(set)` and `super.init(set)`
keep their tokens, which is how lizard's master branch reads them: it takes such
a call for an initialiser declaration, so the function after it, or the rest of
the convenience initialiser, scores as part of an `init` row. Master is the
reference, so the workaround gives the same rows.

**Not covered.**
- A bare `set` word that is not inside `(set)`: a local, parameter or property
  named `set` used as `max(set, 1)` or `set.count`, or a label as in
  `g(set: 1)`. Each still opens a `set` Function, which takes the `{...}` after
  it and moves the enclosing function's CC into that row. A property declared
  `static let set = 1` opens none until it is used this way. lizard master does
  not open the row, so this gap ends when the lizard floor reaches a release
  with its fix.
- `.init(set)`, `self.init(set)` and `super.init(set)`: the next function scores
  as part of an `init` row, in the workaround and in lizard master alike. So does
  `Foo.init(set)` inside a function body, where the row takes the enclosing
  function's `if`s.

**Upstream and removal.** Both bugs are reported as terryyin/lizard#516 and fixed
on lizard's master after 1.24.1; the widened `(set)` rule is quality-gates#89.
The workaround is removed once the lizard floor reaches a release with the fix
(quality-gates#71).

## Current rule, restated 2026-10-12: the skip list

Amends: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070), [Addendum 2026-10-11: skip SwiftPM's .build (v0.9.0)](#addendum-2026-10-11-skip-swiftpms-build-v090)

<!-- rule:skip-list -->
**The skip list** is `.git`, `.venv`, `venv`, `.direnv`, `node_modules`,
`__pycache__`, `backups`, `build`, `.build`, `dist`, `.tox`, `.mypy_cache`,
`.pytest_cache`, `.worktrees`, `.claude/worktrees`. It is one list for both
gates and every language. Every other hidden folder is scanned, so agent-written
hooks in `.claude/hooks` are held to the standard.

An entry matches a folder of that name anywhere below the scanned path, so a
real package called `build` or `dist` is skipped too; for that reason both gates
end their report with a *Skipped N folder(s)* line naming every skipped folder
they found. A folder above the scanned path never counts: a project checked out
under a `build` or `.build` folder is scanned in full, in every language.
<!-- /rule:skip-list -->

## Current rule, restated 2026-10-12: symlinked folders

Amends: [Addendum 2026-10-11: follow symlinked folders (v0.9.0)](#addendum-2026-10-11-follow-symlinked-folders-v090), [Addendum 2026-10-12: baseline keys use the real path (v0.9.0)](#addendum-2026-10-12-baseline-keys-use-the-real-path-v090)

<!-- rule:symlinked-folders -->
**The rule.** The walk follows a symlinked folder unless its name is on the skip
list, and never walks the same real folder twice in one scan:

- **Once each, across the whole scan.** A folder's identity, its device and
  inode, is recorded when the walk enters it, including each scanned path
  itself. Path text cannot tell folders apart: on a case-insensitive volume
  `shared/Shop` and `shared/shop` are one folder under two spellings. A folder
  whose identity was already entered is not walked again, which covers a link to
  an ancestor (a loop), two links to one folder, a link beside the real folder,
  and a folder reached from two scanned paths. The second visit is named on the
  *Skipped N folder(s)* line, like a skip-list folder, but marked: `src/Shop
  (already scanned)`. The mark says the folder's files were scanned once,
  through the first visit, so it is not lost source; a skip-list folder carries
  no mark and was not scanned.
- **Which visit wins is fixed.** Among the folders under one parent, real
  folders are entered before links, then by name; the walk is depth first in
  that order. The first visit is scanned, so the same arguments on the same
  checkout always yield the same file names. The order holds among siblings
  only, and scanned paths are entered in the order given, so a different
  argument order can change which spelling a file shows on screen; its baseline
  key does not change. A link in an earlier subtree (`src/A/link`) reaches a real
  folder in a later one (`src/Z/real`) first, so the files are named by the link
  path and the real folder is the one marked already scanned.
- **File names on screen keep the link path as scanned.** A file reached through
  a link is reported as `Sources/Shop/Shop.swift`, not its real path, and the
  coverage readers (which resolve both sides to a real path) still match it. The
  baseline key does not follow this rule: it is the file's real path.
- **The skip list still applies by name.** A link called `build` is skipped and
  named, as a real folder of that name would be. A link to a folder that does not
  exist is ignored. A scanned path that is itself a link is followed.
- **The skip list checks a link's own name, not its target.** A link into
  `node_modules` or `.build`, or to a parent folder, is followed, and so widens
  the scan. Name such a link on the skip list or remove it.
- **Only folders are deduplicated.** A scan given overlapping folders
  (`src src/pkg`) lists the inner folder's functions once and marks the repeat
  as already scanned. The same file named twice on the command line, or once
  inside a folder that is also scanned, is listed twice.
<!-- /rule:symlinked-folders -->

## Current rule, restated 2026-10-22: TypeScript and JavaScript counting

Amends: [Addendum 2026-10-07: TypeScript and JavaScript (accepted 2026-10-08)](#addendum-2026-10-07-typescript-and-javascript-accepted-2026-10-08), [Addendum 2026-10-22: lizard 1.24.2 is the floor and the Swift workaround is gone (v0.11.0)](#addendum-2026-10-22-lizard-1242-is-the-floor-and-the-swift-workaround-is-gone-v0110), [Current rule, restated 2026-10-12: TypeScript and JavaScript counting](#current-rule-restated-2026-10-12-typescript-and-javascript-counting)

<!-- rule:typescript-counting -->
**TypeScript and JavaScript are the files ending in `.ts`, `.tsx`, `.js`, `.jsx`,
`.cjs` and `.mjs`.** `languages.py` holds that list, and the `--help` text of
`crap` and `cc-check` prints it from there.

**lizard counts both gates,** at 1.24.2 or newer, for the reason radon counts
both for Python: with one counter a fully covered function's CRAP equals its CC,
so the ceilings meet at 8. Each `if`, loop, `case`, `catch`, `&&`, `||`, `??`,
`??=` and `?:` counts one path, and a nested arrow function gets its own score.
Optional chaining (`?.`) counts nothing.

**Default values count.** Each default parameter, and each default inside a
destructuring pattern, counts one path: `function f(a = 1, b = 2)` is CC 3, and
`function f({ a = 1 } = {})` is CC 3.

**`switch` cases count.** Swift is exempt because its compiler requires an
exhaustive `switch`; TypeScript does not, so each `case` is a path that can go
untested. lizard runs without `-m`.
<!-- /rule:typescript-counting -->

## Current rule, restated 2026-10-22: how lizard reads Swift

Amends: [Addendum 2026-10-11: a workaround for two lizard Swift bugs (v0.8.3)](#addendum-2026-10-11-a-workaround-for-two-lizard-swift-bugs-v083), [Addendum 2026-10-12: the `(set)` rule no longer depends on the word before it, except `init` (v0.9.1)](#addendum-2026-10-12-the-set-rule-no-longer-depends-on-the-word-before-it-except-init-v091), [Addendum 2026-10-22: lizard 1.24.2 is the floor and the Swift workaround is gone (v0.11.0)](#addendum-2026-10-22-lizard-1242-is-the-floor-and-the-swift-workaround-is-gone-v0110), [Current rule, restated 2026-10-12: the lizard Swift workaround](#current-rule-restated-2026-10-12-the-lizard-swift-workaround)

<!-- rule:swift-reading -->
**A Swift scan runs plain `lizard`, at 1.24.2 or newer, with no correction.**
That release reads these Swift constructs as follows:

- A failable initialiser, `init?` or `init!`, is a Function named `init` with
  its own CC and lines; its `?` or `!` is not counted as a condition.
- `set` opens a Function only as a property's own accessor block. An access
  modifier (`private(set)`, `package(set)`, with a comment or line break before
  or inside the parens), a value named `set` (`foo(set)`, `max(set, 1)`,
  `set.count`) and a label (`g(set: 1)`) open none.
- A call to an initialiser, `.init(...)`, `self.init(...)`, `super.init(...)`
  or `Foo.init(...)`, is a call, not a declaration, so the function holding it
  and the one after it each keep their own row and CC.

A property's own `get`, `set`, `willSet` and `didSet` blocks are Functions.

**A failing lizard stops the gate.** lizard's CSV output counts no warnings, so
the scan's lizard run exits 0 however many functions exceed lizard's own warning
limit; the scan also passes `-i -1` in case a lizard release starts counting
them. Any other exit is a tool error that shows lizard's error output.
<!-- /rule:swift-reading -->
