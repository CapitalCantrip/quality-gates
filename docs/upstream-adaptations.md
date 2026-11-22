# Upstream adaptations

Every change we make to a file copied from upstream, with the reason and the
way to redo it. When `qg-upstream` reports a changed file, take the new
upstream version, then redo each change listed here for that file. A change
whose reason no longer holds is removed from this list in the same PR.

Every file not listed is a word-for-word copy: replace it with the new
upstream version. Why the copies exist: [ADR-003](adr/archive/ADR-003-vendor-pocock-skills.md).

## mattpocock/skills

### `code-review` ships as `review-against-spec`

**Why:** a project skill named `code-review` hides Claude Code's own
`/code-review`, a bug hunt, and the builder wants both.

**Files and how to redo:**

| Upstream | Ours | Change |
|---|---|---|
| `skills/engineering/code-review/` | `src/quality_gates/skills/review-against-spec/` | Copy the folder under the new name. |
| `skills/engineering/code-review/SKILL.md` | `src/quality_gates/skills/review-against-spec/SKILL.md` | Frontmatter `name: code-review` becomes `name: review-against-spec`. |
| `skills/engineering/implement/SKILL.md` | `src/quality_gates/skills/implement/SKILL.md` | `/code-review` becomes `/review-against-spec`. |
| `skills/engineering/implement-spec/SKILL.md` | `src/quality_gates/skills/implement-spec/SKILL.md` | `` `code-review` `` becomes `` `review-against-spec` ``; step 7 also runs Claude Code's own `code-review` at `high` (see below). |
| `skills/engineering/tdd/SKILL.md` | `src/quality_gates/skills/tdd/SKILL.md` | `` `code-review` skill `` becomes `` `review-against-spec` skill ``. |

**Check after redoing:** `grep -rn code-review src/quality_gates/skills`
finds only mentions of Claude Code's own command (the `standards` skill and
`implement-spec` step 7), and any new upstream mention is either changed here
or added to this table.

### `implement-spec` also runs Claude Code's `/code-review high`

**Why:** `review-against-spec` checks standards and the spec, not correctness.
On PR #211 it passed code in which `/code-review high` then found five bugs,
and that review only ran once the builder started it after the session. Running
both before the session hands back saves the builder a review round.

**How to redo:** in step 7 of `src/quality_gates/skills/implement-spec/SKILL.md`,
after the `review-against-spec` call, add the call to Claude Code's own
`code-review` with `high`, and have the one implementer subagent fix the
findings of both.

### `setup-matt-pocock-skills` is a pointer to `/setup-standards`

**Why:** `/setup-standards` writes `docs/agents/` from his templates, so his
setup would duplicate it. A pointer skill keeps the skills that name his setup
word for word.

**Files:** `src/quality_gates/skills/setup-matt-pocock-skills/SKILL.md` is ours,
not a copy, so an upstream change to his setup's `SKILL.md` needs no redo here.
His setup templates are tracked separately, as ADR-002's addendum describes.
