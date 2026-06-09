"""saakshe.tests.test_credit_routes — the auth + credit gate at the HTTP layer.

These drive the REAL FastAPI app + the REAL ``_session_dep`` (auth resolution +
per-request store/stream binding + contextvar reset) through TestClient — only the
NETWORK leaves are faked (verify_token, the per-user store/stream factories, and the
credit RPC ledger). That is deliberate: the per-request contextvar binding across
FastAPI's dependency/handler boundary, and the refund-reaches-approve money path,
are exactly the glue a mocked dependency would hide. The SQL itself is verified
separately, live, against the real database.

Billing is active here because SAAKSHE_STORE=supabase + a signed-in non-owner —
the flywheel still runs in DEMO (scripted, creds-free) mode, which is the whole
point of decoupling billing from model-liveness.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from common import auth, credits, project
from common.stream import EventStream


# ─── an in-memory credit ledger standing in for the Postgres RPCs ─────────────
class Ledger:
    def __init__(self) -> None:
        self.bal: dict[str, int] = {}
        self.calls: list[str] = []

    def rpc(self, fn: str, params: dict) -> int:
        self.calls.append(fn)
        u = params["p_user_id"]
        if fn == "saakshe_grant_signup":
            self.bal.setdefault(u, params["p_grant"])
            return self.bal[u]
        if fn == "saakshe_spend":
            cur = self.bal.get(u, 0)
            if cur < params["p_amount"]:
                raise credits.CreditError("INSUFFICIENT_CREDITS", code="P0001")
            self.bal[u] = cur - params["p_amount"]
            return self.bal[u]
        if fn == "saakshe_refund":
            self.bal[u] = self.bal.get(u, 0) + params["p_amount"]
            return self.bal[u]
        raise AssertionError(f"unexpected rpc {fn}")

    def get_balance(self, u: str) -> int:
        return self.bal.get(u, 0)


_SYNTH_FACTS = [{"claim": "Pro is $29/mo.", "source": "README"},
                {"claim": "We grandfather subscribers.", "source": "docs/trust"}]


@pytest.fixture
def client(monkeypatch):
    """The app in Supabase-backed mode with auth + credits faked at the leaves but
    the real session dependency, routing, billing and orchestrator in play."""
    import service.app as appmod

    monkeypatch.setenv("SAAKSHE_STORE", "supabase")
    monkeypatch.setenv("SAAKSHE_SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.setenv("SAAKSHE_MODE", "demo")          # scripted flywheel, creds-free
    monkeypatch.delenv("OWNER_EMAILS", raising=False)

    # auth: a token "tok_<name>" verifies to user "u_<name>".
    def fake_verify(token: str) -> dict:
        if token == "bad":
            raise auth.AuthError("bad token")
        uid = token.replace("tok_", "u_")
        return {"sub": uid, "email": f"{uid}@example.com", "aud": "authenticated"}
    monkeypatch.setattr(auth, "verify_token", fake_verify)

    # per-user store: a real (file-backed, tmp) ProjectStore, grounded so the
    # flywheel can run. Cached per uid so start + approve share one run's store.
    stores: dict[str, project.ProjectStore] = {}

    def fake_store_for(uid: str):
        s = stores.get(uid)
        if s is None:
            s = project.ProjectStore(user=uid)
            s.reset()
            stores[uid] = s
        return s
    monkeypatch.setattr(project, "store_for", fake_store_for)

    streams: dict[str, EventStream] = {}
    monkeypatch.setattr(appmod, "_stream_factory",
                        lambda uid: streams.setdefault(uid, EventStream()))

    ledger = Ledger()
    monkeypatch.setattr(credits, "_rpc", ledger.rpc)
    monkeypatch.setattr(credits, "_get_balance", ledger.get_balance)
    appmod._GRANTED.clear()

    c = TestClient(appmod.app)
    c.ledger = ledger          # type: ignore[attr-defined]
    c.stores = stores          # type: ignore[attr-defined]
    return c


def _ground(store):
    store.add_connection("github", "git@github.com:x/app.git", {"mechanism": "ssh"})
    store.set_org(name="X Co", kind="product", one_liner="for makers")
    store.commit_pack(_SYNTH_FACTS, ["warm"], ["no urgency"], note="seed")


def _auth(name: str) -> dict:
    return {"Authorization": f"Bearer tok_{name}"}


# ─── identity + grant ─────────────────────────────────────────────────────────
def test_me_grants_and_returns_balance(client):
    r = client.get("/api/me", headers=_auth("alice"))
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "u_alice" and body["email"] == "u_alice@example.com"
    assert body["balance"] == credits.SIGNUP_GRANT        # first touch granted 100
    assert "saakshe_grant_signup" in client.ledger.calls


def test_me_401_when_anonymous(client):
    assert client.get("/api/me").status_code == 401


def test_me_401_on_bad_token(client):
    assert client.get("/api/me", headers={"Authorization": "Bearer bad"}).status_code == 401


# ─── the flywheel debit ───────────────────────────────────────────────────────
def test_hero_run_debits_flywheel_cost(client):
    client.get("/api/me", headers=_auth("alice"))          # grant 100
    _ground(client.stores["u_alice"])
    r = client.post("/api/hero/run", json={"idem_key": "run-1"}, headers=_auth("alice"))
    assert r.status_code == 200
    assert r.json()["status"] == "awaiting_approval"
    assert client.ledger.get_balance("u_alice") == 100 - credits.cost("flywheel_run")


def test_hero_run_402_when_out_of_credits(client):
    client.get("/api/me", headers=_auth("broke"))
    client.ledger.bal["u_broke"] = 5                       # less than the run cost
    _ground(client.stores["u_broke"])
    r = client.post("/api/hero/run", json={"idem_key": "run-x"}, headers=_auth("broke"))
    assert r.status_code == 402
    assert r.json() == {"error": "out of credits", "balance": 5}


def test_hero_run_requires_auth_in_supabase_mode(client):
    r = client.post("/api/hero/run", json={})
    assert r.status_code == 401


# ─── refund reaches the resumable flywheel's SECOND request (the advisor bug) ─
def test_approve_internal_failure_refunds_the_run(client, monkeypatch):
    client.get("/api/me", headers=_auth("alice"))
    _ground(client.stores["u_alice"])
    started = client.post("/api/hero/run", json={"idem_key": "run-2"}, headers=_auth("alice")).json()
    rid = started["flywheel"]["run_id"] if "flywheel" in started else started["run_id"]
    assert client.ledger.get_balance("u_alice") == 80

    import orchestrator

    async def boom(*a, **k):
        raise ValueError("kalai model died mid-approve")
    monkeypatch.setattr(orchestrator, "approve", boom)

    r = client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g1"}, headers=_auth("alice"))
    assert r.status_code == 200
    assert r.json()["refunded"] is True
    # the spend was returned — the founder is whole again
    assert client.ledger.get_balance("u_alice") == 100
    assert client.ledger.calls.count("saakshe_refund") == 1


# ─── run ownership (cross-tenant approval is a 404) ──────────────────────────
def test_cross_tenant_approve_is_404(client):
    client.get("/api/me", headers=_auth("alice"))
    client.get("/api/me", headers=_auth("mallory"))
    _ground(client.stores["u_alice"])
    started = client.post("/api/hero/run", json={"idem_key": "run-3"}, headers=_auth("alice")).json()
    rid = started["run_id"]
    # Mallory tries to advance Alice's run → must not exist for her.
    r = client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g1"}, headers=_auth("mallory"))
    assert r.status_code == 404
    # Alice's spend is untouched (no refund, no double charge).
    assert client.ledger.get_balance("u_alice") == 80


# ─── the real per-request binding + isolation (no mocked dependency) ─────────
def test_session_binds_each_users_own_store(client):
    client.get("/api/me", headers=_auth("alice"))
    client.get("/api/me", headers=_auth("bob"))
    client.stores["u_alice"].add_connection("website", "https://alice.example", {})
    client.stores["u_bob"].add_connection("github", "git@github.com:bob/b.git", {})

    a = client.get("/api/connect/status", headers=_auth("alice")).json()
    b = client.get("/api/connect/status", headers=_auth("bob")).json()
    assert [c["kind"] for c in a["connections"]] == ["website"]
    assert [c["kind"] for c in b["connections"]] == ["github"]
    # anonymous read in supabase mode is gated
    assert client.get("/api/connect/status").status_code == 401


def test_full_flywheel_debits_once_and_completes(client):
    client.get("/api/me", headers=_auth("alice"))
    _ground(client.stores["u_alice"])
    started = client.post("/api/hero/run", json={"idem_key": "run-4"}, headers=_auth("alice")).json()
    rid = started["run_id"]
    g1 = client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g1"}, headers=_auth("alice")).json()
    g2 = client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g2"}, headers=_auth("alice")).json()
    assert g1["open_gate"]["gate_id"] == "g2"
    assert g2["status"] == "completed"
    # billed exactly once across the three requests; no refund on success
    assert client.ledger.get_balance("u_alice") == 80
    assert client.ledger.calls.count("saakshe_spend") == 1
    assert client.ledger.calls.count("saakshe_refund") == 0
