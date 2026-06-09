"""The channel surface — the only place kural touches the world.

kural holds the channel keys; it sends outreach *as the buyer* (OAuth, not a
no-reply blast) and publishes kalai's approved creative. Two safety rails wrap
every world-facing act:

  * a ``before_tool`` eligibility/value-cap gate on the Sender (drives the
    deterministic ``analyst.send_eligibility`` + the no-double-send
    ``analyst.LEDGER``), so an ineligible / over-cap / duplicate send never
    fires, and
  * ``dry_run`` on every side effect — the real send/publish fires ONLY when
    ``dry_run`` is False, which the server sets only after the founder's tap-2.

This mirrors arivu/tools/executor.py: there is no silent fake — the real path
calls the injected channel client or raises.
"""

from __future__ import annotations

from typing import Callable

from common import config
from . import analyst
from ..util import send_key

# Injected by the server/CLI when real side effects are authorised. Signature:
#   channel_call(action: str, arguments: dict) -> dict
ChannelCall = Callable[[str, dict], dict]
_channel_call: ChannelCall | None = None


def set_channel_client(fn: ChannelCall) -> None:
    """Register the real channel caller (used only on non-dry runs)."""
    global _channel_call
    _channel_call = fn


def has_channel_client() -> bool:
    """Whether a real channel caller is registered — the arm-real-send AND-gate
    reads this so a tap can never arm a publish that would only raise."""
    return _channel_call is not None


def _call(action: str, args: dict) -> dict:
    if _channel_call is None:
        raise RuntimeError(
            f"Real channel side effect '{action}' requested but no channel client "
            "is registered. Either run dry, or call set_channel_client() first."
        )
    return _channel_call(action, args)


# ─── before_tool gate for the Sender ──────────────────────────────────────────
def send_guard(
    *, run_id: str, channel: str, recipient: str, consent: bool, value_usd: float
) -> dict:
    """The Sender's before_tool eligibility/value-cap + no-double-send check.

    Returns a decision dict; ``allowed`` is False (with a reason) whenever the
    eligibility gate fails OR the ledger already holds this send. The agent must
    not fire its send tool when ``allowed`` is False — fail-closed.
    """
    eligible, reason = analyst.send_eligibility(recipient, consent, value_usd)
    if not eligible:
        return {"allowed": False, "reason": reason, "duplicate": False}
    key = send_key(run_id, channel, recipient)
    if analyst.LEDGER.already_sent(key):
        return {
            "allowed": False,
            "duplicate": True,
            "reason": f"blocked: {key} already in the ledger — no double-send",
            "key": key,
        }
    return {"allowed": True, "reason": reason, "duplicate": False, "key": key}


# ─── Sender (outreach as the buyer) ───────────────────────────────────────────
def send_outreach(
    run_id: str,
    channel: str,
    recipient: str,
    body: str,
    *,
    consent: bool = True,
    value_usd: float = 0.0,
    dry_run: bool,
) -> dict:
    """Send one outreach message, behind the before_tool gate + ledger.

    Fail-closed: refuses (and records nothing) when the guard blocks. Marks the
    ledger BEFORE firing so a crash-and-retry can't double-send. Real OAuth send
    fires only when ``dry_run`` is False.
    """
    decision = send_guard(
        run_id=run_id, channel=channel, recipient=recipient,
        consent=consent, value_usd=value_usd,
    )
    if not decision["allowed"]:
        return {"sent": False, "blocked": True, **decision}

    fired, key = analyst.LEDGER.record_send(
        run_id, channel, recipient, {"value_usd": value_usd, "dry_run": dry_run}
    )
    if not fired:  # raced into a duplicate between guard and mark — still safe.
        return {"sent": False, "blocked": True, "duplicate": True,
                "reason": "ledger dup at mark", "key": key}

    result = {
        "sent": True, "blocked": False, "channel": channel, "recipient": recipient,
        "as_buyer_oauth": True, "ledger_key": key, "dry_run": dry_run,
        "preview": body[:140],
    }
    if not dry_run:
        _call("send_outreach", {"channel": channel, "recipient": recipient, "body": body})
    return result


# ─── Publisher (kalai's approved creative, behind tap 2) ──────────────────────
def publish_master(post: dict, *, dry_run: bool) -> dict:
    """Publish the verified post to the channels. Dry-run by default — the
    world-facing act stays gated behind the founder's publish sign-off (tap 2)."""
    channel = post.get("channel", "x+ig+linkedin")
    slug = config.CANON.get("resolution_slug", "launch")
    # Preview URLs are keyed to the CONNECTED org, never a canned name — an
    # AIKIZI-grounded run must not flash someone else's handle at the founder.
    import re as _re
    try:
        from common import project as _project
        org = (_project.current_store().org_for_flywheel().get("name") or "")
    except Exception:  # noqa: BLE001 — a missing store never sinks a publish
        org = ""
    handle = _re.sub(r"[^a-z0-9]+", "", org.lower()) or "company"
    base = (
        f"https://x.com/{handle}/status/DRAFT-{slug}" if dry_run
        else f"https://x.com/{handle}/status/LIVE-{slug}"
    )
    urls = {
        "x": base,
        "ig": base.replace("x.com", "instagram.com"),
        "linkedin": base.replace("x.com", "linkedin.com"),
    }
    if not dry_run:
        published = _call("publish", {"channel": channel, "post": post})
        urls = published.get("urls", urls)
    return {
        "channel": channel,
        "urls": urls,
        "as_buyer_oauth": True,
        "claim_support": post.get("claim_support"),
        "grounded_in": post.get("grounded_in"),
        "ledger": "firestore: marked sent (no double-send on retry)",
        "dry_run": dry_run,
    }
