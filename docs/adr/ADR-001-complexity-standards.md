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

The standards above extend to `.ts`, `.tsx`, `.js` and `.jsx`. Nothing changes
for Python, Swift or Rust.

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
3. else the first entry on that line, which is what 0.7.2 did, and the case
   when lizard's end line runs past the real end because of type annotations.

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
  position.** It would remove the shared-line overlap, but needs columns on
  the lizard side, which do not exist.
