"""The staff register — 42 agents · 4 realms; the witness above, never among."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from common import agents, config
from service.app import app

client = TestClient(app)


def test_the_staff_is_exactly_42():
    assert len(agents.AGENTS) == 42


def test_realm_counts():
    realms = agents.by_realm()
    assert {k: len(v) for k, v in realms.items()} == {
        "manas": 10, "arivu": 10, "kalai": 11, "kural": 11}


def test_ids_and_callsigns_unique():
    assert len({a["id"] for a in agents.AGENTS}) == 42
    assert len({a["call"] for a in agents.AGENTS}) == 42


def test_names_two_words_max_and_not_forbidden():
    forbidden = set(config.FORBIDDEN["names"])
    for a in agents.AGENTS + [agents.WITNESS] + agents.BENCHED:
        assert len(a["name"].split()) <= 2, a["name"]
        assert a["name"].lower() not in forbidden, a["name"]


def test_types_within_taxonomy():
    for a in agents.AGENTS:
        assert a["type"] in ("orchestrator", "action", "verifier", "keeper"), a["id"]


def test_witness_stands_above_not_among():
    assert agents.WITNESS["id"] not in {a["id"] for a in agents.AGENTS}
    payload = agents.as_payload()
    assert payload["total"] == 42
    assert payload["witness"]["name"] == "saakshe"


def test_payload_is_json_and_deterministic():
    a = json.dumps(agents.as_payload(), sort_keys=True)
    b = json.dumps(agents.as_payload(), sort_keys=True)
    assert a == b


def test_every_realm_has_an_orchestrator_and_a_verifier():
    for name, staff_list in agents.by_realm().items():
        types = {a["type"] for a in staff_list}
        assert "orchestrator" in types, name
        assert "verifier" in types, name


def test_endpoint_serves_the_register():
    r = client.get("/api/saakshe/agents")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 42
    assert set(d["realms"]) == {"manas", "arivu", "kalai", "kural"}
    assert d["realms"]["kalai"]["glyph"] == "▲"
    # benched stays visible but uncounted (Prahari sleeps, the vision doesn't)
    assert any(b["id"] == "prahari" for b in d["benched"])


def test_witness_followup_options_deterministic():
    from service import presenter
    blk = presenter.followup_options("what did today cost?")
    assert blk["t"] == "options"
    assert 1 <= len(blk["items"]) <= 3
    assert all("cost" not in i["label"] for i in blk["items"])
    assert blk == presenter.followup_options("what did today cost?")


def test_ask_reply_carries_options_block():
    r = client.post("/api/saakshe/ask", json={"text": "hello there"})
    blocks = r.json()["blocks"]
    assert blocks[-1]["t"] == "options"
    assert all({"label", "send"} <= set(i) for i in blocks[-1]["items"])
