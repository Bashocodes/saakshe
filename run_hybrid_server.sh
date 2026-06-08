#!/usr/bin/env bash
# Hybrid live server: REAL Gemini + scripted Claude, served behind the cockpit.
# Open http://localhost:8000/ → click "● live" → "run the day" to watch real
# Gemini calls flow through the live console. Ctrl-C to stop.
set -euo pipefail
cd "$(dirname "$0")"
# Real GCP project id lives in .env.local (gitignored); copy .env.local.example → .env.local.
[ -f .env.local ] && { set -a; . ./.env.local; set +a; }
: "${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT in .env.local (see .env.local.example)}"
export GOOGLE_CLOUD_PROJECT
export SAAKSHE_MODE=live
export ARIVU_MODE=live
export SAAKSHE_CLAUDE_MODE=demo   # keep Claude scripted; drop this line for full live
export PYTHONPATH=.
exec .venv/bin/uvicorn service.app:app --port 8000 --log-level warning
