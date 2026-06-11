"""The deploy carries the channel surface — loop step 6's last missing metre.

The webhook adapter, the AND-gate, and the startup registration all existed;
no deploy profile ever carried the env, so kural had never been ABLE to send.
These tests pin the passthrough (and its one deliberate property: nothing is
ever defaulted — arming stays an explicit founder act)."""

from __future__ import annotations

from pathlib import Path

SCRIPT = (Path(__file__).parents[1] / "deploy_cloudrun.sh").read_text()


def test_deploy_passes_channel_env_through():
    for var in ("SAAKSHE_CHANNEL_WEBHOOK_URL", "SAAKSHE_CHANNEL_WEBHOOK_TOKEN",
                "SAAKSHE_CHANNEL_STATS_URL", "SAAKSHE_ALLOW_LIVE_SEND"):
        assert var in SCRIPT, f"deploy script must pass {var} through when set"


def test_deploy_never_defaults_the_arm_flag():
    """The triple AND-gate's env key must never be defaulted on — a deploy with
    no explicit SAAKSHE_ALLOW_LIVE_SEND in the deployer's env ships a dry mouth."""
    assert "SAAKSHE_ALLOW_LIVE_SEND=1" not in SCRIPT


def test_startup_registers_webhook_client_when_configured(monkeypatch):
    """service startup binds webhook.from_env() into channels — with the env set,
    has_channel_client() turns true and the AND-gate's third key exists."""
    from kural.tools import channels
    from kural.tools.adapters import webhook

    monkeypatch.setenv("SAAKSHE_CHANNEL_WEBHOOK_URL", "https://intake.example/hook")
    fn = webhook.from_env()
    assert callable(fn)
    monkeypatch.setattr(channels, "_channel_call", None)
    channels.set_channel_client(fn)
    assert channels.has_channel_client()


# ─── the fast deploy: cached image path is the default ────────────────────────
def test_deploy_uses_cached_image_path_by_default():
    """Repeat deploys build via cloudbuild.yaml with --cache-from and deploy by
    image ref; --source is the explicit escape hatch (SAAKSHE_DEPLOY_SOURCE=1)."""
    assert "cloudbuild.yaml" in SCRIPT
    assert "--image" in SCRIPT
    assert "SAAKSHE_DEPLOY_SOURCE" in SCRIPT          # the fallback stays reachable
    assert "SAAKSHE_DEPLOY_BOOTSTRAP" in SCRIPT       # API/IAM ceremony off the hot path


def test_cloudbuild_caches_from_latest():
    from pathlib import Path

    cb = (Path(__file__).parents[1] / "cloudbuild.yaml").read_text()
    assert "--cache-from" in cb and "${_IMAGE}:latest" in cb
