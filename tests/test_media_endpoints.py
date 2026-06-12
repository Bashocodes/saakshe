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


def test_render_canvas_follows_the_source_orientation(monkeypatch):
    """A landscape source must not come back as a 9:16 centre-crop — when the
    client sends no dims, the canvas follows the source image's aspect
    (founder, 2026-06-12), with even dims for the HEVC encoder."""
    from service import app as appmod
    seen = {}

    def fake_render(**kw):
        seen.update(kw)
        return {"out_path": kw["out_path"], "verify": {"ok": True},
                "vcpu_sec_estimate": 1.0}

    monkeypatch.setattr(appmod.media_pipeline, "render", fake_render)
    buf = io.BytesIO()
    Image.fromarray(np.zeros((900, 1600, 3), dtype="uint8")).save(buf, format="PNG")
    r = client.post("/api/kalai/media/render",
                    files={"image": ("land.png", buf.getvalue(), "image/png")},
                    data={"fx": "ripple", "seconds": 1, "budget_usd": 1.0})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    for _ in range(200):
        if client.get(f"/api/kalai/media/job/{jid}").json().get("status") != "rendering":
            break
        time.sleep(0.01)
    assert seen["width"] > seen["height"], seen
    assert abs(seen["width"] / seen["height"] - 16 / 9) < 0.01, seen
    assert seen["width"] % 2 == 0 and seen["height"] % 2 == 0, seen


def test_render_survives_a_restart_via_the_persisted_record():
    """The in-memory job table dies with the instance — the transcript record +
    vault copy must keep a finished render reachable (the refresh-amnesia fix)."""
    from service import app as appmod
    r = client.post("/api/kalai/media/render",
                    files={"image": ("s.png", _png_bytes(), "image/png")},
                    data={"fx": "ripple", "seconds": 1, "budget_usd": 1.0,
                          "width": 16, "height": 28, "fps": 8})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    for _ in range(120):
        s = client.get(f"/api/kalai/media/job/{jid}").json()
        if s.get("status") in ("done", "error"):
            break
        time.sleep(0.5)
    assert s.get("status") == "done", s
    appmod._media_jobs.pop(jid, None)          # simulate the instance restarting
    s2 = client.get(f"/api/kalai/media/job/{jid}").json()
    assert s2.get("status") == "done" and s2.get("persisted") is True, s2
    assert s2.get("verify", {}).get("ok") is True
    f = client.get(f"/api/kalai/media/file/{jid}")
    assert f.status_code == 200 and f.headers["content-type"] == "video/mp4"


def test_interrupted_render_auto_resumes_from_the_vaulted_source():
    """A render the instance lost mid-flight (deploy/crash) restarts from its
    render_pending record the moment the owner polls it — no new charge."""
    from uuid import uuid4
    from common import project, vault
    jid = uuid4().hex
    src_uri = vault.put(f"render_src_{jid}.png", _png_bytes(), "image/png", user="founder")
    project.STORE.append_message(
        "kalai/producer", "render started — 1s ripple, background.",
        meta={"kind": "render_pending", "job_id": jid, "src_uri": src_uri,
              "fx": "ripple", "seconds": 1, "budget_usd": 1.0,
              "width": 16, "height": 28, "fps": 8})
    s = client.get(f"/api/kalai/media/job/{jid}").json()   # the poll IS the resume
    assert s.get("status") in ("rendering", "done"), s
    for _ in range(120):
        s = client.get(f"/api/kalai/media/job/{jid}").json()
        if s.get("status") in ("done", "error"):
            break
        time.sleep(0.5)
    assert s.get("status") == "done", s
    f = client.get(f"/api/kalai/media/file/{jid}")
    assert f.status_code == 200 and f.headers["content-type"] == "video/mp4"
