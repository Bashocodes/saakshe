"""The witness chat transcript persists server-side — a closed tab must be able
to restore the conversation (and its render cards) from /api/saakshe/messages."""
from fastapi.testclient import TestClient

from common import project
from service.app import app

client = TestClient(app)


def test_ask_turns_land_in_the_transcript():
    r = client.post("/api/saakshe/ask", json={"text": "anyone waiting on me?"})
    assert r.status_code == 200
    rows = client.get("/api/saakshe/messages").json()["messages"]
    roles = [m["role"] for m in rows]
    assert "you" in roles and "saakshe/witness" in roles
    # the transcript is append-only across the suite — assert on the LATEST turns
    you = [m for m in rows if m["role"] == "you"][-1]
    assert you["text"] == "anyone waiting on me?"
    reply = [m for m in rows if m["role"] == "saakshe/witness"][-1]
    assert reply["meta"].get("blocks"), "reply blocks must persist for the restore"


def test_media_quote_turn_persists_with_its_blocks():
    r = client.post("/api/saakshe/ask", json={"text": "make hdr"})
    assert r.status_code == 200 and r.json()["kind"] == "media_quote"
    rows = client.get("/api/saakshe/messages").json()["messages"]
    router = [m for m in rows if m["role"] == "kalai/router"]
    assert router and router[-1]["meta"]["kind"] == "media_quote"
    assert router[-1]["meta"]["blocks"]


def test_file_store_transcript_roundtrip_and_tail():
    s = project.ProjectStore(user="chat_tester")
    for i in range(7):
        s.append_message("you", f"turn {i}")
    tail = s.get_messages(limit=3)
    assert [m["text"] for m in tail] == ["turn 4", "turn 5", "turn 6"]
