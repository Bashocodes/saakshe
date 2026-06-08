"""Deterministic engagement math + loop-termination + send-safety logic.

These functions never depend on what a model says — they are kural's safety
property. The mouth must never say something unverified, never send to an
ineligible recipient, never blow a value cap, and never double-send. Every loop
exits on a numeric threshold (claim_support >= CLAIM_THRESHOLD) or a
max-iteration rollback — never on "the copy reads well." Pure functions live
here so tests can pin them; the ADK check-agents in agent.py call them.

This mirrors arivu/tools/analyst.py: the numeric gates that protect the company
are pure, importable, and pinned to exact literals in the tests.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import FunctionTool

from common import config
from ..state import StateKeys, SEND_VALUE_CAP_USD
from ..util import parse_json, send_key


# ─── Claim-Judge gate (the after-agent LLM-as-judge → deterministic pass) ─────
def read_claim_report(state) -> dict[str, Any]:
    """Parse the Claim-Judge's structured report out of state (output_key text)."""
    raw = state.get(StateKeys.CLAIM_REPORT)
    return raw if isinstance(raw, dict) else parse_json(raw)


def claim_support_of(report: dict[str, Any]) -> float:
    """The judge's self-assessed support score in [0, 1], read defensively.

    A live Claude reply forced through the output_schema always yields a float
    here; the defensive parse only matters if the schema is ever loosened, in
    which case an unparseable reply reads 0.0 → the claim FAILS closed (back to
    the writer), never silently passes.
    """
    try:
        return max(0.0, min(1.0, float(report.get("claim_support", 0.0))))
    except (TypeError, ValueError):
        return 0.0


def claim_should_stop(support: float, round_: int) -> tuple[bool, bool, str]:
    """Return (stop, verified, reason) for the Claim-Judge rewrite loop.

    Verified ONLY when support crosses the bar (canon 0.86 ≥ 0.80). If the bounded
    rewrite loop hits MAX_CLAIM_ROUNDS without crossing, it stops UNVERIFIED — the
    mouth refuses to say it ("no safe message"), the inverse of arivu's rollback.
    Never stops on "they agreed" — only on this number or the cap.
    """
    if support >= config.CLAIM_THRESHOLD:
        return True, True, (
            f"claim support {support:.2f} ≥ {config.CLAIM_THRESHOLD} — every claim verified"
        )
    if round_ >= config.MAX_CLAIM_ROUNDS:
        return True, False, (
            f"max rewrite rounds ({config.MAX_CLAIM_ROUNDS}) reached at "
            f"{support:.2f} — unverified, the mouth stays shut (no safe message)"
        )
    return False, False, (
        f"claim support {support:.2f} < {config.CLAIM_THRESHOLD} — back to the writer to re-ground"
    )


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
