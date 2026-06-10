"""media_pipeline — render + HLG encode + fail-closed verifier."""
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from kalai import media_pipeline as mp

ffmpeg_missing = shutil.which("ffmpeg") is None


def _tiny_png(tmp_path):
    p = tmp_path / "src.png"
    Image.fromarray(
        (np.random.default_rng(3).random((28, 16, 3)) * 255).astype("uint8")).save(p)
    return str(p)


def test_fit_canvas_scales_and_crops():
    img = np.zeros((100, 300, 3), dtype="uint8")
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
    assert res["frames"] == 8


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_verifier_fails_closed_on_sdr_file(tmp_path):
    sdr = tmp_path / "sdr.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=red:s=16x16:d=0.5",
                    "-pix_fmt", "yuv420p", str(sdr)], capture_output=True, check=True)
    v = mp.verify(str(sdr))
    assert v["ok"] is False


def test_verifier_fails_closed_on_garbage(tmp_path):
    p = tmp_path / "junk.mp4"
    p.write_bytes(b"not a video")
    assert mp.verify(str(p))["ok"] is False
