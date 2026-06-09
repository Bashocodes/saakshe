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


def test_website_source_surfaces_images_in_meta(tmp_path, monkeypatch):
    # The real auto-extract input: WebsiteSource.read puts discovered image URLs
    # (og:image / <img src> / favicon, absolute) under bundle.meta["images"].
    html = (
        '<html><head><title>Co</title>'
        '<meta property="og:image" content="https://co.example/og.png">'
        '<link rel="icon" href="/favicon.ico">'
        '</head><body><img src="/img/logo.png"><img src="https://cdn.x/hero.jpg">'
        '</body></html>'
    )

    class _Resp:
        def __init__(self, text, url):
            self.text = text
            self.url = url

        def raise_for_status(self):  # pragma: no cover - not exercised here
            return None

    class _Cli:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, *a, **k):
            return _Resp(html, "https://co.example/")

    monkeypatch.setattr(src.httpx, "Client", _Cli)
    bundle = src.WebsiteSource().read("https://co.example")
    imgs = bundle.meta.get("images", [])
    assert "https://co.example/og.png" in imgs
    assert "https://co.example/img/logo.png" in imgs
    assert "https://cdn.x/hero.jpg" in imgs
    assert "https://co.example/favicon.ico" in imgs
