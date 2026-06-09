"""manas.vault — the company's brand-asset vault, manas-side.

manas KNOWS the brand, so it owns the asset index + serves it (kalai consumes,
never owns it — the separation contract). The bytes live in common/vault.py; the
metadata index lives in the ProjectStore. Auto-extract at connect pulls image/logo
bytes a source reader surfaced; a manual add covers the rest. The one network read
(fetching bytes) is the lazy `_fetch_bytes` seam, mocked in tests so live stays
creds-free here.
"""
from __future__ import annotations

import hashlib

from common import a2a, project, vault as blob
from . import sources as src

_IMAGE_KINDS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".svg": "image/svg+xml", ".webp": "image/webp"}


def _classify(url: str, idx: int) -> str:
    """First image found, or one whose name says 'logo', is the logo; rest are refs."""
    low = url.lower()
    if "logo" in low or "favicon" in low or "icon" in low or idx == 0:
        return "logo"
    return "reference"


def _content_type(url: str) -> str:
    low = url.lower().split("?")[0]
    for ext, ct in _IMAGE_KINDS.items():
        if low.endswith(ext):
            return ct
    return "image/png"


def _fetch_bytes(url: str) -> tuple[bytes, str]:
    """Live image fetch (the ONLY network seam — mock in tests). Lazy httpx import."""
    import httpx
    with httpx.Client(follow_redirects=True, timeout=20.0,
                      headers={"user-agent": "saakshe-setu/1.0 (+vault)"}) as cli:
        r = cli.get(url)
        r.raise_for_status()
        return r.content, (r.headers.get("content-type", "").split(";")[0] or _content_type(url))


def _store():
    """The request-scoped store, falling back to the global (the demo path)."""
    return project.current_store() if hasattr(project, "current_store") else project.STORE


def extract_assets(bundle: src.SourceBundle, *, user: str = "founder") -> list[dict]:
    """Pull image/logo bytes a reader surfaced (bundle.meta['images']) into the vault.
    Image-free bundle (demo / the synthetic fixture) -> [] -> the vault stays empty
    -> the demo published output is byte-identical. Fail-soft per asset."""
    urls = list((bundle.meta or {}).get("images", []))
    store = _store()
    out: list[dict] = []
    for i, url in enumerate(urls):
        try:
            data, ct = _fetch_bytes(url)
        except Exception:
            continue  # one bad asset never sinks the connect
        if not data:
            continue
        uri = blob.put(f"a{len(store.assets) + 1}", data, ct, user=user)
        rec = store.add_asset(kind=_classify(url, i), filename=url.rsplit("/", 1)[-1] or "asset",
                              content_type=ct, uri=uri, sha256=hashlib.sha256(data).hexdigest(),
                              provenance=url)
        out.append(rec)
    return out


def add_asset(*, kind: str, filename: str, data: bytes, content_type: str,
              tags=(), provenance: str = "manual", user: str = "founder") -> dict:
    """The manual add path: store bytes -> record in the index."""
    store = _store()
    uri = blob.put(f"a{len(store.assets) + 1}", data, content_type, user=user)
    return store.add_asset(kind=kind, filename=filename, content_type=content_type,
                           uri=uri, sha256=hashlib.sha256(data).hexdigest(),
                           tags=tags, provenance=provenance)


def assets_for(kinds=None, tags=None, *, user: str = "founder") -> list[dict]:
    return _store().assets_for(kinds=kinds, tags=tags)


# ── A2A skill (sibling-facing): kalai may pull assets ─────────────────────────
def _get_assets(kinds=None, tags=None) -> list[dict]:
    return assets_for(kinds=kinds, tags=tags)


a2a.register_skill("manas", "get_assets", _get_assets)
