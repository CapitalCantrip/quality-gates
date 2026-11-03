# quality-gates

This repo is the source of truth for the quality standards every
project that pins it holds agent-written code to. The standards table is in
`README.md`; what is decided now is in the compendium, `docs/adr/README.md`
and its pages. Read the page your task touches. Open `docs/adr/archive/`
only to learn why something was decided.

**Asking the builder:** ask when uncertain about anything irreversible, outward-facing or large in scope, and proceed on reversible work with a stated default. Every question gives what is at stake in plain words, two or three options with only the pros and cons the builder would notice, and a recommendation with its reason (`standards` skill, *ask the builder*).

## Rules

- **A standard changes only through an ADR.** Changing a threshold, a counting
  tool or what a gate covers means a new ADR in `docs/adr/archive/`, or a dated
  addendum on the one it amends, then the compendium page, the code, the skills
  and the README in the same PR. None of them may disagree with the ADR.
- **What a consumer receives is released, at most once a day.** `README.md`
  § Releasing says what counts and lists the steps. The `CHANGELOG.md` entry
  says what a consumer must do when they bump the pin. Consumers pin tags, so
  an unreleased fix reaches nobody.
- **The repo passes its own gates.** `comment-debt` on every commit (the
  pre-commit hook), `cc-check` at 8 and `crap` at 8 on code you change.
- **Skills and agent-facing prose follow `writing-for-agents`.** The checklist
  is in ADR-002 § Writing for agents; review a new or changed skill against it.
- **New code goes in the module ADR-011 names.** Project files and the root
  through the project module, languages through the registry, the manifest
  through the manifest module, baselines and reasons through the ratchet,
  coverage pairing through the matcher. When the module you need does not
  exist yet, stop and ask rather than add a second copy.
- **Python 3.9 is the floor.** CI runs 3.9 and 3.12; the consumers include
  system Python on macOS.

## Run

```bash
uv venv && uv pip install -e .
.venv/bin/python -m unittest discover -s tests
.venv/bin/comment-debt
```

Shell is zsh: an unquoted `$VAR` stays one word, so pass file lists with
`xargs -0`. Stage files by name; the guard blocks `-a`, `-u` and `-A`.

## Issues

The build plan is #37: sprints, the between-sprints routine and model tiers.
Its body changes only in the routine's "update the plan" step; any other
session posts a comment on #37 instead. The tracker and the five triage
labels: see Agent skills below.

## Agent skills

### Issue tracker

GitHub Issues on this repo, through the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Pull requests

Write every PR body with the `pr` skill: Summary, Evidence, Merge Danger. `.github/pull_request_template.md` holds the same headings.
