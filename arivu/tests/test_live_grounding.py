"""Pin live grounding at frame time (2b.3).

In demo, the frame-time grounding bundle is the seed fixture, byte-identical — so
the four original tests are untouched. In live, ``fetch_grounding`` pulls the org's
REAL numbers from the example MCP admin surface; if no live source resolves, the
bundle carries ONLY what is real (the manas corpus section) — fixture numbers
NEVER reach a live chamber ("grounded or silent" means silent, not canned).

The live branch is exercised with a mocked admin fetch (the standard way to test a
live integration without creds / network). One creds-gated smoke confirms the live
path runs end-to-end when credentials are present.
"""

from __future__ import annotations

import pytest

from arivu import config
from arivu.demo_fixtures import DEMO_GROUNDING
from arivu.tools import grounding


def test_demo_grounding_is_the_seed_fixture(monkeypatch):
    """Demo mode grounds from the seed fixture, byte-identical (the 4 originals
    depend on this)."""
    monkeypatch.setenv("ARIVU_MODE", "demo")
    assert grounding.fetch_grounding() == DEMO_GROUNDING


def test_live_grounding_uses_real_numbers_when_available(monkeypatch):
    """In live, a resolved live source overrides the fixture — the chamber argues
    from the org's actual numbers, not the canned 412."""
    monkeypatch.setenv("ARIVU_MODE", "live")
    live_bundle = {"admin_stats": {"paying_users": 999, "current_pro_price": 41}}
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: live_bundle)
    out = grounding.fetch_grounding()
    assert out is live_bundle
    assert out["admin_stats"]["paying_users"] == 999          # live, not 412
    assert out != DEMO_GROUNDING


def test_live_no_source_never_serves_fixture_numbers(monkeypatch):
    """In live with no live source AND no reachable corpus, the bundle is EMPTY —
    fixture numbers never reach a live chamber. An advisor with nothing real to
    cite must qualify or stay silent, not argue from a canned 412-user company."""
    from common import a2a

    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    monkeypatch.delitem(a2a._HANDLERS, "manas.get_founder_context", raising=False)
    out = grounding.fetch_grounding()
    assert out == {}
    assert out != DEMO_GROUNDING


def test_live_fallback_grounds_memory_from_real_corpus(monkeypatch):
    """Live + no admin source: the manas_a2a section is built from the REAL corpus
    (brand/voice + top cited facts) via manas's A2A skill, and NO fixture numbers
    ride along — the chamber argues only from what the founder actually imbibed."""
    from common import a2a

    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    monkeypatch.setitem(
        a2a._HANDLERS, "manas.get_founder_context",
        lambda topic="company": {
            "version": "v9", "grounded": True,
            "voice_rules": ["plain and warm"], "brand_rules": ["honor grandfathering"],
            "facts": [{"claim": "the product is free to start", "source": "site"}],
        },
    )
    out = grounding.fetch_grounding()
    assert out["manas_a2a"] == {
        "brand_canon": "honor grandfathering",
        "voice": "plain and warm",
        "facts": "the product is free to start",
    }
    assert "admin_stats" not in out                    # fixture numbers never leak live
    assert "admin_analytics_user_growth" not in out


def test_live_fallback_empty_when_corpus_ungrounded(monkeypatch):
    """An UNGROUNDED corpus (nothing imbibed) yields an EMPTY live bundle — never
    the seed fixture. Honest silence beats canned confidence."""
    from common import a2a

    monkeypatch.setenv("ARIVU_MODE", "live")
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: None)
    monkeypatch.setitem(
        a2a._HANDLERS, "manas.get_founder_context",
        lambda topic="company": {"version": "v0", "grounded": False,
                                 "voice_rules": [], "brand_rules": []},
    )
    assert grounding.fetch_grounding() == {}


def test_live_admin_bundle_is_gated_off_by_default(monkeypatch):
    """Without EXAMPLE_MCP_ENABLE the live fetch is a no-op (None) — the opt-in
    transport pattern, identical to example_mcp_toolset."""
    monkeypatch.delenv("EXAMPLE_MCP_ENABLE", raising=False)
    assert grounding._live_admin_bundle() is None


@pytest.mark.skipif(
    not config.creds_available(), reason="live grounding smoke needs live creds"
)
def test_live_grounding_path_runs_without_error(monkeypatch):
    """Creds-gated smoke: the live path executes end-to-end. The bundle may be
    empty (nothing real resolved) but it must never be the demo fixture."""
    monkeypatch.setenv("ARIVU_MODE", "live")
    out = grounding.fetch_grounding()
    assert isinstance(out, dict)
    assert out != DEMO_GROUNDING


# ─── the MCP admin fetch is REAL now (was a stub returning None) ──────────────
class _FakeResp:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = {"content-type": "application/json", **(headers or {})}
        self.text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _rpc_tool_result(payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text",
                                    "text": __import__("json").dumps(payload)}]}}


def test_mcp_admin_fetch_builds_bundle(monkeypatch):
    """initialize → 3 tools/call → DEMO_GROUNDING-shaped bundle. The session id
    header is adopted; per-call failures degrade to a partial bundle."""
    import httpx

    calls = []

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None, timeout=None):
            calls.append((json or {}).get("method"))
            method = (json or {}).get("method")
            if method == "initialize":
                return _FakeResp({"jsonrpc": "2.0", "id": 0, "result": {}},
                                 headers={"mcp-session-id": "s-1"})
            if method == "notifications/initialized":
                return _FakeResp({})
            name = json["params"]["name"]
            args = json["params"]["arguments"]
            if name == "admin_stats":
                return _FakeResp(_rpc_tool_result({"paying_users": 999, "mrr_usd": 21000}))
            if args.get("report") == "user_growth":
                return _FakeResp(_rpc_tool_result({"trial_to_paid_pct": 22.1}))
            return _FakeResp(_rpc_tool_result({"cohort_retention_12mo_pct": 81}))

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _FakeClient())
    out = grounding._mcp_admin_fetch("https://mcp.example/mcp", "sek")
    assert out == {
        "admin_stats": {"paying_users": 999, "mrr_usd": 21000},
        "admin_analytics_user_growth": {"trial_to_paid_pct": 22.1},
        "admin_analytics_activity": {"cohort_retention_12mo_pct": 81},
    }
    assert calls.count("tools/call") == 3


def test_mcp_admin_fetch_fail_soft(monkeypatch):
    """A dead admin surface returns None — grounding falls back, never raises."""
    import httpx

    class _Boom:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _Boom())
    assert grounding._mcp_admin_fetch("https://mcp.example/mcp", "sek") is None


def test_tool_result_unwraps_structured_and_text():
    sc = {"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": {"a": 1}}}
    assert grounding._tool_result_dict(sc) == {"a": 1}
    assert grounding._tool_result_dict(_rpc_tool_result({"b": 2})) == {"b": 2}
    err = {"jsonrpc": "2.0", "id": 1, "result": {"isError": True, "content": []}}
    assert grounding._tool_result_dict(err) is None


def test_live_bundle_gains_real_memory_section(monkeypatch):
    """When the admin surface resolves, the REAL corpus canon rides along —
    numbers and memory in one bundle (setdefault: server sections win)."""
    monkeypatch.setenv("ARIVU_MODE", "live")
    live_bundle = {"admin_stats": {"paying_users": 999}}
    monkeypatch.setattr(grounding, "_live_admin_bundle", lambda: live_bundle)
    monkeypatch.setattr(grounding, "_real_memory_section",
                        lambda: {"brand_canon": "real promise", "voice": "calm"})
    out = grounding.fetch_grounding()
    assert out is live_bundle                       # identity contract holds
    assert out["manas_a2a"]["brand_canon"] == "real promise"
