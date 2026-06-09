"""manas.social — the real social handle reader (replaces the runner stub).

Demo: a DETERMINISTIC, structured bundle (the handle + a scripted recent-post / tone
summary) — NOT the old one-line stub ``"Primary social presence: {ref}."``. The text
is richer so the social imbiber reads a real signal, while the bundle stays
``ok=True`` with non-empty text + provenance (so the channel still grounds and
``has_social`` stays True at runner.py:131 → the demo roll-up is byte-identical).

Live: a single mockable fetch seam (``_fetch_handle``) owns the only network path
(lazy ``import httpx`` inside it), so a test that forces live stays creds-free purely
by mocking that one function — there is no client to construct before the dispatch.
"""

from __future__ import annotations

from manas import social
from manas import sources as src

_STUB = "Primary social presence: {ref}."   # the retired one-liner — must NOT come back


# ─── demo: a structured bundle, not the stub ─────────────────────────────────
def test_demo_returns_structured_bundle_not_the_stub():
    ref = "@example_co"
    b = social.read_handle(ref)
    assert isinstance(b, src.SourceBundle)
    assert b.channel == "social"
    assert b.ref == ref
    assert b.ok is True
    assert b.text                                   # non-empty → the channel still grounds
    # the retired stub literal is gone — the reader emits a real, structured signal
    assert b.text != _STUB.format(ref=ref)
    assert "Primary social presence:" not in b.text
    # the structured bundle carries a handle + a recent-post / tone summary
    assert ref.lstrip("@") in b.text
    assert any(w in b.text.lower() for w in ("post", "tone", "update", "audience"))
    assert b.provenance                             # cites where the signal came from


def test_demo_is_deterministic():
    a = social.read_handle("@example_co")
    b = social.read_handle("@example_co")
    assert a.text == b.text and a.provenance == b.provenance
    other = social.read_handle("@another_co")
    assert other.text != a.text                     # the handle drives the bundle


def test_demo_normalizes_a_url_handle():
    b = social.read_handle("https://instagram.com/example_co")
    assert b.ok is True and b.text
    assert "example_co" in b.text                   # the handle is recovered from the url


def test_demo_honors_a_non_instagram_url_verbatim():
    """A full profile URL on ANY platform is read where it actually lives — NOT
    rewritten to instagram (the old hardcode). The platform + handle both survive."""
    b = social.read_handle("https://www.linkedin.com/company/example_co")
    assert b.ok is True and b.text
    assert any("linkedin.com" in p for p in b.provenance)
    assert not any("instagram.com" in p for p in b.provenance)
    assert "example_co" in b.text


def test_handle_url_verbatim_for_any_platform_default_for_bare():
    """The URL seam: any full profile URL passes through untouched; only a bare
    handle (no platform to infer) falls back to the single documented default."""
    assert social._handle_url("https://x.com/acme") == "https://x.com/acme"
    assert social._handle_url("https://www.linkedin.com/company/acme") == "https://www.linkedin.com/company/acme"
    bare = social._handle_url("@example_co")
    assert "example_co" in bare and bare == social._DEFAULT_PROFILE_URL.format(name="example_co")


# ─── live: a real handle read via the mockable fetch seam ────────────────────
def test_live_dispatches_to_the_fetch_seam(monkeypatch):
    calls: dict = {}

    def _fake_fetch(ref: str) -> src.SourceBundle:
        calls["ref"] = ref
        return src.SourceBundle(
            channel="social", ref=ref,
            text="Handle @example_co · 1.2k followers · recent post: launched the Pro tier",
            provenance=[f"https://instagram.com/{ref.lstrip('@')}"], ok=True,
            meta={"followers": 1200},
        )

    monkeypatch.setattr(social, "_fetch_handle", _fake_fetch)
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    b = social.read_handle("@example_co", _force_live=True)
    assert calls["ref"] == "@example_co"            # the ref reached the live seam
    assert b.ok is True
    assert "recent post" in b.text                  # the live signal flowed through
    assert b.meta.get("followers") == 1200


def test_live_fetch_failure_is_defensive(monkeypatch):
    """A failed live read returns an honest empty bundle (ok=False + error) — one bad
    source never sinks the connect (matches sources.py's defensive philosophy)."""
    def _boom(ref: str) -> src.SourceBundle:
        return src.SourceBundle(channel="social", ref=ref, ok=False,
                                meta={"error": "profile is private"})

    monkeypatch.setattr(social, "_fetch_handle", _boom)
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    b = social.read_handle("@private_co", _force_live=True)
    assert b.ok is False
    assert b.meta.get("error") == "profile is private"


# ─── the runner wires the social branch to the reader ────────────────────────
def test_runner_social_branch_uses_read_handle():
    """``_read_one(kind='social')`` now routes through ``social.read_handle`` — the
    inline one-liner stub is gone from the runner."""
    import inspect

    from manas import runner

    src_text = inspect.getsource(runner._read_sources)
    assert "social.read_handle" in src_text or "read_handle(" in src_text
    assert "Primary social presence:" not in src_text
