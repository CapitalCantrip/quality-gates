# Telling Swift default-argument closures apart from functions

`crap --llvm-cov-json` does not try to recognise a closure or autoclosure
default argument (`completion: (Int) -> Void = { _ in }`, `on: Bool = a && b`)
from llvm-cov's mangled names. When such a default argument ends on the line
where its function's `{` opens, the function gets unknown coverage and scores
worst case.

## Why this is out of scope

The result fails safe: the worst a consumer sees is a false FAIL, never a
hidden one. The remedy is one line: put the default argument on a line above
the `{`. ADR-001's *SwiftPM coverage (v0.8.0)* addendum records both the limit
and the remedy.

Recognising these records would mean reading llvm-cov's mangled names (the
`fA<n>_` marker, as in `...tFfA0_yycfU_`), which the same addendum rejected as
a matching strategy, and it needs a real-build fixture to pin. The builder
judged that cost too high for an unusual coding style with a one-line fix.

Revisit if a consumer keeps hitting it.

## Prior requests

- #68: "llvm-cov-json: recognise default-argument records by their mangled name"
