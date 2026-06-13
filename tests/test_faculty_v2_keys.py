"""manas's channel-key custody broker — the four-faculty key custody.

The load-bearing property: kural fires the publish but the raw channel token is read
ONLY inside manas — kural holds a tokenless capability handle.
"""

from __future__ import annotations

from common import a2a
from manas import connectors  # registers manas.publish_action / read_outcomes
from kural.tools import channels


# ─── the broker is registered (the route to the world) ───────────────────────
def test_manas_broker_skills_registered():
    assert a2a.has_skill("manas", "publish_action")
    assert a2a.has_skill("manas", "read_outcomes")


def test_read_outcomes_fail_soft_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SAAKSHE_CHANNEL_STATS_URL", raising=False)
    assert connectors.read_outcomes() == []


def test_publish_action_raises_without_a_key(monkeypatch):
    monkeypatch.delenv("SAAKSHE_CHANNEL_WEBHOOK_URL", raising=False)
    try:
        connectors.publish_action("publish", {"x": 1})
        assert False, "expected RuntimeError when the keeper holds no key"
    except RuntimeError as e:
        assert "no SAAKSHE_CHANNEL_WEBHOOK_URL" in str(e)


# ─── the seam: kural fires, manas holds the token ─────────────────────────────
class _Resp:
    def raise_for_status(self):  # noqa: D401
        return None

    def json(self):
        return {"urls": {"x": "https://x.com/co/status/LIVE-x"}}


def test_publish_routes_through_manas_and_only_manas_sees_the_token(monkeypatch):
    monkeypatch.setenv("SAAKSHE_CHANNEL_WEBHOOK_URL", "https://relay.example/post")
    monkeypatch.setenv("SAAKSHE_CHANNEL_WEBHOOK_TOKEN", "secret-bearer")

    captured: dict = {}

    def fake_post(url, json, headers, timeout):  # noqa: A002 — mirror httpx.post kwargs
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json
        return _Resp()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)

    # kural holds ONLY a tokenless capability handle that dispatches to the keeper;
    # set_channel_client stays on kural's module so has_channel_client()/the
    # orchestrator arm-gate are unchanged.
    channels.set_channel_client(
        lambda action, args: a2a.dispatch("manas", "publish_action", action, args)
    )
    assert channels.has_channel_client()
    try:
        out = channels.publish_master({"channel": "x", "caption": "hi"}, dry_run=False)
    finally:
        channels.set_channel_client(None)

    # The POST fired through manas, and the keeper applied the custodied token —
    # kural's handle never named it.
    assert captured["url"] == "https://relay.example/post"
    assert captured["headers"]["authorization"] == "Bearer secret-bearer"
    assert captured["body"]["action"] == "publish"
    assert out["urls"]["x"].endswith("LIVE-x")


# ─── the orchestrator joined-clearance (kalai media AND kural copy) ───────────
class _Res:
    def __init__(self, output, state):
        self.output = output
        self.state = state
        self.status = "awaiting_approval"
        self.gate = True


def test_joined_clearance_blocks_a_copy_unchecked_post():
    import orchestrator as o

    checked = _Res({"compliance": "cleared"}, {"copy_claim_checked": True})
    unchecked = _Res({"compliance": "cleared"}, {"copy_claim_checked": False})
    # media-cleared AND copy-claim-checked → the post may reach tap-2
    assert o._kalai_media_cleared(checked) and o._kural_copy_claim_checked(checked)
    # media-cleared but copy UNCHECKED → the words were never proven → blocked
    assert o._kalai_media_cleared(unchecked)
    assert o._kural_copy_claim_checked(unchecked) is False
