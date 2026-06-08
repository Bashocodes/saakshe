#!/usr/bin/env bash
# FULL live run (CLI): real Gemini AND real Claude·Vertex (Sonnet 4.6, global).
# Use this once the Anthropic quota is granted (probe shows Claude ✓). Pass
# "server" as an arg to serve the cockpit instead of the one-shot CLI.
set -euo pipefail
cd "$(dirname "$0")"
# Real GCP project id lives in .env.local (gitignored); copy .env.local.example → .env.local.
[ -f .env.local ] && { set -a; . ./.env.local; set +a; }
: "${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT in .env.local (see .env.local.example)}"
export GOOGLE_CLOUD_PROJECT
export SAAKSHE_MODE=live
export ARIVU_MODE=live
export PYTHONPATH=.
if [ "${1:-}" = "server" ]; then
  exec .venv/bin/uvicorn service.app:app --port 8000 --log-level warning
fi
exec .venv/bin/python run_flywheel.py
