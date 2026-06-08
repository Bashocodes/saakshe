#!/usr/bin/env python
"""Run the arivu deliberation chamber from the terminal.

    python run_demo.py                      # the Sundara $39 question
    python run_demo.py "Should we ..."      # any loaded question
    python run_demo.py --approve            # also fire the executor (dry-run)
    python run_demo.py --approve --live-exec  # REAL publish/planner/dispatch

In demo mode (no creds) the orchestration runs for real; only token generation is
replayed. With Vertex ADC the five mantris + chair run on Gemini and the verdict +
prosecution run on Claude via Vertex.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from arivu import config, models, runner

SK = config.StateKeys

_C = {
    "dim": "\033[2m", "b": "\033[1m", "g": "\033[32m", "y": "\033[33m",
    "r": "\033[31m", "c": "\033[36m", "x": "\033[0m",
}


def _banner() -> None:
    d = models.describe()
    print(f"\n{_C['b']}◈ arivu — the faculty of judgment{_C['x']}")
    print(f"{_C['dim']}mode: {d['mode']}  ·  chair/mantris: {d['chair']}/{d['mantris']}"
          f"  ·  verdict/prosecutor: {d['verdict']}{_C['x']}")
    if d["mode"] == "demo":
        print(f"{_C['y']}  (demo replay — add Vertex ADC for live Gemini + Claude){_C['x']}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the arivu deliberation chamber.")
    ap.add_argument("question", nargs="?", default=config.DEFAULT_QUESTION)
    ap.add_argument("--approve", action="store_true",
                    help="simulate the founder's one approval and fire the executor")
    ap.add_argument("--live-exec", action="store_true",
                    help="allow REAL executor side effects (publish/planner/dispatch)")
    ap.add_argument("--trace", action="store_true",
                    help="enable OpenTelemetry console tracing of every chamber span")
    ap.add_argument("--json", action="store_true", help="dump final state as JSON")
    args = ap.parse_args()

    if args.trace:
        from arivu.callbacks import otel
        otel.configure_tracing()

    _banner()
    state = asyncio.run(runner.deliberate(args.question))

    for line in runner.build_transcript(state):
        actor = line["actor"]
        colour = _C["c"]
        if actor.startswith("risk"):
            colour = _C["r"]
        elif actor.startswith("gate") or actor.startswith("approved"):
            colour = _C["g"]
        elif actor.startswith("chair"):
            colour = _C["b"]
        print(f"{colour}{actor:<34}{_C['x']} {line['text']}")

    if args.approve and state.get(SK.GATE_STATUS) == "awaiting_approval":
        print(f"\n{_C['g']}● founder taps APPROVE — the one gate{_C['x']}")
        state[SK.GATE_STATUS] = "approved"
        result = runner.execute_decision(state, dry_run=not args.live_exec)
        res = result["resolution"]
        tag = "REAL" if not result["dry_run"] else "dry-run"
        print(f"{_C['g']}executed ({tag}){_C['x']}")
        print(f"  commit    : {result['commit']['flag']} {result['commit']['from']}→{result['commit']['to']}")
        print(f"  dispatch  : kalai {result['dispatch']['kalai']['command']} · "
              f"kural {result['dispatch']['kural']['command']}")
        print(f"  resolution: {res['url']}  ({res['content_hash']})")
        print(f"  follow-up : {result['followup']['planner_entry']}")

    if args.json:
        print("\n" + json.dumps(state, indent=2, default=str))


if __name__ == "__main__":
    main()
