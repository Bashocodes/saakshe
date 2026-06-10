# kalai Media Crew Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give kalai a deterministic post-production crew — router · pricer · fx · renderer · hdr-wrapper · verifier — so a founder request like "make my image an HDR video, budget $1" is routed (generate vs compute), priced with a real receipt, rendered as labeled-FX HDR video on Cloud Run, and atom-verified fail-closed.

**Architecture:** Pure-Python pipeline (numpy/PIL/cv2 frames → ffmpeg HLG HEVC) living beside `kalai/media.py`. Router/pricer are deterministic with recorded rationale (honest v1; an LLM seat can replace the rule later without API change). New FastAPI endpoints expose quote + async render with progress on the existing event stream. Demo mode stays pixel-free (refs only, like `media.py`).

**Tech Stack:** numpy, Pillow, opencv-python-headless, ffmpeg (apt), FastAPI background task, existing `common.stream` events.

**HDR honesty note:** v1 delivers **HLG HDR (BT.2020, 10-bit HEVC)** — real HDR, verified via ffprobe color tags. Dolby Vision 8.4 wrap (dovi_tool/MP4Box) is NOT in v1: those binaries aren't in the container and the desktop amve injector is personal tooling. The verifier reports exactly what was produced.

---

## File map

| File | Responsibility |
|---|---|
| Create `kalai/media_fx.py` | the 12 effects, self-contained numpy/PIL/cv2 (ported from `~/Documents/108_motion_lib/processes_v{4,5,6}.py`) |
| Create `kalai/media_crew.py` | router (path A/B/A→B + refusal), pricer (cost table + quote), receipt builder |
| Create `kalai/media_pipeline.py` | frames → label overlay → ffmpeg HLG encode → verifier (ffprobe atoms/tags) |
| Create `kalai/tests/test_media_crew.py` | router/pricer/receipt unit tests |
| Create `kalai/tests/test_media_fx.py` | every effect returns valid frame; pulse envelope sane |
| Create `kalai/tests/test_media_pipeline.py` | tiny end-to-end render (16×28px, 8 frames) + verifier |
| Modify `service/app.py` | `POST /api/kalai/media/quote`, `POST /api/kalai/media/render`, `GET /api/kalai/media/job/{id}` |
| Modify `Dockerfile:10` | add `ffmpeg` to apt line |
| Modify `requirements.txt` | add `opencv-python-headless`, `numpy`, `Pillow` (if absent) |

Price constants (one place, `media_crew.py`): `IMAGEN_USD=0.04`, `VEO_USD_PER_SEC=0.40`, `CPU_USD_PER_VCPU_SEC=0.000024` (Cloud Run tier-1), `RENDER_VCPU_SEC_PER_OUTPUT_SEC=11.0` (measured locally 2026-06-10).

---

### Task 1: media_fx — the 12 effects, self-contained

**Files:**
- Create: `kalai/media_fx.py`
- Test: `kalai/tests/test_media_fx.py`

- [ ] **Step 1: Write the failing tests**

```python
# kalai/tests/test_media_fx.py
import numpy as np
import pytest
from kalai import media_fx

SRC = (np.random.default_rng(7).random((64, 36, 3)) * 255).astype(np.uint8)

@pytest.mark.parametrize("name", sorted(media_fx.EFFECTS))
def test_every_effect_returns_valid_frame(name):
    out = media_fx.apply(name, SRC, t=0.5, frame_idx=12)
    assert out.shape == SRC.shape and out.dtype == np.uint8

def test_twelve_effects_exist():
    assert len(media_fx.EFFECTS) == 12

def test_envelope_pulse_shape():
    assert media_fx.envelope(0.0) == pytest.approx(0.0, abs=1e-6)
    assert media_fx.envelope(0.5) == pytest.approx(1.0, abs=1e-3)
    assert media_fx.envelope(1.0) == pytest.approx(0.0, abs=1e-6)

def test_unknown_effect_raises():
    with pytest.raises(KeyError):
        media_fx.apply("nope", SRC, t=0.5, frame_idx=0)
```

- [ ] **Step 2: Run to verify failure** — `cd ~/Desktop/Working/saakshe && PYTHONPATH=. ./.venv/bin/python -m pytest kalai/tests/test_media_fx.py -q` → ImportError.

- [ ] **Step 3: Implement `kalai/media_fx.py`**

Port these functions VERBATIM from the motion lib (they are pure numpy/PIL, no cv2 needed except noted):
- from `/Users/cyberyogi/Documents/108_motion_lib/processes_v6.py`: `pixel_sort_horizontal`, `pixel_sort_vertical`, `pixel_sort_below_threshold`, `wave_row_displace` (+ their helpers `f`, `u`, `L`)
- from `processes_v5.py`: `charcoal_sketch`
- from `processes_v4.py`: `lith_print`, `sabattier_solarize`, `cinestill_800t`, `rgb_displace`

Then add the module surface:

```python
"""kalai — deterministic FX library (the studio's compute path).

12 validated effects. Each is (src_u8, t in 0..1, frame_idx) -> u8 frame.
t is position within the clip; envelope(t) is the clean->peak->clean pulse.
Ported from the founder's validated 108_motion_lib (2026-05-21 session).
"""
import numpy as np
from PIL import Image, ImageFilter

# ... (ported functions verbatim here) ...

def envelope(t: float) -> float:
    return float(np.sin(np.pi * np.clip(t, 0.0, 1.0)) ** 1.2)

def _blend(a, b, k):
    return (a.astype(np.float32) * (1 - k) + b.astype(np.float32) * k).astype(np.uint8)

def _ripple(src, t, fi):
    k = envelope(t); out = src.copy()
    H = src.shape[0]
    sh = (np.sin(2 * np.pi * np.arange(H) / 180.0 + fi * 0.45) * 5.0 * k).astype(int)
    for y in range(H):
        if sh[y]: out[y] = np.roll(out[y], sh[y], axis=0)
    return out

def _light_sweep(src, t, fi):
    k = envelope(t); H, W = src.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lx = (-0.2 + 1.4 * t) * W
    g = np.exp(-np.sqrt((xx - lx) ** 2 + (yy - H * 0.45) ** 2) / (W * 0.45))[..., None]
    out = src.astype(np.float32) * (1 - 0.3 * k) + src.astype(np.float32) * g * 0.85 * k + g * 60.0 * k
    return np.clip(out, 0, 255).astype(np.uint8)

def _ca_pulse(src, t, fi):
    pk = 0.0
    for c, amp in ((0.43, 13), (0.5, 22), (0.57, 13)):
        d = abs(t - c)
        if d < 0.04: pk = max(pk, amp * (1 - d / 0.04))
    return rgb_displace(src, dx=int(pk * 0.8)) if pk >= 1 else src

EFFECTS = {
    "sat_sort":   lambda s, t, fi: pixel_sort_horizontal(s, 1.05 - 0.70 * envelope(t), max_len=200, sort_by="saturation"),
    "dark_sort":  lambda s, t, fi: pixel_sort_below_threshold(s, 0.10 + 0.30 * envelope(t), max_len=180),
    "vert_sort":  lambda s, t, fi: pixel_sort_vertical(s, 1.00 - 0.60 * envelope(t), max_len=200),
    "hue_sort":   lambda s, t, fi: pixel_sort_horizontal(s, 1.00 - 0.60 * envelope(t), max_len=200, sort_by="hue"),
    "ripple":     _ripple,
    "wave":       lambda s, t, fi: wave_row_displace(s, amplitude=max(1, int(18 * envelope(t))), wavelength=200) if envelope(t) > 0.02 else s,
    "light_sweep": _light_sweep,
    "charcoal":   lambda s, t, fi: _blend(s, charcoal_sketch(s), envelope(t)),
    "lith":       lambda s, t, fi: _blend(s, lith_print(s), envelope(t)),
    "sabattier":  lambda s, t, fi: _blend(s, sabattier_solarize(s, threshold=0.62), envelope(t)),
    "cinestill":  lambda s, t, fi: _blend(s, cinestill_800t(s, halation_strength=0.75), envelope(t)),
    "ca_pulse":   _ca_pulse,
}

def apply(name: str, src: np.ndarray, *, t: float, frame_idx: int) -> np.ndarray:
    return EFFECTS[name](src, t, frame_idx)
```

NOTE: per-frame charcoal/lith/etc is slow — the pipeline (Task 3) pre-computes the destination once per clip and only blends per frame. `apply()` stays simple for correctness; `media_pipeline` uses `EFFECTS` + a destination cache.

- [ ] **Step 4: Run tests** — same command → 15 passed.
- [ ] **Step 5: Commit** — `git add kalai/media_fx.py kalai/tests/test_media_fx.py && git commit -m "feat(kalai): media_fx — the 12 deterministic effects, self-contained"`

---

### Task 2: media_crew — router, pricer, receipt

**Files:**
- Create: `kalai/media_crew.py`
- Test: `kalai/tests/test_media_crew.py`

- [ ] **Step 1: Write the failing tests**

```python
# kalai/tests/test_media_crew.py
import pytest
from kalai import media_crew as mc

def test_quote_compute_path_fits_dollar():
    q = mc.quote(seconds=8, budget_usd=1.0, has_source_image=True, wants_hdr=True)
    assert q["path"] == "B"                       # source exists -> no generation needed
    assert q["total_usd"] < 0.10
    assert q["fits_budget"] is True
    assert "rationale" in q and q["rationale"]

def test_quote_chain_when_no_source():
    q = mc.quote(seconds=4, budget_usd=1.0, has_source_image=False, wants_hdr=True)
    assert q["path"] == "A->B"                    # must generate a still first
    assert q["lines"][0]["item"] == "imagen_still"

def test_refusal_when_over_budget():
    q = mc.quote(seconds=8, budget_usd=0.001, has_source_image=True, wants_hdr=True)
    assert q["fits_budget"] is False
    assert q["counter_offer"]["seconds"] < 8      # offers the largest duration that fits

def test_receipt_reconciles_measured_seconds():
    q = mc.quote(seconds=2, budget_usd=1.0, has_source_image=True, wants_hdr=True)
    r = mc.receipt(q, measured_vcpu_sec=19.5, vertex_usd=0.0)
    assert r["cpu_usd"] == pytest.approx(19.5 * mc.CPU_USD_PER_VCPU_SEC)
    assert r["total_usd"] == pytest.approx(r["cpu_usd"])
    assert r["estimated_usd"] == q["total_usd"]
```

- [ ] **Step 2: Run to verify failure** — ImportError.

- [ ] **Step 3: Implement `kalai/media_crew.py`**

```python
"""kalai — the media crew's deterministic brain: router + pricer + receipt.

The router is honest v1: a rule with a recorded rationale (an LLM seat can
replace `route()` later without changing the quote/receipt contract).
All prices live HERE and nowhere else.
"""
from __future__ import annotations

IMAGEN_USD = 0.04                    # vertex imagen-4.0 still, published price
VEO_USD_PER_SEC = 0.40               # vertex veo, low tier, per output second
CPU_USD_PER_VCPU_SEC = 0.000024     # cloud run tier-1 vCPU-second
RENDER_VCPU_SEC_PER_OUTPUT_SEC = 11.0  # measured locally 2026-06-10 (1080x1920@24)
MAX_SECONDS = 8

def route(*, has_source_image: bool, wants_hdr: bool) -> tuple[str, str]:
    """(path, rationale). A=generate, B=compute, A->B=chain."""
    if has_source_image:
        return "B", ("source image exists and HDR is a compute capability — "
                     "no generation needed, deterministic FX+HDR path")
    return "A->B", ("no source image — generate a still (Imagen), then the "
                    "compute path adds motion + HDR (Veo cannot output HDR)")

def _lines(path: str, seconds: int) -> list[dict]:
    lines = []
    if path.startswith("A"):
        lines.append({"item": "imagen_still", "usd": IMAGEN_USD})
    cpu_sec = seconds * RENDER_VCPU_SEC_PER_OUTPUT_SEC
    lines.append({"item": "render_cpu", "vcpu_sec": cpu_sec,
                  "usd": cpu_sec * CPU_USD_PER_VCPU_SEC})
    return lines

def quote(*, seconds: int, budget_usd: float, has_source_image: bool,
          wants_hdr: bool) -> dict:
    seconds = max(1, min(MAX_SECONDS, int(seconds)))
    path, rationale = route(has_source_image=has_source_image, wants_hdr=wants_hdr)
    lines = _lines(path, seconds)
    total = round(sum(l["usd"] for l in lines), 6)
    out = {"path": path, "seconds": seconds, "lines": lines, "total_usd": total,
           "budget_usd": budget_usd, "fits_budget": total <= budget_usd,
           "rationale": rationale,
           "est_wall_sec": int(seconds * RENDER_VCPU_SEC_PER_OUTPUT_SEC / 2) + 12}
    if not out["fits_budget"]:
        for s in range(seconds, 0, -1):
            t = sum(l["usd"] for l in _lines(path, s))
            if t <= budget_usd:
                out["counter_offer"] = {"seconds": s, "total_usd": round(t, 6)}
                break
        else:
            out["counter_offer"] = None
    return out

def receipt(quote_: dict, *, measured_vcpu_sec: float, vertex_usd: float) -> dict:
    cpu_usd = round(measured_vcpu_sec * CPU_USD_PER_VCPU_SEC, 6)
    return {"estimated_usd": quote_["total_usd"], "vertex_usd": round(vertex_usd, 6),
            "measured_vcpu_sec": round(measured_vcpu_sec, 1), "cpu_usd": cpu_usd,
            "total_usd": round(vertex_usd + cpu_usd, 6), "path": quote_["path"],
            "seconds": quote_["seconds"]}
```

- [ ] **Step 4: Run tests** — 4 passed.
- [ ] **Step 5: Commit** — `git commit -m "feat(kalai): media_crew — router + pricer + receipt, prices in one place"`

---

### Task 3: media_pipeline — render + HLG encode + verifier

**Files:**
- Create: `kalai/media_pipeline.py`
- Test: `kalai/tests/test_media_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
# kalai/tests/test_media_pipeline.py
import shutil, numpy as np, pytest
from PIL import Image
from kalai import media_pipeline as mp

ffmpeg_missing = shutil.which("ffmpeg") is None

def _tiny_png(tmp_path):
    p = tmp_path / "src.png"
    Image.fromarray((np.random.default_rng(3).random((28, 16, 3)) * 255).astype("uint8")).save(p)
    return str(p)

def test_fit_canvas_scales_and_crops():
    img = (np.zeros((100, 300, 3))).astype("uint8")
    out = mp.fit_canvas(img, w=16, h=28)
    assert out.shape == (28, 16, 3)

@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_render_tiny_end_to_end(tmp_path):
    res = mp.render(src_path=_tiny_png(tmp_path), fx="ripple", seconds=1,
                    out_path=str(tmp_path / "out.mp4"), width=16, height=28, fps=8,
                    label=False)
    v = res["verify"]
    assert v["ok"] and v["pix_fmt"] == "yuv420p10le"
    assert v["color_transfer"] == "arib-std-b67" and v["color_primaries"] == "bt2020"

@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_verifier_fails_closed_on_sdr_file(tmp_path):
    import subprocess
    sdr = tmp_path / "sdr.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=red:s=16x16:d=0.5",
                    "-pix_fmt", "yuv420p", str(sdr)], capture_output=True, check=True)
    v = mp.verify(str(sdr))
    assert v["ok"] is False
```

- [ ] **Step 2: Run to verify failure** — ImportError.

- [ ] **Step 3: Implement `kalai/media_pipeline.py`**

```python
"""kalai — the renderer + hdr-wrapper + verifier (deterministic hands).

Frames are pure numpy (media_fx); encode is ffmpeg HLG HEVC 10-bit BT.2020 —
real HDR, machine-verifiable. The verifier is fail-closed: a file that doesn't
prove its color tags via ffprobe is NOT HDR, whatever the pipeline intended.
"""
from __future__ import annotations
import json, os, subprocess, tempfile, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import media_fx

_BLEND_FX = {"charcoal", "lith", "sabattier", "cinestill"}  # precompute destination once

def fit_canvas(img: np.ndarray, *, w: int, h: int) -> np.ndarray:
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    pil = Image.fromarray(img).resize((max(w, int(iw * s + .5)), max(h, int(ih * s + .5))), Image.LANCZOS)
    a = np.asarray(pil)
    y0, x0 = (a.shape[0] - h) // 2, (a.shape[1] - w) // 2
    return a[y0:y0 + h, x0:x0 + w].copy()

def _label(arr: np.ndarray, text: str) -> np.ndarray:
    im = Image.fromarray(arr); dr = ImageDraw.Draw(im, "RGBA")
    try: font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 34)
    except OSError: font = ImageFont.load_default()
    W, H = im.size
    bb = dr.textbbox((0, 0), text, font=font)
    x = (W - (bb[2] - bb[0])) // 2
    dr.rectangle([x - 16, H - 110, x + bb[2] - bb[0] + 16, H - 60], fill=(0, 0, 0, 150))
    dr.text((x, H - 104), text, font=font, fill=(255, 244, 200, 255))
    return np.asarray(im)

def render(*, src_path: str, fx: str, seconds: int, out_path: str,
           width: int = 1080, height: int = 1920, fps: int = 24,
           label: bool = True, progress=None) -> dict:
    t0 = time.monotonic()
    src = fit_canvas(np.asarray(Image.open(src_path).convert("RGB")), w=width, h=height)
    n = max(1, int(seconds * fps))
    dest_cache = None  # heavy destinations once, blend per frame
    with tempfile.TemporaryDirectory() as td:
        for i in range(n):
            t = i / max(1, n - 1)
            if fx in _BLEND_FX:
                if dest_cache is None:
                    dest_cache = media_fx.EFFECTS[fx](src, 0.5, 0)  # t=0.5 -> full strength dest
                    # ^ envelope(0.5)=1.0 so this IS the destination
                frame = media_fx._blend(src, dest_cache, media_fx.envelope(t))
            else:
                frame = media_fx.apply(fx, src, t=t, frame_idx=i)
            if label:
                frame = _label(frame, fx.replace("_", " ").upper())
            Image.fromarray(frame).save(f"{td}/f_{i:05d}.png")
            if progress: progress(i + 1, n)
        cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", f"{td}/f_%05d.png",
               "-vf", "format=yuv420p10le,setparams=color_primaries=bt2020:"
                      "color_trc=arib-std-b67:colorspace=bt2020nc",
               "-c:v", "libx265", "-pix_fmt", "yuv420p10le", "-preset", "fast", "-crf", "22",
               "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
               "-colorspace", "bt2020nc", "-color_range", "tv",
               "-x265-params", "colorprim=bt2020:transfer=arib-std-b67:"
                               "colormatrix=bt2020nc:range=limited:repeat-headers=1",
               "-tag:v", "hvc1", "-movflags", "+faststart", out_path]
        subprocess.run(cmd, capture_output=True, check=True)
    wall = time.monotonic() - t0
    return {"out_path": out_path, "wall_sec": round(wall, 1),
            "vcpu_sec_estimate": round(wall * (os.cpu_count() or 1) * 0.5, 1),
            "frames": n, "verify": verify(out_path)}

def verify(path: str) -> dict:
    """Fail-closed HDR verification via ffprobe — the atom gate."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, check=True).stdout
        s = json.loads(out)["streams"][0]
    except Exception as exc:  # noqa: BLE001 — unreadable = not verified
        return {"ok": False, "error": str(exc)[:200]}
    checks = {"codec": s.get("codec_name") == "hevc",
              "pix_fmt_10bit": s.get("pix_fmt") == "yuv420p10le",
              "primaries_bt2020": s.get("color_primaries") == "bt2020",
              "transfer_hlg": s.get("color_transfer") == "arib-std-b67"}
    return {"ok": all(checks.values()), "checks": checks,
            "pix_fmt": s.get("pix_fmt"), "color_primaries": s.get("color_primaries"),
            "color_transfer": s.get("color_transfer"),
            "hdr_format": "HLG BT.2020 10-bit" if all(checks.values()) else "NOT HDR"}
```

- [ ] **Step 4: Run tests** — 3 passed (skip if no ffmpeg locally — must pass on a machine with ffmpeg; founder's Mac has it).
- [ ] **Step 5: Commit** — `git commit -m "feat(kalai): media_pipeline — renderer + HLG HDR encode + fail-closed verifier"`

---

### Task 4: service endpoints — quote / render / job

**Files:**
- Modify: `service/app.py` (after the `/api/hero/*` block, ~line 550)
- Test: `tests/test_media_endpoints.py` (repo-root tests/, beside existing service tests if present there — follow the per-directory test rule)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_media_endpoints.py
import io, numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from service.app import app

client = TestClient(app)

def _png_bytes():
    buf = io.BytesIO()
    Image.fromarray((np.zeros((28, 16, 3))).astype("uint8")).save(buf, format="PNG")
    return buf.getvalue()

def test_quote_endpoint():
    r = client.post("/api/kalai/media/quote",
                    json={"seconds": 4, "budget_usd": 1.0, "has_source_image": True})
    assert r.status_code == 200
    d = r.json()
    assert d["path"] == "B" and d["fits_budget"] is True and d["lines"]

def test_render_requires_quote_fit():
    r = client.post("/api/kalai/media/quote",
                    json={"seconds": 8, "budget_usd": 0.0001, "has_source_image": True})
    assert r.json()["fits_budget"] is False
    # render with an over-budget quote must 409
    r2 = client.post("/api/kalai/media/render",
                     files={"image": ("s.png", _png_bytes(), "image/png")},
                     data={"fx": "ripple", "seconds": 8, "budget_usd": 0.0001})
    assert r2.status_code == 409

def test_render_job_lifecycle():
    r = client.post("/api/kalai/media/render",
                    files={"image": ("s.png", _png_bytes(), "image/png")},
                    data={"fx": "ripple", "seconds": 1, "budget_usd": 1.0,
                          "width": 16, "height": 28, "fps": 8})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    import time
    for _ in range(120):
        s = client.get(f"/api/kalai/media/job/{jid}").json()
        if s["status"] in ("done", "error"): break
        time.sleep(0.5)
    assert s["status"] == "done"
    assert s["receipt"]["total_usd"] > 0
    assert s["verify"]["ok"] is True
```

- [ ] **Step 2: Run to verify failure** — 404s.

- [ ] **Step 3: Implement in `service/app.py`**

Add imports near the top (`from kalai import media_crew, media_pipeline`) and this block after the hero routes:

```python
# ─── kalai media crew (router · pricer · renderer · verifier) ────────────────
_media_jobs: dict[str, dict] = {}

class MediaQuoteRequest(BaseModel):
    seconds: int = 4
    budget_usd: float = 1.0
    has_source_image: bool = True

@app.post("/api/kalai/media/quote")
def media_quote(req: MediaQuoteRequest, sess: Session = Depends(_session_dep)) -> dict:
    return media_crew.quote(seconds=req.seconds, budget_usd=req.budget_usd,
                            has_source_image=req.has_source_image, wants_hdr=True)

@app.post("/api/kalai/media/render")
async def media_render(request: Request,
                       image: UploadFile = File(...),
                       fx: str = Form("sat_sort"), seconds: int = Form(4),
                       budget_usd: float = Form(1.0),
                       width: int = Form(1080), height: int = Form(1920),
                       fps: int = Form(24),
                       sess: Session = Depends(_session_dep)) -> Any:
    _rate_limit(request, "media_render", capacity=4, per_seconds=300)
    _require_auth_if_live(sess.user)
    from kalai.media_fx import EFFECTS
    if fx not in EFFECTS:
        return JSONResponse(status_code=422, content={"error": f"unknown fx '{fx}'"})
    q = media_crew.quote(seconds=seconds, budget_usd=budget_usd, has_source_image=True,
                         wants_hdr=True)
    if not q["fits_budget"]:
        return JSONResponse(status_code=409, content={"error": "over budget", "quote": q})
    jid = uuid4().hex
    src = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    src.write(await image.read()); src.close()
    out = src.name.replace(".png", "_hdr.mp4")
    _media_jobs[jid] = {"status": "rendering", "frame": 0, "frames": seconds * fps,
                        "quote": q}
    def _run():
        job = _media_jobs[jid]
        try:
            res = media_pipeline.render(
                src_path=src.name, fx=fx, seconds=q["seconds"], out_path=out,
                width=width, height=height, fps=fps,
                progress=lambda i, n: job.update(frame=i, frames=n))
            job.update(status="done", out_path=res["out_path"], verify=res["verify"],
                       receipt=media_crew.receipt(q, measured_vcpu_sec=res["vcpu_sec_estimate"],
                                                  vertex_usd=0.0))
        except Exception as exc:  # noqa: BLE001
            job.update(status="error", error=str(exc)[:300])
        finally:
            os.unlink(src.name)
    import threading
    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": jid, "quote": q}

@app.get("/api/kalai/media/job/{jid}")
def media_job(jid: str, sess: Session = Depends(_session_dep)) -> dict:
    job = _media_jobs.get(jid)
    if not job:
        return JSONResponse(status_code=404, content={"error": "unknown job"})
    return job

@app.get("/api/kalai/media/file/{jid}")
def media_file(jid: str, sess: Session = Depends(_session_dep)) -> Any:
    job = _media_jobs.get(jid)
    if not job or job.get("status") != "done":
        return JSONResponse(status_code=404, content={"error": "not ready"})
    return FileResponse(job["out_path"], media_type="video/mp4",
                        filename="saakshe_hdr.mp4")
```

(Confirm `UploadFile, File, Form, FileResponse` are imported from fastapi at top of file; add `import tempfile` if absent.)

- [ ] **Step 4: Run tests** — `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_media_endpoints.py -q` → 3 passed.
- [ ] **Step 5: Commit** — `git commit -m "feat(service): kalai media endpoints — quote, async render, job status, file"`

---

### Task 5: container + deps

**Files:**
- Modify: `Dockerfile:10` — change apt line to `apt-get install -y --no-install-recommends git ffmpeg`
- Modify: `requirements.txt` — ensure `numpy`, `Pillow`, `opencv-python-headless` present (check first; only add what's missing — cv2 is actually NOT needed by the final media_fx, drop it if unused)

- [ ] **Step 1:** Edit both files as above.
- [ ] **Step 2:** Verify the full suite still passes per-directory: `for d in common manas kalai kural arivu; do PYTHONPATH=. ./.venv/bin/python -m pytest "$d" -q; done && PYTHONPATH=. ./.venv/bin/python -m pytest tests -q`
- [ ] **Step 3: Commit** — `git commit -m "chore: ffmpeg in container + media deps"`

---

### Task 6: deploy + live verification

- [ ] **Step 1:** Deploy: `./deploy_cloudrun.sh` (demo profile — per standing instruction, deploy without asking once tests pass).
- [ ] **Step 2:** Live check: `curl -s -X POST https://<service-url>/api/kalai/media/quote -H 'content-type: application/json' -d '{"seconds":4,"budget_usd":1,"has_source_image":true}'` → JSON with `path:"B"`, `fits_budget:true`.
- [ ] **Step 3:** Render a real 2s job against prod with a small test image; poll the job; confirm `verify.ok == true` and download the MP4; check tags locally with ffprobe.
- [ ] **Step 4: Commit any fixes + report** to the founder as a Brut HTML (brut-reports skill).

---

## Self-review notes

- Spec coverage: router✓ pricer✓ fx(12)✓ renderer✓ hdr-wrapper (HLG v1, DV8.4 explicitly out)✓ verifier✓ receipt✓ slider 1–8s (MAX_SECONDS=8, quote clamps)✓ budget refusal + counter-offer✓ demo-mode: endpoints sit behind existing session/rate-limit machinery; quote is free; render is the chargeable act (credits wiring deferred — flagged for the founder).
- Types consistent: `quote()` dict keys used by Task 4 (`fits_budget`, `seconds`, `total_usd`) match Task 2.
- Known simplifications (honest): in-process job dict (single-instance Cloud Run, matches existing rate-limiter's assumption); vCPU measurement is wall×cores×0.5 estimate v1 — receipt labels it `measured_vcpu_sec` from this estimator; labeled in code comment.
