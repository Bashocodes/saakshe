#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/test_all.sh — the REAL test gate.
#
# Every realm ships its own nested tests/ package, and so does the repo root.
# A single `pytest` session that collects two `tests` packages COLLIDES on the
# module name (ModuleNotFoundError: tests.test_*) — which is exactly why
# pytest.ini pins `testpaths = tests`, and why a bare `pytest` silently runs
# only 1 of the 6 suites. This gate runs each suite in its OWN process.
#
# The four-faculty re-assignment (manas custodies the keys · kalai = media only ·
# kural authors the copy · arivu decides) is the permanent architecture — there is
# no flag and no rollback path, so the gate runs the suite once.
#
#   Usage:  bash scripts/test_all.sh           # the .venv interpreter
#           PY=/path/to/python bash scripts/test_all.sh
#   Exit 0 only if EVERY suite is green.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Force DEMO (sealed replay) for EVERY quadrant. The gate verifies deterministic
# correctness, and deploy_cloudrun.sh sources .env.local (GOOGLE_CLOUD_PROJECT)
# BEFORE calling this gate — which would otherwise auto-detect LIVE and make real
# Vertex calls (ADC + network, absent in a build). arivu reads ARIVU_MODE (not
# SAAKSHE_MODE), so force BOTH, plus the Claude-understudy modes.
export SAAKSHE_MODE=demo ARIVU_MODE=demo SAAKSHE_CLAUDE_MODE=demo ARIVU_CLAUDE_MODE=demo
PY="${PY:-$ROOT/.venv/bin/python}"
fail=0

suite() {  # label  cwd  pytest-args...
  local label="$1"; local dir="$2"; shift 2
  echo "── $label ──"
  if ( cd "$dir" && PYTHONPATH=. "$PY" -m pytest "$@" -q -p no:cacheprovider ); then
    :
  else
    echo "✗ FAIL: $label"; fail=1
  fi
}

all_suites() {
  suite "tests (root)" "$ROOT" tests
  suite "common"       "$ROOT" common
  suite "manas"        "$ROOT" manas
  suite "kalai"        "$ROOT" kalai
  suite "kural"        "$ROOT" kural
  # arivu's nested package imports `from arivu import config` (the arivu/arivu
  # package), so it must run with arivu/ as the path root — its own process.
  suite "arivu"        "$ROOT/arivu" tests
}

all_suites

echo
if [ "$fail" -ne 0 ]; then echo "✗ TEST GATE FAILED — a suite is red"; exit 1; fi
echo "✓ TEST GATE GREEN — all six suites pass"
