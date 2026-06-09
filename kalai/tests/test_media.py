"""kalai media wrapper — demo stays pixel-free + creds-free; live dispatches to Vertex.

The studio's one chargeable media act. In demo mode the wrapper returns a
DETERMINISTIC placeholder ref (``vertex://imagen/placeholder/<hash>`` /
``vertex://veo/placeholder/<hash>``) with ``bytes=None`` and ``spend_usd=0.0`` — NO
network, NO creds, so CI never touches Vertex. The live branch dispatches to a tiny
``_vertex_imagen``/``_vertex_veo`` that the tests mock — the only thing that keeps
``SAAKSHE_MODE=live`` from making a real call is that those functions own the genai
client (lazy-imported inside them), so mocking them short-circuits every network path.
"""

from __future__ import annotations

from common import config
from kalai import media


# ─── stills: demo placeholder, no network ────────────────────────────────────
def test_render_still_demo_returns_deterministic_placeholder_no_network(monkeypatch):
    monkeypatch.setenv("SAAKSHE_MODE", "demo")
    out = media.render_still(prompt="a clean launch banner", palette="slate")
    assert out["image_ref"].startswith("vertex://imagen/placeholder/")
    assert out["bytes"] is None              # no pixels in demo
    assert out["spend_usd"] == 0.0
    # deterministic: same prompt → same ref (hashed on the prompt)
    again = media.render_still(prompt="a clean launch banner", palette="charcoal")
    assert again["image_ref"] == out["image_ref"]
    other = media.render_still(prompt="a different banner", palette="slate")
    assert other["image_ref"] != out["image_ref"]


def test_render_still_live_dispatches_to_vertex_with_prompt(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(
        media, "_vertex_imagen",
        lambda **kw: (calls.update(kw) or {
            "image_ref": "vertex://imagen/real/1", "bytes": b"x", "spend_usd": 0.02,
        }),
    )
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    out = media.render_still(prompt="p", palette="slate", _force_live=True)
    assert out["image_ref"] == "vertex://imagen/real/1"
    assert out["bytes"] == b"x"
    assert out["spend_usd"] == 0.02
    assert calls["prompt"] == "p"            # the prompt reached the Vertex client
    assert calls["palette"] == "slate"


# ─── reel/video: demo placeholder, no network ────────────────────────────────
def test_render_reel_demo_returns_deterministic_placeholder_no_network(monkeypatch):
    monkeypatch.setenv("SAAKSHE_MODE", "demo")
    out = media.render_reel(prompt="a 6s launch teaser", stills=["s1", "s2"])
    assert out["video_ref"].startswith("vertex://veo/placeholder/")
    assert out["bytes"] is None
    assert out["spend_usd"] == 0.0
    again = media.render_reel(prompt="a 6s launch teaser", stills=["s1"])
    assert again["video_ref"] == out["video_ref"]


def test_render_reel_live_dispatches_to_vertex_with_prompt(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(
        media, "_vertex_veo",
        lambda **kw: (calls.update(kw) or {
            "video_ref": "vertex://veo/real/1", "bytes": b"v", "spend_usd": 0.40,
        }),
    )
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    out = media.render_reel(prompt="teaser", stills=["s1"], _force_live=True)
    assert out["video_ref"] == "vertex://veo/real/1"
    assert out["bytes"] == b"v"
    assert out["spend_usd"] == 0.40
    assert calls["prompt"] == "teaser"


# ─── the new config ids are wired (not dead constants) ───────────────────────
def test_vertex_model_ids_present():
    assert config.MODEL_IMAGEN and config.MODEL_VEO
    assert "imagen" in config.MODEL_IMAGEN
    assert "veo" in config.MODEL_VEO
