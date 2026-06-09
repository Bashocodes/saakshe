"""manas — the corpus READ side, now backed by the real connected-project store.

There is NO hardcoded company here anymore. The single source of cited memory is
``common.project.STORE`` — filled by a real manas ingestion of the founder's
connected sources (repo + site + docs/social). Until something is connected and
ingested, the store is empty and every read comes back ungrounded / refused. That
is the refuse-out-of-corpus contract made real: manas refuses because it has no
imbibed source, not because a keyword missed a canned map.

Both paths still read this ONE store so "real" and "fixture" can never disagree:
  * the SYNC A2A handlers (get_founder_context / ask_founder_voice) read it directly
    (they stay synchronous + pure so a plain ``def`` caller never breaks);
  * the ASYNC founder_voice_agent + curator pipeline are grounded in the same store,
    and the demo resolver answers FROM it — so the agent's refusal is the same
    refusal the handler returns.
"""

from __future__ import annotations

import re

from common import a2a, project

_STOP = {
    "the", "our", "your", "their", "what", "whats", "with", "from", "into", "over",
    "this", "that", "they", "them", "have", "has", "does", "do", "did", "are", "is",
    "was", "were", "will", "should", "would", "could", "can", "we", "us", "a", "an",
    "of", "to", "in", "on", "for", "and", "or", "at", "by", "it", "be", "as", "if",
}


def _stems(text: str) -> set[str]:
    """Significant 4-char stems of a phrase — a cheap, deterministic relevance key.

    'pricing' → 'pric', which matches 'price' in a claim; 'valuation' → 'valu',
    which matches nothing in a pricing corpus → an honest refusal."""
    words = re.findall(r"[a-z][a-z0-9]+", (text or "").lower())
    return {w[:4] for w in words if len(w) > 3 and w not in _STOP}


def _claim_text(fact: dict) -> str:
    return f"{fact.get('claim', '')} {fact.get('source', '')}".lower()


def _relevant(topic: str, facts: list[dict]) -> list[dict]:
    """Facts whose text shares a stem with the topic. Topic 'company'/'all'/'' →
    everything (the whole company pack)."""
    t = (topic or "").strip().lower()
    if t in ("", "company", "all", "everything"):
        return [dict(f) for f in facts]
    keys = _stems(t)
    if not keys:
        return [dict(f) for f in facts]
    hits = []
    for f in facts:
        text = _claim_text(f)
        if any(k in text for k in keys):
            hits.append(dict(f))
    return hits


# ─── read API (delegates to the store) ───────────────────────────────────────
def topics() -> list[str]:
    """The topics the company actually has memory for (derived, not canned)."""
    facts = project.current_store().all_facts()
    return ["company"] if facts else []


def context_pack(topic: str = "company") -> a2a.ContextPack:
    """The versioned, source-cited Context Pack for a topic — empty/ungrounded when
    nothing relevant is imbibed yet. Never fabricated."""
    pack = project.current_store().pack(project.TOPIC)
    if not pack.facts:
        return a2a.ContextPack(version=pack.version, topic=topic, facts=[],
                               voice_rules=[], brand_rules=[], grounded=False)
    relevant = _relevant(topic, pack.facts)
    if not relevant:
        # The company is grounded, but not on THIS topic → withhold everything
        # (ungrounded, empty) rather than hand over off-topic rules.
        return a2a.ContextPack(version=pack.version, topic=topic, facts=[],
                               voice_rules=[], brand_rules=[], grounded=False)
    return a2a.ContextPack(
        version=pack.version, topic=topic, facts=relevant,
        voice_rules=list(pack.voice_rules), brand_rules=list(pack.brand_rules),
        grounded=True,
    )


# ─── Founder-Voice: answer AS the founder, grounded ONLY in the store ─────────
_REFUSAL = (
    "I don't have that in the founder's corpus yet — I won't invent an answer in "
    "their voice. Connect a source that covers it and I'll imbibe it."
)


def _match_facts(question: str) -> list[dict]:
    keys = _stems(question)
    if not keys:
        return []
    out = []
    for f in project.current_store().all_facts():
        if any(k in _claim_text(f) for k in keys):
            out.append(dict(f))
    return out


def is_in_corpus(question: str) -> bool:
    return bool(_match_facts(question))


def founder_voice(question: str) -> a2a.FounderVoiceAnswer:
    """Answer as the founder iff the question is supported by an imbibed fact;
    otherwise REFUSE (refused=True, citations=[]). The hard refusal keeps the
    company from ever being bound by a hallucinated founder opinion."""
    hits = _match_facts(question)
    if not hits:
        return a2a.FounderVoiceAnswer(answer=_REFUSAL, citations=[], refused=True)
    # Ground the answer in the strongest match; cite up to two supporting facts.
    lead = hits[0]
    cites = [{"claim": h.get("claim", ""), "source": h.get("source", "")} for h in hits[:2]]
    answer = (f"From what I've imbibed: {lead.get('claim', '').rstrip('.')}. "
              "That's grounded in the source on file, not invented.")
    return a2a.FounderVoiceAnswer(answer=answer, citations=cites, refused=False)


def founder_voice_lookup(question: str) -> tuple[str, list[dict], bool]:
    """(answer, citations, refused) — what the demo resolver hands the Claude seat."""
    ans = founder_voice(question)
    return ans.answer, ans.citations, ans.refused
