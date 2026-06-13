#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/test_all.sh — the REAL test gate (faculty-v2 Phase -1).
#
# Every realm ships its own nested tests/ package, and so does the repo root.
# A single `pytest` session that collects two `tests` packages COLLIDES on the
# module name (ModuleNotFoundError: tests.test_*) — which is exactly why
# pytest.ini pins `testpaths = tests`, and why a bare `pytest` silently runs
# only 1 of the 6 suites. This gate runs each suite in its OWN process, so the
# whole company is actually exercised, and aggregates the verdict.
#
#   Usage:  bash scripts/test_all.sh           # demo mode, the .venv interpreter
#           PY=/path/to/python bash scripts/test_all.sh
#   Exit 0 only if EVERY suite is green.
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
    echo "✗ FAIL: $label"; fail=1
  fi
}

suite "tests (root)" "$ROOT" tests
suite "common"       "$ROOT" common
suite "manas"        "$ROOT" manas
suite "kalai"        "$ROOT" kalai
suite "kural"        "$ROOT" kural
# arivu's nested package imports `from arivu import config` (the arivu/arivu
# package), so it must run with arivu/ as the path root — its own process,
# cwd = arivu/, collecting arivu/tests.
suite "arivu"        "$ROOT/arivu" tests

echo
if [ "$fail" -ne 0 ]; then echo "✗ TEST GATE FAILED — at least one suite is red"; exit 1; fi
echo "✓ TEST GATE GREEN — all six suites pass"
