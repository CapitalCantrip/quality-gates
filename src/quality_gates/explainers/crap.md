# Risk gate: complexity without tests

## What it catches

Functions that are both tangled and untested. A tangled function has many routes through it: every choice in its code, such as an `if` or a loop, opens another route, and each route is a place a bug can hide. Untested means no test runs along those routes. The gate scores each function on both at once, and a score above 8 fails.

A function with two routes passes even with no tests, because few routes can go wrong. A function with three or more routes fails with no tests. A function with more than eight routes fails even when every route is tested.

## Why it matters

Bugs gather where the code is hardest to follow and nothing has checked it. Tangled code that is well tested has been checked along its routes; simple code without tests has few routes to go wrong. The two together are where a bug sits unnoticed until a user finds it.

A coverage percentage on its own does not say whether the tests are any good, so the gate reads the tangle as well as the coverage.

## What it asks of you

A failing function needs one of two fixes. If it has many routes, split it into smaller functions, which need fewer tests to pass. If it has few routes but little testing, add tests that run each route. A function with more than eight routes must be split, because no amount of testing brings it under the limit.

The gate reads a coverage report from a test run, so run the tests with coverage before the gate. Functions that already failed when the gate was adopted are recorded with their scores in `crap-baseline.json`. The gate fails any new failing function and any score that has got worse. When a score improves, record the better score with the gate's update option; that option never raises a recorded score.

## Want to go deeper?

- [Test Coverage, Martin Fowler](https://martinfowler.com/bliki/TestCoverage.html): why a coverage percentage is a poor target on its own, which is why this gate reads the tangle too. Checked 2026-11-01.
- [Cyclomatic Complexity, radon documentation](https://radon.readthedocs.io/en/latest/intro.html): how the tangle count is made, one for each place the code can branch. Checked 2026-11-01.
