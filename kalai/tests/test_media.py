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


# ─── imagen EOL escape hatch: a gemini-* pin drives generate_content ─────────
class _FakeInline:
    def __init__(self, data):
        self.data = data


class _FakePart:
    def __init__(self, data):
        self.inline_data = _FakeInline(data)


class _FakeContent:
    def __init__(self, data):
        self.parts = [_FakePart(data)]


class _FakeCandidate:
    def __init__(self, data):
        self.content = _FakeContent(data)


def _fake_client(calls):
    class _Models:
        def generate_images(self, **kw):
            calls["api"] = "generate_images"
            calls.update(kw)
            img = type("I", (), {"image": type("B", (), {"image_bytes": b"imagen-png"})()})()
            return type("R", (), {"generated_images": [img]})()

        def generate_content(self, **kw):
            calls["api"] = "generate_content"
            calls.update(kw)
            return type("R", (), {"candidates": [_FakeCandidate(b"gemini-png")]})()

    class _Client:
        def __init__(self, **kw):
            self.models = _Models()

    return _Client


def test_vertex_imagen_gemini_pin_uses_generate_content(monkeypatch):
    """The Imagen family EOLs 2026-06-24 (mid-judging). Pinning
    SAAKSHE_MODEL_IMAGEN to a gemini image model must drive generate_content and
    pull the still from inline_data — the env pin is a REAL escape hatch, not a
    different way to call a dead API."""
    import google.genai as genai_mod

    calls: dict = {}
    monkeypatch.setattr(genai_mod, "Client", _fake_client(calls))
    monkeypatch.setattr(config, "MODEL_IMAGEN", "gemini-2.5-flash-image")
    out = media._vertex_imagen(prompt="p", palette="slate")
    assert calls["api"] == "generate_content"
    assert out["bytes"] == b"gemini-png"
    assert out["image_ref"] == "vertex://imagen/gemini-2.5-flash-image"


def test_vertex_imagen_imagen_pin_still_uses_generate_images(monkeypatch):
    """An imagen-* pin keeps today's generate_images path, byte-identical."""
    import google.genai as genai_mod

    calls: dict = {}
    monkeypatch.setattr(genai_mod, "Client", _fake_client(calls))
    monkeypatch.setattr(config, "MODEL_IMAGEN", "imagen-4.0-generate-001")
    out = media._vertex_imagen(prompt="p")
    assert calls["api"] == "generate_images"
    assert out["bytes"] == b"imagen-png"
    assert out["image_ref"] == "vertex://imagen/imagen-4.0-generate-001"


# ─── the new config ids are wired (not dead constants) ───────────────────────
def test_vertex_model_ids_present():
    assert config.MODEL_IMAGEN and config.MODEL_VEO
    assert "imagen" in config.MODEL_IMAGEN
    assert "veo" in config.MODEL_VEO
