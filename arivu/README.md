# arivu — the faculty of judgment

> _arivu · Tamil — intellect, wisdom; the determining mind, the faculty that resolves doubt into settled judgment._

**arivu is a company's DECIDE faculty made operational.** A chamber of grounded
advisors deliberate a loaded strategic question, a chair reconciles them into one
verdict, an adversary tries to kill that verdict before it ships, a single human
signs off — and then real execution fires across every team, on the record.
It commits a live change and dispatches A2A commands. **It decides, then it acts;
it never merely recommends.**

Built on the **Google Agent Development Kit (ADK)**. Submitted to the
**Google for Startups AI Agents Challenge — Track 1 · Build**
(judged **30% Technical · 30% Business Case · 20% Innovation · 20% Demo**).

---

## The case it decides

A four-person DTC brand, **Sundara Coffee Co.**, must make a real call this
quarter: **"Should we raise our Pro subscription to $39?"** A real company would
put this to a board, a fractional CFO, a growth lead, and a brand head — argue it
out, pressure-test the downside, decide, and make every team act in lockstep.
Sundara has none of those people and can't afford a single one of those hires, so
the call gets made on a founder's gut at 1am — or never gets made, and rots.

A chatbot answers from model memory: a confident paragraph, ungrounded in the
company's actual revenue and churn, that recommends but cannot commit. arivu is
the apparatus instead — independent lenses arguing from the org's **own live
numbers**, a chair that reconciles them, an adversary that tries to defeat the
verdict, one human sign-off, and real execution across every team. In the demo the
**Risk** mantri catches a churn cliff past $36 that a lone analyst ships straight
past, so the chamber's verdict is **"Raise to $34, grandfather existing, 30-day
notice"** — not the $39 a single model answering from memory would wave through.

---

## Architecture — the ONE earned convergence pipeline

`root_agent` is a `SequentialAgent` named **arivu**. It is the one project in the
set where ADK's `ParallelAgent` and `LoopAgent` primitives genuinely pay for
themselves: multi-lens deliberation truly needs Parallel; the debate and the
prosecution truly need Loop. Every loop exits on a **numeric threshold or a
max-iteration rollback — never on "the advisors agreed."**

```
                        founder's loaded question
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │  frame  ·  Gemini 2.5 Pro      │  decompose + ground via TOOLS:
                   │  (chair, orchestrator)         │  manas A2A · admin_stats · admin_analytics
                   └───────────────────────────────┘
                                   │
                                   ▼
        ┌──────────────────  ParallelAgent  ──────────────────┐
        │   5 mantris · Gemini 2.5 Flash · disjoint lenses     │  anti-groupthink fan-out:
        │   economist · growth · brand · risk · ops            │  positions form before any
        │   (each its own lens + its own grounded data source) │  advisor sees another's
        └─────────────────────────────────────────────────────┘
                                   │
                                   ▼
        ┌──────────────────   LoopAgent   ────────────────────┐
        │   debate · moderator + DebateCheckAgent              │  cross-rebuttal until
        │   exits on convergence ≥ 0.75  OR  max 3 rounds      │  a deterministic number,
        │   (escalate fires on threshold — pure safety logic)  │  not consensus
        └─────────────────────────────────────────────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │  chair · verdict  ·  CLAUDE    │  synthesis-under-conflict →
                   │  (Opus-class · via Vertex AI)  │  {decision, reasons, dissent, confidence}
                   └───────────────────────────────┘
                                   │
                                   ▼
        ┌──────────────────   LoopAgent   ────────────────────┐
        │   prosecution · prosecutor + ProsecutionCheckAgent   │  prosecutor steelmans
        │   CLAUDE (Opus-class · via Vertex AI)                 │  do-nothing & attacks
        │   defensibility ≥ 0.80 → escalate (verdict survives)  │  the verdict on merits
        │   max 3 rounds without surviving → rollback           │  → "no safe decision —
        │                                  ("no safe decision") │     re-frame"
        └─────────────────────────────────────────────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │  gate · GateAgent  ·  HALT     │  ONE human-in-the-loop approval.
                   │  → awaiting_approval           │  The pipeline ends here. NO side effects.
                   └───────────────────────────────┘
                                   │
                       (founder taps APPROVE — one tap)
                                   ▼
                   ┌───────────────────────────────┐
                   │  executor  (separate step)     │  commit feature-flag flip ·
                   │  runner.execute_decision()     │  A2A dispatch → kural + kalai ·
                   │  real side effects ONLY here   │  publish signed resolution to a real URL
                   └───────────────────────────────┘
```

`DebateCheckAgent`, `ProsecutionCheckAgent`, and `GateAgent` carry **no model** —
they are pure deterministic safety logic (threshold math, max-iter rollback, the
single gate). The executor is deliberately **not** part of `root_agent`: the
pipeline halts at the gate, and execution fires only after a human approval via
`runner.execute_decision()`.

---

## The model split — and why

| Step | Model | Why |
|------|-------|-----|
| Chair / frame · orchestration | **Gemini 2.5 Pro** | Routine intelligence: decompose & ground the question. |
| 5 mantris · deliberation | **Gemini 2.5 Flash** | The volume of deliberation — speed and cost matter; Gemini for the many. |
| **Verdict synthesis** | **Claude (Opus-class) · via Vertex AI** | **Synthesis-under-conflict** is the single highest-stakes reasoning step. |
| **Adversarial prosecution** | **Claude (Opus-class) · via Vertex AI** | **Beating a steelmanned argument** is itself a high-stakes reasoning task. |

The two highest-stakes steps run on a **separate, stronger model than the one that
produced the positions it must now judge** — and they run on Claude **through
Vertex AI Model Garden**, satisfying the challenge's "third-party LLM exclusively
through Vertex AI" requirement. ADK's stock `Claude` shares Gemini's
`GOOGLE_CLOUD_LOCATION`; arivu's `VertexClaude` overrides the client to read
`ARIVU_CLAUDE_LOCATION` (default `us-east5`) so the region-restricted Claude and
the global Gemini can target different regions.

---

## The six north stars

1. **DECIDE, don't recommend** — arivu terminates in a committed, dispatched,
   on-the-record decision, or an explicit "no safe decision — re-frame." A
   recommendation that leaves the human to act is a failure mode, not the product.
2. **Grounded or silent** — no advisor speaks from model memory; every position
   cites a number pulled live from the org's own data via a tool, or it is not
   admitted to the chamber.
3. **Survive the prosecution** — a verdict ships only after it beats its own
   steelmanned null case at **defensibility ≥ 0.80**.
4. **One gate, one tap** — exactly one human approval stands between deliberation
   and irreversible action. Never two gates, never zero.
5. **Preserve the dissent** — the minority position is recorded in the resolution,
   never erased. The company can always see what it decided against, and why.
6. **Deterministic termination, always** — every loop ends on a numeric threshold
   or a max-iter rollback, never on "the advisors agreed." No runaway deliberation.

---

## Quickstart

> Python interpreter for this workspace: the shared venv at `../.venv`.
> All commands below are run from the project root (`arivu/`, the directory that
> holds `pyproject.toml` and `run_demo.py`).

### 1 · Set up the environment (`uv`)

```bash
uv venv ../.venv               # create the shared virtualenv next to the repo
source ../.venv/bin/activate
uv pip install -e .            # install arivu + ADK + the Vertex Claude SDK
cp .env.example .env           # then fill in for live runs (see below)
```

### 2 · Demo run — full ADK orchestration, no credentials

In demo mode the **entire ADK orchestration runs for real** — ParallelAgent
fan-out, both LoopAgents, escalate/threshold termination, the HITL gate, and the
executor — and **only LLM token generation is replayed** from checked-in fixtures.
This is a thin net for CI and for surviving a 429 mid-demo; live is the product.

```bash
ARIVU_MODE=demo python run_demo.py                  # the Sundara $39 question
ARIVU_MODE=demo python run_demo.py "Should we ..."  # any loaded question
ARIVU_MODE=demo python run_demo.py --approve        # also fire the executor (dry-run)
```

`--approve` simulates the founder's one tap at the gate and fires the executor in
**dry-run** (it logs the actions it would take and touches nothing).
`--approve --live-exec` allows REAL publish / planner / dispatch side effects.

### 3 · Live run — Gemini + Claude on Vertex AI

Live LLM access goes through **Vertex AI with Application Default Credentials
(ADC)** — including Claude, which runs through Vertex AI Model Garden (the
third-party-LLM-via-Vertex path).

**One-shot bring-up checklist** (do these in order — step 2 is the one people miss):

```bash
# 1. Auth — ADC uses YOUR login, no service-account key needed
gcloud auth login                          # if the gcloud session is stale
gcloud auth application-default login

# 2. ENABLE an Anthropic model in Vertex AI → Model Garden for this project,
#    in the Claude region (us-east5). Model Garden access is per-project; ADC
#    alone is not enough — without this, Claude calls 404 / permission-deny.

# 3. Point arivu at the project + regions
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=global        # Gemini region
export ARIVU_CLAUDE_LOCATION=us-east5      # Claude on Vertex region (independent)

# 4. Probe the riskiest slice FIRST — confirms one real Gemini + one real
#    Claude call answer in your project, and sweeps fallback ids/regions if not.
python scripts/probe_vertex.py

# 5. Once the probe is green, run the chamber live
export ARIVU_MODE=live
python run_demo.py --approve
```

The Claude model defaults to `claude-opus-4-1@20250805` (the most broadly
Model-Garden-available Opus); if the probe finds a newer Opus enabled for your
project it prints the exact `ARIVU_MODEL_VERDICT` / `ARIVU_CLAUDE_LOCATION` to set.

`ARIVU_MODE=auto` (the default in `.env.example`) picks **live** when creds
resolve and falls back to **demo** otherwise, so the chamber always runs
end-to-end.

### 4 · FastAPI server + live UI

```bash
# from the project root (saakshe/arivu)
uvicorn server.app:app --port 8000   # serves the bridge AND the live console
```

Then open **http://localhost:8000/** — the server serves the live chamber console
(`arivu_live.html`) on the same origin as its API, so there is no CORS friction.
It drives the chamber over the bridge and renders the live transcript (the
cockpit-grade visual of doubt crystallizing into a sealed verdict). The cockpit's
**● LIVE** link points here; the product brief / pitch page is `../arivu.html`.

### 5 · Tests — the deterministic pieces

```bash
pytest                              # threshold math, max-iter rollback, executor atomicity
```

`tests/` pins only the machinery that must behave identically every run regardless
of what any model says.

### 6 · Eval (creds-gated)

```bash
# requires live Vertex/Gemini creds — runs the rubric LLM-as-judge tracks
python -m arivu.eval               # AgentEvaluator over eval/evalset.json @ the 0.8 bar
```

The checked-in `eval/` set holds past founder decisions and grades two rubric
tracks — verdict quality and prosecution soundness (the hard defensibility ≥ 0.80
pass/fail) — plus a trajectory check that grounding tools actually fired and that
loop termination was a numeric threshold/escalate, never "advisors agreed."

### 7 · Deploy to Vertex AI Agent Engine

```bash
python deployment/deploy.py        # ships root_agent to Vertex AI Agent Engine
```

Vertex AI Agent Engine is the managed primary runtime — the convergence pipeline,
the HITL pause/resume, and Memory Bank run natively there. Cloud Run is the
secondary target for the A2A front door. All native Google Cloud.

---

## Safety

Irreversible action is safe by construction:

- **Executor is dry-run by default** (`ARIVU_EXECUTOR_DRY_RUN=true`). It logs the
  actions it _would_ take and fires nothing.
- **Real side effects fire ONLY behind the one human approval.** `deliberate()`
  halts at the gate with no side effects; `execute_decision()` refuses to run
  unless the gate survived prosecution, and real effects fire only when
  `dry_run=False` _and_ a human approved.
- **Never writes a price/revenue column.** The committed change is a
  **feature-flag flip** (`pricing.pro_tier_v2`) — a config commit — not a billing
  write. A deliberate retarget given the founder's billing-safety history. The
  downstream A2A dispatch to `kural`/`kalai` causes the real, irreversible spend.

---

## Project layout

```
arivu/
├── pyproject.toml          uv + hatchling; deps incl. anthropic[vertex], google-adk
├── run_demo.py             CLI: deliberate → transcript → optional --approve
├── .env.example            both run modes documented
├── arivu/
│   ├── agent.py            root_agent — the SequentialAgent convergence pipeline
│   ├── runner.py           deliberate() · execute_decision() · build_transcript()
│   ├── config.py           StateKeys, thresholds, model ids, run-mode detection
│   ├── models.py           Gemini + VertexClaude factory + scripted offline replay
│   ├── prompts.py          instruction bodies (one per mantri + chair + prosecutor)
│   ├── sub_agents.py       the LlmAgents: 5 mantris, frame, debate, chair, prosecutor
│   ├── demo_fixtures.py    Sundara replay payloads
│   ├── tools/              grounding (example MCP) · analyst (threshold math) · executor
│   ├── server.py           FastAPI bridge for arivu_live.html
│   └── eval/  tests/       rubric LLM-as-judge @ 0.8 · deterministic-piece pins
└── deployment/deploy.py    Vertex AI Agent Engine
```

> Routine intelligence runs on **Gemini**; the two highest-stakes reasoning steps
> run on **Claude via Vertex AI Model Garden**. One earned convergence pipeline,
> one human gate, decisions that become reality — on the record.

---

_One of four agentic products that form a single self-running company —
**manas** (UNDERSTAND), **arivu** (DECIDE · this repo), **kalai** (MAKE),
**kural** (GROW), with the founder in the run-seat through **saakshe**, the
witness. arivu is the set's only cross-lane node: it decides strategy and priority
across every lane, then commits the call._

Apache License 2.0.
