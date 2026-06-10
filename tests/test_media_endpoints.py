"""kalai media endpoints — quote, async render job, fail-closed over-budget."""
import io
import time

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from service.app import app

client = TestClient(app)


def _png_bytes():
    buf = io.BytesIO()
    Image.fromarray(np.zeros((28, 16, 3), dtype="uint8")).save(buf, format="PNG")
    return buf.getvalue()


def test_quote_endpoint():
    r = client.post("/api/kalai/media/quote",
                    json={"seconds": 4, "budget_usd": 1.0, "has_source_image": True})
    assert r.status_code == 200
    d = r.json()
    assert d["path"] == "B" and d["fits_budget"] is True and d["lines"]


def test_render_rejects_over_budget():
    r = client.post("/api/kalai/media/render",
                    files={"image": ("s.png", _png_bytes(), "image/png")},
                    data={"fx": "ripple", "seconds": 8, "budget_usd": 0.0001})
    assert r.status_code == 409


def test_render_rejects_unknown_fx():
    r = client.post("/api/kalai/media/render",
                    files={"image": ("s.png", _png_bytes(), "image/png")},
                    data={"fx": "sparkle_unicorn", "seconds": 1, "budget_usd": 1.0})
    assert r.status_code == 422


def test_render_job_lifecycle():
    r = client.post("/api/kalai/media/render",
                    files={"image": ("s.png", _png_bytes(), "image/png")},
                    data={"fx": "ripple", "seconds": 1, "budget_usd": 1.0,
                          "width": 16, "height": 28, "fps": 8})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    s = {}
    for _ in range(120):
        s = client.get(f"/api/kalai/media/job/{jid}").json()
        if s.get("status") in ("done", "error"):
            break
        time.sleep(0.5)
    assert s.get("status") == "done", s
    assert s["receipt"]["total_usd"] > 0
    assert s["verify"]["ok"] is True
    f = client.get(f"/api/kalai/media/file/{jid}")
    assert f.status_code == 200 and f.headers["content-type"] == "video/mp4"


def test_unknown_job_404():
    assert client.get("/api/kalai/media/job/nope").status_code == 404
