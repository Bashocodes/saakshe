"""saakshe.common.supastream — the ONE ordered event stream, persisted in Supabase.

A drop-in subclass of :class:`common.stream.EventStream` whose rows live in the
``saakshe.events`` Postgres table (and whose gate queue lives in ``saakshe.gates``)
instead of an in-process list. The row shape is identical to the in-memory stream
and to the BigQuery ``agent_events`` mirror, so a surface (cockpit feed, gate queue,
the witness's telemetry tools) is the same pure render of (stream, cursor) whether
the company runs file-backed/in-memory or Supabase-backed — live is a flag, not a
rewrite.

WHY a subclass and not a method on SupabaseStore: the orchestrator and the witness
already speak the EventStream surface (emit/gate/resolve_gate/action/a2a/since/rows/
open_gates/cursor). Subclassing keeps every inherited helper (action, a2a,
emit_transcript, cost_today) working unchanged — they all funnel through ``emit``,
so overriding ``emit`` to INSERT a row is enough to make them persist.

SEQ ORDERING is authoritative and append-only: ``seq`` is assigned LOCALLY from a
per-instance, per-run counter so concurrent appends never collide and we never pay
a round-trip to learn the next number. The counter is seeded ONCE per unseen run
from ``max(seq)`` of any rows already in the table (so a fresh process resumes a
run mid-flight); after that it is purely in-memory. Reads always come from the
table (``order='seq.asc'``) so any persisted row — including ones written by another
process — is visible.

CLIENT: anything exposing the PostgREST trio ``_get(table, **params)`` /
``_insert(table, row)`` / ``_patch(table, match, patch)`` — by default a
``supastore.SupabaseStore(user_id)`` (the service-role backend); in tests a fake is
injected. The ``_get`` param VALUES carry operator prefixes ('eq.x', 'gte.0');
``_patch`` match VALUES are plain — matching the real supastore asymmetry.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from common.stream import Event, EventStream

_EVENT_COLUMNS = ("run_id", "seq", "source", "agent", "span", "kind", "text", "meta")


def _coerce_meta(raw: Any) -> dict[str, Any]:
    """jsonb may arrive as a dict (already parsed) or a JSON string, or be NULL."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _row_to_event(row: dict) -> Event:
    return Event(
        seq=int(row.get("seq", 0)),
        ts=float(row.get("ts") or 0.0),
        run_id=str(row.get("run_id", "")),
        source=str(row.get("source", "")),
        agent=str(row.get("agent", "")),
        span=str(row.get("span", "agent_run")),
        kind=str(row.get("kind", "note")),
        text=str(row.get("text", "")),
        meta=_coerce_meta(row.get("meta")),
    )


class SupabaseEventStream(EventStream):
    """An :class:`EventStream` whose append/read/gate operations hit Supabase.

    Per-instance state is only the seq bookkeeping: ``_next_seq[run_id]`` is the
    next seq to assign for that run, seeded once from the table. Everything else
    (the events, the gate queue) is the table's responsibility.
    """

    def __init__(self, user_id: str, client: Optional[Any] = None) -> None:
        super().__init__()  # base cost_today() reads self._events; keep it present
        self.user_id = user_id
        if client is not None:
            self.client = client
        else:  # import lazily so tests never construct the real (network) store
            from common import supastore

            self.client = supastore.SupabaseStore(user_id)
        self._next_seq: dict[str, int] = {}

    # ── seq bookkeeping ──────────────────────────────────────────────────────
    def _seq_for(self, run_id: str) -> int:
        """Next seq for ``run_id``. Seeds ONCE per unseen run from the table's
        current max(seq) (default -1, +1 → 0 for a brand-new run). CRITICAL: this
        SELECT happens at most once per run_id, never on every emit."""
        if run_id not in self._next_seq:
            rows = self.client._get(
                "events", user_id=f"eq.{self.user_id}", run_id=f"eq.{run_id}",
                select="seq", order="seq.desc", limit=1,
            )
            last = int(rows[0]["seq"]) if rows else -1
            self._next_seq[run_id] = last + 1
        return self._next_seq[run_id]

    # ── append (every inherited helper funnels through here) ─────────────────
    def emit(
        self,
        run_id: str,
        source: str,
        agent: str,
        text: str,
        *,
        span: str = "agent_run",
        kind: str = "span_end",
        **meta: Any,
    ) -> Event:
        seq = self._seq_for(run_id)
        ev = Event(
            seq=seq,
            ts=time.time(),
            run_id=run_id,
            source=source,
            agent=agent,
            span=span,
            kind=kind,
            text=text,
            meta=dict(meta),
        )
        row = ev.as_row()
        payload = {c: row[c] for c in _EVENT_COLUMNS}
        payload["user_id"] = self.user_id      # tenant stamp → reads are user-scoped
        self.client._insert("events", payload)
        self._next_seq[run_id] = seq + 1
        return ev

    # ── read (always from the table, scoped to THIS tenant) ──────────────────
    def _all_rows(self) -> list[dict]:
        return self.client._get(
            "events", user_id=f"eq.{self.user_id}", select="*", order="seq.asc",
        )

    def since(self, cursor: int = 0) -> list[Event]:
        return [_row_to_event(r) for r in self._all_rows() if int(r.get("seq", 0)) >= cursor]

    def all(self) -> list[Event]:
        return [_row_to_event(r) for r in self._all_rows()]

    def rows(self, cursor: int = 0) -> list[dict]:
        return [e.as_row() for e in self.since(cursor)]

    @property
    def cursor(self) -> int:
        """Max seq seen across the per-run counters (next-seq is last+1, so the
        max next-seq equals max(seq)+1 of the highest run, i.e. the cursor)."""
        return max(self._next_seq.values(), default=0)

    # ── the HITL gate queue (mirrored into the gates table) ──────────────────
    def gate(
        self,
        run_id: str,
        source: str,
        agent: str,
        gate_id: str,
        proposal: str,
        *,
        gate_kind: str,
        reversible: bool,
        **meta: Any,
    ) -> Event:
        ev = super().gate(
            run_id, source, agent, gate_id, proposal,
            gate_kind=gate_kind, reversible=reversible, **meta,
        )
        # mirror upsert_gate: quadrant ← source; status defaults to 'open' in the DB
        self.client._insert("gates", {
            "user_id": self.user_id,
            "run_id": run_id, "gate_id": gate_id, "quadrant": source, "agent": agent,
            "gate_kind": gate_kind, "proposal": proposal, "reversible": reversible,
            "detail": dict(meta),
        })
        return ev

    def resolve_gate(self, run_id: str, gate_id: str, decision: str = "approved") -> Event:
        ev = super().resolve_gate(run_id, gate_id, decision)
        # match includes user_id → a tenant can only resolve its own gate
        self.client._patch("gates",
                            {"user_id": self.user_id, "run_id": run_id, "gate_id": gate_id},
                            {"status": decision})
        return ev

    def open_gates(self, run_id: Optional[str] = None) -> list[dict]:
        """Unresolved gates, read from the gates TABLE (status='open') — not
        stream-derived. The persisted queue is the source of truth here, scoped
        to this tenant."""
        params: dict[str, Any] = {"user_id": f"eq.{self.user_id}",
                                  "status": "eq.open", "select": "*", "order": "created_at.asc"}
        if run_id:
            params["run_id"] = f"eq.{run_id}"
        return self.client._get("gates", **params)
