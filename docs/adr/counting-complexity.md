# How complexity is counted

Read this when you change a limit, a counter, how a function is found or
named, or how `crap` reads coverage, or when a score looks wrong for one
language.

## The complexity ceiling

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
work: an empty or whitespace-only path, a missing file, a file that is not UTF-8,
one that is not valid JSON, or one whose JSON has the wrong shape is a tool error
(exit 2) naming the problem, never a quiet fall back to the worst-case ranking.

**A function the report holds no usable figure for is unmeasured,** whether the
report never saw its file or the reader cannot place it in a file it did see. An
unmeasured function is graded `UNMEASURED` and gets no CRAP score, so a gap in
measuring never reads as untested code. It still fails the gate (exit 1), so the
gate fails safe: measure the file, or take it out of the scan. The table shows
`—` for its score, and the summary counts unmeasured functions and names their
files. In `--json` the function has `"crap": null` and the report lists the files
under `"unmeasured"`. When a report was given, at least one function was scored
and none got a figure, `crap` also prints a line to stderr saying the report may
have been made elsewhere or hold no figures for the scanned files.

**A project may tighten these limits, never loosen them.**
<!-- /rule:complexity-ceiling -->

## What a function is

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

## Repeated names

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

## Functions that share a start line

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

## TypeScript and JavaScript counting

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

## How lizard reads Swift

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

## Decisions behind these rules

- **One counter per measure.** Python CC is counted by radon because `crap`
  counts with radon, so a fully covered function's CRAP equals its CC and the
  two ceilings meet at 8. ([ADR-001 § Decision](archive/ADR-001-complexity-standards.md#decision))
- **CRAP is a gate only with coverage data.** `crap --no-coverage` is a
  worst-case ranking, never a result. A function the report holds no figure
  for is `UNMEASURED` and fails, rather than scoring worst case.
  ([ADR-001 addendum 2026-10-25](archive/ADR-001-complexity-standards.md#addendum-2026-10-25-unmeasured-functions-v0120))
- **A project may tighten these limits, never loosen them,** until recorded
  loosening ships (see [Baselines and loosening](baselines-and-loosening.md)).
- **Decided, not built yet: one matcher pairs scanned functions with coverage
  entries,** in source order, so line drift is absorbed and no figure is lent
  to a neighbour. Readers only parse. ([ADR-011 § 4](archive/ADR-011-code-structure.md#4-coverage-matching-in-one-place))

## Not folded in yet

These ADR-001 addenda hold coverage-reader details that no rule above restates
yet. Until they are folded in, read them in the archive:
[the suffix list](archive/ADR-001-complexity-standards.md#addendum-2026-10-10-the-suffix-list-v074),
[SwiftPM coverage](archive/ADR-001-complexity-standards.md#addendum-2026-10-10-swiftpm-coverage-v080),
[coverage readers fail loudly](archive/ADR-001-complexity-standards.md#addendum-2026-10-11-coverage-readers-fail-loudly-v081),
[xccov matches exact paths](archive/ADR-001-complexity-standards.md#addendum-2026-10-11-xccov-matches-exact-paths-v082),
[a review rule covers the closure gap](archive/ADR-001-complexity-standards.md#addendum-2026-10-11-a-review-rule-covers-the-closure-gap-v084),
[the freshness check reads the scan's files](archive/ADR-001-complexity-standards.md#addendum-2026-10-11-the-freshness-check-reads-the-scans-files-v090),
[Python end lines from the AST](archive/ADR-001-complexity-standards.md#addendum-2026-10-11-python-end-lines-from-the-ast-v090),
[a closure outside any function is not scored](archive/ADR-001-complexity-standards.md#addendum-2026-10-12-a-closure-outside-any-function-is-not-scored-v0101).
