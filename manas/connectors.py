"""manas/connectors.py — manas as the CUSTODIAN of the company's keys to the world.

Under the faculty-v2 re-assignment, the channel credentials (the founder's
delivery webhook + the stats surface + their Bearer) are held HERE, in the
memory/keeper realm — not in kural. kural (the mouth) still DECIDES and FIRES:
it calls these broker skills at tap-2 and never sees the raw token. manas
resolves the credential and makes the privileged call.

    The key lives in the keeper (manas); the act lives in the mouth (kural).

This preserves manas's "knows; never acts/posts" contract: manas does not decide
to publish and does not run the gate — it only lends the credential and relays
the one POST kural already cleared. The env var NAMES are unchanged
(SAAKSHE_CHANNEL_WEBHOOK_URL / SAAKSHE_CHANNEL_WEBHOOK_TOKEN /
SAAKSHE_CHANNEL_STATS_URL) so the deploy passthrough + its test are untouched and
a revert is pure code. Secrets are read LAZILY at call time — never at import,
never logged.

Registered A2A skills (always registered, inert under v1 — nobody dispatches to
them until SAAKSHE_FACULTY_V2 routes kural's channel client + measure here):

  * manas.publish_action(action, args) -> dict   the world-facing POST (kural fires it post-tap-2)
  * manas.read_outcomes()              -> list    the stats GET (kural.measure reads through it)
"""

from __future__ import annotations

import os

from common import a2a

NS = "manas"
_TIMEOUT = 20.0


def _webhook_url() -> str:
    return (os.environ.get("SAAKSHE_CHANNEL_WEBHOOK_URL") or "").strip()


def _stats_url() -> str:
    return (os.environ.get("SAAKSHE_CHANNEL_STATS_URL") or "").strip()


def _token() -> str:
    return (os.environ.get("SAAKSHE_CHANNEL_WEBHOOK_TOKEN") or "").strip()


def channel_configured() -> bool:
    """Whether the keeper holds a delivery webhook — the arm-gate's connector key."""
    return bool(_webhook_url())


def stats_configured() -> bool:
    """Whether the keeper holds a stats surface — mirrors kural's v1 stats_url()
    guard so an unconfigured surface stays inert (no facts, no stream events)."""
    return bool(_stats_url())


def publish_action(action: str, args: dict) -> dict:
    """The world-facing channel POST, fired with manas-custodied credentials.

    kural dispatches here (a2a.dispatch("manas", "publish_action", …)) ONLY on a
    non-dry, tap-2-armed publish. Returns the receiver JSON verbatim. Raises on a
    transport error (the executor's no-silent-fake rule) — kural's ledger has
    already marked the attempt, so a retry cannot double-send. The raw token is
    read here and never leaves this function.
    """
    url = _webhook_url()
    if not url:
        raise RuntimeError(
            "manas.publish_action: no SAAKSHE_CHANNEL_WEBHOOK_URL configured — "
            "the keeper holds no channel key to fire."
        )
    import httpx  # lazy — no client at import, mirrors the media/webhook rule

    headers = {"content-type": "application/json"}
    token = _token()
    if token:
        headers["authorization"] = f"Bearer {token}"
    resp = httpx.post(url, json={"action": action, "args": args},
                      headers=headers, timeout=_TIMEOUT)
    resp.raise_for_status()
    try:
        out = resp.json()
    except ValueError:
        out = {}
    return out if isinstance(out, dict) else {}


def read_outcomes() -> list[dict]:
    """Read raw engagement-outcome rows from the founder's stats surface.

    Fail-soft: [] when unconfigured or on ANY failure (a flaky stats endpoint must
    never break a run — only world-facing WRITES fail closed). kural.measure
    normalizes these rows into cited facts.
    """
    url = _stats_url()
    if not url:
        return []
    headers = {"accept": "application/json"}
    token = _token()
    if token:
        headers["authorization"] = f"Bearer {token}"
    try:
        import httpx  # lazy

        resp = httpx.get(url, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001 — reads fail soft
        return []
    rows = data.get("outcomes") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


# Register the broker skills at import (idempotent). Always registered so the
# demo/CI import path is identical regardless of the flag; v1 simply never
# dispatches to them.
a2a.register_skill(NS, "publish_action", publish_action)
a2a.register_skill(NS, "read_outcomes", read_outcomes)
a2a.register_skill(NS, "stats_configured", stats_configured)
