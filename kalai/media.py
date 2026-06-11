"""kalai — the Vertex media client wrapper (real pixels/video; demo pixel-free).

The studio's one chargeable media act. ``render_still`` (Vertex Imagen) and
``render_reel`` (Vertex Veo) are the surface kalai's Designer/Producer calls; the
runner attaches the result to ``CreativeMaster.media`` (image_ref / video_ref).

DESIGN RULE that keeps CI creds-free even under ``SAAKSHE_MODE=live``: the public
``render_*`` functions own ONLY the branch + the keyword dispatch — they import no
genai and build no client. The single live network call lives inside the tiny
``_vertex_imagen`` / ``_vertex_veo`` (lazy ``from google import genai`` inside the
function, exactly like ``arivu/scripts/probe_vertex.py`` and ``kalai/runner.py``).
So a test that sets ``SAAKSHE_MODE=live`` is held creds-free purely by mocking those
two functions — there is no client to construct before the dispatch.

Demo path (``not is_live()`` and not ``_force_live``): a DETERMINISTIC placeholder
ref keyed by a hash of the prompt (``vertex://imagen/placeholder/<hash>`` /
``vertex://veo/placeholder/<hash>``), ``bytes=None``, ``spend_usd=0.0`` — no network,
no creds. Real media is Vertex-only; this module never touches any third-party gen platform.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from common import config

_HASH_LEN = 16


def _placeholder_ref(kind: str, prompt: str) -> str:
    """Deterministic, creds-free asset ref keyed on the prompt.

    Same prompt → same ref (so the demo flywheel + tests are byte-stable); a
    different prompt → a different ref. ``kind`` is ``imagen`` (still) or ``veo``
    (video), so the ref also records which Vertex model would have produced it.
    """
    digest = hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()[:_HASH_LEN]
    return f"vertex://{kind}/placeholder/{digest}"


# ─── live Vertex clients (the ONLY network/creds path — mock these in tests) ──
def _gen_image_bytes(client: Any, model: str, full_prompt: str) -> Optional[bytes]:
    """One still attempt on one model. A ``gemini-*`` id (the Nano Banana family)
    drives ``generate_content`` (bytes arrive as ``inline_data``); an ``imagen-*``
    pin keeps the classic ``generate_images`` path (family EOLs 2026-06-24 — an
    escape hatch, not the default)."""
    if model.startswith("gemini"):
        resp = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config={"response_modalities": ["TEXT", "IMAGE"]},
        )
        for cand in getattr(resp, "candidates", None) or []:
            parts = getattr(getattr(cand, "content", None), "parts", None) or []
            for part in parts:
                data = getattr(getattr(part, "inline_data", None), "data", None)
                if data:
                    return data
        return None
    resp = client.models.generate_images(
        model=model,
        prompt=full_prompt,
        config={"number_of_images": 1},
    )
    images = getattr(resp, "generated_images", None) or []
    if images:
        img = getattr(images[0], "image", None)
        return getattr(img, "image_bytes", None)
    return None


def _vertex_imagen(*, prompt: str, palette: str = "", **kwargs: Any) -> dict:
    """Live Vertex still-render call. Lazy genai import so the module is creds-free
    until this function actually runs. Returns {image_ref, bytes, spend_usd}.

    Model chain mirrors aikizi production: primary ``MODEL_IMAGEN`` (default
    nano-banana-pro → gemini-3-pro-image-preview), then ``MODEL_IMAGE_FALLBACK``
    (default nano-banana-2 → gemini-3.1-flash-image-preview). First model that
    yields bytes wins; the ref records WHICH model actually rendered."""
    from google import genai  # lazy — no import/client at module load or in demo

    client = genai.Client(
        vertexai=True,
        project=config.GOOGLE_CLOUD_PROJECT,
        location=config.GEMINI_LOCATION,
    )
    full_prompt = prompt if not palette else f"{prompt}\nPalette: {palette}"
    chain = [config.MODEL_IMAGEN]
    if config.MODEL_IMAGE_FALLBACK and config.MODEL_IMAGE_FALLBACK not in chain:
        chain.append(config.MODEL_IMAGE_FALLBACK)
    img_bytes: Optional[bytes] = None
    used = chain[0]
    last_err: Optional[Exception] = None
    for model in chain:
        try:
            img_bytes = _gen_image_bytes(client, model, full_prompt)
        except Exception as exc:  # noqa: BLE001 — fall to the next model in the chain
            last_err = exc
            img_bytes = None
        if img_bytes:
            used = model
            break
    if img_bytes is None and last_err is not None and len(chain) > 1:
        # every model in the chain failed — surface the last real error
        raise last_err
    return {
        "image_ref": f"vertex://imagen/{used}",
        "bytes": img_bytes,
        "spend_usd": 0.0,  # real cost is metered by the spend executor, not estimated here
    }


def _vertex_veo(*, prompt: str, stills: Optional[list] = None, **kwargs: Any) -> dict:
    """Live Vertex Veo call. Lazy genai import. Returns {video_ref, bytes, spend_usd}."""
    from google import genai  # lazy — no import/client at module load or in demo

    client = genai.Client(
        vertexai=True,
        project=config.GOOGLE_CLOUD_PROJECT,
        location=config.GEMINI_LOCATION,
    )
    operation = client.models.generate_videos(
        model=config.MODEL_VEO,
        prompt=prompt,
        config={"number_of_videos": 1},
    )
    return {
        "video_ref": f"vertex://veo/{config.MODEL_VEO}",
        "bytes": None,  # Veo returns a long-running op; bytes fetched downstream
        "spend_usd": 0.0,
        "operation": getattr(operation, "name", ""),
    }


# ─── public wrappers (branch + keyword dispatch ONLY — no genai, no client) ───
def render_still(prompt: str, palette: str = "", *, _force_live: bool = False, **kwargs: Any) -> dict:
    """Render a still. Live → Vertex Imagen (via ``_vertex_imagen``); else a
    deterministic, creds-free placeholder (``bytes=None``, ``spend_usd=0.0``)."""
    if config.is_live() or _force_live:
        return _vertex_imagen(prompt=prompt, palette=palette, **kwargs)
    return {
        "image_ref": _placeholder_ref("imagen", prompt),
        "bytes": None,
        "spend_usd": 0.0,
    }


def render_reel(prompt: str, stills: Optional[list] = None, *, _force_live: bool = False, **kwargs: Any) -> dict:
    """Render a reel/video. Live → Vertex Veo (via ``_vertex_veo``); else a
    deterministic, creds-free placeholder (``bytes=None``, ``spend_usd=0.0``)."""
    if config.is_live() or _force_live:
        return _vertex_veo(prompt=prompt, stills=stills or [], **kwargs)
    return {
        "video_ref": _placeholder_ref("veo", prompt),
        "bytes": None,
        "spend_usd": 0.0,
    }
