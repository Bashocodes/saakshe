"""smriti — temporal decision memory + recency-weighted outcome selection.

The doctrine under test: temporal keys ride the existing cited-fact dicts (no
new storage); nothing is ever deleted or decayed away — a superseded decision
stays, CLOSED with valid_until + superseded_by (the citation chain); supersede
fires only on a deterministic same-subject trigger (the question asked); decay
weights selection into grounding bundles, never the memory itself.
"""

from __future__ import annotations

from common import smriti

T0 = "2026-06-01T00:00:00Z"
T1 = "2026-06-08T00:00:00Z"
T2 = "2026-06-11T00:00:00Z"


# ─── subjects are deterministic, content-word based ──────────────────────────

def test_subject_is_deterministic_and_ignores_noise():
    a = smriti.subject_of("Should we move the Pro tier to $34?")
    b = smriti.subject_of("should we MOVE the pro tier to $34??")
    assert a == b and len(a) == 8


def test_different_questions_get_different_subjects():
    a = smriti.subject_of("Should we move the Pro tier to $34?")
    b = smriti.subject_of("Should we launch on LinkedIn?")
    assert a != b


# ─── the version chain: fold + supersede ─────────────────────────────────────

def test_fold_decision_appends_an_open_ruling():
    facts = smriti.fold_decision([], "Decided: Pro to $34",
                                 question="Should we move the Pro tier to $34?",
                                 source="founder decision · today", now=T0)
    d = facts[-1]
    assert d["kind"] == "decision" and d["claim"] == "Decided: Pro to $34"
    assert d["valid_from"] == T0 and d["valid_until"] is None
    assert d["sid"].startswith("d-") and d["superseded_by"] is None


def test_same_subject_supersedes_the_open_ruling():
    q = "Should we move the Pro tier to $34?"
    facts = smriti.fold_decision([], "Decided: Pro to $34", question=q,
                                 source="s", now=T0)
    facts = smriti.fold_decision(facts, "Decided: Pro stays at $29", question=q,
                                 source="s", now=T1)
    old, new = facts[-2], facts[-1]
    assert old["valid_until"] == T1 and old["superseded_by"] == new["sid"]
    assert new["valid_until"] is None
    # nothing was deleted — both rulings remain, cited
    assert len(facts) == 2


def test_different_subject_never_supersedes():
    facts = smriti.fold_decision([], "Decided: Pro to $34",
                                 question="Should we move the Pro tier to $34?",
                                 source="s", now=T0)
    facts = smriti.fold_decision(facts, "Decided: launch on LinkedIn",
                                 question="Should we launch on LinkedIn?",
                                 source="s", now=T1)
    assert facts[0]["valid_until"] is None and facts[1]["valid_until"] is None


def test_plain_facts_pass_through_fold_untouched():
    plain = {"claim": "Pricing page lists $29", "source": "web:pricing"}
    facts = smriti.fold_decision([plain], "Decided: Pro to $34",
                                 question="q", source="s", now=T0)
    assert facts[0] == plain


# ─── precedents: only OPEN rulings, with chain depth ─────────────────────────

def test_precedents_show_only_current_rulings_with_chain_depth():
    q = "Should we move the Pro tier to $34?"
    facts = smriti.fold_decision([], "Decided: Pro to $34", question=q, source="s", now=T0)
    facts = smriti.fold_decision(facts, "Decided: Pro stays at $29", question=q, source="s", now=T1)
    ps = smriti.precedents(facts)
    assert len(ps) == 1 and ps[0]["claim"] == "Decided: Pro stays at $29"
    assert ps[0]["supersedes"] == 1
    line = smriti.precedents_text(facts)
    assert "Pro stays at $29" in line and "supersedes 1" in line
    assert "Pro to $34" not in line  # a dead ruling is never offered as current


def test_precedents_text_is_empty_without_decisions():
    assert smriti.precedents_text([{"claim": "x", "source": "y"}]) == ""


# ─── outcomes: stamped, weighted, selected by recency ────────────────────────

def test_stamp_outcomes_adds_kind_and_observed_at_without_mutating_input():
    rows = [{"claim": "post 1: 5 replies", "source": "stats · p1"}]
    out = smriti.stamp_outcomes(rows, now=T2)
    assert out[0]["kind"] == "outcome" and out[0]["observed_at"] == T2
    assert "kind" not in rows[0]


def test_outcome_weight_halves_every_halflife():
    fresh = {"kind": "outcome", "observed_at": T2}
    week_old = {"kind": "outcome", "observed_at": "2026-06-04T00:00:00Z"}
    w_fresh = smriti.outcome_weight(fresh, now=T2, halflife_hours=168)
    w_old = smriti.outcome_weight(week_old, now=T2, halflife_hours=168)
    assert abs(w_fresh - 1.0) < 1e-9
    assert abs(w_old - 0.5) < 1e-9


def test_select_facts_prefers_fresh_outcomes_and_excludes_decisions():
    facts = [
        {"claim": "old outcome", "source": "s", "kind": "outcome",
         "observed_at": "2026-04-01T00:00:00Z"},
        {"claim": "plain fact", "source": "s"},
        {"claim": "fresh outcome", "source": "s", "kind": "outcome",
         "observed_at": T2},
    ]
    facts = smriti.fold_decision(facts, "Decided: X", question="q", source="s", now=T2)
    chosen = smriti.select_facts(facts, limit=2, now=T2)
    claims = [f["claim"] for f in chosen]
    # decisions ride the precedents line, never the evidence seats
    assert claims == ["fresh outcome", "old outcome"] or claims == ["fresh outcome", "plain fact"]
    assert "Decided: X" not in claims
    assert claims[0] == "fresh outcome"


def test_select_facts_keeps_pack_order_for_plain_facts():
    facts = [{"claim": f"f{i}", "source": "s"} for i in range(4)]
    chosen = smriti.select_facts(facts, limit=3, now=T2)
    assert [f["claim"] for f in chosen] == ["f0", "f1", "f2"]
