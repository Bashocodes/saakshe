"""saakshe.tests.test_supastream — guards the Supabase-persisted EventStream.

A fake PostgREST client (lists, minimal 'eq.'/'gte.' filter parsing) stands in for
common.supastore.SupabaseStore so the seq-per-run counter, the CRITICAL seed-once
behaviour, table-backed reads, and the gate mirror are exercised with zero network.
"""

from __future__ import annotations

import json

import pytest

from common.supastream import SupabaseEventStream


# ─── fake PostgREST client (mimics supastore._get/_insert/_patch over lists) ──
class FakeClient:
    """In-memory stand-in. _get values carry operator prefixes ('eq.x','gte.0');
    _insert/_patch take plain match values — mirroring the real supastore asymmetry."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.gates: list[dict] = []
        self._ins = 0                       # insertion counter → sortable created_at
        self.get_calls: list[dict] = []     # every _get param set (for the seed-once assertion)

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _match(row: dict, key: str, spec: str) -> bool:
        if "." not in spec:
            return str(row.get(key)) == spec
        op, val = spec.split(".", 1)
        cur = row.get(key)
        if op == "eq":
            return str(cur) == val
        if op == "gte":
            return cur is not None and float(cur) >= float(val)
        raise AssertionError(f"unsupported op {op!r} in fake")

    def _table(self, name: str) -> list[dict]:
        return self.events if name == "events" else self.gates

    # -- PostgREST surface --------------------------------------------------
    def _get(self, table: str, **params) -> list[dict]:
        self.get_calls.append({"table": table, **params})
        select = params.pop("select", None)
        order = params.pop("order", None)
        limit = params.pop("limit", None)
        rows = [
            dict(r) for r in self._table(table)
            if all(self._match(r, k, v) for k, v in params.items())
        ]
        if order:
            col, _, direction = order.partition(".")
            rows.sort(key=lambda r: r.get(col), reverse=(direction == "desc"))
        if limit is not None:
            rows = rows[: int(limit)]
        if select and select != "*":
            cols = [c.strip() for c in select.split(",")]
            rows = [{c: r.get(c) for c in cols} for r in rows]
        return rows

    def _insert(self, table: str, row: dict) -> dict:
        stored = dict(row)
        stored.setdefault("created_at", self._ins)
        if table == "gates":
            stored.setdefault("status", "open")  # DB default 'open' (supastore relies on it)
        self._ins += 1
        self._table(table).append(stored)
        return stored

    def _patch(self, table: str, match: dict, patch: dict) -> dict:
        out: dict = {}
        for r in self._table(table):
            if all(str(r.get(k)) == str(v) for k, v in match.items()):
                r.update(patch)
                out = dict(r)
        return out


@pytest.fixture
def stream() -> SupabaseEventStream:
    return SupabaseEventStream("founder", client=FakeClient())


# ─── per-run seq counter ──────────────────────────────────────────────────────
def test_seq_is_local_and_per_run(stream):
    e0 = stream.emit("r1", "manas", "scribe", "first")
    e1 = stream.emit("r1", "manas", "scribe", "second")
    assert (e0.seq, e1.seq) == (0, 1)

    # an independent run restarts at 0
    e2 = stream.emit("r2", "kalai", "maker", "other run")
    assert e2.seq == 0


def test_seed_max_seq_is_queried_once_per_unseen_run(stream):
    """CRITICAL: do NOT SELECT max(seq) on every emit — only once per unseen run."""
    client = stream.client
    for _ in range(4):
        stream.emit("r1", "manas", "scribe", "tick")
    stream.emit("r2", "kalai", "maker", "tick")

    seed_gets = [
        c for c in client.get_calls
        if c["table"] == "events" and c.get("order") == "seq.desc"
    ]
    runs = sorted(c["run_id"] for c in seed_gets)
    assert runs == ["eq.r1", "eq.r2"]          # exactly one seed query per run, no more


def test_seed_resumes_from_existing_rows(stream):
    """An unseen run seeds its counter from max(seq) of rows already in the table."""
    client = stream.client
    client.events.append({"run_id": "r9", "seq": 7, "source": "manas",
                          "agent": "a", "span": "agent_run", "kind": "span_end",
                          "text": "old", "meta": {}, "ts": 1.0})
    ev = stream.emit("r9", "manas", "scribe", "resumed")
    assert ev.seq == 8


# ─── persistence (insert lands in the events table) ──────────────────────────
def test_emit_inserts_event_row(stream):
    stream.emit("r1", "manas", "scribe", "hello", span="call_llm", kind="note", k="v")
    rows = stream.client.events
    assert len(rows) == 1
    r = rows[0]
    assert r["run_id"] == "r1" and r["seq"] == 0
    assert r["source"] == "manas" and r["agent"] == "scribe"
    assert r["span"] == "call_llm" and r["kind"] == "note"
    assert r["text"] == "hello" and r["meta"] == {"k": "v"}


# ─── reads come from the table ───────────────────────────────────────────────
def test_rows_returns_table_rows_in_seq_order(stream):
    stream.emit("r1", "manas", "scribe", "a", x=1)
    stream.emit("r1", "manas", "scribe", "b", x=2)
    stream.emit("r2", "kalai", "maker", "c")

    rows = stream.rows(0)
    r1 = [r for r in rows if r["run_id"] == "r1"]
    assert [r["seq"] for r in r1] == [0, 1]
    assert [r["text"] for r in r1] == ["a", "b"]
    assert [r["meta"]["x"] for r in r1] == [1, 2]
    assert isinstance(r1[0], dict)


def test_rows_honours_cursor(stream):
    stream.emit("r1", "manas", "scribe", "a")
    stream.emit("r1", "manas", "scribe", "b")
    later = stream.rows(1)
    assert all(r["seq"] >= 1 for r in later)
    assert {r["text"] for r in later} == {"b"}


def test_since_returns_event_objects(stream):
    stream.emit("r1", "manas", "scribe", "a")
    stream.emit("r1", "manas", "scribe", "b")
    evs = stream.since(0)
    assert [e.seq for e in evs] == [0, 1]
    assert evs[0].text == "a"
    # Event objects, not dicts
    assert hasattr(evs[0], "as_row")


def test_meta_jsonb_string_is_coerced(stream):
    """A DB that hands back jsonb meta as a STRING must be coerced to a dict."""
    client = stream.client
    client.events.append({"run_id": "r1", "seq": 0, "source": "manas", "agent": "a",
                          "span": "agent_run", "kind": "note", "text": "raw",
                          "meta": json.dumps({"k": 9}), "ts": 1.0})
    rows = stream.rows(0)
    assert rows[0]["meta"] == {"k": 9}
    evs = stream.since(0)
    assert evs[0].meta == {"k": 9}


def test_meta_null_becomes_empty_dict(stream):
    client = stream.client
    client.events.append({"run_id": "r1", "seq": 0, "source": "manas", "agent": "a",
                          "span": "agent_run", "kind": "note", "text": "raw",
                          "meta": None, "ts": 1.0})
    assert stream.rows(0)[0]["meta"] == {}


# ─── cursor ──────────────────────────────────────────────────────────────────
def test_cursor_is_max_seq_seen(stream):
    assert stream.cursor == 0
    stream.emit("r1", "manas", "scribe", "a")
    stream.emit("r1", "manas", "scribe", "b")
    stream.emit("r2", "kalai", "maker", "c")
    # next-seq for r1 is 2, for r2 is 1 → max 2
    assert stream.cursor == 2


# ─── the gate queue (table-backed, not stream-derived) ───────────────────────
def test_gate_mirrors_into_gates_table_and_event_stream(stream):
    ev = stream.gate("r1", "manas", "scribe", "g1", "ship the price change",
                     gate_kind="decision", reversible=False, note="hi")
    # event row landed
    assert any(r["kind"] == "gate" and r["meta"].get("gate_id") == "g1"
               for r in stream.client.events)
    assert ev.run_id == "r1"
    # gates table row landed, quadrant ← source, status defaults open
    g = stream.client.gates
    assert len(g) == 1
    assert g[0]["gate_id"] == "g1" and g[0]["quadrant"] == "manas"
    assert g[0]["proposal"] == "ship the price change"
    assert g[0]["reversible"] is False and g[0]["status"] == "open"


def test_open_gates_then_resolve(stream):
    stream.gate("r1", "manas", "scribe", "g1", "ship it",
                gate_kind="decision", reversible=True)
    opens = stream.open_gates("r1")
    assert [g["gate_id"] for g in opens] == ["g1"]

    stream.resolve_gate("r1", "g1", "approved")
    assert stream.open_gates("r1") == []
    # the resolution event row also landed in the stream
    assert any(r["kind"] == "action" and r["meta"].get("gate_id") == "g1"
               for r in stream.client.events)
    # gate table row now reflects the decision
    assert stream.client.gates[0]["status"] == "approved"


def test_open_gates_all_runs_when_run_id_none(stream):
    stream.gate("r1", "manas", "scribe", "g1", "a", gate_kind="decision", reversible=True)
    stream.gate("r2", "kalai", "maker", "g2", "b", gate_kind="publish", reversible=True)
    assert {g["gate_id"] for g in stream.open_gates()} == {"g1", "g2"}


# ─── inherited helpers persist through the overridden emit ───────────────────
def test_a2a_and_action_persist_event_rows(stream):
    stream.action("r1", "kalai", "maker", "made the asset", asset="x")
    stream.a2a("r1", "manas", "kural", "draft the post")
    kinds = [(r["kind"], r["text"]) for r in stream.client.events]
    assert ("action", "made the asset") in kinds
    assert any(k == "a2a" for k, _ in kinds)
    # both carried real seqs in run r1
    seqs = sorted(r["seq"] for r in stream.client.events)
    assert seqs == [0, 1]


def test_emit_transcript_persists_note_rows(stream):
    stream.emit_transcript("r1", "manas", [{"actor": "scribe", "text": "line one"},
                                           {"actor": "scribe", "text": "line two"}])
    notes = [r for r in stream.client.events if r["kind"] == "note"]
    assert [r["text"] for r in notes] == ["line one", "line two"]
    assert [r["seq"] for r in notes] == [0, 1]
