#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/test_all.sh — the REAL test gate (faculty-v2).
#
# Every realm ships its own nested tests/ package, and so does the repo root.
# A single `pytest` session that collects two `tests` packages COLLIDES on the
# module name (ModuleNotFoundError: tests.test_*) — which is exactly why
# pytest.ini pins `testpaths = tests`, and why a bare `pytest` silently runs
# only 1 of the 6 suites. This gate runs each suite in its OWN process.
#
# Phase 3 flipped SAAKSHE_FACULTY_V2 ON by default (go-live). The flag stays as
# the rollback path, so this gate runs the WHOLE suite under BOTH faculty states
# — the go-live default (v2) AND the explicit rollback (v1) — and is green only
# if BOTH pass. That keeps the rollback path from silently rotting.
#
#   Usage:  bash scripts/test_all.sh           # both states, the .venv interpreter
#           PY=/path/to/python bash scripts/test_all.sh
#   Exit 0 only if EVERY suite is green in BOTH faculty states.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export SAAKSHE_MODE="${SAAKSHE_MODE:-demo}"
PY="${PY:-$ROOT/.venv/bin/python}"
fail=0

suite() {  # label  cwd  pytest-args...
  local label="$1"; local dir="$2"; shift 2
  echo "── $label ──"
  if ( cd "$dir" && PYTHONPATH=. "$PY" -m pytest "$@" -q -p no:cacheprovider ); then
    :
  else
    echo "✗ FAIL: $label  (faculty-v2=$SAAKSHE_FACULTY_V2)"; fail=1
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

# Run the full suite under BOTH faculty states. 1 = the go-live default; 0 = the
# explicit rollback path. Only "1" can be overridden by skipping (the gate must
# never deploy a broken go-live), so always test both here.
for FV in 1 0; do
  export SAAKSHE_FACULTY_V2="$FV"
  who=$([ "$FV" = 1 ] && echo "go-live default (v2)" || echo "rollback path (v1)")
  echo "═══════════════ faculty-v2 = $FV — $who ═══════════════"
  all_suites
done

echo
if [ "$fail" -ne 0 ]; then echo "✗ TEST GATE FAILED — a suite is red in at least one faculty state"; exit 1; fi
echo "✓ TEST GATE GREEN — all six suites pass under BOTH faculty states (v2 + v1)"
