#!/usr/bin/env bash
# Launch Open Interpreter with Sarvam (via the local LiteLLM proxy) as the model.
#
# Prerequisites (see README_Open Interpreter.md):
#   - The LiteLLM proxy from README.md is running on http://localhost:4000.
#   - LITELLM_MASTER_KEY is exported with the same value the proxy was started with.
#   - .venv-oi/ exists (Python 3.11/3.12 virtualenv with `open-interpreter` installed).
#
# Any extra args (e.g. -s, --auto_run, a prompt) are passed straight through to `interpreter`.

set -euo pipefail

PROXY_URL="${LITELLM_PROXY_URL:-http://localhost:4000}"
MASTER_KEY="${LITELLM_MASTER_KEY:-sk-local-demo}"
MODEL="${SARVAM_PROXY_MODEL:-openai/sarvam-m}"
INTERPRETER="${INTERPRETER_BIN:-.venv-oi/bin/interpreter}"

if [[ ! -x "$INTERPRETER" ]]; then
  echo "error: $INTERPRETER not found. Run the install in README_Open Interpreter.md first." >&2
  exit 1
fi

# OI reads these env vars in addition to the CLI flags; export both for safety.
export OPENAI_API_KEY="$MASTER_KEY"
export OPENAI_BASE_URL="$PROXY_URL"

exec "$INTERPRETER" \
  --model "$MODEL" \
  --api_base "$PROXY_URL" \
  --api_key "$MASTER_KEY" \
  "$@"
