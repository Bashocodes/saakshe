"""kalai — small shared helpers (no ADK runtime imports). Mirrors arivu/util.py."""

from __future__ import annotations

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
    if isinstance(text, dict):
        return text
    text = str(text).strip()
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


def brand_block(context_pack: dict[str, Any] | None) -> str:
    """Render the manas Context Pack as a compact, citable brand asset bank for prompts."""
    if not isinstance(context_pack, dict):
        return "• (no brand canon available)"
    lines: list[str] = []
    version = context_pack.get("version")
    if version:
        lines.append(f"• CANON VERSION: {version}")
    for rule in context_pack.get("brand_rules", []) or []:
        lines.append(f"• BRAND: {rule}")
    for rule in context_pack.get("voice_rules", []) or []:
        lines.append(f"• VOICE: {rule}")
    for fact in context_pack.get("facts", []) or []:
        if isinstance(fact, dict):
            lines.append(f"• FACT: {fact.get('claim','')} (src {fact.get('source','?')})")
    return "\n".join(lines) if lines else "• (brand canon present but empty)"
