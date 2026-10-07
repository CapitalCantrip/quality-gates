# Mutation-testing tools for Python, TypeScript, Rust and Swift

Research for ticket #23, a child of the wayfinder map #22. Run on 2026-10-07 in a Linux cloud container (4 cores, 15 GB).

The question: which mutation-testing tool would each language's gate wrap, and is each one fast and machine-readable enough to be a gate?

## How to read this

Every figure is labelled one of two ways.

- **Measured**: I ran it and timed it here. The command, the target and the version are given.
- **Read**: taken from the tool's documentation, its package metadata or its source. I did not run it. Where a "read" claim came through a summarising fetch tool and not from the source, it says so.

Nothing is stated as measured that was not. The gaps are listed in [What was not measured](#what-was-not-measured).

## Answer in one table

| | Python | TypeScript | Rust | Swift |
|---|---|---|---|---|
| Tool to wrap | mutmut (cosmic-ray as the fallback) | StrykerJS | cargo-mutants | Muter |
| Evidence | measured on this repo | measured on a small public repo | measured on LocalBar's `localbar-core` | read only |
| Scope to changed code | by file, by function-name glob | by file and line range, and an incremental file | by diff (`--in-diff`), by file, by regex | by file glob (`--files-to-mutate`) |
| Per-function score | derivable from mutmut's `.meta` files | no, per-mutant line spans only | yes, function name and span on every mutant | no, per-mutant file and line only |
| Equivalent-mutant mark | comment, `# pragma: no mutate` | comment, `// Stryker disable` | attribute needing a crate, or a config regex with no code change | comment, `// muter:disable` |
| Gate shape that fits | commit on one function, ticket on a file, CI nightly on the package | ticket and CI, with the checker off at commit | ticket on a diff, CI on the package | unproven |

Headline recommendation per language:

- **Python: mutmut**, pinned to 3.3.1 on Python 3.9. On the same file and test suite it finished in 16 s on four workers, where cosmic-ray took 184 s on one (different mutant counts, 171 and 90). cosmic-ray is the fallback if the gate needs the newest release on 3.9, a documented JSON dump, or a built-in git-diff filter.
- **TypeScript: StrykerJS.** It is the only serious candidate. It works, but two version combinations fail, one of them silently (see [StrykerJS](#strykerjs)). The gate must pin versions and check that the score is plausible.
- **Rust: cargo-mutants.** The strongest fit of the five. Per-function output, a diff mode and a config-only way to mark equivalent mutants. A full run of `localbar-core` took 8 minutes, so it belongs on a ticket or in CI, not on commit.
- **Swift: Muter, unproven.** It could not run here (no Swift toolchain on Linux in this container). Decide after a spike on a Mac, not from this document.

## What each answer means for the map

The map's open question is whether mutation score could replace line coverage inside CRAP. That needs a score per function.

- **Per-function data exists today** in cargo-mutants (named in the JSON), mutmut (named in the `.meta` key, an internal format) and cosmic-ray (`definition_name` in `cosmic-ray dump`).
- **StrykerJS and Muter give only locations.** A per-function score needs a line-to-function map. `crap` already uses radon for Python and lizard for Swift; that lizard also parses TypeScript and Rust is my inference from its language list, not something I tested.
- **Speed decides where each gate can run.** Only a small scoped run (one function, one diff) fits in seconds. A package-wide run is minutes to tens of minutes and is a ticket or nightly gate.
- **Baselines.** Mutant identifiers are not stable across edits in any of the tools (mutmut's own source carries a TODO saying so). A per-function score ratchet, the same shape as `cc-check --baseline`, is more stable than a list of known surviving mutants. This is my reading, not a tested design.
- **Equivalent-mutant marks collide with the no-comments gate.** `comment-debt` exempts only `noqa`, `type: ignore`, `pragma: no cover`, `pragma: no branch` and `fmt:` markers (`PRAGMA` in `src/quality_gates/comment_debt.py`). `# pragma: no mutate` is not exempt, so it would count as a new comment. Changing that is a threshold change and needs an ADR. cargo-mutants alone has a no-comment route (a config regex).

## Python

### What was run

Target: this repo at `origin/main` (e4971ea), `src/quality_gates`, 174 tests, run from a scratch copy outside the working tree. Python 3.9.25 on Linux. The test suite takes 2.1 s under pytest (**measured**).

The suite is `unittest`-style. mutmut needs pytest as its runner, which is an extra dev dependency for a consumer that does not use pytest. cosmic-ray runs any test command.

### mutmut

Versions: **3.3.1 on Python 3.9**, and 3.8.0 on Python 3.13 for comparison.

| Run | Result |
|---|---|
| `src/quality_gates/ratchet.py` only, 3.3.1, Python 3.9, 4 workers (**measured**) | 171 mutants in 16.4 s: 145 killed, 26 survived (85%) |
| Same, repeated with no change (**measured**) | 15.0 s. No speed-up seen in 3.3.1 |
| Same, one function's mutants only, `mutmut run "quality_gates.ratchet.x_check*"` (**measured**) | 4.6 s. A fixed start-up of about 3 s is included |
| Whole package, 3.3.1, Python 3.9, 4 workers (**measured**) | 2,905 mutants in 514 s (8 min 34 s): 2,100 killed, 786 survived, 19 with no covering test. Score 72.8% of tested mutants |
| `ratchet.py` only, 3.8.0, Python 3.13, 4 workers (**measured**) | 177 mutants in 12.4 s: 151 killed, 26 survived |

**Scoped runs.** Mutants are named `<module>.x_<function>__mutmut_<n>`, and `mutmut run <glob>` runs only the matching ones. A file is scoped by listing the others under `do_not_mutate` (**measured**: that is how the `ratchet.py` run was made). There is no flag that takes a git diff. The 3.8.0 README says it re-tests only functions whose source changed; I did not confirm that. 3.8.0 also records which tests cover which function in `mutmut-stats.json` (**measured**: the file exists with that key) so it runs fewer tests per mutant.

**Output.**
- 3.3.1 has no report command that writes JSON. Results are in `mutants/<path>.py.meta`, JSON with `exit_code_by_key` (**measured**). Because each key carries the function name, a per-function score is a few lines of code. I did that on `ratchet.py`; for example `check` 23 of 24 killed and `write` 7 of 16. The file format is internal and undocumented, so it can change between releases.
- 3.8.0 adds `mutmut export-cicd-stats`, which writes only totals (`killed`, `survived`, `total`, and so on) to `mutants/mutmut-cicd-stats.json` (**measured**). The per-function data stays in the `.meta` files.
- Exit codes in the `.meta`: 1 killed, 0 survived, 33 no covering test (**read** from `status_by_exit_code` in the source).

**Install and fit.**
- 3.3.1 is the last release that installs on Python 3.9. 3.4.0 and later declare `requires-python >=3.10` (**measured** against PyPI metadata). On 3.9, uv resolved to 3.3.1 on its own (**measured**).
- Linux and macOS only, because it forks. Windows needs WSL (**read**).
- It copies the source and the tests into a `mutants/` directory, so anything else the tests read from the repo must be listed under `also_copy`. This repo's tests read the baselines, `README.md`, `CLAUDE.md`, `docs/`, `.claude/`, and more. Without that list the first run failed at the stats phase (**measured**: each missing class of file failed the stats phase in turn).
- It sets `MUTANT_UNDER_TEST` in the environment and the trampoline reads it. A test that clears the environment fails with `KeyError`. This repo has one, `tests/test_upstream.py` line 103 (`mock.patch.dict(os.environ, env, clear=True)`). It broke the run until the test kept that variable (**measured**).
- `libcst` is a dependency. On some macOS architectures it needs a Rust toolchain to build (**read**, README of 3.8.0).

**Maintenance.** 3.8.0 released 2026-09-12 (PyPI). Releases in 2026: February, June, July, September. Active.

**Equivalent mutants.**
- `# pragma: no mutate` on a line, plus block and range forms in the 3.8.0 README (**read**). 3.3.1 reads the line form (`pragma_no_mutate_lines` in its source, **read**).
- A file can be excluded in config with `do_not_mutate` (**measured**), which needs no comment.
- There is no file of "known survivors". The source says mutant ids are not stable (a TODO in `mutmut/__main__.py`).

### cosmic-ray

Version 8.7.0 on Python 3.9, Linux.

| Run | Result |
|---|---|
| `ratchet.py`, `cosmic-ray init` (**measured**) | 1.7 s |
| `cosmic-ray baseline` (**measured**) | 3.2 s, passed |
| `cosmic-ray exec`, local distributor (**measured**) | **183.6 s** for 90 mutants: 77 killed, 13 survived (14.44% survived) |
| Diff-scoped: `cr-filter-git`, then `exec` (**measured**) | 98 jobs, 90 skipped, 8 run, 19.4 s. 5 of the 8 survived |

- **Speed.** About 2 s per mutant. It ran the whole suite, unscoped, once per mutant, and the local distributor runs one at a time. mutmut did the same file in 16.4 s on four workers. The two ran different mutant sets (171 and 90), so compare per mutant: about 0.1 s against about 2.0 s. A parallel distributor exists (`http-workers`); I did not run it.
- **Scoped runs.** `cr-filter-git` marks every mutant outside the lines changed against a branch as skipped (**measured**). The branch is set with `[cosmic-ray.filters.git-filter] branch` and defaults to `master`. `cr-filter-lines` and `cr-filter-operators` also exist (**read** from `--help` and the source). The git filter diffs the working tree against the branch, so uncommitted changes count.
- **Pitfall.** `cr-rate` and `cr-report` count skipped jobs in the denominator: it printed "surviving mutants: 5 (5.10%)" for 5 survivors of 8 executed. A gate must compute its own score over executed jobs.
- **Output.** Results are a SQLite file. `cosmic-ray dump` prints JSON lines of `[job, result]`. Each job has `module_path`, `operator_name`, `start_pos`, `end_pos` and `definition_name` (the function), so a per-function score is easy (**measured**: I aggregated the 90 results by function). `cr-xml` and `cr-html` also exist (**read**).
- **Operators.** It made no mutants in two of the twelve functions of `ratchet.py` (`record` and `lowered`), where mutmut did (**measured**).
- **Install.** Python `>=3.9` for 8.7.0 (**measured** against PyPI metadata). Only needs a test command, no pytest. Works in place: it rewrites the source file and restores it, and the working tree was clean afterwards (**measured**).
- **Maintenance.** 8.7.0 released 2026-08-09. Releases in 2026: February, April, August. Active.
- **Equivalent mutants.** `cr-filter-pragma` skips lines with `# pragma: no mutate` (**read** from its `--help`; I did not run it). The same comment collision as mutmut.

## TypeScript: StrykerJS

### What was run

LocalBar's TypeScript is a React UI under `localbar-tauri/ui` with no test runner and no tests (**measured**: `package.json` has only `dev`, `build` and `preview`, and no test files exist). StrykerJS cannot be measured there. **I used a small public repo instead: `unjs/defu` at 82632b6**, 97 lines of source in two files, 23 vitest tests. The numbers below say nothing about a large TypeScript project.

Versions: `@stryker-mutator/core` 10.0.0 with the vitest runner and the typescript checker, TypeScript 6.0.3, vitest 4.1.11, Node 22.22.

| Run | Result |
|---|---|
| Install of the six packages (**measured**) | 6 s |
| Whole source, typescript checker, per-test coverage, 4 processes (**measured**) | 103 mutants in 48 to 51 s, score 80.77%. 60 killed, 3 timeout, 14 survived, 1 no coverage, 25 compile errors |
| One file, no checker (**measured**) | 67 mutants in 8 s, score 79.1% |
| `--mutate "src/defu.ts:55-70"` (**measured**) | 20 mutants in 16.1 s |
| `--incremental`, first run (**measured**) | 49.7 s, full |
| `--incremental` after a one-line source change (**measured**) | 14.0 s |

- **Speed.** The typescript checker costs most of the time: 8 s without it for one file against about 48 s with it on both. The checker removes mutants that do not compile (25 here), which also keeps them out of the score.
- **Scoped runs.** `--mutate "file:start-end"` limits mutation to a line range (**measured**). `--incremental` keeps `reports/stryker-incremental.json` and re-runs only mutants whose code or covering tests changed (**measured**). No flag takes a git diff, so a gate would turn `git diff` into line ranges.
- **Output.** `reports/mutation.json` follows the mutation-testing-elements schema, version 1.0 (**measured**). It holds `files[path].mutants[]`, and each mutant has `id`, `mutatorName`, `replacement`, `status`, `location` (start and end line and column), `coveredBy` and `statusReason`. There is no function name and no per-file score field in the JSON, so scores and function mapping are the consumer's work.
- **Install.** Node `>=22` for 10.0.0, and `>=20` for 9.6.1 (**measured** against the npm registry). The consumer needs a runner plugin (vitest, jest, mocha or a command runner) and, for the checker, TypeScript. It adds a Node dev dependency to a project that has one already. It does not add one to a Python-only project.
- **Maintenance.** 10.0.0 released 2026-08-14. Active.
- **Equivalent mutants.** `// Stryker disable next-line all: <reason>` ignores a mutant. Measured: one such line over the `__proto__` check made 10 mutants `Ignored` and left the score denominator without them. It is a comment, so it collides with the comment gate (#3 covers the TypeScript comment checker). Config-level exclusions exist; I did not check their syntax because the documentation site was blocked from this container.

### Two failures a gate must guard against

Both were hit while setting up, and both were silent or near-silent.

1. **vitest 5.0.3 gave a score of 3% with no error.** The same code and tests scored 79.1% on vitest 4.1.11. All mutants in `src/defu.ts` survived on vitest 5.0.3 (`~` in the clear-text report, 2 killed of 66), while `src/_utils.ts` scored normally. I did not find the cause. A wrong, low score fails a gate on a healthy suite, and a wrong, high one could pass it. The gate needs a plausibility check, such as requiring the dry run to report kills against a known-bad mutant.
2. **TypeScript 7.0.2 crashed Stryker 10.0.0** with `ts.parseConfigFileTextToJson is not a function`. TypeScript 7 is the native port without the JavaScript compiler API. This one is loud. LocalBar pins `typescript ~5.8`, so it is not affected today.

npm 10.9.4 also failed with `Cannot read properties of null (reading 'edgesOut')` when the peer ranges clashed, and `--legacy-peer-deps` got past it. That is npm's, not Stryker's, but a consumer would see it.

I also ran `npx stryker` once by mistake in a directory without it installed. It downloaded the abandoned `stryker@1.0.1` from 2017 and crashed. The package name to install is `@stryker-mutator/core`. A setup skill must never suggest `npx stryker`.

## Rust: cargo-mutants

### What was run

Target: **LocalBar** (`CapitalCantrip/LocalBar`, commit 4fbaa3d, 2026-10-06), package `localbar-core`, 6,708 lines of Rust, 320 tests. The repo is public and was cloned over the session's git proxy, into a scratch copy. `localbar-tauri` was not attempted.

Version: cargo-mutants 27.1.0, Rust 1.97, Linux.

| Run | Result |
|---|---|
| `cargo install cargo-mutants --locked` (**measured**) | 1 min 12 s to compile |
| `cargo test -p localbar-core`, first run, then warm (**measured**) | 19.6 s, then 0.5 s. 320 tests |
| Baseline inside cargo-mutants (**measured**) | build 16.6 s, test 0.4 s |
| Full package, `cargo mutants -p localbar-core -j 4` (**measured**) | **676 mutants in 8 min** (461 s wall time): 458 caught, 114 missed, 104 unviable, 0 timeout. Exit code 2 because mutants were missed |
| `-f localbar-core/src/net.rs -j 4` (**measured**) | 15 mutants in 64 s |
| `--in-diff` on a one-line change, `-j 1` (**measured**) | 4 mutants in 22.7 s (about 17 s of that is the baseline build) |
| Same, `-j 4` (**measured**) | 59 s. Four parallel builds of a fresh tree were slower than one |

- **Score.** 458 of 572 viable mutants caught: 80.1%. Unviable mutants (they do not compile) are excluded.
- **Per function.** `mutants.out/outcomes.json` has one entry per mutant with `scenario.Mutant.function.function_name`, `return_type` and the function's `span` (**measured**). I aggregated it: 266 functions had mutants, and 53 of them had only missed mutants. Per-file scores ranged from 100% (`launcher.rs`, `executable.rs`, `types.rs`) to 0% (`driver.rs`, `drivers/http.rs`).
- **Scoped runs.** `--in-diff <file>` takes a `git diff` and tests only mutants overlapping changed lines (**measured**: it picked the 4 mutants in the changed function). The book says it covers production code only, and that edits in one place can weaken tests of another, so it does not replace a full run (**read**). `-f <file>`, `--re` and `--exclude-re` also scope. `--list` shows the mutants without running them (**measured**).
- **Install.** `cargo install`, or a prebuilt binary (not checked). Building it needs Rust 1.88 or later (crates.io metadata). It then uses the project's own `cargo test`. No extra tool in the consumer's tree unless `#[mutants::skip]` is used.
- **Maintenance.** 27.1.0 released 2026-06-02, on a steady release cadence (crates.io, 687,411 downloads).
- **Equivalent mutants.** Three routes.
  1. `#[mutants::skip]` on a function (**measured**: the function's mutants vanished from `--list`). It needs `mutants = "0.0.3"` as a regular dependency in `Cargo.toml` (**read**), and without it the build fails with `E0433: cannot find module or crate mutants` (**measured**).
  2. `exclude_re = ["is_local"]` in `.cargo/mutants.toml` (**measured**: that function's mutants left `--list`, 15 became 11). The regex matches the whole mutant name, which holds file, function and replacement text, so one line can exclude a single mutation on a single function. No code change and no comment, so it passes the no-comments gate.
  3. `--exclude-re` on the command line.
- **Flakiness.** One of 18 `cargo test -p localbar-core` runs here failed one test (319 passed, 1 failed), and 12 reruns were clean. I did not capture which test. cargo-mutants stops if its baseline fails, so a flaky suite will block the gate at random. Worth a ticket on LocalBar.

## Swift: Muter (read only, not run)

No Swift toolchain was available in this container (`swift` is not installed) and I did not try to install one, so **nothing here was run**. Everything below is from Muter's README, `Package.swift`, release page and JSON example. Several of those came through a summarising fetch tool, which is why the JSON shape is flagged as second-hand.

- **Install.** `brew install muter-mutation-testing/formulae/muter`, or build from source with `make install`. Needs Swift 5.9 or later. It depends on `swift-syntax` 601 and `swift-format` 601 (`Package.swift`). The README says macOS 10.15 or later and Linux; `Package.swift` declares `.macOS(.v12)`, and a Linux build was not checked. The project does not bundle Swift, which fits the map's rule.
- **Config.** `muter.conf.yml` with `executable`, `arguments`, `exclude`, `excludeCalls`, `coverageThreshold` and `testSuiteTimeout`.
- **Speed.** The README says only that a run "can be a lengthy process" and that UI test suites make it worse. No numbers. Release 16 added mutant schemata, which builds once with every mutant behind a switch and so avoids a rebuild per mutant (the README says this "increases the performance a lot").
- **Scoped runs.** `--files-to-mutate <globs>`. The README suggests feeding it `git diff --name-only`, which is file-level, not function-level. `--skip-coverage` skips the coverage step.
- **Output.** `--format plain|json|html|xcode` with `--output`. The JSON example in the repo (second-hand) has `mutants[]` with `file`, `line`, `mutationOperator` and `result`, a `summary` with `mutationScore` and `codeCoverage`, and `fileScores[]` with a score per file. So: per file, plus a line for each mutant. No function names, so the same line-to-function mapping as StrykerJS (lizard already parses Swift in `crap`).
- **Operators.** Only four: `RelationalOperatorReplacement`, `RemoveSideEffects`, `ChangeLogicalConnector`, `SwapTernary` (README flag text). A narrow set compared with the others.
- **Maintenance.** The latest release is "Release 16", published "16 Sep", and the page showed no year. The `swift-syntax 601` pin dates the code to September 2025 or later (my inference). The repo showed 568 commits and 31 open issues. I could not confirm the last commit date. Treat maintenance as unverified.
- **Equivalent mutants.** `// muter:disable` and `// muter:enable` comments, and `excludeCalls` in the config (README). The comment form collides with the comment gate.

The map's "Not yet specified" list says gates that need a running test suite are weaker on Swift and Rust. For Rust this research says otherwise: cargo-mutants is the best-fitting tool. For Swift it is still open.

## What was not measured

- **Swift, Muter**: everything.
- **StrykerJS on LocalBar**: its UI has no tests. StrykerJS on a project of real size.
- **cargo-mutants on `localbar-tauri`.**
- **mutmut on macOS**, and cosmic-ray's parallel distributor.
- **mutmut's no-change rerun speed-up**: not seen in 3.3.1, and not tried on 3.8.0.
- **Any tool at the commit-time budget**: the scoped runs here are 4 to 22 seconds with a fixed start-up cost of 3 to 17 s, so a commit hook is plausible for one function and implausible for a file or a package.
- **The documentation sites** for mutmut, cosmic-ray and StrykerJS were blocked from this container. Their features come from the READMEs on GitHub raw, the packages' own `--help` text and source, and registry metadata.

## Reproduce

Python, from a scratch copy with its own git repo (the repo-scanning tests need one):

```bash
uv venv --python 3.9 v39
uv pip install --python v39/bin/python -e . coverage mutmut cosmic-ray
v39/bin/mutmut run --max-children 4
v39/bin/cosmic-ray init cr.toml cr.sqlite && v39/bin/cosmic-ray exec cr.toml cr.sqlite
```

mutmut's config (`pyproject.toml`) needs `paths_to_mutate`, `do_not_mutate` for the files to leave alone, `tests_dir`, and `also_copy` for every non-Python file the tests read.

Rust:

```bash
cargo install cargo-mutants --locked
cargo mutants -p localbar-core -j 4
cargo mutants -p localbar-core --in-diff change.diff
```

TypeScript, in a clean directory with a minimal `package.json`:

```bash
npm install --ignore-scripts --legacy-peer-deps vitest@4 typescript@6 \
  @stryker-mutator/core @stryker-mutator/vitest-runner @stryker-mutator/typescript-checker
node_modules/.bin/stryker run
```
