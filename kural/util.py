"""kural — small shared helpers (no ADK runtime imports).

Kept self-contained (stdlib only) so tools, tests, and the demo fixtures can
import it without pulling in the ADK runtime or the rest of the company.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def parse_json(text: str | None) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from a model response.

    Tolerates ```json fences, leading prose, and trailing commentary. Returns
    {} if nothing parseable is found so callers can fall back deterministically —
    the same contract arivu relies on so an output_schema-less reply never
    silently collapses a numeric gate to 0.0.
    """
    if not text:
        return {}
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except (json.JSONDecodeError, ValueError):
                    return {}
    return {}


def send_key(run_id: str, channel: str, recipient: str) -> str:
    """Stable idempotency key for a single outbound message — the ledger's PK.

    The same (run, channel, recipient) can only ever post once, even on a retry;
    a content hash is folded in so a genuinely new draft is a new key.
    """
    raw = f"{run_id}|{channel}|{recipient}".encode("utf-8")
    return "snd:" + hashlib.sha256(raw).hexdigest()[:16]


def transcript_line(actor: str, text: str) -> dict[str, str]:
    """One line of the engagement transcript."""
    return {"actor": actor, "text": text}
