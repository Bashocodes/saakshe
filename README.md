# saakshe — the agentic company, behind one witness

> The founder talks only to **saakshe** (the witness). Behind it, a four-quadrant
> agentic company runs the work: **manas** knows · **arivu** decides · **kalai** makes ·
> **kural** engages. Every action flows through a resumable **two-gate flywheel** —
> the founder taps twice, and nothing irreversible happens without a tap.
>
> Built for the **Google for Startups · AI Agents Challenge** (Track 1 · Build), on
> **Google ADK** with routine intelligence on **Gemini** and the highest-stakes seats
> on **Claude via Vertex AI Model Garden**.

---

## The idea

One front door (the witness) over a real company of agents. A founder asks a real
decision; the flywheel grounds it in the company's own memory, argues it, seals a
defensible verdict, makes the asset, writes the outreach, and learns from it — halting
at exactly **two human gates** (the decision, and the publish). The witness holds **no
static knowledge**: it answers only from the live event stream and **refuses** anything
it can't see. That refusal is the point — it's an agent, not a dashboard with a chatbot.

```
founder ──▶ saakshe (witness) ──▶ manas.ground + arivu.deliberate ──▶ ◗ GATE 1 (decision)
                                                                          │ tap
        arivu.execute + kalai.make + kural.engage ◀──────────────────────┘
                                  │
                                  └──▶ ◗ GATE 2 (publish) ──tap──▶ kural.publish + manas.learn ──▶ closed
```

- **manas** (KNOWS) — memory: parallel imbibers + a Claude curator that verifies every
  claim cites a source before commit; a Founder-Voice that refuses out-of-corpus.
- **arivu** (DECIDES) — five Gemini lenses debate; a Claude bench seals + prosecutes the
  verdict against a deterministic defensibility threshold. *(imported untouched)*
- **kalai** (MAKES) — a brand-fidelity loop + a fail-closed compliance gate; no channel keys.
- **kural** (ENGAGES) — the only mouth; a claim-judge loop, then holds the publish gate.
- **witness** — tools-over-telemetry + refusal + a voice bridge (text-over-WS demo today).

Everything is a pure render of **one ordered event stream**.

---

## Quickstart (demo — creds-free)

Demo mode is the default and needs **no credentials** — the ADK orchestration runs for
real; only the model token-generation is replayed from per-quadrant fixtures.

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# run the whole site (landing → onboarding → cockpit + API + WebSocket) on one port:
PYTHONPATH=. ./.venv/bin/uvicorn service.app:app --port 8000
# → open http://localhost:8000/   (landing; "enter" → the cockpit at /cockpit.html)
```

Or run the flywheel end-to-end in the terminal:

```bash
PYTHONPATH=. ./.venv/bin/python run_flywheel.py
```

Run the tests (135 green):

```bash
PYTHONPATH=. ./.venv/bin/pytest -q                       # core (flywheel + witness)
PYTHONPATH=. ./.venv/bin/pytest manas/tests kalai/tests kural/tests -q
( cd arivu && PYTHONPATH=. ../.venv/bin/pytest tests/ -q )   # arivu runs from its own dir
```

---

## Modes

| Mode | Command | Gemini | Claude |
|------|---------|--------|--------|
| **demo** (default) | `uvicorn service.app:app --port 8000` | scripted replay | scripted replay |
| **hybrid** | `./run_hybrid_server.sh` | **real (Vertex)** | scripted (quota pending) |
| **live** | `./run_live.sh server` | **real** | **real (Vertex)** |

Hybrid is the runnable live path today (the Claude·Vertex quota is still pending). In the
cockpit, click the **● live** toggle to drive a real run through the live console.

### Live/hybrid setup

Live runs need a Google Cloud project with Vertex AI + Model Garden enabled, and ADC:

```bash
gcloud auth application-default login
cp .env.local.example .env.local      # then set GOOGLE_CLOUD_PROJECT in .env.local
```

`.env.local` is **git-ignored** — the real project id never enters the repo. Model ids
and regions live in `.env` (also git-ignored; see `.env.example`), but the app already
defaults to the verified ids in `common/config.py`, so demo works with no `.env` at all.

---

## Layout

```
saakshe/
├── service/app.py        # the ONE FastAPI service — cockpit at / + all /api + /ws/voice
├── orchestrator.py       # the resumable 2-gate flywheel
├── common/               # shared substrate: config · models · a2a · project store · stream
├── manas/ kalai/ kural/  # three real-ADK quadrants (knows · makes · engages)
├── arivu/                # the decides quadrant (nested arivu/arivu/, imported untouched)
├── witness/              # tools-over-telemetry + refusal + voice
├── web/                  # the whole site — landing (/) · onboarding · cockpit ·
│                         #   faculty pages (manas·arivu·kalai·kural·setu·darshana) · explainers
├── docs/                 # cockpit + landing specs
├── tests/                # cross-quadrant integration + witness regression tests
├── requirements.txt
└── run_*.sh              # demo / hybrid / live entry points
```

> **Note on imports:** the quadrants are imported from the repo root via `PYTHONPATH=.`
> (not pip-installed). `common/__init__.py` adds `arivu/` to `sys.path`, so `import arivu`
> resolves even though arivu lives at `arivu/arivu/`. This is intentional.

---

## The store

State persists to `~/.saakshe/project_founder.json` (a file-based store, **outside** the
repo). A Supabase-backed store is wired as an opt-in (`SAAKSHE_STORE=supabase` + a service
key at `~/.saakshe_supabase_key`); the default stays file-based.

---

## Deployment

Runs locally on `:8000` for now. The domain (saakshe.com) connects on demo day via
Cloudflare; until then everything is local. Each quadrant also carries a `deployment/`
config for Vertex AI Agent Engine.
