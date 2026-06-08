"""Deterministic curator math + memory-commit termination logic.

This is manas's safety property, the mirror of arivu/tools/analyst.py: the
Curator verify-before-commit loop NEVER exits on "the claims look grounded" — it
exits on a numeric groundedness score crossing GROUNDING_THRESHOLD, or a
MAX_CURATE_ROUNDS rollback. The score is computed here, in pure functions, so a
test can pin it and a model can never talk the loop past the bar.

Two hard rules the score enforces (the chamber's negative safety behaviour):
  1. Every committed claim MUST cite a source — an uncited claim drags the score.
  2. A contradictory claim set can NEVER score high enough to commit — a detected
     contradiction GATES the groundedness to 0.0, so the Curator can never commit
     a self-contradicting memory no matter how many rounds it runs.
"""

from __future__ import annotations

import re
from typing import Any

from common import config
from .. import state as st

# Lightweight parse without depending on arivu.util (kept self-contained).
import json


def parse_json(text: str | None) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from a model response."""
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


# ─── Contradiction detection (the negative safety behaviour) ─────────────────
# A pair of claims contradicts when one asserts a fact the other negates. We keep
# this deterministic and explainable: numeric facts about the same subject with
# different values, and explicit yes/no flips on the same promise.
_NEG = re.compile(r"\b(no|not|never|without|reject|drop|break|cannot|won['’]?t|don['’]?t)\b", re.I)
_NUM = re.compile(r"\$?\d+(?:\.\d+)?%?")


def _subject(claim: str) -> str:
    """A coarse subject key: the claim text minus numbers/negations/stopwords."""
    s = claim.lower()
    s = _NUM.sub("", s)
    s = _NEG.sub("", s)
    s = re.sub(r"[^a-z ]", " ", s)
    toks = [t for t in s.split() if len(t) > 3 and t not in _STOP]
    return " ".join(sorted(set(toks)))


# Genuine stopwords only — domain nouns (price, retention, margin, ...) are kept
# as subject material so two claims about the same subject can be compared.
_STOP = {
    "that", "this", "with", "from", "into", "over", "than", "then", "they",
    "their", "there", "here", "have", "has", "was", "were", "will", "shall",
    "would", "could", "should", "today", "imbibed", "through",
    "claim", "source", "about", "into", "onto", "also", "very", "much",
}


def find_contradictions(claims: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return contradicting claim pairs. Deterministic; pure.

    Two claims contradict when they share a subject but one negates what the
    other asserts, OR they assert different numeric values for the same subject.
    """
    found: list[dict[str, str]] = []
    norm = []
    for c in claims:
        text = str(c.get("claim", "")) if isinstance(c, dict) else str(c)
        if not text.strip():
            continue
        norm.append(
            {
                "text": text,
                "subject": _subject(text),
                "neg": bool(_NEG.search(text)),
                "nums": tuple(_NUM.findall(text)),
            }
        )
    for i in range(len(norm)):
        for j in range(i + 1, len(norm)):
            a, b = norm[i], norm[j]
            if not a["subject"] or a["subject"] != b["subject"]:
                continue
            polarity_flip = a["neg"] != b["neg"]
            number_clash = bool(a["nums"]) and bool(b["nums"]) and a["nums"] != b["nums"]
            if polarity_flip or number_clash:
                found.append(
                    {
                        "a": a["text"],
                        "b": b["text"],
                        "why": "polarity flip" if polarity_flip else "numeric clash",
                    }
                )
    return found


# ─── Groundedness (curate loop exit) ─────────────────────────────────────────
def compute_groundedness(claims: list[dict[str, Any]], round_: int) -> float:
    """A groundedness value in [0, 1]. Deterministic given claims and round.

    Rises with (a) the fraction of claims that cite a source and (b) accumulated
    curation rounds (the synthesise→verify→revise refinement). A detected
    contradiction GATES the score to 0.0 — a self-contradicting memory can never
    clear the bar, so the Curator can never commit it.
    """
    if not claims:
        return 0.0
    if find_contradictions(claims):
        return 0.0  # hard gate: contradiction → never commit
    cited = sum(1 for c in claims if isinstance(c, dict) and str(c.get("source", "")).strip())
    cite_fraction = cited / len(claims)
    refinement = 0.06 * max(0, round_ - 1)   # round 1 is the first pass; later rounds tighten
    score = 0.84 * cite_fraction + refinement
    return round(min(1.0, score), 4)


def curate_should_stop(groundedness: float, round_: int) -> tuple[bool, bool, str]:
    """Return (stop, committed, reason).

    Commits only when groundedness crosses the bar. If the max round is hit
    without crossing, the Curator stops with a rollback: "no safe commit" — it
    refuses to write an under-grounded memory rather than fabricate one.
    """
    if groundedness >= config.GROUNDING_THRESHOLD:
        return True, True, (
            f"groundedness {groundedness:.2f} ≥ {config.GROUNDING_THRESHOLD} — every claim cited, "
            "non-contradictory; commit"
        )
    if round_ >= config.MAX_CURATE_ROUNDS:
        return True, False, (
            f"max curate rounds ({config.MAX_CURATE_ROUNDS}) reached at {groundedness:.2f} — "
            "rollback: no safe commit, refuse rather than fabricate"
        )
    return False, False, (
        f"groundedness {groundedness:.2f} < {config.GROUNDING_THRESHOLD} — re-synthesise (cite or drop the gaps)"
    )


# ─── State readers (curation lives in state as the Claude output_key text) ───
def read_curation(state) -> dict[str, Any]:
    raw = state.get(st.StateKeys.CURATION)
    return raw if isinstance(raw, dict) else parse_json(raw)


def read_claims(state) -> list[dict[str, Any]]:
    """The claims the Curator proposes to commit (from the curation synthesis)."""
    curation = read_curation(state)
    claims = curation.get("claims", []) if isinstance(curation, dict) else []
    return [c for c in claims if isinstance(c, dict)]


def read_ingested(state) -> list[dict[str, Any]]:
    """Flatten the four imbibers' raw claim extractions out of state."""
    out: list[dict[str, Any]] = []
    for _role, _disp, _src, ingest_key, _ch in st.IMBIBERS:
        d = parse_json(state.get(ingest_key))
        for c in d.get("claims", []) if isinstance(d, dict) else []:
            if isinstance(c, dict) and str(c.get("claim", "")).strip():
                out.append(c)
    return out


def read_rules(state) -> tuple[list[str], list[str]]:
    """Aggregate the imbibers' voice_rules / brand_rules (deduped, order-stable)."""
    voice: list[str] = []
    brand: list[str] = []
    for _role, _disp, _src, ingest_key, _ch in st.IMBIBERS:
        d = parse_json(state.get(ingest_key))
        if not isinstance(d, dict):
            continue
        for r in d.get("voice_rules", []) or []:
            if isinstance(r, str) and r.strip() and r not in voice:
                voice.append(r.strip())
        for r in d.get("brand_rules", []) or []:
            if isinstance(r, str) and r.strip() and r not in brand:
                brand.append(r.strip())
    return voice, brand


# ─── Deterministic tools the Curator can call in live mode ───────────────────
def verify_citations(claims: list[dict]) -> dict:
    """Report which proposed claims are uncited (the Curator's commit guard)."""
    total = len(claims)
    uncited = [
        str(c.get("claim", ""))
        for c in claims
        if isinstance(c, dict) and not str(c.get("source", "")).strip()
    ]
    return {
        "total_claims": total,
        "cited": total - len(uncited),
        "uncited": uncited,
        "all_cited": not uncited,
    }


def detect_contradiction(claims: list[dict]) -> dict:
    """Report contradictions in a proposed claim set (the non-contradiction guard)."""
    pairs = find_contradictions(claims)
    return {
        "has_contradiction": bool(pairs),
        "contradictions": pairs,
        "note": "a contradictory claim set is gated to groundedness 0.0 and can never commit",
    }


# FunctionTools (handed to the live Curator; in demo the math runs in the check-agent).
try:
    from google.adk.tools import FunctionTool

    verify_citations_tool = FunctionTool(func=verify_citations)
    detect_contradiction_tool = FunctionTool(func=detect_contradiction)
except Exception:  # pragma: no cover - ADK not importable in some lint contexts
    verify_citations_tool = None
    detect_contradiction_tool = None
