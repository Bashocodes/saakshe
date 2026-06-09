"""saakshe.witness.telemetry — tools-over-telemetry.

The witness holds NO static knowledge. Every answer is one of these tools run
against the live ordered stream. In Phase C these become ADK FunctionTools on a
Gemini LlmAgent (and the Gemini Live voice agent); the bodies are unchanged, so
the agent's answers can never drift from what the stream actually says.

The data contract is explicit, which is exactly why the witness can refuse: a
question that maps to no tool here gets an honest "I can't see that" — not a guess.
"""

from __future__ import annotations

from typing import Optional

from common import config, project
from common.stream import STREAM, EventStream

# The buckets the witness can actually see (drives the refusal: anything else =
# out-of-telemetry). Kept as data so the refusal lists what IS available.
KNOWN_BUCKETS = {
    "gates": "anyone waiting on me · the approval queue",
    "cost": "what today cost · token usage",
    "reversible": "what's reversible right now",
    "learned": "what manas learned · the Context Pack version",
    "activity": "who is acting right now",
}


def whos_acting_now(run_id: Optional[str] = None, stream: EventStream = STREAM, n: int = 6) -> dict:
    # "Acting" = a seat actually doing work. That is a Cloud-Trace *span*
    # (agent_run / call_llm / execute_tool), NOT a *kind* — the old filter mixed
    # the two ("agent_run" is never a kind), so it only ever caught the founder's
    # span_start and never the working agents.
    rows = [e for e in stream.all()
            if (not run_id or e.run_id == run_id)
            and e.span in ("agent_run", "call_llm", "execute_tool")
            and e.source != "saakshe"]
    recent = rows[-n:]
    return {
        "acting": [{"source": e.source, "agent": e.agent, "text": e.text} for e in recent],
        "count": len(recent),
    }


def anyone_waiting(run_id: Optional[str] = None, stream: EventStream = STREAM) -> dict:
    gates = stream.open_gates(run_id)
    return {
        "waiting": bool(gates),
        "gates": [
            {"gate_id": g["gate_id"], "from": g["source"], "kind": g["gate_kind"],
             "proposal": g["proposal"], "reversible": g["reversible"]}
            for g in gates
        ],
    }


def cost_today(run_id: Optional[str] = None, stream: EventStream = STREAM) -> dict:
    c = stream.cost_today(run_id)
    # Rough Vertex-ish estimate so a number exists in demo; real cost in live BQ.
    est = round((c["input_tokens"] * 3 + c["output_tokens"] * 15) / 1_000_000, 4)
    return {**c, "est_usd": est}


def whats_reversible(run_id: Optional[str] = None, stream: EventStream = STREAM) -> dict:
    out = []
    for e in stream.all():
        if run_id and e.run_id != run_id:
            continue
        if e.kind == "gate":
            out.append({"gate_id": e.meta.get("gate_id"), "reversible": e.meta.get("reversible"),
                        "proposal": e.text.removeprefix("GATE — ")})
        if e.kind == "action" and "dry_run" in e.meta:
            out.append({"action": e.text, "reversible": bool(e.meta.get("dry_run"))})
    return {"items": out}


def what_learned(run_id: Optional[str] = None, stream: EventStream = STREAM) -> dict:
    version = None
    for e in stream.all():
        if run_id and e.run_id != run_id:
            continue
        if e.meta.get("context_pack_to"):
            version = e.meta["context_pack_to"]
    # Fall back to the real store version (v0 when nothing is connected yet) —
    # never a canned pack number.
    return {"context_pack": version or project.current_store().version,
            "learned": version is not None}
