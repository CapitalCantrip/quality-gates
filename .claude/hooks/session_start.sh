#!/bin/bash
set -euo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "$CLAUDE_PROJECT_DIR"

if [ ! -x .venv/bin/comment-debt ]; then
  uv venv -q .venv
  uv pip install -q --python .venv/bin/python -e .
fi
