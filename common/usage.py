"""saakshe.common.usage — capture REAL token usage from live ADK runs.

In demo, the per-seat stream events carry rough fixed token estimates so a cost
number exists. In live, we sum the ACTUAL gen_ai usage from the ADK events
(prompt/candidates token counts) and emit one *authoritative* usage event per
quadrant. The witness's cost tool prefers authoritative events when present, so
the cockpit shows TRUE live spend — and falls back to the estimate in demo.
"""

from __future__ import annotations

from typing import Any


def usage_from_events(events: list) -> dict:
    """Sum real input/output token counts across a quadrant's ADK events."""
    inp = out = calls = 0
    for ev in events:
        um = getattr(ev, "usage_metadata", None)
        if not um:
            continue
        p = getattr(um, "prompt_token_count", 0) or 0
        c = getattr(um, "candidates_token_count", 0) or 0
        if p or c:
            inp += int(p)
            out += int(c)
            calls += 1
    return {"input_tokens": inp, "output_tokens": out, "llm_calls": calls}


def emit_authoritative(stream: Any, run_id: str, source: str, usage: dict | None, *, live: bool) -> None:
    """Emit one authoritative real-usage event for a quadrant (live only)."""
    if not live or not usage:
        return
    inp, out = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    if not (inp or out):
        return
    stream.emit(
        run_id, source, "usage",
        f"real model usage · {inp} in / {out} out tokens · {usage.get('llm_calls', 0)} live calls",
        span="call_llm", kind="note",
        usage={"input_tokens": inp, "output_tokens": out}, auth=True,
    )
