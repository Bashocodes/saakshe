"""arivu — small shared helpers (no ADK runtime imports)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def parse_json(text: str | None) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from a model response.

    Tolerates ```json fences, leading prose, and trailing commentary. Returns
    {} if nothing parseable is found so callers can fall back deterministically.
    """
    if not text:
        return {}
    text = text.strip()
    # Strip a fenced block if present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    # Fall back to the first balanced {...}.
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


def grounding_text(grounding: dict[str, Any]) -> str:
    """Render the grounding bundle as a compact, citable block for prompts."""
    lines: list[str] = []
    labels = {
        "admin_stats": "STATS (admin_stats)",
        "admin_analytics_user_growth": "GROWTH (admin_analytics·user-growth)",
        "admin_analytics_activity": "ACTIVITY/CHURN (admin_analytics·activity)",
        "manas_a2a": "BRAND/MEMORY (manas A2A)",
        "kural_a2a": "FUNNEL (kural A2A)",
    }
    for key, label in labels.items():
        blob = grounding.get(key)
        if not blob:
            continue
        kvs = ", ".join(f"{k}={v}" for k, v in blob.items())
        lines.append(f"• {label}: {kvs}")
    return "\n".join(lines) if lines else "• (no grounding available)"


def content_hash(payload: Any) -> str:
    """Stable content hash for a filed resolution (audit trail)."""
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()[:16]


def transcript_line(actor: str, text: str) -> dict[str, str]:
    """One line of the chamber transcript."""
    return {"actor": actor, "text": text}
