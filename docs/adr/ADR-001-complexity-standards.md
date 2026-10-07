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

## Addendum 2026-10-07: TypeScript and JavaScript (proposed)

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
