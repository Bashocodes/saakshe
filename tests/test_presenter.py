"""presenter — formats replies into blocks; never authors content."""
from fastapi.testclient import TestClient

from service import presenter
from service.app import app

client = TestClient(app)


def test_witness_reply_becomes_text_block():
    blocks = presenter.to_blocks({"kind": "witness", "text": "hello", "pills": ["a", "b"]})
    assert blocks[0] == {"t": "text", "who": "saakshe/witness", "md": "hello"}
    assert blocks[1]["t"] == "data" and len(blocks[1]["rows"]) == 2


def test_media_intent_detected():
    mi = presenter.media_intent("make my image an hdr video, budget $1")
    assert mi == {"is_media": True, "budget_usd": 1.0, "wants_hdr": True}
    assert presenter.media_intent("what changed yesterday?")["is_media"] is False


def test_quote_becomes_blocks():
    q = {"path": "B", "seconds": 4, "total_usd": 0.027, "budget_usd": 1.0,
         "fits_budget": True, "est_wall_sec": 58, "rationale": "source exists",
         "lines": [{"item": "render_cpu", "usd": 0.027}]}
    blocks = presenter.quote_blocks(q)
    assert [b["t"] for b in blocks] == ["text", "data", "slider", "actions"]
    assert blocks[2]["max"] == 8


def test_refusal_blocks_show_counter_offer():
    q = {"path": "B", "seconds": 8, "total_usd": 0.07, "budget_usd": 0.01,
         "fits_budget": False, "est_wall_sec": 100, "rationale": "r",
         "lines": [], "counter_offer": {"seconds": 1, "total_usd": 0.009}}
    blocks = presenter.quote_blocks(q)
    labels = [i["label"] for b in blocks if b["t"] == "actions" for i in b["items"]]
    assert any("1s" in l for l in labels)


def test_ask_returns_blocks():
    r = client.post("/api/saakshe/ask", json={"text": "hello there"})
    assert "blocks" in r.json()


def test_ask_media_question_returns_quote_blocks():
    r = client.post("/api/saakshe/ask",
                    json={"text": "make my image an HDR video, budget $1"})
    d = r.json()
    assert d["kind"] == "media_quote"
    assert any(b["t"] == "slider" for b in d["blocks"])
