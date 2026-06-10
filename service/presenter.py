"""saakshe — the presenter seat. Formats, never authors.

Any faculty's raw reply becomes a ``blocks[]`` list the chat panel renders as
data rows + actionable buttons. Words pass through untouched — same rule as
kural's assembler: format is not authorship.

Block kinds: text · data · actions · slider · progress · receipt.
"""
from __future__ import annotations

import re

_MEDIA_WORDS = ("hdr", "video", "reel", "animate", "motion")


def media_intent(text: str) -> dict:
    """Detect a media-shaped ask + parse its budget ($N) and HDR wish."""
    low = text.lower()
    m = re.search(r"\$\s*(\d+(?:\.\d+)?)", low)
    return {"is_media": any(w in low for w in _MEDIA_WORDS),
            "budget_usd": float(m.group(1)) if m else 1.0,
            "wants_hdr": "hdr" in low}


def to_blocks(reply: dict) -> list[dict]:
    blocks: list[dict] = [{"t": "text", "who": "saakshe/witness",
                           "md": reply.get("text", "")}]
    pills = reply.get("pills") or []
    if pills:
        blocks.append({"t": "data", "rows": [[p, ""] for p in pills]})
    return blocks


def quote_blocks(q: dict) -> list[dict]:
    rows = [[l["item"].replace("_", " "), f"${l['usd']:.3f}"] for l in q["lines"]]
    rows.append(["total", f"${q['total_usd']:.3f} of ${q['budget_usd']:.2f}"])
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
