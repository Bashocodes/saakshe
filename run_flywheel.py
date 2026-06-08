"""saakshe — run the whole flywheel end-to-end (demo, creds-free).

    cd ~/Desktop/Working/saakshe && PYTHONPATH=. ./.venv/bin/python run_flywheel.py

Proves the walking skeleton: manas grounds → arivu decides (HALT g1) → tap →
kalai makes → handoff → kural engages (HALT g2) → tap → publish (dry-run) →
manas learns. Then asks the witness a question it can answer and one it must refuse.
"""

from __future__ import annotations

import asyncio

from common import config
from common.stream import STREAM
import orchestrator
from witness import agent as witness

C = {"q": "\033[36m", "b": "\033[1m", "g": "\033[32m", "y": "\033[33m", "d": "\033[2m", "x": "\033[0m"}


def _print_new(prev_cursor: int) -> int:
    for e in STREAM.since(prev_cursor):
        tag = {"gate": C["y"], "action": C["g"], "a2a": C["d"]}.get(e.kind, "")
        print(f"  {tag}{e.source:>8} · {e.agent:<22}{C['x']} {e.text}")
    return STREAM.cursor


async def main() -> None:
    print(f"\n{C['b']}◈ saakshe — the agentic company, behind one witness{C['x']}")
    print(f"{C['d']}mode: {config.mode()}  ·  {config.TOTAL_SEATS} seats · {config.TOTAL_CLAUDE_SEATS} Claude·Vertex{C['x']}\n")

    cur = STREAM.cursor
    s = await orchestrator.start()
    print(f"{C['q']}— manas grounds → arivu decides —{C['x']}")
    cur = _print_new(cur)
    assert s["status"] == "awaiting_approval" and s["open_gate"]["gate_id"] == "g1", s
    print(f"\n{C['g']}● gate 1 in the queue: {s['open_gate']['proposal']}{C['x']}\n")

    s = await orchestrator.approve(s["run_id"], "g1")
    print(f"{C['q']}— tap 1 → execute → kalai makes → handoff → kural engages —{C['x']}")
    cur = _print_new(cur)
    assert s["status"] == "awaiting_approval" and s["open_gate"]["gate_id"] == "g2", s
    print(f"\n{C['g']}● gate 2 in the queue: {s['open_gate']['proposal']}{C['x']}\n")

    s = await orchestrator.approve(s["run_id"], "g2")
    print(f"{C['q']}— tap 2 → publish (dry-run) → manas learns —{C['x']}")
    cur = _print_new(cur)
    assert s["status"] == "completed", s
    print(f"\n{C['g']}✓ flywheel closed · actions: {[a['quadrant'] for a in s['actions']]}{C['x']}")

    rid = s["run_id"]
    print(f"\n{C['b']}— the witness answers from telemetry —{C['x']}")
    for q in ["anyone waiting on me?", "what did today cost?", "what did manas learn?",
              "how much did we spend on ads today?"]:
        a = witness.answer(q, rid)
        mark = f"{C['y']}REFUSE{C['x']}" if a["refused"] else f"{C['g']}answer{C['x']}"
        print(f"  [{mark}] {C['d']}{q}{C['x']}\n          {a['text']}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
