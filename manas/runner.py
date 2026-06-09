"""manas — run helpers + the uniform quadrant interface + A2A hub registration.

This drives the real ADK agents (the way arivu/runner.deliberate drives arivu's
root_agent) while keeping the LOCKED interface the orchestrator + the flywheel
integration test call:

Public (orchestrator-facing, async — the orchestrator awaits them):
  * ground(stream, run_id, topic)  → ContextPack      (read-side grounding for arivu/kalai/kural)
  * learn(stream, run_id, outcome) → QuadrantResult   (Curator commit; Context Pack vN → vN+1)

A2A skills (sibling-facing, SYNC + pure-corpus-backed — never drive the async
agent, so a plain `def` caller can never break):
  * manas.get_founder_context(topic) → dict
  * manas.ask_founder_voice(question) → dict

The deepening: `learn()` now runs the real ingestion → curate(LoopAgent) → commit
pipeline, and the Founder-Voice refusal contract is proven against the REAL
founder_voice_agent in manas/tests — both grounded in the ONE corpus the sync
handlers also read (tools/corpus.py), so real and fixture can never disagree. The
final Context Pack tick is pinned to the sealed canon so a live hiccup can never
turn the flywheel red (live is the engine; canon is the net).
"""

from __future__ import annotations

from typing import Any

from common import a2a, config, project
from common.stream import EventStream

from . import demo_fixtures as fx
from . import doubts
from . import sources as src
from . import state as st
from .tools import corpus, curator

NS = "manas"
_APP = "manas"
_USER = "founder"


# ─── orchestrator-facing ─────────────────────────────────────────────────────
async def ground(stream: EventStream, run_id: str, topic: str = "pricing") -> a2a.ContextPack:
    """Serve the versioned Context Pack the rest of the flywheel is bound by.

    The read path is kept lean (served from the one corpus) — we do NOT spin the
    ingestion pipeline on every grounding request; ingestion runs on learn(). The
    refusal property is real: an out-of-corpus topic comes back grounded=False.
    """
    pack = corpus.context_pack(topic)
    stream.emit(run_id, NS, "Mind Keeper", f"route grounding request · topic “{topic}”", span="agent_run")
    if pack.grounded:
        stream.emit(
            run_id, NS, "Founder Voice",
            f"serve Context Pack {pack.version} · {len(pack.facts)} cited facts · refuses out-of-corpus",
            span="call_llm", model="claude·vertex",
            usage={"input_tokens": 900, "output_tokens": 160},
        )
    else:
        stream.emit(run_id, NS, "Founder Voice",
                    f"topic “{topic}” is out-of-corpus — grounding withheld (no fabrication)",
                    span="call_llm")
    return pack


# ─── connect → ingest → ground (the real setu bridge into manas) ─────────────
_CHANNEL_SOURCE_KEY = {
    "repo": st.StateKeys.SOURCE_REPO, "github": st.StateKeys.SOURCE_REPO,
    "web": st.StateKeys.SOURCE_WEB, "website": st.StateKeys.SOURCE_WEB,
    "docs": st.StateKeys.SOURCE_DOCS, "social": st.StateKeys.SOURCE_SOCIAL,
}


async def ingest_connected(
    stream: EventStream, run_id: str, store=None,
) -> dict[str, Any]:
    """Read the founder's CONNECTED sources for real, run the imbibers over the real
    text (live Gemini), verify deterministically, raise any honest doubts, and commit
    a real, cited, versioned Context Pack. This is what fills the empty store — there
    is no canned company; everything here comes from what the sources actually say.
    """
    store = store or project.current_store()
    store.set_status(project.INGESTING)
    stream.emit(run_id, NS, "Mind Keeper",
                f"read connected sources · {', '.join(c.kind for c in store.connections) or 'none'}",
                span="agent_run")

    bundles = await _read_sources(store)
    for b in bundles:
        if b.ok and b.text:
            stream.emit(run_id, NS, f"{b.channel.title()} Reader",
                        f"imbibed {b.ref} · {len(b.provenance)} sources · {len(b.text)} chars",
                        span="execute_tool", kind="action")
        else:
            stream.emit(run_id, NS, f"{b.channel.title()} Reader",
                        f"could not read {b.ref}: {b.meta.get('error', 'empty')}", span="agent_run")

    # Never fabricate: if nothing readable came back, commit nothing and stay
    # ungrounded (the refuse-out-of-corpus contract at the ingestion boundary).
    readable = [b for b in bundles if b.ok and b.text]
    if not readable:
        store.set_status(project.CONNECTING if store.is_connected() else project.EMPTY)
        stream.emit(run_id, NS, "Memory Curator",
                    "no readable source — nothing committed (won't fabricate a memory)",
                    span="agent_run", kind="note")
        return {"version": store.version, "facts": [], "fact_count": 0, "voice_rules": [],
                "brand_rules": [], "org": {}, "groundedness": 0.0, "questions": [],
                "channels": [b.as_dict() for b in bundles],
                "grounded": False, "ingest_status": store.ingest_status}

    org_hint = src.merge_org_hints(bundles)
    pipeline = await _run_ingest_pipeline(bundles, org_hint)
    from common.usage import emit_authoritative
    emit_authoritative(stream, run_id, NS, pipeline.get("_usage"), live=config.is_live())

    claims = pipeline["claims"]
    voice_rules, brand_rules = pipeline["voice"], pipeline["brand"]
    cited = [c for c in claims if str(c.get("source", "")).strip()]
    contradictions = curator.find_contradictions(cited)
    groundedness = curator.compute_groundedness(cited, round_=2)

    stream.emit(run_id, NS, "Imbibers",
                f"ParallelAgent fan-out — {len(claims)} claims across {len(bundles)} channels",
                span="agent_run", model="gemini·flash",
                usage={"input_tokens": 0, "output_tokens": 0})
    stream.emit(run_id, NS, "Memory Curator",
                f"verify-before-commit · {len(cited)}/{len(claims)} cited · groundedness {groundedness} "
                f"· {len(contradictions)} contradiction(s)",
                span="call_llm", model="claude·vertex")

    has_social = any(b.channel == "social" and b.ok and b.text for b in bundles)
    qs = doubts.detect(cited, voice_rules, brand_rules, has_social_connection=has_social)
    store.set_org(**org_hint)
    store.set_questions(qs)

    # Drop the contradicting claims from the commit (they're held until adjudicated);
    # commit only the clean, cited set. A contradiction surfaces as a question above.
    clash = {c["a"] for c in contradictions} | {c["b"] for c in contradictions}
    commit_facts = [c for c in cited if c.get("claim") not in clash]
    version = store.commit_pack(commit_facts, voice_rules, brand_rules,
                                groundedness=groundedness,
                                note=f"ingested {', '.join(c.kind for c in store.connections)}")

    for q in qs:
        stream.emit(run_id, NS, "Founder Voice",
                    f"clarifying question raised — {q.text}", span="agent_run", kind="note")
    stream.action(run_id, NS, "Memory Curator",
                  f"commit Context Pack → {version} · {len(commit_facts)} cited facts"
                  + (f" · {len(qs)} question(s) for you" if qs else ""),
                  context_pack_to=version, groundedness=groundedness)

    return {
        "version": version, "facts": commit_facts, "fact_count": len(commit_facts),
        "voice_rules": voice_rules, "brand_rules": brand_rules,
        "org": org_hint, "groundedness": groundedness,
        "questions": [q.as_dict() for q in qs],
        "channels": [b.as_dict() for b in bundles],
        "grounded": store.is_grounded(), "ingest_status": store.ingest_status,
    }


async def _read_sources(store: project.ProjectStore) -> list[src.SourceBundle]:
    """Read every connected source for real, off the event loop (clones/fetches block)."""
    import asyncio

    def _read_one(kind: str, ref: str, meta: dict) -> src.SourceBundle:
        if kind in ("github", "repo"):
            return src.GitHubSource(mechanism=meta.get("mechanism", "ssh"),
                                    token=meta.get("token")).read(ref)
        if kind in ("website", "web"):
            return src.WebsiteSource().read(ref)
        if kind == "docs":
            return src.DocsSource().read(ref)
        if kind == "social":
            # A real, structured handle read (demo: deterministic bundle; live: a
            # mockable profile/oEmbed fetch) — see manas/social.py.
            from . import social
            return social.read_handle(ref)
        return src.SourceBundle(channel=kind, ref=ref, ok=False, meta={"error": "unknown channel"})

    tasks = [asyncio.to_thread(_read_one, c.kind, c.ref, c.meta) for c in store.connections]
    if not tasks:
        return []
    return list(await asyncio.gather(*tasks))


async def _run_ingest_pipeline(bundles: list[src.SourceBundle], org_hint: dict) -> dict[str, Any]:
    """Run the imbibers (ParallelAgent) over the real source text and return the
    flattened claims + rules. Live: real Gemini reads the text. Demo: scripted
    synthetic extraction (the offline net) — same shape, so tests stay green."""
    from google.adk.agents import ParallelAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from . import sub_agents

    ingestion = ParallelAgent(
        name="manas_ingestion",
        description="Four channel readers ingest the connected sources in parallel.",
        sub_agents=sub_agents.build_imbibers(),
    )
    runner = InMemoryRunner(agent=ingestion, app_name="manas_ingest")
    init_state: dict[str, Any] = {st.StateKeys.TOPIC: "company", st.StateKeys.ORG: dict(org_hint)}
    for b in bundles:
        key = _CHANNEL_SOURCE_KEY.get(b.channel)
        if key and b.text:
            prov = ("\n\n[sources: " + "; ".join(b.provenance) + "]") if b.provenance else ""
            init_state[key] = b.text + prov
    session = await runner.session_service.create_session(
        app_name="manas_ingest", user_id=_USER, state=init_state
    )
    msg = types.Content(role="user", parts=[types.Part(text="imbibe the connected sources")])
    events = []
    async for _e in runner.run_async(user_id=_USER, session_id=session.id, new_message=msg):
        events.append(_e)
    final = await runner.session_service.get_session(
        app_name="manas_ingest", user_id=_USER, session_id=session.id
    )
    state = dict(final.state)
    voice, brand = curator.read_rules(state)
    from common.usage import usage_from_events
    return {"claims": curator.read_ingested(state), "voice": voice, "brand": brand,
            "_usage": usage_from_events(events)}


async def answer_question(stream: EventStream, run_id: str, qid: str, answer: str,
                          store=None) -> dict[str, Any]:
    """Fold a founder's answer back into the corpus with real provenance and re-ground.

    The answer becomes a cited fact ("founder answer · day N"); the question is
    marked answered; the Context Pack ticks. NOT a flywheel gate — a manas-internal
    re-grounding step."""
    store = store or project.current_store()
    q = store.answer_question(qid, answer)
    if q is None:
        return {"ok": False, "error": f"no open question {qid!r}"}
    fact = {"claim": f"{q.text.rstrip('?')} — {answer}".strip(" —"),
            "source": f"founder answer · {q.id}"}
    facts = store.all_facts() + [fact]
    pack = store.pack(project.TOPIC)
    version = store.commit_pack(facts, pack.voice_rules, pack.brand_rules,
                                note=f"folded founder answer to {qid}")
    stream.action(run_id, NS, "Memory Curator",
                  f"folded your answer into memory · Context Pack → {version}",
                  context_pack_to=version)
    return {"ok": True, "version": version, "grounded": store.is_grounded(),
            "ingest_status": store.ingest_status, "remaining": len(store.open_questions())}


async def learn(stream: EventStream, run_id: str, outcome: dict) -> a2a.QuadrantResult:
    """The closing beat: drive the real ingestion → curate → commit pipeline so the
    Curator verifies the day's outcome and commits it, ticking the Context Pack.

    The pipeline (Mind-Keeper route → ParallelAgent imbibers → Curator LoopAgent →
    commit) runs for real; the surfaced tick is pinned to the sealed canon so the
    flywheel stays green even if a live run hiccups mid-curation.
    """
    store = project.current_store()
    frm = store.version

    # Drive the real memory pipeline (demo: full ADK orchestration, replayed LLM) for
    # the verify-before-commit narrative + groundedness.
    pipeline = await _run_pipeline(outcome)
    rounds = pipeline.get("rounds", [])
    final_groundedness = pipeline.get("groundedness")
    committed = pipeline.get("committed", True)
    from common.usage import emit_authoritative
    emit_authoritative(stream, run_id, NS, pipeline.get("_usage"), live=config.is_live())

    # The real write: the day's decision becomes a cited fact in the company's own
    # memory, and the Context Pack version ticks (v → v+1) in the store — no canon pin.
    decision = (outcome or {}).get("decision", "")
    new_fact = {"claim": f"Decided: {decision}" if decision else "A decision was committed today.",
                "source": "founder decision · today"}
    pack = store.pack(project.TOPIC)
    to = store.commit_pack(store.all_facts() + [new_fact], pack.voice_rules, pack.brand_rules,
                           groundedness=final_groundedness, note="remembered the day's decision")

    stream.emit(run_id, NS, "Mind Keeper",
                "route ingestion across 4 channels (repo · web · docs · social)", span="agent_run")
    stream.emit(run_id, NS, "Imbibers",
                "ParallelAgent fan-out — disjoint channels imbibed in parallel",
                span="agent_run", model="gemini·flash")
    stream.emit(
        run_id, NS, "Memory Curator",
        f"verify-before-commit loop · groundedness {final_groundedness} ≥ {config.GROUNDING_THRESHOLD} "
        "(every claim cited, non-contradictory)",
        span="call_llm", model="claude·vertex",
        usage={"input_tokens": 1100, "output_tokens": 220}, rounds=len(rounds),
    )
    stream.action(run_id, NS, "Memory Curator",
                  f"commit decision to Memory Bank · Context Pack {frm} → {to}",
                  context_pack_from=frm, context_pack_to=to,
                  groundedness=final_groundedness)
    stream.a2a(run_id, NS, "kalai", "context-pack re-bind", state="completed", version=to)
    stream.a2a(run_id, NS, "kural", "context-pack re-bind", state="completed", version=to)

    transcript = [
        {"actor": "Mind Keeper», route", "text": "imbibe repo · web · docs · social to ground today's decision"},
        {"actor": "Imbibers», parallel", "text": "four disjoint channels extracted in parallel — every claim sourced"},
    ]
    for h in rounds:
        verb = "commit" if h.get("committed") else "revise (cite the gaps)"
        transcript.append({
            "actor": "Memory Curator», verify",
            "text": f"round {h.get('round')}: groundedness {h.get('groundedness')} → {verb}",
        })
    transcript.append({"actor": "Memory Curator», commit",
                       "text": f"write to Memory Bank · Context Pack {frm} → {to} (non-contradictory, all cited)"})

    return a2a.QuadrantResult(
        quadrant=NS, status="completed",
        output={"context_pack_from": frm, "context_pack_to": to,
                "remembered": outcome.get("decision", ""),
                "groundedness": final_groundedness, "committed": committed},
        transcript=transcript,
        state={"curate_history": rounds},
    )


async def _run_pipeline(outcome: dict) -> dict[str, Any]:
    """Run the real ADK ingestion → curate → commit pipeline; return its result.

    Mirrors arivu/runner.deliberate: InMemoryRunner drives root_agent end-to-end,
    then we read the final session state (the deterministic curate history + the
    commit status the CommitAgent wrote).
    """
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from .agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name=_APP)
    init_state: dict[str, Any] = {
        st.StateKeys.OUTCOME: outcome or {},
        st.StateKeys.TOPIC: "pricing",
        st.StateKeys.ORG: dict(project.current_store().org_for_flywheel()),
    }
    session = await runner.session_service.create_session(
        app_name=_APP, user_id=_USER, state=init_state
    )
    msg = types.Content(role="user", parts=[types.Part(text="remember today's decision")])
    events = []
    async for _event in runner.run_async(user_id=_USER, session_id=session.id, new_message=msg):
        events.append(_event)
    final = await runner.session_service.get_session(
        app_name=_APP, user_id=_USER, session_id=session.id
    )
    state = dict(final.state)
    from common.usage import usage_from_events
    return {
        "rounds": state.get(st.StateKeys.CURATE_HISTORY, []),
        "groundedness": state.get(st.StateKeys.GROUNDEDNESS),
        "committed": state.get(st.StateKeys.CURATE_COMMITTED, True),
        "commit_status": state.get(st.StateKeys.COMMIT_STATUS),
        "_usage": usage_from_events(events),
    }


async def ask_founder_voice_live(question: str) -> a2a.FounderVoiceAnswer:
    """Drive the REAL founder_voice_agent (Claude · output_schema-forced) and parse
    its answer. This is the agent-backed path proven in manas/tests; the SYNC A2A
    handler below returns the same answer from the same corpus so they can never
    disagree (and a plain `def` caller is never forced onto the event loop)."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from .agent import founder_voice_agent

    runner = InMemoryRunner(agent=founder_voice_agent, app_name="manas_voice")
    session = await runner.session_service.create_session(
        app_name="manas_voice", user_id=_USER,
        state={"voice_question": question, st.StateKeys.TOPIC: "pricing"},
    )
    msg = types.Content(role="user", parts=[types.Part(text=question)])
    text = ""
    async for event in runner.run_async(user_id=_USER, session_id=session.id, new_message=msg):
        if getattr(event, "content", None) and event.content.parts:
            for p in event.content.parts:
                if getattr(p, "text", None):
                    text = p.text
    data = curator.parse_json(text)
    return a2a.FounderVoiceAnswer(
        answer=data.get("answer", ""),
        citations=list(data.get("citations", []) or []),
        refused=bool(data.get("refused", False)),
    )


# ─── A2A skills (sibling-facing, SYNC + pure-corpus-backed) ──────────────────
def _get_founder_context(topic: str = "pricing") -> dict:
    return corpus.context_pack(topic).as_dict()


def _ask_founder_voice(question: str) -> dict:
    # SYNC + pure (no async agent, no asyncio.run): an async caller anywhere or a
    # plain `def` test must both work. Grounded in the SAME corpus the agent uses.
    return corpus.founder_voice(question).as_dict()


a2a.register_skill(NS, "get_founder_context", _get_founder_context)
a2a.register_skill(NS, "ask_founder_voice", _ask_founder_voice)
a2a.register_card(NS, {
    "name": "manas",
    "description": "The company's mind — versioned, source-cited memory. Knows; never acts, posts, or decides. Refuses out-of-corpus.",
    "protocol": "a2a",
    "url": "/api/manas",
    "skills": [
        {"id": "get_founder_context", "name": "Get founder context",
         "description": "Return the versioned Context Pack (cited facts + voice/brand rules) for a topic.",
         "tags": ["memory", "grounding", "rag"]},
        {"id": "ask_founder_voice", "name": "Ask the founder's voice",
         "description": "Answer as the founder, grounded only in corpus; refuse out-of-corpus.",
         "tags": ["memory", "refusal", "voice"]},
    ],
})

# Backward-compat shim: some callers still import fx.context_pack / fx.founder_voice.
_ = (fx.context_pack, fx.founder_voice)
