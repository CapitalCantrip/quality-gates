---
status: accepted
date: 2026-11-01
---

# ADR-011: The code's structure

## Context

Stage 4 of quality-gates#37 adds seven builds (#137, #138, #139, #114, #3,
#115, #112) and Stage 5 adds six gates (ADR-006). An architecture review on
`main` 56981ef (#37, "Architecture review, 2026-11-01") found that the three
seams they all sit on, languages, gates and project files, each exist in two
to four partial copies:

- The project root is found four ways, and two file walkers skip different
  folders. Setup edits the hook and the CI workflow only through skill prose.
- `languages.py` knows three languages, `status.PROJECT_MARKERS` knows four
  (with Rust), comment-debt hardcodes `*.py`, and the manifest and a test each
  keep their own language lists. A new language touches about five places.
- Each gate has its own argument parsing, report and exit-code rule.
  comment-debt has its own ratchet (#110), and `ratchet.py` is shallow.
- Four coverage readers pair functions with the report four different ways.
  #124, #90 and #83 are matching bugs in three of them.
- `components.json` is read raw in `status.py` and validated only in tests,
  and `qg` lives inside `status.py`.

The builder decided five candidates, one per seam: candidate 1 on #37 and
candidates 2 to 5 in a grilling session on 2026-11-01. This ADR records all
five. Words like module, interface, seam, depth and adapter carry their
`codebase-design` meanings.

## Decision

### 1. One project module

One module owns three jobs: finding the root, deciding which files the gates
look at, and reading and writing every file quality-gates keeps in a project.

- **Git is required; a cloud copy is not.** Outside a git repo, commands fail
  with a clear message and never fall back to the current folder. Projects
  without GitHub are #150.
- **Files in scope are the files git would commit:** tracked files plus
  untracked files that are not ignored. The project's own `.gitignore` replaces
  our skip list. Paths given on the command line narrow the set, and the choice
  file's exclusions apply on top. A file is listed once, which closes #87's
  double counting.
- **Tests are gated.** Fixture folders are excluded from detection and from the
  gates by a default exclusion that is written into the choice file, where it
  can be seen and changed (#120).
- **Code edits the hook and the CI workflow,** and only the lines between
  quality-gates' markers. Every other line is kept.
- **Old hooks without markers:** gate lines from past setup versions are
  recognised and replaced. Anything that looks like a gate but is not
  recognised is listed for the builder.
- **Baselines have fixed default names** that the module knows. `--baseline`
  stays as an override.
- **Every write goes through one planned-changes step:** setup shows which
  files will change and writes them on the builder's "go".
- **One project per git repo,** with one choice file at the root. Each
  language may name its folder and where its coverage report is (LocalBar's
  `localbar-tauri/ui`).
- The instruction file, `docs/agents/*` and the PR template belong to the same
  module.

### 2. One language registry

Amended by: [Addendum 2026-11-01: the languages-by-gates generator has its own module](#addendum-2026-11-01-the-languages-by-gates-generator-has-its-own-module)

- **The registry holds what makes a language, and nothing about gates:** name,
  label, file suffixes, project markers, and the `.xcodeproj` rule. Each gate
  keeps its own table, keyed by language name, of what it supports and how
  (the counter, the coverage readers, the comment syntax). A test fails when
  any gate names a language the registry does not know. A languages-by-gates
  table is generated from the gate tables, so gaps can be seen.
- **Every language the choice file can record is registered,** including Rust
  and shell, even where few gates support it. The choice file is validated
  against the registry.
- **Detection is split.** The registry says which language a file or marker
  belongs to. The project module supplies the files. The registry never walks
  the tree.
- **The registry is Python code,** a frozen table, not a data file.

### 3. One gate interface and one ratchet

- **Gates only find.** A gate takes the files in scope and returns findings.
  Each finding has a location (a file, plus a function or line where there is
  one), a number (a score or a count), a kind, and display text that is shown
  but never stored. A gate does not read baselines, reasons or command-line
  flags, and it does not decide the exit code.
- **One ratchet module applies the rest, in this order:** recorded reasons
  (ADR-009), then the baseline, then the outcome (pass, fail, baseline behind,
  unmeasured). It writes the baseline on `--update` and hands the result to the
  runner, which records it for the track record (#141) and the checkpoint
  (ADR-008). The track record cannot store a leaked key, because the finding
  never carries one into storage.
- **One baseline format for every gate,** a number per location that may only
  go down. Each gate keeps its own baseline file under its fixed name. comment
  debt's per-file count becomes one more location. The old formats are still
  read for a release or two after the change, and setup's planned-changes step
  converts them.
- **A language a gate does not support** gives one plain line and a pass, for
  example "crap does not score Rust; see the languages table". The line also
  shows in `qg status` and in the checkpoint.
- **A gate that cannot run** (a missing tool, a missing or stale coverage
  report, no git repo) raises a typed "could not run" error with a plain
  reason. The ratchet module turns it into exit 2 and one line, and the runner
  records it as "did not run", never as "passed".

### 4. Coverage matching in one place

- **Readers only parse.** Each reader turns its report into one shared shape:
  for each file, keyed by its exact real path, a list of the report's functions
  (name where known, start, end, figures) and figures per line. Python's report
  gives lines only. A reader translates its format's names into the scanner's
  names (xccov's `getter` becomes `get`), because that is knowledge of the
  format.
- **One matcher pairs scanned functions with report entries.** Within a file,
  it lines up the scanned functions and the report's functions in source
  order, using names where both sides have them, so line drift like #124's is
  absorbed. Each report function supplies at most one scanned function, so no
  figure is lent (#83) or borrowed from a neighbour. A scanned function with no
  partner is UNMEASURED: it is never dropped and never given zero. For a report
  with lines only, the figure comes from the lines in the function's own range.

### 5. One manifest module, and a thin `qg` dispatcher

- **One manifest module reads both shipped files,** `components.json` and
  `upstream.json`. It validates them as it loads them and hands out typed
  records: components, parts, sources and admission records (ADR-010). No
  caller reads raw JSON, and a malformed manifest fails on every run.
- **What is installed and what is scored stay separate.** The manifest says
  which languages a component installs for, and each gate's table says which
  languages it scores. A test fails when the two differ. Loading rejects any
  language the registry does not know. The generated languages-by-gates table
  shows both.
- **`qg` is a dispatcher with no logic of its own.** It maps a subcommand name
  to that module's entry point. `qg status` moves to its own module, and every
  new command is a `qg` subcommand.
- **With #138, the seven old command names** (`comment-debt`, `cc-check`,
  `crap`, `qg-skills`, `qg-agent-docs`, `qg-upstream`, `qg-references`) become
  `qg <name>`. The old names stay as aliases for a release or two, and that
  release's CHANGELOG entry tells consumers to re-run setup.

### Landing order

Each candidate lands as a refactor with no behaviour change, just before the
first build that needs it. The changes that do alter behaviour each ship in
their own release.

| Lands before | Refactor, no behaviour change | Ships as a release |
|---|---|---|
| #137 (choice file) | 1, 2, and 5's manifest module, dispatcher and `qg status` module | with #137: candidate 1's new file rules (git required, the files git would commit, each listed once, closing #87; the default fixture exclusion, closing #120) |
| #138 (runner) | 3: gate interface and ratchet module | with #138: code edits the hook and CI between markers, the old names fold into `qg`, and the common baseline format with conversion |
| side-lane batch 2 (#149) | 4: readers parse, and the matcher reproduces today's rules exactly | the new matching rule, fixing #124, #83 and #90, with an ADR-001 addendum |

## Consequences

- A new language is one registry entry plus one row in each gate that supports
  it. A new gate is a finder plus a row in the manifest. Reasons, baselines,
  the track record and exit codes come from the ratchet module.
- `qg run` (#138) calls gates through the gate interface, not by running their
  commands.
- On the #137 release, a file that was scored twice (#87) or a fixture folder
  that was scanned (#120) shows as PAID, and the consumer lowers the baseline.
- Consumers act twice more. On the #138 release they re-run setup, which rewrites
  the hook and CI to `qg <name>` and converts the baselines. On the matching
  release, TypeScript and Swift scores move where pairing was wrong, the
  ratchet reports them as PAID or FAIL, and the consumer re-records.
- The briefs of #137, #138, #139, #114, #3, #115, #112 and #149 name the module
  they build on.

## Rejected

- **A registry entry that holds every gate's facts.** The registry would import
  every gate's adapters and become a hub that changes with every gate.
- **Registering only the languages our own commands score.** The choice file
  and `qg status` would each keep a second list.
- **A registry that walks the tree.** It would be a second walker with its own
  exclusions, which is the cause of #87 and #120.
- **The registry as a data file.** It holds plain facts that no consumer edits,
  so a parser and validator would serve no reader.
- **Merging `components.json` and `upstream.json`.** It means a format change
  and churn in `qg-upstream` for no gain in depth.
- **Validating the manifest only in tests.** A broken shipped file would
  surface as a crash in a consumer's project.
- **Deriving the manifest's languages from the gate tables.** The manifest
  module would depend on every gate.
- **Keeping the old command names for good.** The number of command names would
  keep growing with each new command.
- **Today's gate shape with shared helpers.** Every new gate would re-implement
  the order of steps, which is how comment-debt got its own ratchet.
- **Keeping each baseline file's format.** It needs one format adapter per gate
  for good.
- **Failing a gate for a language it does not support.** It is noisy, and
  ADR-009 would make it a loosening.
- **Fixing each matching bug in its own reader.** The rule would stay in four
  places, and the next format would make a fifth.
- **Matching on the nearest start line within a tolerance.** Drift past the
  tolerance fails, and neighbours can still be paired wrongly.
- **Dropping scanned functions the report seems to lack.** #124's first build
  did this and hid real untested functions, a false pass.
- **Changing the matcher and the rule in one step.** A reviewer could not tell
  moved code from changed scores.

## Addendum 2026-11-01: the languages-by-gates generator has its own module

Amends: [2. One language registry](#2-one-language-registry)

`src/quality_gates/languages_table.py` generates
`docs/languages-by-gates.md`, the table § 2 calls for. It reads the registry,
every gate's language table and `components.json`, so it depends on all of
them. It cannot live in the registry, which imports no gate (Rejected: a
registry entry that holds every gate's facts). It cannot live in the manifest
module either, which would then depend on every gate (Rejected: deriving the
manifest's languages from the gate tables). The generator sits above both.

It is a tool for this repo's own docs, not a consumer command. It has no entry
in `[project.scripts]` and no `qg` subcommand. It writes only inside the
quality-gates checkout that holds the package, whatever folder it runs from.
A copy installed in a consumer project refuses to write and says why.
`--check` reads the same page and exits 1 when the page differs from the
tables.
