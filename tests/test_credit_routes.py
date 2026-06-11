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
from common.pending import PendingChanges
from common.stream import EventStream


class PendFake:
    """In-memory pending_changes table (eq. matching) for the route tests."""
    def __init__(self) -> None:
        self.rows: list[dict] = []; self._id = 0

    def _get(self, table, **p):
        p.pop("select", None); p.pop("order", None); lim = p.pop("limit", None)
        out = [dict(r) for r in self.rows
               if all(str(r.get(k)).lower() == str(v).split(".", 1)[1].lower() for k, v in p.items())]
        return out[: int(lim)] if lim else out

    def _insert(self, table, row):
        self._id += 1
        r = dict(row); r["id"] = str(self._id); r["created_at"] = self._id; r.setdefault("applied_at", None)
        self.rows.append(r); return r

    def _patch(self, table, match, patch):
        out = {}
        for r in self.rows:
            if all(str(r.get(k)) == str(v) for k, v in match.items()):
                r.update(patch); out = dict(r)
        return out


# ─── an in-memory credit ledger standing in for the Postgres RPCs ─────────────
class Ledger:
    def __init__(self) -> None:
        self.bal: dict[str, int] = {}
        self.calls: list[str] = []
        self.spends: list[dict] = []          # every spend's params, for key assertions
        self.claimed: set[tuple[str, str]] = set()  # (user, idem_key) — mirrors the SQL claim

    def rpc(self, fn: str, params: dict) -> int:
        self.calls.append(fn)
        u = params["p_user_id"]
        if fn == "saakshe_grant_signup":
            self.bal.setdefault(u, params["p_grant"])
            return self.bal[u]
        if fn == "saakshe_spend":
            self.spends.append(dict(params))
            # claim-first idempotency, like the real saakshe_spend: a replayed
            # key short-circuits to the current balance — no second charge.
            if (u, params["p_idem_key"]) in self.claimed:
                return self.bal.get(u, 0)
            cur = self.bal.get(u, 0)
            if cur < params["p_amount"]:
                raise credits.CreditError("INSUFFICIENT_CREDITS", code="P0001")
            self.claimed.add((u, params["p_idem_key"]))
            self.bal[u] = cur - params["p_amount"]
            return self.bal[u]
        if fn == "saakshe_refund":
            # release the spend claim (the SQL renames it) so a real retry re-charges
            self.claimed.discard((u, params.get("p_spend_idem_key", "")))
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

    pend = PendFake()
    monkeypatch.setattr(appmod, "_pending_factory", lambda uid: PendingChanges(uid, client=pend))

    c = TestClient(appmod.app)
    c.ledger = ledger          # type: ignore[attr-defined]
    c.stores = stores          # type: ignore[attr-defined]
    c.pend = pend              # type: ignore[attr-defined]
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
    assert body["balance"] == credits.SIGNUP_GRANT        # first touch granted SIGNUP_GRANT
    assert "saakshe_grant_signup" in client.ledger.calls


def test_me_401_when_anonymous(client):
    assert client.get("/api/me").status_code == 401


def test_me_401_on_bad_token(client):
    assert client.get("/api/me", headers={"Authorization": "Bearer bad"}).status_code == 401


# ─── the flywheel debit ───────────────────────────────────────────────────────
def test_hero_run_debits_flywheel_cost(client):
    client.get("/api/me", headers=_auth("alice"))          # signup grant
    _ground(client.stores["u_alice"])
    r = client.post("/api/hero/run", json={"idem_key": "run-1"}, headers=_auth("alice"))
    assert r.status_code == 200
    assert r.json()["status"] == "awaiting_approval"
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT - credits.cost("flywheel_run")


def test_hero_run_402_when_out_of_credits(client):
    client.get("/api/me", headers=_auth("broke"))
    client.ledger.bal["u_broke"] = 0                       # less than the run cost
    _ground(client.stores["u_broke"])
    r = client.post("/api/hero/run", json={"idem_key": "run-x"}, headers=_auth("broke"))
    assert r.status_code == 402
    assert r.json() == {"error": "out of credits", "balance": 0}


def test_hero_run_requires_auth_in_supabase_mode(client):
    r = client.post("/api/hero/run", json={})
    assert r.status_code == 401


# ─── refund reaches the resumable flywheel's SECOND request (the advisor bug) ─
def test_approve_internal_failure_refunds_the_run(client, monkeypatch):
    client.get("/api/me", headers=_auth("alice"))
    _ground(client.stores["u_alice"])
    started = client.post("/api/hero/run", json={"idem_key": "run-2"}, headers=_auth("alice")).json()
    rid = started["flywheel"]["run_id"] if "flywheel" in started else started["run_id"]
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT - credits.cost("flywheel_run")

    import orchestrator

    async def boom(*a, **k):
        raise ValueError("kalai model died mid-approve")
    monkeypatch.setattr(orchestrator, "approve", boom)

    r = client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g1"}, headers=_auth("alice"))
    assert r.status_code == 200
    assert r.json()["refunded"] is True
    # the spend was returned — the founder is whole again
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT
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
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT - credits.cost("flywheel_run")


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


# ─── manas live-edits → charged, immutable pending changes ───────────────────
def test_manas_edit_charges_and_persists(client):
    client.get("/api/me", headers=_auth("alice"))
    r = client.post("/api/manas/edit", headers=_auth("alice"), json={
        "entity_type": "company_profile", "instruction": "warmer tagline",
        "target": {"tagline": "We sell software"}, "idem_key": "edit-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is True
    assert body["pending"]["status"] == "pending"
    assert body["pending"]["changed_fields"] == ["tagline"]
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT - credits.cost("manas_edit")


def test_manas_reject_refunds_the_edit(client):
    client.get("/api/me", headers=_auth("alice"))
    pid = client.post("/api/manas/edit", headers=_auth("alice"), json={
        "instruction": "x", "target": {"tagline": "t"}, "idem_key": "edit-2"}).json()["pending"]["id"]
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT - credits.cost("manas_edit")
    r = client.post(f"/api/manas/pending/{pid}/reject", headers=_auth("alice"))
    assert r.json()["refunded"] is True
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT
    # applying after reject is a no-op (status no longer pending)
    client.post(f"/api/manas/pending/{pid}/apply", headers=_auth("alice"))
    assert client.pend.rows[0]["status"] == "rejected"


def test_manas_edit_is_owner_scoped(client):
    client.get("/api/me", headers=_auth("alice"))
    pid = client.post("/api/manas/edit", headers=_auth("alice"), json={
        "instruction": "x", "target": {"tagline": "t"}, "idem_key": "edit-3"}).json()["pending"]["id"]
    client.get("/api/me", headers=_auth("mallory"))
    # Mallory can't see or apply Alice's pending change
    assert client.get("/api/manas/pending", headers=_auth("mallory")).json()["pending"] == []
    assert client.post(f"/api/manas/pending/{pid}/apply", headers=_auth("mallory")).status_code == 404


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
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT - credits.cost("flywheel_run")
    assert client.ledger.calls.count("saakshe_spend") == 1
    assert client.ledger.calls.count("saakshe_refund") == 0


# ─── the witness chat turn debit (everyone-access pricing, 2026-06-11) ───────
def test_ask_debits_one_credit(client):
    client.get("/api/me", headers=_auth("alice"))
    r = client.post("/api/saakshe/ask", json={"text": "anyone waiting on me?"},
                    headers=_auth("alice"))
    assert r.status_code == 200
    assert client.ledger.get_balance("u_alice") == \
        credits.SIGNUP_GRANT - credits.cost("saakshe_ask")


def test_ask_402_when_out_of_credits(client):
    client.get("/api/me", headers=_auth("broke"))
    client.ledger.bal["u_broke"] = 0
    r = client.post("/api/saakshe/ask", json={"text": "anyone waiting on me?"},
                    headers=_auth("broke"))
    assert r.status_code == 402
    assert r.json()["error"] == "out of credits"


# ─── server-side idem-key namespacing (the cross-route collision fix) ─────────
def test_spend_keys_are_server_namespaced(client):
    """The server, not the client, owns the spend-key namespace: hero runs land
    under run:, manas edits under edit: — a client key can't pick its prefix."""
    client.get("/api/me", headers=_auth("alice"))
    _ground(client.stores["u_alice"])
    client.post("/api/hero/run", json={"idem_key": "k1"}, headers=_auth("alice"))
    client.post("/api/manas/edit",
                json={"instruction": "punchier", "target": {"tagline": "old"}, "idem_key": "k2"},
                headers=_auth("alice"))
    keys = [p["p_idem_key"] for p in client.ledger.spends]
    assert "run:k1" in keys and "edit:k2" in keys


def test_crafted_run_key_cannot_preclaim_the_grasp_spend(client, monkeypatch):
    """The 100-for-1 exploit: a 1-credit run squatting on 'ingest:<k>' must NOT
    make the later 100-credit grasp replay free."""
    import service.app as appmod
    client.get("/api/me", headers=_auth("alice"))
    _ground(client.stores["u_alice"])
    client.post("/api/hero/run", json={"idem_key": "ingest:steal"}, headers=_auth("alice"))
    after_run = client.ledger.get_balance("u_alice")

    async def fake_ingest(stream, run_id, store):
        return {"status": "ok", "facts": 3}
    monkeypatch.setattr(appmod.manas_runner, "ingest_connected", fake_ingest)
    r = client.post("/api/connect/ingest", json={"idem_key": "steal"}, headers=_auth("alice"))
    assert r.status_code == 200
    assert client.ledger.get_balance("u_alice") == after_run - credits.cost("connect_ingest")


# ─── kalai render bills kalai_make (priced-but-never-charged fix) ─────────────
def _render_and_wait(client, monkeypatch, render_fn):
    import time

    import service.app as appmod
    monkeypatch.setattr(appmod.media_pipeline, "render", render_fn)
    r = client.post("/api/kalai/media/render",
                    files={"image": ("a.png", b"\x89PNGfake", "image/png")},
                    data={"fx": "sat_sort"}, headers=_auth("alice"))
    if r.status_code != 200:
        return r, None
    jid = r.json()["job_id"]
    for _ in range(200):
        job = client.get(f"/api/kalai/media/job/{jid}", headers=_auth("alice")).json()
        if job["status"] != "rendering":
            return r, job
        time.sleep(0.01)
    raise AssertionError("render job never finished")


def test_media_render_debits_kalai_make(client, monkeypatch):
    client.get("/api/me", headers=_auth("alice"))
    r, job = _render_and_wait(client, monkeypatch, lambda **kw: {
        "out_path": kw["out_path"], "verify": {"ok": True}, "vcpu_sec_estimate": 1.0})
    assert r.status_code == 200 and job["status"] == "done"
    assert client.ledger.get_balance("u_alice") == \
        credits.SIGNUP_GRANT - credits.cost("kalai_make")


def test_media_render_refunds_when_the_job_fails(client, monkeypatch):
    def boom(**kw):
        raise RuntimeError("render died")
    client.get("/api/me", headers=_auth("alice"))
    r, job = _render_and_wait(client, monkeypatch, boom)
    assert r.status_code == 200 and job["status"] == "error"
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT
    assert "saakshe_refund" in client.ledger.calls


def test_media_render_402_when_out_of_credits(client, monkeypatch):
    client.get("/api/me", headers=_auth("alice"))
    client.ledger.bal["u_alice"] = 0
    r, _ = _render_and_wait(client, monkeypatch, lambda **kw: {})
    assert r.status_code == 402
    assert r.json()["error"] == "out of credits"


# ─── kural engage bills the ARMED publish tap only ────────────────────────────
def _arm_live_send(monkeypatch):
    from kural.tools import channels
    monkeypatch.setenv("SAAKSHE_ALLOW_LIVE_SEND", "1")
    monkeypatch.setenv("SAAKSHE_CHANNEL_WEBHOOK_URL", "https://example.com/intake")
    monkeypatch.setattr(channels, "_channel_call", lambda action, args: {"ok": True})


def test_armed_publish_tap_debits_kural_engage(client, monkeypatch):
    _arm_live_send(monkeypatch)
    client.get("/api/me", headers=_auth("alice"))
    _ground(client.stores["u_alice"])
    rid = client.post("/api/hero/run", json={"idem_key": "run-e"}, headers=_auth("alice")).json()["run_id"]
    client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g1"}, headers=_auth("alice"))
    g2 = client.post("/api/hero/approve",
                     json={"run_id": rid, "gate_id": "g2", "arm_real_send": True},
                     headers=_auth("alice")).json()
    assert g2["status"] == "completed"
    assert client.ledger.get_balance("u_alice") == \
        credits.SIGNUP_GRANT - credits.cost("flywheel_run") - credits.cost("kural_engage")


def test_unarmed_approve_never_debits_engage(client, monkeypatch):
    _arm_live_send(monkeypatch)   # deploy CAN send — but the founder didn't arm the tap
    client.get("/api/me", headers=_auth("alice"))
    _ground(client.stores["u_alice"])
    rid = client.post("/api/hero/run", json={"idem_key": "run-u"}, headers=_auth("alice")).json()["run_id"]
    client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g1"}, headers=_auth("alice"))
    client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g2"}, headers=_auth("alice"))
    assert client.ledger.get_balance("u_alice") == \
        credits.SIGNUP_GRANT - credits.cost("flywheel_run")


def test_armed_tap_on_sendless_deploy_is_free(client):
    """No env / no channel client → the publish dry-runs → no engage charge."""
    client.get("/api/me", headers=_auth("alice"))
    _ground(client.stores["u_alice"])
    rid = client.post("/api/hero/run", json={"idem_key": "run-d"}, headers=_auth("alice")).json()["run_id"]
    client.post("/api/hero/approve", json={"run_id": rid, "gate_id": "g1"}, headers=_auth("alice"))
    client.post("/api/hero/approve",
                json={"run_id": rid, "gate_id": "g2", "arm_real_send": True},
                headers=_auth("alice"))
    assert client.ledger.get_balance("u_alice") == \
        credits.SIGNUP_GRANT - credits.cost("flywheel_run")


# ─── profile point-and-edit bills one credit ──────────────────────────────────
def test_profile_edit_debits_one_credit(client, monkeypatch):
    import service.app as appmod
    from common import config
    monkeypatch.setattr(config, "is_live", lambda: True)
    monkeypatch.setattr(appmod, "_profile_edit_llm", lambda prompt: "Sharper tagline.",
                        raising=False)
    client.get("/api/me", headers=_auth("alice"))
    r = client.post("/api/profile/edit",
                    json={"label": "Tagline", "current_text": "old", "instruction": "sharper",
                          "provenance": "README"},
                    headers=_auth("alice"))
    assert r.status_code == 200 and r.json()["text"] == "Sharper tagline."
    assert client.ledger.get_balance("u_alice") == \
        credits.SIGNUP_GRANT - credits.cost("profile_edit")


def test_profile_edit_refunds_when_the_model_dies(client, monkeypatch):
    import service.app as appmod
    from common import config
    monkeypatch.setattr(config, "is_live", lambda: True)

    def boom(prompt):
        raise RuntimeError("vertex down")
    monkeypatch.setattr(appmod, "_profile_edit_llm", boom, raising=False)
    client.get("/api/me", headers=_auth("alice"))
    r = client.post("/api/profile/edit",
                    json={"label": "Tagline", "current_text": "old", "instruction": "sharper"},
                    headers=_auth("alice"))
    assert r.status_code == 502
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT


# ─── empty-start interview costs 1, not the 100-credit grasp ─────────────────
def test_empty_start_ingest_charges_interview_not_grasp(client, monkeypatch):
    import service.app as appmod
    client.get("/api/me", headers=_auth("alice"))   # no _ground → zero connections

    async def fake_interview(stream, run_id, store):
        return {"status": "NEEDS_ANSWERS", "questions": ["what do you sell?"]}
    monkeypatch.setattr(appmod.manas_runner, "ingest_connected", fake_interview)
    r = client.post("/api/connect/ingest", json={"idem_key": "i1"}, headers=_auth("alice"))
    assert r.status_code == 200
    assert client.ledger.get_balance("u_alice") == credits.SIGNUP_GRANT - 1


# ─── voice turns bill like chat turns ─────────────────────────────────────────
def test_voice_text_turn_debits_one_credit(client):
    import json as _json
    client.get("/api/me", headers=_auth("alice"))
    with client.websocket_connect("/ws/voice?token=tok_alice") as ws:
        hello = _json.loads(ws.receive_text())
        assert hello["type"] == "hello"
        ws.send_text(_json.dumps({"type": "text", "text": "anyone waiting on me?"}))
        reply = _json.loads(ws.receive_text())
    assert reply["type"] == "reply"
    assert client.ledger.get_balance("u_alice") == \
        credits.SIGNUP_GRANT - credits.cost("voice_turn")


def test_voice_turn_out_of_credits_sends_error_frame(client):
    import json as _json
    client.get("/api/me", headers=_auth("broke"))
    client.ledger.bal["u_broke"] = 0
    with client.websocket_connect("/ws/voice?token=tok_broke") as ws:
        _json.loads(ws.receive_text())          # hello
        ws.send_text(_json.dumps({"type": "text", "text": "anyone waiting?"}))
        frame = _json.loads(ws.receive_text())
    assert frame["type"] == "error" and frame["error"] == "out of credits"


# ─── manas edit bills on the file-store gated profile too ────────────────────
@pytest.fixture
def gated_client(monkeypatch):
    """The GATED prod shape: file store (no SAAKSHE_STORE=supabase), billing
    armed via SAAKSHE_BILLING=1, Supabase auth configured."""
    import service.app as appmod

    monkeypatch.delenv("SAAKSHE_STORE", raising=False)
    monkeypatch.setenv("SAAKSHE_BILLING", "1")
    monkeypatch.setenv("SAAKSHE_SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.delenv("OWNER_EMAILS", raising=False)

    def fake_verify(token: str) -> dict:
        uid = token.replace("tok_", "u_")
        return {"sub": uid, "email": f"{uid}@example.com", "aud": "authenticated"}
    monkeypatch.setattr(auth, "verify_token", fake_verify)

    stores: dict[str, project.ProjectStore] = {}

    def fake_store_for(uid: str):
        s = stores.get(uid)
        if s is None:
            s = project.ProjectStore(user=uid)
            s.reset()
            stores[uid] = s
        return s
    monkeypatch.setattr(project, "store_for", fake_store_for)

    ledger = Ledger()
    monkeypatch.setattr(credits, "_rpc", ledger.rpc)
    monkeypatch.setattr(credits, "_get_balance", ledger.get_balance)
    appmod._GRANTED.clear()

    pend = PendFake()
    monkeypatch.setattr(appmod, "_pending_factory", lambda uid: PendingChanges(uid, client=pend))

    c = TestClient(appmod.app)
    c.ledger = ledger          # type: ignore[attr-defined]
    c.pend = pend              # type: ignore[attr-defined]
    return c


def test_manas_edit_bills_and_persists_on_gated_filestore(gated_client):
    gated_client.get("/api/me", headers=_auth("alice"))
    r = gated_client.post("/api/manas/edit",
                          json={"instruction": "warmer", "target": {"tagline": "old"},
                                "idem_key": "ge1"},
                          headers=_auth("alice"))
    assert r.status_code == 200
    assert r.json()["persisted"] is True
    assert gated_client.ledger.get_balance("u_alice") == \
        credits.SIGNUP_GRANT - credits.cost("manas_edit")
    assert len(gated_client.pend.rows) == 1
