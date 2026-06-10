"""manas.questions — the Gemini phrasing pass over code-triggered doubts.

doubts.detect stays the only source of questions (a CODE trigger found a real
gap — the "no fabricated data" contract). This pass lets live Gemini REPHRASE
each ask against the real corpus, so the founder hears "Excalidraw is free and
open-source today — how do you plan to make money?" instead of the same template
every company gets. The a2a.ClarifyingQuestion docstring already reserves this
seam: "Phrasing may be Gemini-written; the *trigger* is code."

Hard rules, enforced here:
  * demo/CI never consults the model — the deterministic templates ARE the demo
    (byte-identical runs, no creds needed);
  * the model may never add, drop, or reorder a question — unknown ids are
    ignored, count and order are the trigger's;
  * a rewrite is accepted only if it is a non-empty line that still fits a chat
    card (≤ _MAX_TEXT chars); anything else keeps the template;
  * ANY live failure (network, quota, malformed JSON) falls back to the
    templates — phrasing is polish, never a gate.
"""

from __future__ import annotations

import asyncio
import dataclasses

from common import a2a, config
from common.stream import EventStream

from .tools import curator

NS = "manas"
_MAX_TEXT = 280
_MAX_FACTS = 24


def _build_prompt(qs: list[a2a.ClarifyingQuestion], facts: list[dict],
                  voice_rules: list[str], brand_rules: list[str], org: dict) -> str:
    name = str(org.get("name") or "this company").strip()
    what = str(org.get("what") or "").strip()
    digest = "\n".join(
        f"- {f.get('claim', '')} (source: {f.get('source', '')})"
        for f in facts[:_MAX_FACTS]
    ) or "- (no cited facts yet)"
    voice = " · ".join(list(voice_rules) + list(brand_rules))
    asks = "\n".join(
        f'- id: {q.id}\n  trigger: {q.trigger}\n  why: {q.why}\n  template: {q.text}'
        for q in qs
    )
    return (
        f"You are manas, the memory of {name}"
        + (f" ({what})" if what else "")
        + ". While grounding the company you found real gaps — each question below "
          "was raised by a deterministic code trigger, with the honest reason in `why`.\n\n"
        f"The corpus you DID ground (cited facts):\n{digest}\n"
        + (f"\nBrand voice: {voice}\n" if voice else "")
        + f"\nThe questions to ask the founder:\n{asks}\n\n"
        "Rephrase each question so it is specific to this company: reference what the "
        "corpus already shows, then ask exactly for the gap in `why`. Speak directly to "
        "the founder as I, manas (e.g. \"I can see X — but no source tells me Y\"). Plain, "
        "warm, one sentence or two, no hype. NEVER invent facts that are not in the corpus above; "
        "NEVER ask about anything beyond the listed questions; keep any quoted options "
        "from the template (a contradiction must still present both candidates).\n\n"
        "Return ONLY a JSON object mapping each question id to its rephrased text, e.g. "
        '{"missing-1a2b3c4d": "…"}. No other keys, no commentary.'
    )


def _call_gemini(prompt: str) -> str:
    """One live Gemini Flash call (the network seam tests monkeypatch)."""
    from google import genai

    client = genai.Client(vertexai=True, project=config.GOOGLE_CLOUD_PROJECT,
                          location=config.GEMINI_LOCATION)
    resp = client.models.generate_content(model=config.MODEL_FLASH, contents=prompt)
    return resp.text or ""


async def personalize(
    qs: list[a2a.ClarifyingQuestion],
    facts: list[dict],
    voice_rules: list[str] | None = None,
    brand_rules: list[str] | None = None,
    org: dict | None = None,
    stream: EventStream | None = None,
    run_id: str = "",
) -> list[a2a.ClarifyingQuestion]:
    """Return the questions with live-Gemini phrasing where accepted; the input
    objects are never mutated. Demo/CI and every failure path return ``qs``."""
    if not qs or not config.is_live():
        return qs
    prompt = _build_prompt(qs, facts, voice_rules or [], brand_rules or [], org or {})
    try:
        raw = await asyncio.to_thread(_call_gemini, prompt)
        mapping = curator.parse_json(raw)
    except Exception:
        return qs
    if not isinstance(mapping, dict) or not mapping:
        return qs

    out: list[a2a.ClarifyingQuestion] = []
    rewritten = 0
    for q in qs:
        text = mapping.get(q.id)
        if isinstance(text, str) and 0 < len(text.strip()) <= _MAX_TEXT:
            out.append(dataclasses.replace(q, text=text.strip()))
            rewritten += 1
        else:
            out.append(q)
    if rewritten and stream is not None:
        stream.emit(run_id, NS, "Founder Voice",
                    f"phrased {rewritten} question(s) against the corpus",
                    span="call_llm", model="gemini·flash")
    return out
