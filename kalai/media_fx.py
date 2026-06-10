"""kalai — deterministic FX library (the studio's compute path).

12 validated effects. Each entry in ``EFFECTS`` is ``(src_u8, t, frame_idx) ->
u8 frame`` where ``t`` is the position within the clip in 0..1 and
``envelope(t)`` is the clean -> peak -> clean pulse every clip rides.

Ported verbatim from the founder's validated 108_motion_lib (2026-05-21
session) so output matches the approved reels pixel-for-pixel. Pure
numpy + Pillow — no cv2, no desktop dependency; runs on Cloud Run as-is.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

# ─── helpers (108_motion_lib processes_v4/v6) ─────────────────────────────────

def _f(a):
    return a.astype(np.float32) / 255.0


def _u(a):
    return np.clip(a * 255, 0, 255).astype(np.uint8)


def _L(arr_f):
    return 0.2126 * arr_f[..., 0] + 0.7152 * arr_f[..., 1] + 0.0722 * arr_f[..., 2]


def _s_curve_arr(x, k=2.0, pivot=0.5):
    if k < 0.01:
        return x
    return pivot + 0.5 * np.tanh(k * (x - pivot)) / np.tanh(k * 0.5)


def envelope(t: float) -> float:
    """The pulse every clip rides: 0 at the edges, 1 at the centre."""
    return float(np.sin(np.pi * np.clip(t, 0.0, 1.0)) ** 1.2)


def _blend(a, b, k):
    return (a.astype(np.float32) * (1 - k) + b.astype(np.float32) * k).astype(np.uint8)


# ─── ported effects (verbatim semantics) ──────────────────────────────────────

def pixel_sort_horizontal(arr, threshold=0.55, max_len=180, sort_by="luma"):
    H, W, _ = arr.shape
    out = arr.copy()
    af = _f(arr)
    if sort_by == "luma":
        key_map = _L(af)
    elif sort_by == "saturation":
        maxc = np.max(af, axis=-1)
        minc = np.min(af, axis=-1)
        key_map = np.where(maxc > 0, (maxc - minc) / np.maximum(maxc, 1e-8), 0)
    elif sort_by == "hue":
        r, g, b = af[..., 0], af[..., 1], af[..., 2]
        maxc, minc = np.max(af, axis=-1), np.min(af, axis=-1)
        delta = maxc - minc
        rc = np.where(delta > 0, (maxc - r) / np.maximum(delta, 1e-8), 0)
        gc = np.where(delta > 0, (maxc - g) / np.maximum(delta, 1e-8), 0)
        bc = np.where(delta > 0, (maxc - b) / np.maximum(delta, 1e-8), 0)
        h = np.where(r == maxc, bc - gc, np.where(g == maxc, 2.0 + rc - bc, 4.0 + gc - rc))
        key_map = (h / 6.0) % 1.0
    else:
        raise ValueError(f"unknown sort_by {sort_by!r}")
    for y in range(H):
        row = arr[y].copy()
        row_key = key_map[y]
        mask = row_key > threshold
        i = 0
        while i < W:
            if mask[i]:
                j = i
                while j < W and mask[j] and (j - i) < max_len:
                    j += 1
                seg = row[i:j]
                order = np.argsort(row_key[i:j])
                out[y, i:j] = seg[order]
                i = j
            else:
                i += 1
    return out


def pixel_sort_vertical(arr, threshold=0.55, max_len=180, sort_by="luma"):
    rotated = np.rot90(arr, k=-1)
    sorted_rot = pixel_sort_horizontal(rotated, threshold=threshold, max_len=max_len, sort_by=sort_by)
    return np.ascontiguousarray(np.rot90(sorted_rot, k=1))


def pixel_sort_below_threshold(arr, threshold=0.40, max_len=180):
    H, W, _ = arr.shape
    out = arr.copy()
    key_map = _L(_f(arr))
    for y in range(H):
        row = arr[y].copy()
        row_key = key_map[y]
        mask = row_key < threshold
        i = 0
        while i < W:
            if mask[i]:
                j = i
                while j < W and mask[j] and (j - i) < max_len:
                    j += 1
                seg = row[i:j]
                order = np.argsort(-row_key[i:j])
                out[y, i:j] = seg[order]
                i = j
            else:
                i += 1
    return out


def wave_row_displace(arr, amplitude=15, wavelength=80):
    H, W, _ = arr.shape
    out = np.zeros_like(arr)
    for y in range(H):
        shift = int(amplitude * np.sin(2 * np.pi * y / wavelength))
        if shift >= 0:
            out[y, shift:] = arr[y, : W - shift]
            out[y, :shift] = arr[y, :shift]
        else:
            shift = -shift
            out[y, : W - shift] = arr[y, shift:]
            out[y, W - shift:] = arr[y, W - shift:]
    return out


def charcoal_sketch(arr):
    af = _f(arr)
    luma = _L(af)
    eh = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
    ev = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
    edges = np.clip(np.sqrt(eh ** 2 + ev ** 2) * 6, 0, 1)
    paper = 1 - luma * 0.65
    charcoal = np.clip(paper - edges * 0.7, 0, 1)
    rng = np.random.default_rng(108)
    charcoal = np.clip(charcoal + rng.normal(0, 0.04, charcoal.shape), 0, 1)
    return _u(np.stack([charcoal * 0.96, charcoal * 0.93, charcoal * 0.85], axis=-1))


def lith_print(arr, blacks_lift=0.04, contrast_k=3.5):
    af = _f(arr)
    bw = (0.4 * af[..., 0] + 0.45 * af[..., 1] + 0.15 * af[..., 2])[..., None]
    bw3 = np.repeat(bw, 3, axis=-1)
    bw3 = _s_curve_arr(bw3, k=contrast_k)
    bw3 = bw3 * (1 - blacks_lift) + blacks_lift
    bw3[..., 0] *= 1.04
    bw3[..., 2] *= 0.94
    rng = np.random.default_rng(108)
    bw3 = bw3 + rng.normal(0, 0.025, bw3.shape[:2])[..., None]
    return _u(bw3)


def sabattier_solarize(arr, threshold=0.65):
    af = _f(arr)
    luma = _L(af)[..., None]
    mask = np.clip((luma - threshold) / (1 - threshold + 0.001), 0, 1) ** 1.4
    out = af * (1 - mask) + (1 - af) * mask
    return _u(_s_curve_arr(out, k=1.6))


def cinestill_800t(arr, halation_strength=0.40):
    af = _f(arr)
    luma = _L(af)[..., None]
    af[..., 2] = np.clip(af[..., 2] + (1 - luma)[..., 0] * 0.06, 0, 1)
    af[..., 0] = np.clip(af[..., 0] + luma[..., 0] * 0.04, 0, 1)
    thr = 0.65
    mask = np.clip((luma - thr) / (1 - thr), 0, 1)[..., 0]
    red = af[..., 0] * mask
    red_blur = np.asarray(
        Image.fromarray(_u(red[..., None].repeat(3, -1))).filter(ImageFilter.GaussianBlur(28))
    ).astype(np.float32) / 255.0
    af[..., 0] = np.clip(af[..., 0] + red_blur[..., 0] * halation_strength, 0, 1)
    af[..., 1] = np.clip(af[..., 1] + red_blur[..., 0] * halation_strength * 0.35, 0, 1)
    return _u(af)


def rgb_displace(arr, dx=8):
    H, W, _ = arr.shape
    out = arr.copy()
    if dx <= 0:
        return out
    out[..., 0] = np.roll(arr[..., 0], dx, axis=1)
    out[..., 2] = np.roll(arr[..., 2], -dx, axis=1)
    return out


# ─── clip-time wrappers ───────────────────────────────────────────────────────

def _ripple(src, t, fi):
    k = envelope(t)
    out = src.copy()
    H = src.shape[0]
    sh = (np.sin(2 * np.pi * np.arange(H) / 180.0 + fi * 0.45) * 5.0 * k).astype(int)
    for y in range(H):
        if sh[y]:
            out[y] = np.roll(out[y], sh[y], axis=0)
    return out


def _light_sweep(src, t, fi):
    k = envelope(t)
    H, W = src.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lx = (-0.2 + 1.4 * t) * W
    g = np.exp(-np.sqrt((xx - lx) ** 2 + (yy - H * 0.45) ** 2) / (W * 0.45))[..., None]
    out = src.astype(np.float32) * (1 - 0.3 * k) + src.astype(np.float32) * g * 0.85 * k + g * 60.0 * k
    return np.clip(out, 0, 255).astype(np.uint8)


def _ca_pulse(src, t, fi):
    # triple heartbeat around the clip centre (validated apex pattern)
    pk = 0.0
    for c, amp in ((0.43, 13), (0.5, 22), (0.57, 13)):
        d = abs(t - c)
        if d < 0.04:
            pk = max(pk, amp * (1 - d / 0.04))
    return rgb_displace(src, dx=int(pk * 0.8)) if pk >= 1.5 else src


EFFECTS = {
    "sat_sort": lambda s, t, fi: pixel_sort_horizontal(
        s, 1.05 - 0.70 * envelope(t), max_len=200, sort_by="saturation"),
    "dark_sort": lambda s, t, fi: pixel_sort_below_threshold(
        s, 0.10 + 0.30 * envelope(t), max_len=180),
    "vert_sort": lambda s, t, fi: pixel_sort_vertical(
        s, 1.00 - 0.60 * envelope(t), max_len=200),
    "hue_sort": lambda s, t, fi: pixel_sort_horizontal(
        s, 1.00 - 0.60 * envelope(t), max_len=200, sort_by="hue"),
    "ripple": _ripple,
    "wave": lambda s, t, fi: wave_row_displace(
        s, amplitude=max(1, int(18 * envelope(t))), wavelength=200) if envelope(t) > 0.02 else s,
    "light_sweep": _light_sweep,
    "charcoal": lambda s, t, fi: _blend(s, charcoal_sketch(s), envelope(t)),
    "lith": lambda s, t, fi: _blend(s, lith_print(s), envelope(t)),
    "sabattier": lambda s, t, fi: _blend(s, sabattier_solarize(s, threshold=0.62), envelope(t)),
    "cinestill": lambda s, t, fi: _blend(s, cinestill_800t(s, halation_strength=0.75), envelope(t)),
    "ca_pulse": _ca_pulse,
}


def apply(name: str, src: np.ndarray, *, t: float, frame_idx: int) -> np.ndarray:
    """Run one effect at clip-time ``t``; KeyError on unknown name (fail loud)."""
    return EFFECTS[name](src, t, frame_idx)
