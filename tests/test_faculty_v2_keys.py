"""faculty-v2 Phase 0+1 — the migration flag + manas's channel-key custody broker.

V1 (flag OFF, the default everywhere incl. these tests' baseline) is byte
identical; these tests exercise the NEW v2 surface explicitly. The load-bearing
property: under v2 kural fires the publish but the raw channel token is read
ONLY inside manas — kural holds a tokenless capability handle.
"""

from __future__ import annotations

from common import a2a, config
from manas import connectors  # registers manas.publish_action / read_outcomes
from kural.tools import channels


# ─── the flag ────────────────────────────────────────────────────────────────
def test_faculty_v2_default_is_on_after_golive(monkeypatch):
    # Phase 3 flipped the default ON (go-live); the flag stays as the rollback path.
    monkeypatch.delenv("SAAKSHE_FACULTY_V2", raising=False)
    assert config.faculty_v2() is True
    # the rollback is explicit and still works:
    monkeypatch.setenv("SAAKSHE_FACULTY_V2", "0")
    assert config.faculty_v2() is False


def test_faculty_v2_reads_env(monkeypatch):
    monkeypatch.setenv("SAAKSHE_FACULTY_V2", "1")
    assert config.faculty_v2() is True
    monkeypatch.setenv("SAAKSHE_FACULTY_V2", "off")
    assert config.faculty_v2() is False


# ─── the broker is registered (inert under v1, the route under v2) ───────────
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


def test_v2_publish_routes_through_manas_and_only_manas_sees_the_token(monkeypatch):
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


# ─── Phase 2: the orchestrator joined-clearance (kalai media AND kural copy) ───
class _Res:
    def __init__(self, output, state):
        self.output = output
        self.state = state
        self.status = "awaiting_approval"
        self.gate = True


def test_joined_clearance_blocks_a_copy_unchecked_post(monkeypatch):
    monkeypatch.setenv("SAAKSHE_FACULTY_V2", "1")
    import orchestrator as o

    checked = _Res({"compliance": "cleared"}, {"copy_claim_checked": True})
    unchecked = _Res({"compliance": "cleared"}, {"copy_claim_checked": False})
    # media-cleared AND copy-claim-checked → the post may reach tap-2
    assert o._kalai_media_cleared(checked) and o._kural_copy_claim_checked(checked)
    # media-cleared but copy UNCHECKED → the words were never proven → blocked
    assert o._kalai_media_cleared(unchecked)
    assert o._kural_copy_claim_checked(unchecked) is False


def test_joined_clearance_is_a_noop_under_v1(monkeypatch):
    monkeypatch.setenv("SAAKSHE_FACULTY_V2", "0")   # the explicit rollback path
    import orchestrator as o

    # v1: kural authors nothing (kalai cleared the copy), so the copy signal is
    # always "checked" and the joined-clearance never blocks.
    assert o._kural_copy_claim_checked(_Res({}, {})) is True
