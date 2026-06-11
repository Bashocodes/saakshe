"""smriti — the remembered: temporal decision memory + recency-weighted recall.

Two techniques lifted from the memory-systems literature (mnemosyne's temporal
version chains and recency decay), rebuilt saakshe's way:

* **No new storage.** The temporal keys ride the existing cited-fact dicts
  through both stores (file + Supabase keep facts as JSON — extra keys survive).
* **Nothing is deleted, nothing decays away.** A superseded decision stays in
  memory, CLOSED with ``valid_until`` + ``superseded_by`` — a citation chain,
  not an erasure. Decay only weights *selection into grounding bundles*.
* **Deterministic triggers.** Supersede fires on a same-subject match (the
  question asked, else the claim's content words) — code, never model judgment,
  mirroring manas/doubts.py.
* **Fail-soft.** Callers wrap smriti in try/except; a smriti error must never
  break learn() or a grounding fetch. Every function tolerates junk rows.

Decision fact shape (keys ADDED to the ordinary {claim, source} fact):
    kind:"decision" · subject · sid:"d-<sha8>" · valid_from · valid_until(None=open)
    · superseded_by(None|sid) · asked:<question, ≤140>
Outcome fact shape: kind:"outcome" · observed_at.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone

_ISO = "%Y-%m-%dT%H:%M:%SZ"

# words that carry no subject identity — tiny on purpose; determinism over cleverness
_STOPWORDS = frozenset(
    "a an and are at be do for from in is it of on or our should that the this to we what".split()
)

_DEFAULT_HALFLIFE_HOURS = 168.0  # one week — recent numbers speak louder, old ones never vanish


def default_halflife_hours() -> float:
    """Founder-configurable selection halflife (hours); never raises."""
    try:
        return float(os.environ.get("SAAKSHE_SMRITI_HALFLIFE_HOURS", "") or _DEFAULT_HALFLIFE_HOURS)
    except ValueError:
        return _DEFAULT_HALFLIFE_HOURS


def _now_iso(now: str | None = None) -> str:
    return now or datetime.now(timezone.utc).strftime(_ISO)


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, _ISO).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def subject_of(text: str) -> str:
    """Deterministic subject key: sha1[:8] over the sorted content words."""
    words = re.findall(r"[a-z0-9]+", str(text or "").lower())
    content = sorted(set(w for w in words if w not in _STOPWORDS)) or ["(blank)"]
    return hashlib.sha1(" ".join(content).encode("utf-8")).hexdigest()[:8]


def decision_fact(claim: str, *, question: str = "", source: str = "",
                  now: str | None = None) -> dict:
    """One temporal decision record — an ordinary cited fact plus the chain keys."""
    ts = _now_iso(now)
    subject = subject_of(question or claim)
    sid = "d-" + hashlib.sha1(f"{subject}:{ts}:{claim}".encode("utf-8")).hexdigest()[:8]
    fact = {"claim": str(claim), "source": str(source), "kind": "decision",
            "subject": subject, "sid": sid, "valid_from": ts, "valid_until": None,
            "superseded_by": None}
    if question:
        fact["asked"] = str(question)[:140]
    return fact


def fold_decision(facts: list, claim: str, *, question: str = "", source: str = "",
                  now: str | None = None) -> list:
    """Append a new ruling, closing every OPEN ruling on the same subject.

    Returns a new list; closed rulings are shallow-copied (the caller's originals
    are never mutated). Nothing is removed — the chain is the memory.
    """
    new = decision_fact(claim, question=question, source=source, now=now)
    ts = new["valid_from"]
    out: list = []
    for f in facts or []:
        if (isinstance(f, dict) and f.get("kind") == "decision"
                and f.get("subject") == new["subject"] and f.get("valid_until") is None):
            closed = dict(f)
            closed["valid_until"] = ts
            closed["superseded_by"] = new["sid"]
            out.append(closed)
        else:
            out.append(f)
    out.append(new)
    return out


def stamp_outcomes(results: list, now: str | None = None) -> list:
    """Mark measured results as outcomes with an observation time (copies)."""
    ts = _now_iso(now)
    return [dict(r, kind="outcome", observed_at=ts)
            for r in (results or []) if isinstance(r, dict)]


def outcome_weight(fact: dict, *, now: str | None = None,
                   halflife_hours: float | None = None) -> float:
    """Recency weight 0.5^(age/halflife). Unstamped or unparsable → 0.0."""
    seen = _parse((fact or {}).get("observed_at", ""))
    if seen is None:
        return 0.0
    ref = _parse(_now_iso(now)) or datetime.now(timezone.utc)
    age_h = max(0.0, (ref - seen).total_seconds() / 3600.0)
    hl = halflife_hours or default_halflife_hours()
    return 0.5 ** (age_h / hl) if hl > 0 else 0.0


def precedents(facts: list, now: str | None = None) -> list:
    """The CURRENT rulings (open decisions), newest first, with chain depth.

    A closed ruling is never offered as current — that is the whole point.
    """
    rows = [f for f in (facts or [])
            if isinstance(f, dict) and f.get("kind") == "decision"]
    descendants: dict = {}
    for f in rows:
        sid = f.get("superseded_by")
        if sid:
            descendants.setdefault(sid, []).append(f)

    def _depth(sid: str) -> int:
        total = 0
        for child in descendants.get(sid, []):
            total += 1 + _depth(child.get("sid", ""))
        return total

    open_rulings = [f for f in rows if f.get("valid_until") is None]
    open_rulings.sort(key=lambda f: f.get("valid_from") or "", reverse=True)
    return [{"claim": f.get("claim", ""), "source": f.get("source", ""),
             "since": f.get("valid_from", ""), "asked": f.get("asked", ""),
             "sid": f.get("sid", ""), "supersedes": _depth(f.get("sid", ""))}
            for f in open_rulings]


def precedents_text(facts: list, *, limit: int = 4, now: str | None = None) -> str:
    """One citable line for the chamber prompts — current rulings only."""
    parts = []
    for p in precedents(facts, now=now)[: max(0, limit)]:
        bit = f"{p['claim']} (since {p['since'][:10]}"
        if p["supersedes"]:
            bit += f", supersedes {p['supersedes']} earlier ruling" + ("s" if p["supersedes"] > 1 else "")
        bit += ")"
        parts.append(bit)
    return " · ".join(parts)


_WEIGHT_FLOOR = 0.01  # ≈6.6 halflives — older outcomes drop to pack order, never away


def select_facts(facts: list, *, limit: int = 8, now: str | None = None,
                 halflife_hours: float | None = None) -> list:
    """The grounding-bundle seats: fresh outcomes first (recency-weighted), then
    everything else in pack order. Decisions are EXCLUDED — they travel on the
    dedicated precedents line, so a dead ruling can never be cited as evidence.
    """
    rows = [f for f in (facts or [])
            if isinstance(f, dict) and f.get("kind") != "decision"]
    fresh: list = []
    rest: list = []
    for f in rows:
        w = outcome_weight(f, now=now, halflife_hours=halflife_hours) \
            if f.get("kind") == "outcome" else 0.0
        (fresh if w >= _WEIGHT_FLOOR else rest).append((w, f))
    fresh.sort(key=lambda p: p[0], reverse=True)
    seated = [f for _, f in fresh] + [f for _, f in rest]
    return seated[: max(0, limit)]
