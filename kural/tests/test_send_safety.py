"""Pin the send-safety rails — the mouth never blasts and never double-sends.

Two deterministic guards wrap every world-facing act:
  * the before_tool eligibility / value-cap gate (analyst.send_eligibility +
    channels.send_guard), and
  * the no-double-send ledger (analyst.SendLedger).
These are pure / in-process so the test pins them exactly; the live backend
(Firestore) has the identical shape.
"""

from __future__ import annotations

import pytest

from kural.state import SEND_VALUE_CAP_USD
from kural.tools import analyst, channels


# ─── eligibility / value-cap gate ─────────────────────────────────────────────
def test_eligible_consented_recipient_within_cap():
    ok, reason = analyst.send_eligibility("buyer@co.com", consent=True, value_usd=10.0)
    assert ok is True
    assert "eligible" in reason


def test_blocks_no_recipient():
    ok, reason = analyst.send_eligibility("", consent=True, value_usd=0.0)
    assert ok is False
    assert "recipient" in reason


def test_blocks_without_consent_never_blasts():
    ok, reason = analyst.send_eligibility("buyer@co.com", consent=False, value_usd=0.0)
    assert ok is False
    assert "consent" in reason


def test_blocks_over_value_cap():
    ok, reason = analyst.send_eligibility("buyer@co.com", consent=True, value_usd=SEND_VALUE_CAP_USD + 1)
    assert ok is False
    assert "cap" in reason


def test_value_at_exactly_cap_is_allowed():
    ok, _ = analyst.send_eligibility("buyer@co.com", consent=True, value_usd=SEND_VALUE_CAP_USD)
    assert ok is True


# ─── no-double-send ledger ────────────────────────────────────────────────────
def test_ledger_marks_once_then_blocks_dup():
    ledger = analyst.SendLedger()
    fired1, key1 = ledger.record_send("runX", "x", "buyer@co.com")
    fired2, key2 = ledger.record_send("runX", "x", "buyer@co.com")
    assert fired1 is True
    assert fired2 is False           # the no-double-send guarantee
    assert key1 == key2              # same (run, channel, recipient) → same key
    assert ledger.count() == 1


def test_ledger_distinct_recipients_each_fire():
    ledger = analyst.SendLedger()
    f1, _ = ledger.record_send("runX", "x", "a@co.com")
    f2, _ = ledger.record_send("runX", "x", "b@co.com")
    assert (f1, f2) == (True, True)
    assert ledger.count() == 2


# ─── before_tool guard wires both rails together (fail-closed) ────────────────
def test_send_guard_blocks_dup_via_fresh_ledger(monkeypatch):
    fresh = analyst.SendLedger()
    monkeypatch.setattr(analyst, "LEDGER", fresh)
    d1 = channels.send_guard(run_id="r", channel="x", recipient="buyer@co.com", consent=True, value_usd=0.0)
    assert d1["allowed"] is True
    # mark it sent, then the guard must block the second attempt as a duplicate
    fresh.mark(d1["key"], {})
    d2 = channels.send_guard(run_id="r", channel="x", recipient="buyer@co.com", consent=True, value_usd=0.0)
    assert d2["allowed"] is False and d2["duplicate"] is True


def test_send_outreach_fail_closed_blocks_and_records_nothing(monkeypatch):
    fresh = analyst.SendLedger()
    monkeypatch.setattr(analyst, "LEDGER", fresh)
    res = channels.send_outreach("r", "x", recipient="", body="hi", consent=True, dry_run=True)
    assert res["sent"] is False and res["blocked"] is True
    assert fresh.count() == 0        # a blocked send leaves no ledger trace


def test_send_outreach_dry_run_does_not_call_client(monkeypatch):
    fresh = analyst.SendLedger()
    monkeypatch.setattr(analyst, "LEDGER", fresh)
    # No channel client registered → a real send would raise; dry-run must not call it.
    res = channels.send_outreach("r", "x", recipient="buyer@co.com", body="hi", dry_run=True)
    assert res["sent"] is True and res["dry_run"] is True
    # second identical send is a ledger dup — no double-send even in dry-run
    dup = channels.send_outreach("r", "x", recipient="buyer@co.com", body="hi", dry_run=True)
    assert dup["sent"] is False and dup.get("duplicate") is True


def test_send_outreach_live_without_client_raises(monkeypatch):
    fresh = analyst.SendLedger()
    monkeypatch.setattr(analyst, "LEDGER", fresh)
    channels.set_channel_client(None)  # ensure no client
    with pytest.raises(RuntimeError):
        channels.send_outreach("r", "x", recipient="buyer@co.com", body="hi", dry_run=False)
