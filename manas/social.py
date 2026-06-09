"""manas.social — the real social handle reader (the world's-pulse channel's hands).

Replaces the runner's one-line stub (``"Primary social presence: {ref}."``) with a
``SourceBundle`` carrying a real, structured signal: the handle, a recent-post / tone
summary, and provenance the social imbiber can read like any other channel.

DESIGN RULE that keeps CI creds-free even under ``SAAKSHE_MODE=live`` (mirrors
``kalai/media.py``): the public ``read_handle`` owns ONLY the demo/live branch. The
single live network read lives inside the tiny ``_fetch_handle`` (lazy ``import httpx``
inside the function), so a test that forces live is held creds-free purely by mocking
that one function — there is no client to construct before the dispatch.

Live reads a public profile / oEmbed signal through a neutral httpx seam — no coupling
to any sibling content platform; manas only KNOWS, it never posts.

Demo path (``not is_live()`` and not ``_force_live``): a DETERMINISTIC structured
bundle keyed off the handle (same handle → same text), ``ok=True`` with non-empty
text + provenance — so the social channel still grounds and ``has_social`` stays True
(the demo roll-up is byte-identical: the social imbiber replays ``_INGEST['social']``
regardless of this text).
"""

from __future__ import annotations

import re

from common import config

from . import sources as src


def _handle_name(ref: str) -> str:
    """The bare handle from a ``@name``, a profile url, or a plain name."""
    ref = (ref or "").strip()
    if ref.startswith(("http://", "https://")):
        # …/example_co or …/example_co/ → example_co
        tail = re.sub(r"[?#].*$", "", ref).rstrip("/").rsplit("/", 1)[-1]
        return tail.lstrip("@") or ref
    return ref.lstrip("@")


# ─── live read (the ONLY network/creds path — mock this in tests) ─────────────
def _fetch_handle(ref: str) -> src.SourceBundle:
    """Live social read. Lazy ``import httpx`` so the module is creds-free until this
    runs. Reads a public profile / oEmbed signal and reduces it to a structured text
    bundle; a failed read returns an honest empty bundle (``ok=False`` + the error in
    ``meta``) so one bad source never sinks the connect."""
    try:
        import httpx
    except Exception as e:  # noqa: BLE001 — httpx unavailable → defensive empty bundle
        return src.SourceBundle(channel="social", ref=ref, ok=False,
                                meta={"error": f"httpx not available: {e}"})

    name = _handle_name(ref)
    url = f"https://www.instagram.com/{name}/"
    try:
        with httpx.Client(follow_redirects=True, timeout=15,
                          headers={"user-agent": "saakshe-setu/1.0 (+manas social read)"}) as cli:
            r = cli.get(url)
            r.raise_for_status()
            title, desc, body, _ = src._parse_html(r.text, base=str(r.url))
        signal = " ".join(s for s in (title, desc) if s) or body[:600]
        if not signal.strip():
            return src.SourceBundle(channel="social", ref=ref, ok=False,
                                    meta={"error": "no readable profile signal"})
        text = (f"Social handle @{name} ({url}).\n"
                f"Profile signal: {signal}".strip())
        return src.SourceBundle(channel="social", ref=ref, text=text[:src.WEB_CAP],
                                provenance=[url], ok=True)
    except Exception as e:  # noqa: BLE001
        return src.SourceBundle(channel="social", ref=ref, ok=False,
                                meta={"error": str(e)[:300]})


# ─── demo bundle (deterministic, creds-free, structured — not the old stub) ───
def _demo_bundle(ref: str) -> src.SourceBundle:
    """A deterministic, structured social signal: the handle + a scripted recent-post
    / tone summary. Same handle → same text. Obviously-synthetic (brand-free), so the
    offline net stays a net, never the product."""
    name = _handle_name(ref) or "the_company"
    url = f"https://instagram.com/{name}"
    text = (
        f"Social handle @{name} ({url}).\n"
        "Recent posts: product updates and behind-the-scenes notes on the main channel.\n"
        "Tone of voice: plain and warm, never hypey — speaks to the audience directly.\n"
        "Audience: independent makers and small teams follow along for product news."
    )
    # No org_hint: the social signal informs voice/audience, not the org's identity —
    # repo/web own the merged org profile (merge_org_hints is first-wins).
    return src.SourceBundle(channel="social", ref=ref, text=text,
                            provenance=[url, "social profile"], ok=True)


# ─── public reader (branch + dispatch ONLY — no network in demo) ──────────────
def read_handle(ref: str, *, _force_live: bool = False) -> src.SourceBundle:
    """Read a connected social handle → a ``SourceBundle`` the social imbiber consumes.

    Live → a real profile/oEmbed read via ``_fetch_handle``; else a deterministic,
    creds-free structured bundle (no network). Sync by design — it is called inside
    ``asyncio.to_thread`` from the runner alongside the other channel readers."""
    if config.is_live() or _force_live:
        return _fetch_handle(ref)
    return _demo_bundle(ref)
