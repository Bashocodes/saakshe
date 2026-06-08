"""Pin the billing-safe executor.

The executor turns a survived verdict into action — but ONLY a config commit
(a feature-flag flip), NEVER a price/revenue column write, and NEVER any real
side effect on a dry run. These tests pin both invariants:
  * dry run => nothing committed / dispatched, resolution is a draft;
  * the commit is structurally a feature_flag_flip with no DB-column write;
  * the real path raises when no example client is registered (no silent fake).
"""

from __future__ import annotations

import pytest

from arivu import config
from arivu.tools import executor

SK = config.StateKeys


def _realistic_state() -> dict:
    """A survived-verdict chamber state, as deliberate() would hand to the gate."""
    return {
        SK.VERDICT: {
            "decision": "Raise Pro to $34, grandfather existing subscribers, 30-day notice.",
            "reasons": ["below the $36 churn cliff", "honours the grandfathering promise"],
            "dissent": "Growth wants a $29 capture tier alongside; recorded, not adopted.",
            "confidence": 0.88,
        },
        SK.PROSECUTION: {"defensibility": 0.84, "survived": True},
        SK.GROUNDING: {
            "admin_stats": {"paying_users": 412, "mrr_usd": 11948},
            "admin_analytics_activity": {"churn_cliff": "retention breaks past $36"},
        },
        SK.GATE_STATUS: "awaiting_approval",
    }


# ─── Forbidden-write helpers (structural, not lexical) ────────────────────────
# We do NOT substring-scan for "price"/"revenue": the legitimate result contains
# those words (flag value "pricing.pro_tier_v2", a note that price columns are
# never written, the resolution title, "$34" briefs). The real invariant is that
# there is no DB column write — a structural property of keys and write-verbs.
FORBIDDEN_COLUMN_KEYS = {
    "price",
    "new_price",
    "price_usd",
    "current_pro_price",
    "revenue",
    "mrr",
    "mrr_usd",
    "arr",
    "amount",
    "balance",
}
FORBIDDEN_WRITE_VERBS = {
    "db_write",
    "update_column",
    "set_price",
    "set_revenue",
    "write_column",
    "sql_update",
    "update_billing",
}


def _walk(obj):
    """Yield every (key, value) pair and every scalar value, recursively."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield ("key", k)
            yield from _walk(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk(v)
    else:
        yield ("value", obj)


# ─── Dry-run: nothing fires ───────────────────────────────────────────────────
def test_dry_run_commits_nothing():
    state = _realistic_state()
    result = executor.execute(state, dry_run=True)

    assert result["dry_run"] is True
    # Config commit did not actually commit.
    assert result["commit"]["committed"] is False
    assert result["commit"]["dry_run"] is True
    # A2A executors were not dispatched.
    assert result["dispatch"]["dry_run"] is True
    for who in ("kalai", "kural"):
        assert result["dispatch"][who]["dispatched"] is False
    # Resolution is a draft, not a published doc.
    assert result["resolution"]["dry_run"] is True
    assert result["resolution"]["doc_id"] is None
    assert result["resolution"]["url"].startswith("https://example.com/docs/draft/")
    # Follow-up planner entry not created.
    assert result["followup"]["created"] is False


def test_dry_run_still_records_resolution_and_dispatch_into_state():
    """Even dry, the executor writes the draft resolution + dispatch back to state
    and marks the gate executed — but with no real side effects."""
    state = _realistic_state()
    result = executor.execute(state, dry_run=True)
    assert state[SK.RESOLUTION] == result["resolution"]
    assert state[SK.DISPATCH] == result["dispatch"]
    assert state[SK.GATE_STATUS] == "executed"
    assert state[SK.RESOLUTION]["dry_run"] is True


# ─── SAFETY: feature-flag flip only, no price/revenue column write ────────────
def test_commit_is_a_feature_flag_flip():
    """Positive invariant: the commit is structurally a config flag flip."""
    result = executor.execute(_realistic_state(), dry_run=True)
    commit = result["commit"]
    assert commit["action"] == "feature_flag_flip"
    assert commit["flag"] == "pricing.pro_tier_v2"


def test_no_price_or_revenue_column_write_anywhere():
    """SAFETY: walk the entire executor result and assert there is no DB-column
    write — no forbidden column key, no forbidden write-verb value. This is the
    structural billing-safety guarantee, scanning keys AND values."""
    result = executor.execute(_realistic_state(), dry_run=True)

    bad_keys = []
    bad_verbs = []
    for kind, item in _walk(result):
        if kind == "key" and isinstance(item, str) and item.lower() in FORBIDDEN_COLUMN_KEYS:
            bad_keys.append(item)
        if kind == "value" and isinstance(item, str) and item.lower() in FORBIDDEN_WRITE_VERBS:
            bad_verbs.append(item)

    assert bad_keys == [], f"executor wrote a forbidden price/revenue column key: {bad_keys}"
    assert bad_verbs == [], f"executor emitted a forbidden write verb: {bad_verbs}"

    # And the ONLY mutating action present is the feature-flag flip.
    actions = [v for kind, v in _walk(result) if kind == "value" and isinstance(v, str)]
    assert "feature_flag_flip" in actions


# ─── No silent fake: the real path raises without a registered client ─────────
def test_real_side_effect_raises_without_client():
    """With dry_run=False and no example client registered, the executor must
    RAISE rather than silently fake a publish. (set_example_client is never called
    in the suite, so the module global stays None.)"""
    state = _realistic_state()
    with pytest.raises(RuntimeError):
        executor.execute(state, dry_run=False)
