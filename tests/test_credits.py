"""Credits module tests — the cost-map + idempotent spend/refund seam.

Pins the contract the routes depend on WITHOUT touching Supabase: every test
monkeypatches the two private httpx seams (`credits._rpc`, `credits._get_balance`)
with in-process fakes, so the whole suite runs creds-free and offline.

The behaviours pinned here:
  * the canonical cost-map defaults (and the signup grant);
  * `cost()` recomputes from env at call time (so a route can override per-deploy);
  * spend returns the new balance, and a P0001 INSUFFICIENT_CREDITS turns into an
    `OutOfCredits` carrying the *current* balance (read via the balance seam);
  * refund threads both idempotency keys through to the RPC;
  * `charge` is a NO-OP for owners, in demo mode, and when the store isn't Supabase
    (no RPC fires at all), spends exactly once on the live+supabase+non-owner path,
    and on an exception inside the block refunds then re-raises — the witness's
    "temporary, not charged" rule, classified by error CODE not message.
"""

from __future__ import annotations

import pytest

from common import config, credits


# ─── a recording fake for the rpc seam ───────────────────────────────────────
class RecordingRpc:
    """Stands in for credits._rpc; records every call and returns a scripted int."""

    def __init__(self, ret: int = 0):
        self.calls: list[tuple[str, dict]] = []
        self.ret = ret

    def __call__(self, fn: str, params: dict) -> int:
        self.calls.append((fn, dict(params)))
        return self.ret


class _User:
    """Duck-typed account object (.user_id + .is_owner) the charge ctx expects."""

    def __init__(self, user_id: str = "u1", is_owner: bool = False):
        self.user_id = user_id
        self.is_owner = is_owner


@pytest.fixture
def live_supabase(monkeypatch):
    """Force the chargeable path: live mode + the Supabase store selected."""
    monkeypatch.setenv("SAAKSHE_STORE", "supabase")
    monkeypatch.setattr(config, "mode", lambda: "live")
    return monkeypatch


# ─── the cost-map defaults (the founder's price card, 2026-06-11) ─────────────
def test_cost_defaults():
    assert credits.COSTS == {
        "flywheel_run": 1,
        "connect_ingest": 100,   # grasping a repository, questions included
        "manas_edit": 1,
        "kalai_make": 1,
        "kural_engage": 1,
        "saakshe_ask": 1,        # a chat turn is an action too
    }
    assert credits.SIGNUP_GRANT == 500


def test_cost_helper_matches_defaults():
    assert credits.cost("connect_ingest") == 100
    assert credits.cost("manas_edit") == 1
    assert credits.cost("saakshe_ask") == 1


def test_cost_helper_recomputes_from_env(monkeypatch):
    # COSTS is the frozen import-time snapshot; cost() must re-read env at call time.
    monkeypatch.setenv("COST_FLYWHEEL_RUN", "99")
    assert credits.cost("flywheel_run") == 99
    assert credits.COSTS["flywheel_run"] == 1  # snapshot unchanged


def test_billing_enabled_by_store_or_flag(monkeypatch):
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    monkeypatch.delenv("SAAKSHE_BILLING", raising=False)
    assert credits.billing_enabled() is False
    monkeypatch.setenv("SAAKSHE_BILLING", "1")          # the gated file-store demo
    assert credits.billing_enabled() is True
    monkeypatch.delenv("SAAKSHE_BILLING")
    monkeypatch.setenv("SAAKSHE_STORE", "supabase")     # the full billing profile
    assert credits.billing_enabled() is True


# ─── spend ────────────────────────────────────────────────────────────────────
def test_spend_returns_new_balance(monkeypatch):
    rec = RecordingRpc(ret=80)
    monkeypatch.setattr(credits, "_rpc", rec)
    out = credits.spend("u1", 20, "flywheel run", "idem-1")
    assert out == 80
    assert len(rec.calls) == 1
    fn, params = rec.calls[0]
    assert fn == "saakshe_spend"
    assert params == {
        "p_user_id": "u1",
        "p_amount": 20,
        "p_reason": "flywheel run",
        "p_idem_key": "idem-1",
    }


def test_spend_insufficient_raises_out_of_credits_with_balance(monkeypatch):
    def boom(fn, params):
        raise credits.CreditError("INSUFFICIENT_CREDITS", code="P0001")

    monkeypatch.setattr(credits, "_rpc", boom)
    # the balance seam the route reads to tell the user how much they have left
    monkeypatch.setattr(credits, "_get_balance", lambda uid: 7)

    with pytest.raises(credits.OutOfCredits) as ei:
        credits.spend("u1", 20, "flywheel run", "idem-2")
    assert ei.value.balance == 7
    assert isinstance(ei.value, credits.CreditError)


def test_spend_other_failure_raises_credit_error(monkeypatch):
    def boom(fn, params):
        raise credits.CreditError("boom", code="500")

    monkeypatch.setattr(credits, "_rpc", boom)
    with pytest.raises(credits.CreditError):
        credits.spend("u1", 20, "flywheel run", "idem-x")


# ─── refund ───────────────────────────────────────────────────────────────────
def test_refund_threads_both_keys(monkeypatch):
    rec = RecordingRpc(ret=100)
    monkeypatch.setattr(credits, "_rpc", rec)
    out = credits.refund("u1", 20, "internal failure — not charged", "idem-3", "idem-3:refund")
    assert out == 100
    fn, params = rec.calls[0]
    assert fn == "saakshe_refund"
    assert params == {
        "p_user_id": "u1",
        "p_amount": 20,
        "p_reason": "internal failure — not charged",
        "p_spend_idem_key": "idem-3",
        "p_refund_idem_key": "idem-3:refund",
    }


# ─── grant_signup ─────────────────────────────────────────────────────────────
def test_grant_signup_uses_signup_grant(monkeypatch):
    rec = RecordingRpc(ret=100)
    monkeypatch.setattr(credits, "_rpc", rec)
    out = credits.grant_signup("u1", "founder@example.com", is_owner=True)
    assert out == 100
    fn, params = rec.calls[0]
    assert fn == "saakshe_grant_signup"
    assert params == {
        "p_user_id": "u1",
        "p_email": "founder@example.com",
        "p_grant": credits.SIGNUP_GRANT,
        "p_is_owner": True,
    }


# ─── balance ──────────────────────────────────────────────────────────────────
def test_balance_routes_through_get_balance_seam(monkeypatch):
    monkeypatch.setattr(credits, "_get_balance", lambda uid: 42)
    assert credits.balance("u1") == 42


# ─── charge: the NO-OP branches ───────────────────────────────────────────────
def test_charge_owner_is_noop(monkeypatch):
    rec = RecordingRpc()
    monkeypatch.setattr(credits, "_rpc", rec)
    monkeypatch.setenv("SAAKSHE_STORE", "supabase")
    monkeypatch.setattr(config, "mode", lambda: "live")

    with credits.charge(_User(is_owner=True), "flywheel_run",
                        idem_key="k", reason="r") as r:
        assert r["charged"] is False
    assert rec.calls == []  # owners are never charged — no RPC at all


def test_charge_demo_mode_with_supabase_still_bills(monkeypatch):
    """DELIBERATE: billing tracks the Supabase backend + a real founder, NOT the
    model-liveness mode. So a signed-in user on the Supabase store IS billed even in
    demo/scripted mode (this is what makes the billing path testable creds-free, and
    bills correctly in the hybrid deploy). The public file-store demo stays free —
    see test_charge_non_supabase_store_is_noop."""
    rec = RecordingRpc(ret=80)
    monkeypatch.setattr(credits, "_rpc", rec)
    monkeypatch.setenv("SAAKSHE_STORE", "supabase")
    monkeypatch.setattr(config, "mode", lambda: "demo")

    with credits.charge(_User(is_owner=False), "flywheel_run",
                        idem_key="k", reason="r") as r:
        assert r["charged"] is True
    assert [c[0] for c in rec.calls] == ["saakshe_spend"]


def test_charge_non_supabase_store_is_noop(monkeypatch):
    rec = RecordingRpc()
    monkeypatch.setattr(credits, "_rpc", rec)
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)  # file store → no billing
    monkeypatch.setattr(config, "mode", lambda: "live")

    with credits.charge(_User(is_owner=False), "flywheel_run",
                        idem_key="k", reason="r") as r:
        assert r["charged"] is False
    assert rec.calls == []


# ─── charge: the chargeable path ──────────────────────────────────────────────
def test_charge_live_supabase_nonowner_spends_once(live_supabase):
    rec = RecordingRpc(ret=80)
    live_supabase.setattr(credits, "_rpc", rec)

    with credits.charge(_User(is_owner=False), "flywheel_run",
                        idem_key="k1", reason="flywheel run") as r:
        assert r["charged"] is True

    assert len(rec.calls) == 1
    fn, params = rec.calls[0]
    assert fn == "saakshe_spend"
    assert params["p_amount"] == credits.cost("flywheel_run")
    assert params["p_idem_key"] == "k1"
    assert params["p_reason"] == "flywheel run"


def test_charge_exception_inside_block_refunds_then_reraises(live_supabase):
    rec = RecordingRpc(ret=80)
    live_supabase.setattr(credits, "_rpc", rec)

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with credits.charge(_User(is_owner=False), "flywheel_run",
                            idem_key="k2", reason="flywheel run"):
            raise Boom("downstream model died")

    # spend, then refund — the work failed so the user is made whole.
    assert [c[0] for c in rec.calls] == ["saakshe_spend", "saakshe_refund"]
    refund_params = rec.calls[1][1]
    assert refund_params["p_amount"] == credits.cost("flywheel_run")
    assert refund_params["p_spend_idem_key"] == "k2"
    assert refund_params["p_refund_idem_key"] == "k2:refund"
    assert refund_params["p_reason"] == "internal failure — not charged"


# ─── the route-facing constants ───────────────────────────────────────────────
def test_temporary_failure_msg_present():
    assert credits.TEMPORARY_FAILURE_MSG == (
        "Something failed on our side — this is temporary and you were not charged."
    )


def test_out_of_credits_payload_shape():
    assert credits.out_of_credits_payload(7) == {"error": "out of credits", "balance": 7}
