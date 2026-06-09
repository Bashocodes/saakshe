"""Deterministic engagement math + loop-termination + send-safety logic.

These functions never depend on what a model says — they are kural's safety
property. The mouth must never send to an ineligible recipient, never blow a
value cap, and never double-send — deterministic guards, never "the copy reads
well." (Claim-verification moved to kalai's fidelity loop in the separation; the
mouth carries kalai's cleared master verbatim.) Pure functions live here so
tests can pin them; the ADK agents in agent.py call them.

This mirrors arivu/tools/analyst.py: the numeric gates that protect the company
are pure, importable, and pinned to exact literals in the tests.
"""

from __future__ import annotations

from google.adk.tools import FunctionTool

from ..state import SEND_VALUE_CAP_USD
from ..util import send_key


# ─── Sender eligibility + value-cap gate (the before_tool guard) ──────────────
# SEND_VALUE_CAP_USD is the blast-radius guard: a single automated send may never
# exceed this notional value without a human. The mouth is a buyer, not a spender.
def send_eligibility(
    recipient: str,
    consent: bool,
    value_usd: float,
) -> tuple[bool, str]:
    """Decide whether a single outbound send is allowed BEFORE the tool fires.

    Three deterministic guards, fail-closed:
      * a real recipient (non-empty),
      * recorded consent (no cold blasts — the mouth never blasts),
      * value within the campaign cap (blast-radius / spend guard).
    """
    if not recipient or not str(recipient).strip():
        return False, "blocked: no recipient — the mouth never sends into the void"
    if not consent:
        return False, "blocked: no recorded consent — the mouth never blasts"
    try:
        v = float(value_usd)
    except (TypeError, ValueError):
        v = 0.0
    if v > SEND_VALUE_CAP_USD:
        return False, (
            f"blocked: value ${v:.2f} exceeds the per-send cap "
            f"${SEND_VALUE_CAP_USD:.2f} — needs a human"
        )
    return True, (
        f"eligible: consented recipient, value ${v:.2f} within the "
        f"${SEND_VALUE_CAP_USD:.2f} cap"
    )


# ─── No-double-send ledger (idempotent outbound, survives a retry) ────────────
class SendLedger:
    """An append-only, idempotent outbound ledger.

    The mouth marks a send BEFORE it fires and refuses any send whose key is
    already present, so a retry / re-run can never post the same thing twice.
    In live mode the same keys live in Firestore; the shape is identical so the
    backend is a flag, not a rewrite.
    """

    def __init__(self) -> None:
        self._sent: dict[str, dict] = {}

    def already_sent(self, key: str) -> bool:
        return key in self._sent

    def mark(self, key: str, meta: dict | None = None) -> bool:
        """Mark a key sent. Returns True if newly marked, False if it was a dup
        (in which case nothing should fire)."""
        if key in self._sent:
            return False
        self._sent[key] = dict(meta or {})
        return True

    def record_send(
        self, run_id: str, channel: str, recipient: str, meta: dict | None = None
    ) -> tuple[bool, str]:
        """Attempt to record one outbound send. Returns (fired, key).

        ``fired`` is False on a duplicate — the no-double-send guarantee.
        """
        key = send_key(run_id, channel, recipient)
        fired = self.mark(key, {"channel": channel, "recipient": recipient, **(meta or {})})
        return fired, key

    def count(self) -> int:
        return len(self._sent)


# A single shared in-process ledger for the running service (Firestore in live).
LEDGER = SendLedger()


# ─── Deterministic tools the research/channel agents call in live mode ────────
def audience_fit(list_size: int, opens_30d: int, topic_match_pct: float) -> dict:
    """Score how well a prospect list fits an outreach topic (Prospect Scout)."""
    reachable = max(0, int(opens_30d))
    fit = round(max(0.0, min(1.0, float(topic_match_pct) / 100.0)), 3)
    return {
        "reachable_30d": reachable,
        "fit_score": fit,
        "qualified_estimate": int(reachable * fit),
        "note": "send only to the consented, topic-fit slice — never the whole list",
    }


def timing_window(competitor_posts_7d: int, our_last_post_days: int) -> dict:
    """Pick a non-colliding publish window (Market Watcher)."""
    crowded = competitor_posts_7d >= 5
    stale = our_last_post_days >= 7
    return {
        "crowded_feed": crowded,
        "we_are_stale": stale,
        "recommendation": (
            "post now — feed is open and we've been quiet" if (stale and not crowded)
            else "hold for an open window — feed is crowded" if crowded
            else "post in the next 24h"
        ),
    }


audience_fit_tool = FunctionTool(func=audience_fit)
timing_window_tool = FunctionTool(func=timing_window)
