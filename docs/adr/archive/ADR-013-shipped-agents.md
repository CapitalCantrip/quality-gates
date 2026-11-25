---
status: accepted
date: 2026-11-25
---

# ADR-013: quality-gates ships agent definitions

## Context

A retro over a month of sessions (2026-09-16 to 2026-10-16, across four
repos) counted about 100 subagent spawns. 80 were `general-purpose` with a long
hand-written prompt, and most of each prompt repeated the same rules: how an
implementer builds a ticket (test first, one test per acceptance criterion
named as a sentence, no comments, stage files by name, no push, no version
bump, a set report) and how a reviewer gates a merge (read-only, the spec
review then Claude Code's `code-review`, real-run evidence, **hard** versus
**judgement call** findings).

The builder moved those rules into agent definitions in their user-level
`~/.claude/agents/`. A user-level folder never reaches a cloud session, which
has only the repo clone. The skills hit the same limit, and `qg-skills` copies
them into each project for that reason (ADR-003).

The builder settled the open questions in a grilling session on 2026-11-14
(quality-gates#101).

## Decision

**Four agents ship in the package and `qg-skills` copies them** into the
project's `.claude/agents/`, beside the skills:

| Agent | Does | Model |
|---|---|---|
| `implementer` | Builds one ticket test-first on a branch it is given, commits, never pushes | Sonnet 5.5, high effort |
| `reviewer` | Reviews a branch against its spec and the repo's standards, read-only, with real-run evidence | Opus 5.5, high effort |
| `debt-payer` | Pays down one batch of comment, complexity or coverage debt without changing behaviour | Sonnet 5.5, medium effort |
| `diagnoser` | Finds a bug's root cause with evidence, without fixing it | Opus 5.5, high effort |

- **One implementer definition; the model is passed per spawn.** The
  orchestrator passes Opus 5.5 at medium effort for a skeleton ticket and for
  any ticket that changes an interface or the wiring. There is no separate
  Opus variant to keep in step.
- **`skill-vetter` stays user-level.** It vets third-party installs on the
  builder's machine, which is housekeeping, not a code standard.
- **The agents are part of the core component.** A consumer cannot switch them
  off. `components.json` lists each as a part of kind `agent`, and `qg status`
  reports each one as installed, missing or different.
- **The copier touches only what it shipped.** It records the agents it
  installed in `.claude/agents/.shipped-by-quality-gates`. It overwrites and
  removes only agents on that list. Any other file in `.claude/agents/` is never
  changed or removed. When the project already has a different agent with a
  shipped name, `qg-skills` stops with exit 2, changes nothing and names the
  file; `/setup-standards` puts the choice to the builder. An unlisted agent
  identical to the shipped one is taken over. This differs from skills, where
  `qg-skills` replaces any folder with a shipped skill's name.
- **The agent file handling lives in the project module** (`project_files`),
  beside the hook copier, because ADR-011 routes every file quality-gates
  keeps in a project through it; `qg-skills` only calls it.
- **`qg-skills --check` fails** on a shipped agent that is missing or differs, on
  an agent it shipped that the release no longer ships, and on a project's own
  agent with a shipped name.
- **Agents name skills by the names quality-gates ships** (`diagnosing-bugs`,
  not `mattpocock-skills:diagnosing-bugs`) and follow
  [ADR-002 § Writing for agents](ADR-002-engineering-standards.md#writing-for-agents).
  The reviewer also calls Claude Code's own `code-review`, which quality-gates
  deliberately does not ship.
- **The repo copy wins over a user-level agent of the same name,** so local
  and cloud sessions run the same rules.

The rules that tie the agents to the module map (the implementer stops when
the map lacks a module, and the reviewer's shape check) are a separate change
(quality-gates#122).

## Consequences

- An orchestrator spawns `implementer` or `reviewer` by name, with a short
  brief, instead of pasting the rules into every prompt.
- A consumer reruns `qg-skills` at the pin bump. An orchestration prompt that
  names the old `builder` agent now names `implementer`.
- A project that already has its own `reviewer.md` or `implementer.md` gets a
  stop at its first `qg-skills` run after the bump, and chooses whether to
  rename its agent or take the shipped one.
- The agent texts change through a release, like the skills. After the release
  that first ships them, the builder replaces their user-level copies of the
  four with the shipped text by hand.
