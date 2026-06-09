# saakshe Track B · #6 — Brand-asset VAULT (design)

**Status:** design, approved (Approach A + the empty-vault byte-identical gate) 2026-06-09.
**Where it fits:** Track B, sub-project #6 of 4 (VAULT · learning flywheel · precedent panel · witness-parity/BYOK/budgets). Track A (agentic depth) is code-complete + green (264 tests). Track B is the SaaS moat; the VAULT is its most product-defining piece and it **completes Track A's kalai media path** — kalai can call Vertex Imagen/Veo but today has no brand assets to ground generation in.

---

## 1 · What this builds

A real **binary-asset store** for the company's brand: logos, reference/style images, and font files — indexed, versioned, queryable, and **proactively served** to kalai. Not text rules (hex palettes, font *names*, voice — those stay in manas's Context Pack where they already live); the vault owns the *files*.

### The three settled decisions (locked)
1. **Scope = binary files only.** Pack = facts/rules; vault = files. Kinds in v1: `logo | reference | font`. The pack/vault boundary is clean and non-duplicating.
2. **Population = auto-extract at connect + a manual add path.** manas's source readers pull logo/image bytes found in the repo/site during ingest; a `add_asset(...)` API + endpoint covers what extraction misses.
3. **Serve = proactive push.** When arivu's executor dispatches a brief to kalai, manas attaches the matching vault assets to the `Dispatch`; kalai grounds generation on them. kalai may also pull via an A2A skill.

---

## 2 · Architecture (Approach A — split index/blobs, mirror the store seam)

The index (small metadata) and the blobs (large binaries) live in different places, each mirroring a pattern saakshe already runs:

- **Index** rides in `ProjectStore` (a new versioned `assets` list, persisted to the file store and Supabase exactly like `packs` — the `ProjectStore ↔ SupabaseStore` seam already exists). Querying the index for the proactive-serve selector is a cheap in-memory filter.
- **Blobs** live behind a new `common/vault.py` backend that mirrors `kalai/media.py`: demo writes bytes to local disk and returns a **deterministic** `vault://<sha256[:16]>` URI (creds-free); live writes to a Supabase Storage `vault` bucket and returns its key. Gated on `SAAKSHE_STORE=supabase` + `available()`, with a file fallback on any error.

Rejected: **B** (everything in a Supabase bucket, metadata as sidecar JSON) — querying becomes a bucket scan, bad for the serve selector, and the demo needs a fake bucket. **C** (blobs as Postgres `bytea`) — Postgres is wrong for multi-MB images/fonts.

**Cost note (forward-looking, not v1 work):** the live blob backend is Supabase Storage. Brand assets (logos / a few reference images / fonts) and even generated *images* are small — storage + egress are pennies, so Supabase is the right simple home and where it stays. The one future swap: **generated video served to audiences at scale** is egress-heavy, where **Cloudflare R2's zero egress** wins. So keep `common/vault.py`'s backend **pluggable** (a thin `put/get` seam) so a `video → R2` home can be added later by config without touching callers. Google credits cover Google egress during the contest; the R2 move is a post-credits, at-scale decision — explicitly **deferred**.

---

## 3 · Components + interfaces

### 3.1 `common/vault.py` — the blob backend (NEW)
```
def available() -> bool                          # supastore.available() AND SAAKSHE_STORE==supabase
def put(asset_id: str, data: bytes, content_type: str, *, user="founder") -> str
    # demo: write ~/.saakshe/vault/<user>/<asset_id> ; return f"vault://{sha256(data)[:16]}"
    # live: upload to Supabase Storage bucket "vault" at <user>/<asset_id> ; return that key
    # any live error -> fall back to the demo disk path (never hard-fail an ingest)
def get(uri: str, *, user="founder") -> bytes | None   # round-trips put(); None if missing
```
Demo URIs are deterministic (content-hashed) so tests pin them, exactly like kalai's `vertex://` placeholder. No client is constructed until `put`/`get` runs in live (lazy import), so forcing live in a test is creds-free by mocking these two functions.

### 3.2 `common/project.py` — the index (EXTEND `ProjectStore`)
New field `self.assets: list[dict]` (persisted in `_save`/`_load` beside `packs`; included in `as_dict`/`status_dict` counts). Each record:
```
{ "id", "kind": "logo|reference|font", "filename", "content_type",
  "uri", "sha256", "tags": [...], "provenance": "<source url/ref>",
  "version": "v1", "day": <int> }
```
New methods (reuse `_next_version()`, `_day()`, `_save()`):
- `add_asset(kind, filename, content_type, uri, sha256, tags=(), provenance="") -> dict` — dedup by `sha256` (same bytes never stored twice); bumps the store version like `commit_pack`.
- `assets_for(kinds=None, tags=None) -> list[dict]` — the serve selector (in-memory filter by kind/tag).
- `asset_count() -> int`.

### 3.3 The serve channel — `kalai.make(..., assets=None) → BRAND_BLOCK`
kalai's real entry is `kalai.runner.make(stream, run_id, brief, context_pack)` (`orchestrator.py:203`) and the `kalai.render_asset(brief, context_pack)` A2A skill. Both gain an optional `assets: list[dict] | None = None` (default → `[]`), threaded into a new `kalai/state.StateKeys.ASSETS` and rendered into the **existing** `StateKeys.BRAND_BLOCK` (kalai already reserves a "brand-asset-bank text for prompts" slot). Assets stay **out of the `ContextPack`** (rules-only, per decision #1). An asset ref is just the index record dict (id/kind/uri/filename/content_type/provenance) — no new class. Empty default → byte-identical to today.

### 3.4 `manas/vault.py` — the manas face (NEW)
```
def extract_assets(bundle: sources.SourceBundle, *, user="founder") -> list[dict]
    # find logo/image bytes in a read source: <img src>, og:image, <link rel=icon>,
    # README image refs / repo image files already surfaced by sources.py; for each,
    # fetch bytes (lazy httpx, the ONE network seam — mock in tests) -> vault.put -> store.add_asset.
    # demo / no real images (the synthetic fixture) -> returns [] -> vault stays empty.
def add_asset(kind, filename, data: bytes, content_type, tags=(), provenance="manual", *, user="founder") -> dict
    # the manual path: vault.put(bytes) -> store.add_asset(...)
def assets_for(kinds=None, tags=None, *, user="founder") -> list[dict]   # -> store.assets_for(...)
```
A2A skill `manas.get_assets(kinds=None, tags=None) -> list[dict]` registered for the pull path (kalai may ask).

### 3.5 Wiring
- **Populate** (`manas/runner.py`): after `_read_sources` yields each `SourceBundle`, call `vault.extract_assets(bundle)` (off-loop, alongside the imbiber pipeline). The asset index commits with the connect, versioned like the pack.
- **Serve / push** (`orchestrator.py:203`): pass `assets=a2a.dispatch("manas","get_assets", kinds=["logo","reference"])` into `kalai.make(...)`. Fail-soft: an empty/erroring manas → `assets=[]` → today's behavior.
- **Consume** (kalai `runner.make`/`render_asset` → `state[ASSETS]` → designer's `BRAND_BLOCK`): the designer renders the served assets into `BRAND_BLOCK` **only when non-empty**. Empty → today's prompt + `render_still` placeholder byte-for-byte; non-empty (live) → the prompt lists the assets and `render_still` may pass reference image URIs to Imagen. Demo `render_still` stays the deterministic `vertex://` placeholder regardless.

### 3.6 Service (`service/app.py`)
- `GET /api/vault/list` → `store.assets` (metadata only; never streams bytes inline).
- `POST /api/vault/add` (multipart) → `manas.vault.add_asset(...)`; auth-gated + credit/no-op per the existing pattern; empty-state-safe.
- (Cockpit Brut/Obsidian vault panel = a **later step**, not v1-blocking.)

---

## 4 · Data flow

**Populate (connect-time):** founder connects repo+site → `_read_sources` reads each → `extract_assets` pulls logo/og-image/favicon/README-image bytes → `vault.put` (blob) + `store.add_asset` (index, versioned) → the imbiber pipeline runs unchanged on the same bundles.

**Serve (decision-time):** arivu seals a verdict → executor builds kalai's `Dispatch` → asks manas `get_assets(kinds=[logo,reference])` → attaches them to `dispatch.assets` → kalai's designer grounds the brief on them and (live) conditions Imagen on the reference images → `CreativeMaster.media` carries the result.

---

## 5 · Demo byte-identical contract (the gate)

The vault is net-new and **starts empty in demo** (the synthetic `grounded_company` fixture has no real images → `extract_assets` returns `[]`). kalai's consumption is **gated on a non-empty `dispatch.assets`**, so:
- Existing 264 tests: vault empty → `dispatch.assets == []` → kalai instruction + render are byte-for-byte today's → **all stay green**.
- New tests assert only new behavior (blob round-trip, index, extract, selector, the gate's non-empty branch with a stubbed asset).
- The demo published-output + the md5 flywheel comparison are unchanged.

A richer seeded-vault demo (for the eventual cockpit panel) is **opt-in**, never the default — so it can't perturb the byte-identical baseline.

---

## 6 · Constraints (carried from Track A — all binding)

- **ZERO-aikizi** in the tree: no import/call, and the literal token absent from code + comments (grep stays clean). Study only as a pattern reference.
- **TDD + production-grade**; keep all **264 tests green**; the demo stays **creds-free + byte-identical**; one real-path test per change.
- Respect the **separation contract** (vault is manas's; kalai consumes, never owns the index), the **two-tap flywheel**, **fail-closed** behavior (a bad asset fetch never sinks a connect or a dispatch — fail-soft to empty).
- Any UI matches the **Brut/Obsidian** system.
- Build via **ultracode workflows**; run the full suite before each commit; **commit per step, do not push** unless asked.

---

## 7 · Testing strategy (TDD, per piece)

1. `common/vault.py`: `put`→`get` round-trips bytes; demo URI is the deterministic `vault://<sha>`; live mocked seam never constructs a client in demo.
2. `ProjectStore.assets`: `add_asset` dedups by sha256, bumps version; `assets_for` filters by kind/tag; persists + reloads (file) and round-trips through the Supabase mirror.
3. `manas.vault.extract_assets`: over a synthetic HTML/repo bundle with mocked image fetch → N asset records with correct kind/provenance; over the image-free fixture → `[]`.
4. `assets_for` serve selector returns the right kinds.
5. **The gate:** kalai designer/`media` with `dispatch.assets == []` is byte-identical to today (assert against the current instruction/placeholder); with a stub asset, the instruction references it and (mocked) live render receives the ref URI.
6. `/api/vault/{list,add}` happy path + empty-state + auth gate.

---

## 8 · Out of scope (YAGNI — explicitly deferred)

- Cockpit vault **UI panel** (later step; backend + endpoints first).
- kalai's **generated outputs flowing back** into the vault as new references (that's the **learning flywheel**, sub-project #7).
- Asset **transforms** (thumbnailing, format conversion, palette extraction from a logo).
- Per-asset **ACL / sharing**; multi-brand namespaces beyond the existing per-user store key.
- Fonts actually **applied** in render (v1 stores font files + references them; wiring a font into Imagen output is later).

---

## 9 · The TDD cut (phases for the plan)

- **V1** — `common/vault.py` blob backend (demo disk + deterministic URI; live Supabase Storage seam, mocked).
- **V2** — `ProjectStore.assets` index (add/dedup/version/query/persist) + Supabase mirror.
- **V3** — `manas/vault.py` (`extract_assets` + `add_asset` + `assets_for`) + the A2A `get_assets` skill.
- **V4** — populate wiring in `manas/runner._read_sources` (connect-time auto-fill; demo stays empty).
- **V5** — `Dispatch.assets` field + arivu executor push + kalai consume **gated on non-empty** (the byte-identical gate test is the centerpiece).
- **V6** — `/api/vault/{list,add}` endpoints.
- (Cockpit panel — separate, post-V6.)

---

## 10 · Self-review

- **Placeholders:** none — every interface has a concrete signature and the integration points are named real symbols (`ProjectStore`, `Dispatch`, `manas/runner._read_sources`, `arivu .../executor.dispatch_a2a`, `kalai/media.render_still`).
- **Consistency:** the index lives in the store (queryable, versioned, Supabase-mirrored); blobs live in the vault backend (object storage, deterministic demo) — no overlap. `Dispatch.assets` is the single serve channel; the empty default is the byte-identical guarantee.
- **Scope:** one subsystem, ~6 phases, each independently testable — fits a single implementation plan. The other three Track B sub-projects are explicitly out of scope.
- **Ambiguity:** the pack/vault boundary is pinned (rules vs files); the serve model is push with an optional pull skill; demo-empty + consumption-gated removes any "does this change published output?" ambiguity.
