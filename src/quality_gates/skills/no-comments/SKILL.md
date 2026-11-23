---
name: no-comments
description: >
  Set up or run the no-code-comments gate (comment-debt) in a repo, or pay down
  one file's comment debt. Use when adding the gate to a project, when
  comment-debt fails, or when asked to convert or pay down comments.
---

# /no-comments — comment gate

Code carries no comments in any language the choice file switches on: Python
(`no-comments`), Rust, TypeScript, Swift and shell (`no-comments-<language>`).
Every comment counts once per line, doc comments included, and in Python
docstrings and strings used as comments too. Bare tool pragmas
(`# noqa: E402`, `eslint-disable`, `swiftlint:disable`) are exempt. A
recognised convention, such as Rust's `// SAFETY:` above `unsafe`
(`rust-safety`), counts until it is switched on in
`settings.no-comments.conventions`; `qg explain no-comments` names them.
Existing comments are debt, held by a per-file baseline that only goes down.

## Run

```bash
comment-debt            # exit 1 if any file is above or below its baseline
comment-debt --status   # remaining debt by area, rationale-flagged files first
comment-debt --update   # lower the baseline after paying debt; never raises
comment-debt --report rust   # one language's comment lines, chosen or not
```

Option: `--baseline PATH` (default `comment-debt.json` at the repo root). It
checks the [comment gate's files](references/comment-gate-files.md), which start
from the [files in scope](references/files-in-scope.md). Before a language is
switched on, `/setup-standards` shows its report and offers two choices:
record as debt, where `qg setup --go --choose <id>` records its existing
comments, or clean first (below). `--update` never adds them.
`--exclude` is refused: run `/setup-standards` to move the prefixes into the file.

## Set up in a repo

1. Install the package (see below) and add it to the project's dev
   dependencies, pinned to a tag.
2. `comment-debt --update` writes the first baseline. A new repo gets `{}`.
3. Add `.githooks/pre-commit` containing `exec comment-debt` and run
   `git config core.hooksPath .githooks`. For cloud sessions, add a
   `SessionStart` hook to `.claude/settings.json` that runs that git config.
4. Add a test that calls `quality_gates.comment_debt.main([], root=<repo>)` and
   asserts 0, so the suite and CI enforce it.

## Where a comment's knowledge goes

Prefer somewhere that fails when the knowledge stops being true.

| The comment says… | It goes to |
|---|---|
| why an edge case behaves as it does | a test named as a sentence |
| why a value is what it is | a named constant, plus a test if load-bearing |
| what a caller must do first | the signature, or the function does the step itself |
| why this design and not another | the repo's ADR, as a dated addendum |
| what a domain word means | the repo's glossary |
| a known risk or deferred fix | an issue |
| `--help` text read through `__doc__` | argparse `description=` |
| what the next line plainly does | nowhere; delete it |

## Paying down one file

1. `comment-debt --status`, pick the top file.
2. Write tests for the edge cases the comments describe; they must pass first.
3. Remove the comments; run the suite.
4. `comment-debt --update`; commit the file, its tests and the baseline
   together, saying where each piece of knowledge went.

## Clean first, before a language is chosen

`--status` and `--update` do not see a language that is not chosen yet.
`/setup-standards` offers clean first after the language's report:

1. The builder scopes what to pay down now from
   `comment-debt --report <language>`, by area, file or kind.
2. Pay each file in the scope down as above, without changing behaviour, with
   the report in place of `--status` and `--update`; commit only the file and
   its tests. For a long run, give each batch to a subagent (a `debt-payer`
   agent where the project has one).
3. Rerun `comment-debt --report <language>` until the scope shows none.
4. Only if the builder asks, open an issue for the remainder whose body is
   that report.
5. Run `qg setup --go --choose <id>`: it records the rest as debt and switches
   the language on.

Done when the report shows none in the scope and the language is chosen.

## Installing the commands

If `comment-debt` is missing, install with the install line in `/setup-standards`.
