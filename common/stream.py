"""saakshe.common.stream — the ONE ordered event stream (CONTRACT 1).

Every surface — the cockpit constellation, the activity feed, the gate queue, the
witness's telemetry tools — is a pure render of (stream, cursor). The stream is a
single, append-only, ordered list of immutable events. In live mode these rows
land in BigQuery as ``agent_events`` (stamped by Agent Engine); in demo they live
in this in-process store. **The row shape is identical** so live is a flag, not a
rewrite.

Authentic vocabulary only (Cloud Trace / Agent Engine):
  * ``span`` ∈ {invocation, agent_run, call_llm, execute_tool}  — Cloud Trace span_name
  * ``kind`` ∈ {span_start, span_end, gate, action, a2a, note}  — agent_events event_type
A2A states are hyphenated (submitted, working, completed) per the A2A spec; token
usage is reported as ``input_tokens`` / ``output_tokens`` (gen_ai.usage.*).
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

SOURCES = ("saakshe", "manas", "arivu", "kalai", "kural")
SPANS = ("invocation", "agent_run", "call_llm", "execute_tool")
KINDS = ("span_start", "span_end", "gate", "action", "a2a", "note")


@dataclass(frozen=True)
class Event:
    """One immutable row in the ordered stream = one BigQuery ``agent_events`` row."""

    seq: int
    ts: float
    run_id: str
    source: str            # which of the five systems
    agent: str             # the seat / agent name
    span: str              # Cloud Trace span_name (invocation|agent_run|call_llm|execute_tool)
    kind: str              # agent_events event_type (span_start|span_end|gate|action|a2a|note)
    text: str              # human-readable line for the feed
    meta: dict[str, Any] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


class EventStream:
    """Append-only ordered event log + the derived gate queue.

    Mirrors the BigQuery ``agent_events`` table: rows are never mutated, only
    appended; the gate queue is *derived* (a gate is open until a matching
    resolution event arrives) so the queue can never desync from the stream.
    """

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._seq = 0

    # ── append ──────────────────────────────────────────────────────────────
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
        ev = Event(
            seq=self._seq,
            ts=time.time(),
            run_id=run_id,
            source=source,
            agent=agent,
            span=span,
            kind=kind,
            text=text,
            meta=dict(meta),
        )
        self._events.append(ev)
        self._seq += 1
        return ev

    def emit_transcript(self, run_id: str, source: str, transcript: list[dict]) -> None:
        """Translate a quadrant's human transcript into agent_events rows.

        Lets the orchestrator surface arivu's (untouched) transcript and any
        stub quadrant's lines into the one stream uniformly. Gate/action/a2a
        rows are emitted explicitly by the orchestrator, not from here.
        """
        for line in transcript:
            actor = str(line.get("actor", source))
            self.emit(run_id, source, actor, str(line.get("text", "")), kind="note")

    def gate(
        self,
        run_id: str,
        source: str,
        agent: str,
        gate_id: str,
        proposal: str,
        *,
        gate_kind: str,            # "decision" (tap 1 @ arivu) | "publish" (tap 2 @ kural)
        reversible: bool,
        **meta: Any,
    ) -> Event:
        return self.emit(
            run_id, source, agent,
            f"GATE — {proposal}",
            span="invocation", kind="gate",
            gate_id=gate_id, gate_kind=gate_kind, reversible=reversible,
            gate_state="open", **meta,
        )

    def resolve_gate(self, run_id: str, gate_id: str, decision: str = "approved") -> Event:
        return self.emit(
            run_id, "saakshe", "founder",
            f"the founder taps — {gate_id} {decision}",
            span="invocation", kind="action",
            gate_id=gate_id, gate_state=decision,
        )

    def action(self, run_id: str, source: str, agent: str, text: str, **meta: Any) -> Event:
        return self.emit(run_id, source, agent, text, span="execute_tool", kind="action", **meta)

    def a2a(self, run_id: str, source: str, target: str, command: str, state: str = "submitted", **meta: Any) -> Event:
        return self.emit(
            run_id, source, f"{source}→{target}",
            f"A2A {state}: {command}",
            span="execute_tool", kind="a2a",
            a2a_from=source, a2a_to=target, a2a_command=command, a2a_state=state, **meta,
        )

    # ── read (the only thing the witness + cockpit do) ───────────────────────
    def since(self, cursor: int) -> list[Event]:
        return [e for e in self._events if e.seq >= cursor]

    def all(self) -> list[Event]:
        return list(self._events)

    def rows(self, cursor: int = 0) -> list[dict]:
        return [e.as_row() for e in self._events if e.seq >= cursor]

    @property
    def cursor(self) -> int:
        return self._seq

    # ── derived: the gate queue (never stored, always computed) ──────────────
    def open_gates(self, run_id: Optional[str] = None) -> list[dict]:
        """Gates that have been raised but not yet resolved — derived from the
        stream so the queue can never desync. This backs saakshe's gate-queue
        surface and the witness's 'anyone waiting on me?' tool."""
        opened: dict[str, dict] = {}
        resolved: set[str] = set()
        for e in self._events:
            if run_id and e.run_id != run_id:
                continue
            gid = e.meta.get("gate_id")
            if not gid:
                continue
            if e.kind == "gate":
                opened[gid] = {
                    "gate_id": gid,
                    "run_id": e.run_id,
                    "source": e.source,
                    "agent": e.agent,
                    "proposal": e.text.removeprefix("GATE — "),
                    "gate_kind": e.meta.get("gate_kind"),
                    "reversible": e.meta.get("reversible"),
                    "seq": e.seq,
                    **{k: v for k, v in e.meta.items() if k not in ("gate_id", "gate_state")},
                }
            elif e.meta.get("gate_state") in ("approved", "rejected"):
                resolved.add(gid)
        return [g for gid, g in opened.items() if gid not in resolved]

    def cost_today(self, run_id: Optional[str] = None) -> dict:
        """Aggregate gen_ai.usage token cost across the stream (witness tool).

        Prefers AUTHORITATIVE usage events (real metered token counts from live
        ADK runs) when present; otherwise falls back to the per-seat estimates
        (demo). So the cockpit shows true spend live, a plausible number in demo.
        """
        rows = [e for e in self._events if not run_id or e.run_id == run_id]
        usage_evs = [e for e in rows if isinstance(e.meta.get("usage"), dict)]
        auth = [e for e in usage_evs if e.meta.get("auth")]
        src = auth if auth else usage_evs
        inp = out = calls = 0
        for e in src:
            u = e.meta["usage"]
            inp += int(u.get("input_tokens", 0) or 0)
            out += int(u.get("output_tokens", 0) or 0)
            calls += 1
        return {"input_tokens": inp, "output_tokens": out, "llm_calls": calls, "live_metered": bool(auth)}


# A single shared in-process stream for the running service. (Live mode would
# read agent_events from BigQuery instead; same rows, same readers.)
STREAM = EventStream()
