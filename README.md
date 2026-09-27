# quality-gates

Quality gates for agent-written code, shared across projects. One version,
pinned by tag in each project, so a fix lands everywhere by bumping the pin.

| Command | What it gates |
|---|---|
| `comment-debt` | No new code comments. Existing ones are a per-file baseline that only goes down |
| `cc-check` | Cyclomatic complexity per Python function (radon) |
| `crap` | CRAP score (complexity × missing coverage) for Python and Swift |

The Claude Code plugin ships the matching skills: `/no-comments`, `/cc-python`,
`/cc-rust`, `/cc-swift`, `/crap`.

## Install the commands

```bash
uv tool install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.1.0"
```

In a project, pin it in the dev dependencies instead:

```
quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.1.0
```

Swift support needs `lizard`: install with the `[swift]` extra.

## Enable the skills in a project

Add to the project's `.claude/settings.json`, so local and cloud sessions both
get them:

```json
{
  "extraKnownMarketplaces": {
    "quality-gates": { "source": { "source": "github", "repo": "CapitalCantrip/quality-gates" } }
  },
  "enabledPlugins": { "quality-gates@quality-gates": true }
}
```

## Adopt the comment gate

See `skills/no-comments/SKILL.md`. In short: install, `comment-debt --update`
to write `comment-debt.json`, a pre-commit hook running `comment-debt`, and a
test that calls `quality_gates.comment_debt.main` so CI enforces it.

## Releasing

Bump `version` in `pyproject.toml`, `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` together, tag `vX.Y.Z`, then bump the pin in
each consuming project.

## Development

```bash
uv venv && uv pip install -e .
.venv/bin/python -m unittest discover -s tests
.venv/bin/comment-debt
```

This repo gates itself. The 190 comment lines in `comment-debt.json` came with
the tools from their first home and are paid down like any other debt.
