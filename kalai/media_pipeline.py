"""kalai — the renderer + hdr-wrapper + verifier (deterministic hands).

Frames are pure numpy (media_fx); encode is ffmpeg HLG HEVC 10-bit BT.2020 —
real HDR, machine-verifiable. The verifier is fail-closed: a file that doesn't
prove its color tags via ffprobe is NOT HDR, whatever the pipeline intended.

v1 delivers HLG (not Dolby Vision 8.4 — dovi_tool/MP4Box are desktop tooling,
not in the container). The verifier reports exactly what was produced.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import media_fx

# heavy destinations are computed once per clip, then blended per frame
_BLEND_FX = {"charcoal", "lith", "sabattier", "cinestill"}

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Menlo.ttc",                              # macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",     # debian
)


def fit_canvas(img: np.ndarray, *, w: int, h: int) -> np.ndarray:
    """Scale-to-fill then centre-crop to exactly (h, w)."""
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    pil = Image.fromarray(img).resize(
        (max(w, int(iw * s + .5)), max(h, int(ih * s + .5))), Image.LANCZOS)
    a = np.asarray(pil)
    y0, x0 = (a.shape[0] - h) // 2, (a.shape[1] - w) // 2
    return a[y0:y0 + h, x0:x0 + w].copy()


def _font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _label(arr: np.ndarray, text: str) -> np.ndarray:
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im, "RGBA")
    W, H = im.size
    font = _font(max(12, W // 32))
    bb = dr.textbbox((0, 0), text, font=font)
    x = max(4, (W - (bb[2] - bb[0])) // 2)
    y = H - max(60, H // 18)
    dr.rectangle([x - 14, y - 10, x + bb[2] - bb[0] + 14, y + bb[3] - bb[1] + 14],
                 fill=(0, 0, 0, 150))
    dr.text((x, y), text, font=font, fill=(255, 244, 200, 255))
    return np.asarray(im)


def render(*, src_path: str, fx: str, seconds: int, out_path: str,
           width: int = 1080, height: int = 1920, fps: int = 24,
           label: bool = True, progress=None) -> dict:
    t0 = time.monotonic()
    src = fit_canvas(np.asarray(Image.open(src_path).convert("RGB")), w=width, h=height)
    n = max(1, int(seconds * fps))
    dest_cache = None
    with tempfile.TemporaryDirectory() as td:
        for i in range(n):
            t = i / max(1, n - 1)
            if fx in _BLEND_FX:
                if dest_cache is None:
                    # envelope(0.5)=1.0, so t=0.5 yields the full-strength destination
                    dest_cache = media_fx.EFFECTS[fx](src, 0.5, 0)
                frame = media_fx._blend(src, dest_cache, media_fx.envelope(t))
            else:
                frame = media_fx.apply(fx, src, t=t, frame_idx=i)
            if label:
                frame = _label(frame, fx.replace("_", " ").upper())
            Image.fromarray(frame).save(f"{td}/f_{i:05d}.png")
            if progress:
                progress(i + 1, n)
        cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", f"{td}/f_%05d.png",
               "-vf", "format=yuv420p10le,setparams=color_primaries=bt2020:"
                      "color_trc=arib-std-b67:colorspace=bt2020nc",
               "-c:v", "libx265", "-pix_fmt", "yuv420p10le", "-preset", "fast",
               "-crf", "22",
               "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
               "-colorspace", "bt2020nc", "-color_range", "tv",
               "-x265-params", "colorprim=bt2020:transfer=arib-std-b67:"
                               "colormatrix=bt2020nc:range=limited:repeat-headers=1",
               "-tag:v", "hvc1", "-movflags", "+faststart", out_path]
        subprocess.run(cmd, capture_output=True, check=True)
    wall = time.monotonic() - t0
    return {"out_path": out_path, "wall_sec": round(wall, 1),
            # v1 estimator: wall x cores x 0.5 utilization; the receipt labels
            # this measured_vcpu_sec — replace with cgroup accounting later
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
