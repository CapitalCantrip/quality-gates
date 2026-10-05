# quality-gates

This repo is the source of truth for the quality standards every
project that pins it holds agent-written code to. The standards table is in
`README.md`; the reasons are in `docs/adr/`.

## Rules

- **A standard changes only through an ADR.** Changing a threshold, a counting
  tool or what a gate covers means a new ADR in `docs/adr/`, or a dated addendum
  on the one it amends, then the code, the skills and the README in the same PR.
  The skills and the README must never disagree with the ADR.
- **Every change to behaviour is a release.** Bump the version in the three
  places `README.md` § Releasing lists, add a `CHANGELOG.md` entry that says what
  a consumer must do when they bump the pin, and update the skills' install
  lines. Consumers pin tags, so an unreleased fix reaches nobody.
- **The repo passes its own gates.** `comment-debt` on every commit (the
  pre-commit hook), `cc-check` at 8 and `crap` at 8 on code you change.
- **Skills and agent-facing prose follow `writing-for-agents`.** The checklist
  is in ADR-002 § Writing for agents; review a new or changed skill against it.
- **Python 3.9 is the floor.** CI runs 3.9 and 3.12; the consumers include
  system Python on macOS.

## Run

```bash
uv venv && uv pip install -e .
.venv/bin/python -m unittest discover -s tests
.venv/bin/comment-debt
```

## Issues

GitHub Issues on this repo. Labels: `needs-triage`, `ready-for-agent`,
`ready-for-human`.
