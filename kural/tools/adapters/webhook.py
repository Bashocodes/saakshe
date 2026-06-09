"""The generic webhook channel — kural's first REAL outbound adapter.

POSTs every armed channel action to one founder-configured endpoint:

    SAAKSHE_CHANNEL_WEBHOOK_URL    — where the action lands (required)
    SAAKSHE_CHANNEL_WEBHOOK_TOKEN  — optional Bearer for that endpoint

Body shape (one POST per action):

    {"action": "publish" | "send_outreach", "args": {…}}

The receiver decides what the action means — a content-autopilot queue that
carries the post through its own approval to the platforms, a webhook relay,
a custom worker. saakshe holds no platform keys and names no platform: the
founder's delivery infrastructure is pure configuration, so the codebase
stays ZERO-coupled to any one company or service.

The response JSON is returned verbatim to ``channels.publish_master`` /
``send_outreach`` — a receiver that returns ``{"urls": {...}}`` sees those
URLs surface on the founder's stream. Errors raise (mirroring the executor's
no-silent-fake rule); the publish ledger has already marked the attempt, so a
retry cannot double-send.
"""

from __future__ import annotations

import os
from typing import Optional

_TIMEOUT = 20.0


def from_env() -> Optional["ChannelCall"]:  # noqa: F821 — protocol lives in channels.py
    """Build the webhook ChannelCall from the environment, or None if unset."""
    url = (os.environ.get("SAAKSHE_CHANNEL_WEBHOOK_URL") or "").strip()
    if not url:
        return None
    token = (os.environ.get("SAAKSHE_CHANNEL_WEBHOOK_TOKEN") or "").strip()

    def channel_call(action: str, arguments: dict) -> dict:
        import httpx  # lazy — no client at import, mirrors the media wrapper rule

        headers = {"content-type": "application/json"}
        if token:
            headers["authorization"] = f"Bearer {token}"
        resp = httpx.post(url, json={"action": action, "args": arguments},
                          headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        try:
            out = resp.json()
        except ValueError:
            out = {}
        return out if isinstance(out, dict) else {}

    return channel_call
