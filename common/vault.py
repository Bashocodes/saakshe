"""saakshe.common.vault — the brand-asset BLOB backend (the vault's bytes).

Mirrors kalai/media.py's discipline: the demo path is deterministic + creds-free
(content-addressed files on disk, a `vault://<sha>` URI), and the ONLY network/creds
path (Supabase Storage) is a lazy seam so a test forcing live stays creds-free by
mocking it. The small metadata INDEX lives in ProjectStore.assets, not here — this
module only stores and returns bytes. ZERO coupling to any third-party gen platform.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

_DIR = Path(os.environ.get("SAAKSHE_PROJECT_DIR", "~/.saakshe")).expanduser()
_BUCKET = "vault"


def _vault_dir(user: str) -> Path:
    return _DIR / "vault" / user


def available() -> bool:
    """True only when the live Supabase Storage backend is opted in + configured."""
    if os.environ.get("SAAKSHE_STORE", "").strip().lower() != "supabase":
        return False
    try:
        from . import supastore
        return supastore.available()
    except Exception:
        return False


def put(asset_id: str, data: bytes, content_type: str, *, user: str = "founder") -> str:
    """Store bytes; return a URI the index records. Live → Supabase Storage (fallback
    to demo disk on any error, never hard-fail an ingest). Demo → content-addressed
    file on disk + a deterministic `vault://<sha256[:16]>` URI."""
    if available():
        try:
            return _live_put(asset_id, data, content_type, user=user)
        except Exception:
            pass  # fall through to the demo disk path
    sha = hashlib.sha256(data).hexdigest()
    d = _vault_dir(user)
    d.mkdir(parents=True, exist_ok=True)
    (d / sha).write_bytes(data)
    return f"vault://{sha[:16]}"


def get(uri: str, *, user: str = "founder") -> Optional[bytes]:
    """Round-trip put(). None if the blob is missing."""
    if uri.startswith("vault://"):
        prefix = uri[len("vault://"):]
        d = _vault_dir(user)
        for f in d.glob(f"{prefix}*") if d.exists() else []:
            return f.read_bytes()
        return None
    if available():
        try:
            return _live_get(uri, user=user)
        except Exception:
            return None
    return None


# ── live seam (Supabase Storage) — lazy, mocked in tests ──────────────────────
def _live_put(asset_id: str, data: bytes, content_type: str, *, user: str) -> str:
    import httpx
    from . import supastore
    base = os.environ["SAAKSHE_SUPABASE_URL"].rstrip("/")
    key = supastore._read_key()
    object_key = f"{user}/{asset_id}"
    url = f"{base}/storage/v1/object/{_BUCKET}/{object_key}"
    with httpx.Client(timeout=30.0) as cli:
        r = cli.post(url, content=data, headers={
            "apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": content_type, "x-upsert": "true"})
        r.raise_for_status()
    return object_key


def _live_get(object_key: str, *, user: str) -> Optional[bytes]:
    import httpx
    from . import supastore
    base = os.environ["SAAKSHE_SUPABASE_URL"].rstrip("/")
    key = supastore._read_key()
    url = f"{base}/storage/v1/object/{_BUCKET}/{object_key}"
    with httpx.Client(timeout=30.0) as cli:
        r = cli.get(url, headers={"apikey": key, "Authorization": f"Bearer {key}"})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content
