"""The chamber cites PRECEDENT — smriti's temporal decision memory reaches the
grounding bundle. Current rulings ride a dedicated ``precedents`` line (a dead,
superseded ruling never reaches the chamber as current), and the evidence seats
are recency-weighted (fresh outcomes outrank stale ones, decisions excluded)."""

from __future__ import annotations

from arivu.tools import grounding


def _corpus_with_chain():
    from common import smriti

    facts = [
        {"claim": "the product is free to start", "source": "site"},
        {"claim": "Published x/1: reach 90 · replies 0.", "source": "stats · x/1",
         "kind": "outcome", "observed_at": "2026-03-01T00:00:00Z"},
        {"claim": "Published x/2: reach 1240 · replies 3.", "source": "stats · x/2",
         "kind": "outcome", "observed_at": "2026-06-11T00:00:00Z"},
    ]
    q = "Should we move the Pro tier to $34?"
    facts = smriti.fold_decision(facts, "Decided: Raise Pro to $34", question=q,
                                 source="founder decision", now="2026-06-01T00:00:00Z")
    facts = smriti.fold_decision(facts, "Decided: Hold Pro at $29", question=q,
                                 source="founder decision", now="2026-06-10T00:00:00Z")
    return facts


def test_memory_section_carries_current_precedent_only(monkeypatch):
    from common import a2a

    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    monkeypatch.setitem(
        a2a._HANDLERS, "manas.get_founder_context",
        lambda topic="company": {"version": "v9", "grounded": True,
                                 "voice_rules": ["plain"], "brand_rules": ["honest"],
                                 "facts": _corpus_with_chain()},
    )
    section = grounding.fetch_grounding()["manas_a2a"]
    # the current ruling is named, with its chain depth — the dead one is absent
    assert "Hold Pro at $29" in section["precedents"]
    assert "supersedes 1" in section["precedents"]
    assert "Raise Pro to $34" not in section["precedents"]
    # decisions never seat as evidence; fresh outcomes outrank stale ones
    assert "Decided:" not in section["facts"]
    assert section["facts"].index("reach 1240") < section["facts"].index("reach 90")


def test_memory_section_has_no_precedents_key_without_decisions(monkeypatch):
    from common import a2a

    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    monkeypatch.setitem(
        a2a._HANDLERS, "manas.get_founder_context",
        lambda topic="company": {"version": "v9", "grounded": True,
                                 "voice_rules": ["plain"], "brand_rules": ["honest"],
                                 "facts": [{"claim": "free to start", "source": "site"}]},
    )
    section = grounding.fetch_grounding()["manas_a2a"]
    assert "precedents" not in section
    assert section["facts"] == "free to start"
