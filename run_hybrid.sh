#!/usr/bin/env bash
# Hybrid live run (CLI): REAL Gemini for the ~20 routine seats, scripted Claude
# for the 8 high-stakes seats (Vertex Anthropic quota pending). No Claude quota
# needed. Runs the full flywheel once and prints the transcript.
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
exec .venv/bin/python run_flywheel.py
