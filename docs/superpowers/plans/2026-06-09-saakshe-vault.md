# Brand-asset VAULT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This build runs via an **ultracode workflow** (sequential TDD builders, suite-green gate between phases).

**Goal:** Give saakshe a real brand-asset vault — manas stores logos/reference-images/fonts (auto-extracted at connect + manual add) and serves them to kalai at generation time, completing Track A's kalai media path.

**Architecture:** Split index/blobs (Approach A). The metadata **index** lives in `ProjectStore.assets` (versioned, file + Supabase-mirrored, like `packs`). The **blobs** live behind a new `common/vault.py` backend — demo writes to disk and returns a deterministic `vault://<sha256[:16]>` URI (creds-free), live writes to a Supabase Storage `vault` bucket. The vault is empty in demo; kalai consumption is gated on non-empty served assets, so all 264 existing tests stay byte-identical.

**Tech Stack:** Python · pytest (asyncio-auto) · Google ADK · httpx (existing) · Supabase Storage (live, opt-in) · FastAPI (service).

**Hard constraints (every task):** ZERO-`aikizi` in the tree (no import/call, token absent from code+comments). Keep all **264 tests green** + demo **byte-identical** + **creds-free**. Respect the **separation contract** (vault is manas's; kalai consumes, never owns the index). **Fail-closed / fail-soft** (a bad asset never sinks a connect or a render). **Commit per step; DO NOT push.** Run the full suite (`for d in common manas kalai kural arivu; do PYTHONPATH=. ./.venv/bin/python -m pytest $d -q; done` + `pytest tests -q`) before each phase commit.

---

## File Structure

| File | Responsibility | New/Modify |
|---|---|---|
| `common/vault.py` | Blob backend: `available`/`put`/`get`. Demo disk + deterministic URI; live Supabase Storage. | **Create** |
| `common/tests/test_vault.py` | Blob backend tests. | **Create** |
| `common/project.py` | `ProjectStore.assets` index: `add_asset`/`assets_for`/`asset_count` + persist. | Modify |
| `common/supastore.py` | `SupabaseStore` parity: `add_asset`/`assets_for`/`asset_count` (live mirror). | Modify |
| `tests/test_vault_index.py` | Index add/dedup/version/query/persist tests (file store). | **Create** |
| `manas/vault.py` | manas face: `extract_assets`/`add_asset`/`assets_for` + the `manas.get_assets` A2A skill. | **Create** |
| `manas/tests/test_vault.py` | manas-face tests (extract over a synthetic bundle, selector, skill). | **Create** |
| `manas/runner.py` | Call `vault.extract_assets` per bundle during `ingest_connected` (off-loop). | Modify |
| `kalai/state.py` | Add `StateKeys.ASSETS`. | Modify |
| `kalai/runner.py` | `make(...)`/`render_asset(...)` gain optional `assets=None` → `state[ASSETS]`. | Modify |
| `kalai/sub_agents.py` | Designer renders served assets into `BRAND_BLOCK` **only when non-empty**. | Modify |
| `kalai/tests/test_vault_gate.py` | The byte-identical gate test (empty vs non-empty). | **Create** |
| `orchestrator.py` | At line 203, push `assets=a2a.dispatch("manas","get_assets",...)` into `kalai.make`. | Modify |
| `service/app.py` | `GET /api/vault/list`, `POST /api/vault/add`. | Modify |
| `tests/test_vault_routes.py` | Endpoint tests (list/add/empty/auth). | **Create** |

---

## Task V1: The blob backend (`common/vault.py`)

**Files:**
- Create: `common/vault.py`
- Test: `common/tests/test_vault.py`

The blob store mirrors `kalai/media.py`'s discipline: a deterministic, creds-free demo path; the only network/creds path (Supabase Storage) is a lazy seam mocked in tests. Demo blobs are **content-addressed** (filename = sha256 of bytes) so the demo URI is deterministic and identical bytes dedup for free.

- [ ] **Step 1: Write the failing tests**

```python
# common/tests/test_vault.py
"""The vault blob backend — demo disk (deterministic, creds-free) + a mockable live seam."""
from __future__ import annotations

import hashlib

from common import vault


def _iso(tmp_path, monkeypatch):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))   # isolate the vault dir
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)         # demo backend


def test_demo_put_returns_deterministic_content_hash_uri(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    data = b"a-logo-png"
    uri = vault.put("asset-1", data, "image/png")
    assert uri == f"vault://{hashlib.sha256(data).hexdigest()[:16]}"
    # same bytes -> same uri (idempotent, content-addressed)
    assert vault.put("asset-1", data, "image/png") == uri


def test_put_get_round_trips_bytes(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    data = b"font-file-bytes"
    uri = vault.put("a2", data, "font/ttf")
    assert vault.get(uri) == data


def test_get_missing_returns_none(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    assert vault.get("vault://0000000000000000") is None


def test_demo_is_creds_free(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    assert vault.available() is False            # no Supabase env -> demo only
    # put/get never construct a client in demo (no exception, pure disk)
    vault.put("a3", b"x", "image/png")
```

- [ ] **Step 2: Run — verify it fails**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest common/tests/test_vault.py -q`
Expected: FAIL (`ModuleNotFoundError: common.vault`).

- [ ] **Step 3: Implement `common/vault.py`**

```python
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
```

- [ ] **Step 4: Run — verify pass**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest common/tests/test_vault.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add common/vault.py common/tests/test_vault.py
git commit -m "feat(vault): blob backend — demo content-addressed disk + live Supabase Storage seam"
```

---

## Task V2: The index (`ProjectStore.assets`)

**Files:**
- Modify: `common/project.py` (`reset`, `_load`, `_save`, `status_dict`, + new methods)
- Modify: `common/supastore.py` (`SupabaseStore` parity — live mirror)
- Test: `tests/test_vault_index.py`

The index is a versioned `list[dict]` beside `packs`, dedup'd by `sha256`. Reuse `_next_version()`/`_day()`/`_save()`.

- [ ] **Step 1: Write the failing tests** (file store)

```python
# tests/test_vault_index.py
"""The vault metadata INDEX in ProjectStore — versioned, dedup'd, queryable."""
from __future__ import annotations

from common import project


def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    s = project.ProjectStore(user="t")
    s.reset(persist=False)
    return s


def test_add_asset_records_and_bumps_version(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    v0 = s.version
    rec = s.add_asset(kind="logo", filename="logo.png", content_type="image/png",
                      uri="vault://abc", sha256="abc", tags=["primary"], provenance="repo")
    assert rec["kind"] == "logo" and rec["uri"] == "vault://abc"
    assert s.version != v0                      # versioned like a pack commit
    assert s.asset_count() == 1


def test_add_asset_dedups_by_sha(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    s.add_asset(kind="logo", filename="a.png", content_type="image/png", uri="vault://x", sha256="x")
    s.add_asset(kind="logo", filename="a-copy.png", content_type="image/png", uri="vault://x", sha256="x")
    assert s.asset_count() == 1                  # same bytes -> one record


def test_assets_for_filters_by_kind_and_tag(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    s.add_asset(kind="logo", filename="l.png", content_type="image/png", uri="vault://l", sha256="l", tags=["primary"])
    s.add_asset(kind="reference", filename="r.jpg", content_type="image/jpeg", uri="vault://r", sha256="r")
    assert [a["kind"] for a in s.assets_for(kinds=["logo"])] == ["logo"]
    assert len(s.assets_for(kinds=["logo", "reference"])) == 2
    assert s.assets_for(tags=["primary"])[0]["filename"] == "l.png"


def test_assets_persist_and_reload(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    s.add_asset(kind="font", filename="f.ttf", content_type="font/ttf", uri="vault://f", sha256="f")
    s._save()
    s2 = project.ProjectStore(user="t")          # fresh instance reads from disk
    assert s2.asset_count() == 1 and s2.assets_for(kinds=["font"])[0]["uri"] == "vault://f"
```

- [ ] **Step 2: Run — verify it fails**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_vault_index.py -q`
Expected: FAIL (`AttributeError: 'ProjectStore' object has no attribute 'add_asset'`).

- [ ] **Step 3: Implement the index in `common/project.py`**

In `reset()` add `self.assets: list[dict] = []`. In `_load()` add `self.assets = raw.get("assets", [])`. In `_save()` add `"assets": self.assets` to the payload. In `status_dict()` add `"asset_count": self.asset_count()`. Add the methods (after `all_facts`):

```python
    # ── brand-asset vault index (binary assets; bytes live in common/vault.py) ──
    def add_asset(self, *, kind: str, filename: str, content_type: str, uri: str,
                  sha256: str, tags=(), provenance: str = "") -> dict:
        """Record one vault asset and tick the memory version. Dedup by sha256:
        identical bytes are stored once (the blob is content-addressed too)."""
        with self._lock:
            for a in self.assets:
                if a.get("sha256") == sha256:
                    return a                       # already held — no duplicate
            rec = {"id": f"asset-{len(self.assets) + 1}", "kind": kind,
                   "filename": filename, "content_type": content_type, "uri": uri,
                   "sha256": sha256, "tags": list(tags), "provenance": provenance,
                   "version": self._next_version(), "day": self._day()}
            self.assets.append(rec)
            self.version = rec["version"]
            self.history.append({"version": self.version, "at": time.time(),
                                 "note": f"added {kind} asset {filename}"})
        self._save()
        return rec

    def assets_for(self, kinds=None, tags=None) -> list[dict]:
        """The serve selector — filter the index by kind and/or tag (in-memory)."""
        out = self.assets
        if kinds:
            ks = set(kinds)
            out = [a for a in out if a.get("kind") in ks]
        if tags:
            ts = set(tags)
            out = [a for a in out if ts & set(a.get("tags", []))]
        return [dict(a) for a in out]

    def asset_count(self) -> int:
        return len(self.assets)
```

- [ ] **Step 4: Run — verify pass**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_vault_index.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Add `SupabaseStore` parity (live mirror)**

In `common/supastore.py`, give `SupabaseStore` the same three methods so a live store never `AttributeError`s when the populate hook calls `add_asset`. Follow the file's **existing `commit_pack`/`pack` persistence pattern** (assets stored on the project row's JSON, or a `assets` column, mirroring how packs persist): `add_asset(...)` upserts the asset list + bumps the version row exactly like `commit_pack`; `assets_for(...)` reads it back and filters in-memory; `asset_count()` returns the length. (Live-only; not CI-tested, consistent with the rest of `SupabaseStore`.)

- [ ] **Step 6: Run full suite — verify byte-identical**

Run: `for d in common manas kalai kural arivu; do PYTHONPATH=. ./.venv/bin/python -m pytest $d -q -p no:cacheprovider; done && PYTHONPATH=. ./.venv/bin/python -m pytest tests -q -p no:cacheprovider`
Expected: all green, 264 + the 4 new index tests, 0 regressions.

- [ ] **Step 7: Commit**

```bash
git add common/project.py common/supastore.py tests/test_vault_index.py
git commit -m "feat(vault): ProjectStore.assets index — versioned, sha-dedup, queryable (+ Supabase parity)"
```

---

## Task V3: The manas face (`manas/vault.py`)

**Files:**
- Create: `manas/vault.py`
- Modify: `manas/runner.py` (register the `manas.get_assets` A2A skill near the other `a2a.register_skill` calls)
- Test: `manas/tests/test_vault.py`

`extract_assets` is the auto-extract path; its only network read (fetching image bytes) is a lazy `httpx` seam mocked in tests. Demo / image-free sources → `[]` (the byte-identical guarantee at the source).

- [ ] **Step 1: Write the failing tests**

```python
# manas/tests/test_vault.py
"""manas's vault face — auto-extract at connect, the selector, the A2A skill."""
from __future__ import annotations

from common import a2a, project
from manas import vault as mvault
from manas import sources as src


def _iso(tmp_path, monkeypatch):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    project.STORE.reset(persist=False)


def test_extract_pulls_images_from_a_bundle(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    # a read bundle that surfaced image refs (logo + a reference picture)
    bundle = src.SourceBundle(channel="web", ref="https://co.example", ok=True,
                              text="...", provenance=["https://co.example"],
                              meta={"images": ["https://co.example/logo.png",
                                               "https://co.example/hero.jpg"]})
    monkeypatch.setattr(mvault, "_fetch_bytes",
                        lambda url: (b"bytes-of-" + url.encode()[-6:], "image/png"))
    recs = mvault.extract_assets(bundle)
    assert len(recs) == 2
    assert {r["kind"] for r in recs} <= {"logo", "reference"}
    assert project.STORE.asset_count() == 2          # committed to the index


def test_extract_is_empty_for_an_image_free_bundle(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    bundle = src.SourceBundle(channel="web", ref="x", ok=True, text="no images", meta={})
    assert mvault.extract_assets(bundle) == []        # the byte-identical guarantee
    assert project.STORE.asset_count() == 0


def test_extract_failed_fetch_is_skipped(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    bundle = src.SourceBundle(channel="web", ref="x", ok=True, text="",
                              meta={"images": ["https://co.example/broken.png"]})
    def _boom(url):
        raise RuntimeError("404")
    monkeypatch.setattr(mvault, "_fetch_bytes", _boom)
    assert mvault.extract_assets(bundle) == []        # one bad asset never sinks the connect


def test_add_asset_manual_and_selector(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    rec = mvault.add_asset(kind="logo", filename="l.png", data=b"L", content_type="image/png")
    assert rec["kind"] == "logo"
    assert mvault.assets_for(kinds=["logo"])[0]["filename"] == "l.png"


def test_get_assets_a2a_skill(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    mvault.add_asset(kind="logo", filename="l.png", data=b"L", content_type="image/png")
    got = a2a.dispatch("manas", "get_assets", kinds=["logo"])
    assert got and got[0]["kind"] == "logo"
    assert a2a.dispatch("manas", "get_assets", kinds=["reference"]) == []
```

- [ ] **Step 2: Run — verify it fails**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest manas/tests/test_vault.py -q`
Expected: FAIL (`ModuleNotFoundError: manas.vault`).

- [ ] **Step 3: Implement `manas/vault.py`**

```python
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
from typing import Optional

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


def extract_assets(bundle: src.SourceBundle, *, user: str = "founder") -> list[dict]:
    """Pull image/logo bytes a reader surfaced (bundle.meta['images']) into the vault.
    Image-free bundle (demo / the synthetic fixture) -> [] -> the vault stays empty
    -> the demo published output is byte-identical. Fail-soft per asset."""
    urls = list((bundle.meta or {}).get("images", []))
    store = project.current_store() if hasattr(project, "current_store") else project.STORE
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
    store = project.current_store() if hasattr(project, "current_store") else project.STORE
    uri = blob.put(f"a{len(store.assets) + 1}", data, content_type, user=user)
    return store.add_asset(kind=kind, filename=filename, content_type=content_type,
                           uri=uri, sha256=hashlib.sha256(data).hexdigest(),
                           tags=tags, provenance=provenance)


def assets_for(kinds=None, tags=None, *, user: str = "founder") -> list[dict]:
    store = project.current_store() if hasattr(project, "current_store") else project.STORE
    return store.assets_for(kinds=kinds, tags=tags)


# ── A2A skill (sibling-facing): kalai may pull assets ─────────────────────────
def _get_assets(kinds=None, tags=None) -> list[dict]:
    return assets_for(kinds=kinds, tags=tags)


a2a.register_skill("manas", "get_assets", _get_assets)
```

Import `manas.vault` once so the skill registers — add `from . import vault  # noqa: F401` to `manas/__init__.py` (next to where `runner` is imported), or register it in `manas/runner.py`. Confirm `project.current_store` exists (it does — the request-scoped seam); the `hasattr` guard keeps the plain `def` tests working against `project.STORE`.

- [ ] **Step 4: Run — verify pass**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest manas/tests/test_vault.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Confirm `SourceBundle` surfaces `meta['images']`**

Check `manas/sources.py`: `WebsiteSource`/`GitHubSource` should put discovered image URLs in `bundle.meta["images"]`. If `_parse_html` already collects `<img src>`/`og:image`/favicon, expose them under `meta["images"]`; if not, add that collection (small, in `sources.py`) — it's the real auto-extract input. Add a focused test in `manas/tests/test_vault.py` if you extend `sources.py`.

- [ ] **Step 6: Commit**

```bash
git add manas/vault.py manas/__init__.py manas/sources.py manas/tests/test_vault.py
git commit -m "feat(vault): manas face — extract at connect + manual add + manas.get_assets skill"
```

---

## Task V4: Populate at connect-time

**Files:**
- Modify: `manas/runner.py` (`ingest_connected`, after `bundles = await _read_sources(store)`)
- Test: `manas/tests/test_vault.py` (add one)

- [ ] **Step 1: Write the failing test**

```python
# append to manas/tests/test_vault.py
import asyncio
from manas import runner


def test_ingest_populates_the_vault_from_bundles(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    captured = {}
    def _fake_extract(bundle, **kw):
        captured.setdefault("n", 0)
        captured["n"] += 1
        return []
    monkeypatch.setattr(runner_vault_mod(), "extract_assets", _fake_extract)
    bundles = [src.SourceBundle(channel="web", ref="x", ok=True, text="t", meta={})]
    # the populate hook runs extract over each bundle (helper exercised directly)
    runner._populate_vault(bundles)
    assert captured["n"] == 1


def runner_vault_mod():
    from manas import vault
    return vault
```

- [ ] **Step 2: Run — verify it fails** (`AttributeError: _populate_vault`).

- [ ] **Step 3: Implement the hook in `manas/runner.py`**

Add a small sync helper + call it from `ingest_connected` right after the bundles are read:

```python
def _populate_vault(bundles) -> None:
    """Auto-fill the brand-asset vault from the freshly-read sources. Fail-soft:
    a vault error never blocks the ingest. Demo/image-free bundles add nothing."""
    from . import vault
    for b in bundles:
        try:
            vault.extract_assets(b)
        except Exception:
            pass
```

In `ingest_connected`, after `bundles = await _read_sources(store)`:

```python
    await asyncio.to_thread(_populate_vault, bundles)   # off-loop; fail-soft
```

- [ ] **Step 4: Run — verify pass**, then the full ingest suite to prove demo unchanged:

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest manas -q`
Expected: PASS, including the existing `test_ingest.py` (demo vault stays empty → published output byte-identical).

- [ ] **Step 5: Commit**

```bash
git add manas/runner.py manas/tests/test_vault.py
git commit -m "feat(vault): auto-populate the vault from connected sources at ingest (fail-soft, demo empty)"
```

---

## Task V5: Serve to kalai (the byte-identical gate) — **the centerpiece**

**Files:**
- Modify: `kalai/state.py` (add `StateKeys.ASSETS = "assets"`)
- Modify: `kalai/runner.py` (`make`/`render_asset`/`_run_pipeline` accept `assets=None` → `state[ASSETS]`)
- Modify: `kalai/sub_agents.py` (designer renders served assets into `BRAND_BLOCK` only when non-empty)
- Modify: `orchestrator.py:203` (push `assets` from manas)
- Test: `kalai/tests/test_vault_gate.py`

- [ ] **Step 1: Write the failing gate tests**

```python
# kalai/tests/test_vault_gate.py
"""The byte-identical gate: an empty served-asset list leaves kalai's prompt EXACTLY
as today; a non-empty list grounds the designer on the assets. This is what keeps the
264 baseline byte-identical while the vault is live."""
from __future__ import annotations

import inspect
from kalai import runner, sub_agents


def test_make_accepts_optional_assets_default_none():
    sig = inspect.signature(runner.make)
    assert "assets" in sig.parameters
    assert sig.parameters["assets"].default is None     # default → empty → today's behavior


def test_empty_assets_render_no_brand_block_change():
    # the designer's BRAND_BLOCK rendering is byte-identical for [] vs the pre-vault path
    empty = sub_agents.render_brand_block(assets=[])
    none_ = sub_agents.render_brand_block(assets=None)
    assert empty == none_ == ""                          # nothing served → nothing added


def test_nonempty_assets_appear_in_brand_block():
    block = sub_agents.render_brand_block(assets=[
        {"kind": "logo", "filename": "logo.png", "uri": "vault://abc", "provenance": "repo"}])
    assert "logo.png" in block and "logo" in block.lower()
```

- [ ] **Step 2: Run — verify it fails** (`render_brand_block` missing; `make` has no `assets` param).

- [ ] **Step 3: Implement**

`kalai/state.py`: add `ASSETS = "assets"` to `StateKeys`.

`kalai/sub_agents.py`: add the pure renderer and use it where `BRAND_BLOCK` is built:

```python
def render_brand_block(assets) -> str:
    """Render the served vault assets into the designer's brand-asset-bank text.
    Empty/None -> "" so the prompt is byte-identical to the pre-vault path."""
    assets = assets or []
    if not assets:
        return ""
    lines = ["BRAND ASSETS ON FILE (use these — they are the company's real marks):"]
    for a in assets:
        lines.append(f"  - {a.get('kind')}: {a.get('filename')} ({a.get('uri')}) — from {a.get('provenance','')}")
    return "\n".join(lines)
```

In the designer instruction provider, append `render_brand_block(ctx.state.get(StateKeys.ASSETS))` to the existing `BRAND_BLOCK`/prompt **only when it is non-empty** (a non-empty string concatenation; empty string changes nothing).

`kalai/runner.py`: thread the param:
```python
async def make(stream, run_id, brief, context_pack, assets=None):
    ...
    state = await _run_pipeline(brief, context_pack, assets=assets)
...
async def _run_pipeline(brief, context_pack, assets=None):
    ...
    state[SK.ASSETS] = list(assets or [])     # [] in demo -> byte-identical
```
Mirror the optional `assets=None` on the `render_asset(brief="", context_pack=None, assets=None)` A2A skill.

`orchestrator.py` line 203 — push from manas, fail-soft:
```python
    try:
        assets = a2a.dispatch("manas", "get_assets", kinds=["logo", "reference"])
    except Exception:
        assets = []
    kalai_res = await kalai.make(stream, run_id, brief, state.context_pack, assets=assets)
```

- [ ] **Step 4: Run — verify pass + the WHOLE suite byte-identical**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest kalai/tests/test_vault_gate.py -q` → PASS.
Then: `for d in common manas kalai kural arivu; do PYTHONPATH=. ./.venv/bin/python -m pytest $d -q -p no:cacheprovider; done && PYTHONPATH=. ./.venv/bin/python -m pytest tests -q -p no:cacheprovider`
Expected: all green. In demo the vault is empty → `get_assets` returns `[]` → `render_brand_block([]) == ""` → the kalai prompt + the `vertex://` placeholder are byte-for-byte today's. The `tests/test_flywheel.py` md5 of the published output is unchanged.

- [ ] **Step 5: Commit**

```bash
git add kalai/state.py kalai/runner.py kalai/sub_agents.py orchestrator.py kalai/tests/test_vault_gate.py
git commit -m "feat(vault): serve assets to kalai via BRAND_BLOCK, gated on non-empty (demo byte-identical)"
```

---

## Task V6: The service endpoints

**Files:**
- Modify: `service/app.py` (`GET /api/vault/list`, `POST /api/vault/add`)
- Test: `tests/test_vault_routes.py`

Mirror the existing `/api/connect/*` pattern: `Depends(_session_dep)` binds the per-user store; the endpoint reads/writes via `manas.vault` + `project.current_store()`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vault_routes.py
"""The vault endpoints — list metadata + manual add. Empty-state safe."""
from __future__ import annotations

import base64
from fastapi.testclient import TestClient

from service.app import app
from common import project

client = TestClient(app)


def test_vault_list_empty_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    project.STORE.reset(persist=False)
    r = client.get("/api/vault/list")
    assert r.status_code == 200
    assert r.json()["assets"] == []


def test_vault_add_then_list(monkeypatch, tmp_path):
    monkeypatch.setenv("SAAKSHE_PROJECT_DIR", str(tmp_path))
    project.STORE.reset(persist=False)
    payload = {"kind": "logo", "filename": "l.png", "content_type": "image/png",
               "data_b64": base64.b64encode(b"PNG").decode()}
    r = client.post("/api/vault/add", json=payload)
    assert r.status_code == 200 and r.json()["asset"]["kind"] == "logo"
    assert len(client.get("/api/vault/list").json()["assets"]) == 1
```

- [ ] **Step 2: Run — verify it fails** (404 — routes not defined).

- [ ] **Step 3: Implement in `service/app.py`** (follow the `/api/connect/*` shape, same `_session_dep`):

```python
class VaultAddRequest(BaseModel):
    kind: str
    filename: str
    content_type: str = "image/png"
    data_b64: str
    tags: list[str] = []


@app.get("/api/vault/list")
def vault_list(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    return {"assets": project.current_store().assets_for()}


@app.post("/api/vault/add")
def vault_add(req: VaultAddRequest, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    import base64
    from manas import vault
    data = base64.b64decode(req.data_b64)
    rec = vault.add_asset(kind=req.kind, filename=req.filename, data=data,
                          content_type=req.content_type, tags=req.tags)
    return {"asset": rec}
```

Add `assets_for` to the `ProjectStore` view if the endpoint calls `current_store().assets_for()` (it exists from V2). Keep the auth/empty-state behaviour identical to the connect routes (the demo `_session_dep` binds `project.STORE`).

- [ ] **Step 4: Run — verify pass + full suite**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_vault_routes.py -q` → PASS.
Then the full suite (all five faculties + `tests`) → all green.

- [ ] **Step 5: Commit**

```bash
git add service/app.py tests/test_vault_routes.py
git commit -m "feat(vault): /api/vault/list + /api/vault/add endpoints (empty-state safe)"
```

---

## Final verification (after V6)

- [ ] Full suite green: `for d in common manas kalai kural arivu; do PYTHONPATH=. ./.venv/bin/python -m pytest $d -q -p no:cacheprovider; done && PYTHONPATH=. ./.venv/bin/python -m pytest tests -q -p no:cacheprovider` → 264 + new vault tests, **0 regressions**.
- [ ] ZERO-aikizi: `grep -rni "aikizi" --include="*.py" common manas kalai kural arivu service tests | grep -v "/.venv/"` → empty.
- [ ] Byte-identical: `tests/test_flywheel.py` md5 of the demo published output unchanged from `main`.
- [ ] Do **not** push.

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task: §3.1 blob backend → V1; §3.2 index → V2; §3.3 serve channel (`make(assets=)`→`BRAND_BLOCK`) → V5; §3.4 manas face → V3; §3.5 populate + serve wiring → V4 + V5; §3.6 endpoints → V6; §5 byte-identical gate → V5 (the centerpiece test) + the full-suite gate after each phase; §8 out-of-scope respected (no cockpit UI, no flywheel-back, no transforms). Cost note (R2-for-video-later) is forward-looking, no task — correct.

**2. Placeholder scan** — no TBD/TODO; every code step shows real code. The two live-only paths (Supabase Storage `_live_put/_live_get`, `SupabaseStore` asset parity) are concrete where determinable and reference the file's **existing packs persistence pattern** for the parts that can't be unit-tested without creds — the one acceptable "follow the established pattern" pointer in an existing codebase.

**3. Type/name consistency** — `add_asset(kind=, filename=, content_type=, uri=, sha256=, tags=, provenance=)` is identical in `ProjectStore` (V2), `manas.vault` (V3), and the endpoint (V6). `assets_for(kinds=, tags=)` consistent across V2/V3/V6. `StateKeys.ASSETS`, `render_brand_block(assets)`, and `make(..., assets=None)` consistent across V5. URIs are `vault://<sha256[:16]>` everywhere.
