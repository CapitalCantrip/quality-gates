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

## Addendum 2026-10-11: skip SwiftPM's .build (v0.9.0)

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

The limits above are unchanged. The shared walk of the 2026-10-09 addendum did
not follow symlinks, so with `Sources/Shop -> ../shared/Shop` a scan of
`Sources/` returned functions from `Sources/A` only and left the linked folder
out of both gates, silently (#58). A symlinked source folder is source the
project ships, and a gate that covers less than it appears to is the failure
mode these standards guard against.

**The rule.** The walk follows a symlinked folder unless its name is on the skip
list, and never walks the same real folder twice in one scan:

- **Once each, across the whole scan.** A folder's real path is recorded when the
  walk enters it, including each scanned path itself. A folder whose real path
  was already entered is not walked again, which covers a link to an ancestor
  (a loop), two links to one folder, a link beside the real folder, and a folder
  reached from two scanned paths. The second visit is named on the *Skipped N
  folder(s)* line, like a skip-list folder.
- **Which visit wins is fixed.** Among the folders under one parent, real
  folders are entered before links, then by name; the walk is depth first in
  that order. The first visit is scanned, so the same checkout always yields the
  same file names.
- **File names keep the link path as scanned.** A file reached through a link is
  reported as `Sources/Shop/Shop.swift`, not its real path, so a baseline key
  follows what the builder typed, and the coverage readers (which already resolve
  both sides to a real path) still match it.
- **The skip list still applies by name.** A link called `build` is skipped and
  named, as a real folder of that name would be. A link to a folder that does not
  exist is ignored. A scanned path that is itself a link is followed.

**Effect on existing scores.** A repo with a symlinked source folder gains the
functions in it, so a crap or cc baseline recorded before may lack their rows
and is re-recorded. A repo with no such links scans as before. A scan given
overlapping paths (`src src/pkg`) used to list the inner folder's functions
twice, the second copy numbered `#2`; it now lists them once and names the
repeat as skipped.

### Rejected

- **Not following links.** It leaves shipped source out of the gates without a
  word, which is the failure the standards guard against.
- **Following links with no guard.** A link to a parent never ends, and two
  links to one folder double its functions.
- **Reporting the real path of a linked file.** It would rename every
  function in the folder if the link target moves, and baseline keys would no
  longer match what the builder passes on the command line.
- **Counting a repeated visit under its link path as well.** The same function
  would be scored, and baselined, twice.

## Addendum 2026-10-11: the freshness check reads the scan's files (v0.9.0)

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
to the chosen language's suffixes. The scan returns that list as `sources`, and
`crap` reads it; there is no second walk and no second copy of the skip rules. A
path given as a single file counts if its suffix is the language's, as it does
for the scan. A file that cannot be read for its time is ignored, as before.

`crap` now scans before it checks freshness, so a scan error (a missing path, a
missing tool) is reported ahead of a stale coverage file, and with
`--strict-freshness` the counting tool runs even when the file turns out stale.

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
