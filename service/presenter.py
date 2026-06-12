"""saakshe — the presenter seat. Formats, never authors.

Any faculty's raw reply becomes a ``blocks[]`` list the chat panel renders as
data rows + actionable buttons. Words pass through untouched — same rule as
kural's assembler: format is not authorship.

Block kinds: text · data · actions · slider · progress · receipt · options.
"""
from __future__ import annotations

import re

_MEDIA_WORDS = ("hdr", "video", "reel", "animate", "motion")

# Every answer offers the next asks as tappable chips — agent-to-human talk is
# structured, never a dead end. Chips are shortcuts; the founder can ALWAYS
# type instead. Deterministic: drawn from the witness's telemetry buckets,
# minus whatever was just asked.
_FOLLOWUPS = (
    ("wait", "anyone waiting on me?"),
    ("cost", "what did today cost?"),
    ("learn", "what did the company learn?"),
    ("acting", "who's acting right now?"),
    ("revers", "what's reversible?"),
)


def followup_options(asked: str = "") -> dict:
    low = (asked or "").lower()
    items = [{"label": s, "send": s} for k, s in _FOLLOWUPS if k not in low]
    return {"t": "options", "items": items[:3]}


def media_intent(text: str) -> dict:
    """Detect a media-shaped ask + parse its budget ($N) and HDR wish."""
    low = text.lower()
    m = re.search(r"\$\s*(\d+(?:\.\d+)?)", low)
    return {"is_media": any(w in low for w in _MEDIA_WORDS),
            "budget_usd": float(m.group(1)) if m else 1.0,
            "wants_hdr": "hdr" in low}


def to_blocks(reply: dict, asked: str = "") -> list[dict]:
    blocks: list[dict] = [{"t": "text", "who": "saakshe/witness",
                           "md": reply.get("text", "")}]
    # The witness's gate context must reach the panel — "something is waiting"
    # without WHAT is a dead end for the founder.
    gates = reply.get("gates") or []
    if gates:
        blocks.append({"t": "data", "rows": [
            [f"gate {g.get('gate_id', '')}".strip(),
             (g.get("proposal", "") or "")[:90]
             + (" · reversible" if g.get("reversible") else "")]
            for g in gates]})
    pills = reply.get("pills") or []
    if pills:
        blocks.append({"t": "data", "rows": [[p, ""] for p in pills]})
    blocks.append(followup_options(asked))
    return blocks


def quote_blocks(q: dict) -> list[dict]:
    rows = [[l["item"].replace("_", " "), f"${l['usd']:.3f}"] for l in q["lines"]]
    rows.append(["total", f"${q['total_usd']:.3f}"])
    # the budget is a DEFAULT cap, not something the founder set — say so
    rows.append(["budget", f"${q['budget_usd']:.2f} — say “under $5” to change it"])
    blocks: list[dict] = [
        {"t": "text", "who": "kalai/router",
         "md": f"Path {q['path']} — {q['rationale']}."},
        {"t": "data", "rows": rows},
        {"t": "slider", "action": "media.requote", "min": 1, "max": 8,
         "value": q["seconds"],
         "quote": {"total_usd": q["total_usd"], "est_wall_sec": q["est_wall_sec"]}},
    ]
    if q["fits_budget"]:
        items = [{"label": "RENDER", "kind": "primary", "action": "media.render",
                  "args": {"seconds": q["seconds"]}},
                 {"label": "PICK FX (12)", "kind": "plain", "action": "media.fxmenu",
                  "args": {}}]
    else:
        items = [{"label": "OVER BUDGET", "kind": "blocked", "action": "noop", "args": {}}]
        co = q.get("counter_offer")
        if co:
            items.append({"label": f"FITS: {co['seconds']}s · ${co['total_usd']:.3f}",
                          "kind": "primary", "action": "media.requote",
                          "args": {"seconds": co["seconds"]}})
    blocks.append({"t": "actions", "items": items})
    return blocks


def receipt_blocks(job: dict) -> list[dict]:
    r, v = job["receipt"], job["verify"]
    return [
        {"t": "text", "who": "kalai/verifier",
         "md": (f"done — {v['hdr_format']}." if v["ok"]
                else "render finished but HDR verification FAILED — not shipping.")},
        {"t": "receipt",
         "rows": [["estimated", f"${r['estimated_usd']:.3f}"],
                  ["cpu", f"{r['measured_vcpu_sec']} vCPU-s · ${r['cpu_usd']:.3f}"],
                  ["vertex", f"${r['vertex_usd']:.3f}"],
                  ["total", f"${r['total_usd']:.3f}"]],
         "verify": v},
        {"t": "actions", "items": (
            [{"label": "VIEW HDR", "kind": "primary", "action": "media.view", "args": {}},
             {"label": "DISCARD", "kind": "no", "action": "media.discard", "args": {}}]
            if v["ok"] else
            [{"label": "RETRY", "kind": "primary", "action": "media.render", "args": {}}])},
    ]
