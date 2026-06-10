# Devpost Submission — saakshe

Paste each section into the matching Devpost field. Track 1 (Build), Google for Startups AI Agents Challenge.

---

## 1. Project name + tagline

**Project name:** saakshe

**Tagline (85 chars):**
One founder, a whole company, one witness. Three faculties work; you tap twice a day.

---

## 2. Inspiration / the problem

I am that founder. I run **AIKIZI** — an AI image platform, live for about five months, with an iOS app — alone. I am the company's memory (what did we promise users, what does the brand actually say), its decision-maker (should we change the price), its maker (write the announcement, design the creative), and its mouth (post it, reply, follow up). Every hour spent in one role is stolen from the others. When I am deep in a pricing decision I am not making the launch graphic. When I am making the graphic I am not remembering the grandfathering promise I wrote into a doc months ago. And I want to run the company from anywhere — I travel.

The existing answer is "hire," which I can't, or "use AI tools," which means ten disconnected chat windows with no shared memory, no deliberation, and no governance — a copy tool that doesn't know your brand promises, a scheduler that will happily post whatever you paste into it. I built saakshe for myself first: a one-person company gets the faculties of a whole one — grounded memory, an adversarial decision chamber, a maker, and a mouth — with me still holding the only two switches that touch the real world. The demo runs on AIKIZI because that is the actual use, not a staging trick.

---

## 3. What it does

saakshe is a startup-buddy agent system for companies that already exist — it connects to your real repo and website. The founder talks only to **saakshe, the witness**. Under the witness, three shapes do the work:

- ⬤ **manas (knows)** — versioned, source-cited memory of your company. It grounds everyone, and it refuses to answer beyond its corpus rather than guess.
- ▲ **kalai (makes)** — all media and every word of copy. Stills via Vertex Imagen in live mode (the Veo reel wrapper is shipped; wiring it into the flywheel is roadmap).
- ◼ **kural (engages)** — carries kalai's cleared work out to channels verbatim. It authors nothing, by construction.

All three call **arivu, the shared decision chamber** — not a fourth peer, but the room where decisions get fought over before they're made.

**One concrete day.** The founder asks: "Should we raise Pro to $39?"

1. **manas grounds it.** It pulls cited facts it extracted from the founder's own repo and website at connect time — current list price, the grandfathering promise in the brand canon, the churn data — each fact carrying its source. It verifies: no citation, no fact.
2. **arivu's chamber deliberates.** A parallel advisor panel argues (Gemini seats), a debate loop sharpens the disagreement, a Claude verdict seat synthesizes, and then a Claude prosecutor attacks the verdict's weakest reason. If the prosecutor lands a hit, the chamber revises only the faulted reason — graduated, never a full reset. The output is a decision with its reasoning and its survived objections attached.
3. **Tap 1.** The founder approves the company decision at arivu's gate. Nothing acts before this.
4. **kalai makes the announcement.** Creative brief through its own chamber (deciding factor: brand fit), copy in the founder's extracted voice, the still rendered with Imagen, brand assets pulled from the vault that was auto-extracted at connect. Every variant is verified against the brand block before it clears.
5. **kural carries it out.** Its delivery planner picks channels and timing — but its schema has no text field. The assembler copies kalai's cleared variant byte-for-byte. The mouth structurally cannot rewrite the words.
6. **Tap 2.** The founder approves at kural's publish gate. The executor fires only after approval, and dry-run is the hardcoded default.
7. **manas learns.** The day's outcome is committed back as a new cited fact and the Context Pack ticks a version. Tomorrow's decisions stand on today's.

At every step the pattern is the same: an agent **acts**, then something **verifies** — a citation check, a prosecutor, a schema, a human tap. Errors never sink the day (a failed render or connect degrades soft); safety gates fail closed.

Throughout, the witness answers the founder from tools, not vibes: `anyone_waiting`, `cost_today`, `whats_reversible`, `what_learned`, `whos_acting_now`. Asked beyond its data, it refuses by default.

---

## 4. How we built it

**Python ADK, one service.** Every faculty is a google-adk agent tree, and the whole system ships as ONE FastAPI service on Cloud Run (us-central1), live at saakshe.com. Sequential, Parallel, and Loop agents are used where the shape is genuinely earned: manas ingests four modalities with a ParallelAgent and verifies-before-commit with a curator LoopAgent; the chamber is a SequentialAgent wrapping a ParallelAgent panel and two loops (debate, prosecution).

**The chamber is a primitive, not a copy-paste.** `common/chamber.py` defines the full deliberation pipeline once — frame → parallel advisor panel → debate loop → Claude verdict → graduated prosecutor → gate — and arivu instantiates it via a `ChamberSpec` with its exact deciding factor, threshold, and human-tap flag, gating company questions on the founder. The other faculties run chamber-shaped panel-and-verify loops of their own: kalai's decides brand fit; kural's decides send-eligibility — kalai's compliance gate already cleared every claim.

**Gemini-many, Claude-few — all via Vertex.** The many routine and panel seats run Gemini on Vertex (gemini-3.1-pro-preview, gemini-3.5-flash). The 7 highest-stakes seats — verdict, prosecutor, founder voice, memory curator, creative director, compliance, envoy lead (the prosecutor's reviser and kural's delivery planner ride the same model) — run Claude (claude-sonnet-4-6) through Vertex Model Garden. Every third-party LLM call goes through Vertex.

**Three modes, honestly separated.** `demo` runs the entire orchestration creds-free with scripted model output — deterministic and byte-identical, so judges and CI see the same day. `hybrid` runs real Gemini with Claude scripted. `live` is all real, including Imagen still renders and the witness's Gemini Live voice.

**Tested.** 316 tests pass (6 skipped), creds-free. Per-faculty ADK evalsets are checked in at the 0.8 bar — they require live credentials and have not yet been run live; we say so plainly. Supabase provides auth and an opt-in per-user store; OTel span callbacks trace every seat; each faculty serves an A2A agent card at `/api/{faculty}/agent-card`.

---

## 5. The innovation

**(a) The chamber primitive.** Adversarial deliberation — panel, debate, verdict, prosecutor, gate — built exactly once, instantiated by arivu via `ChamberSpec`, and echoed as chamber-shaped panel-and-verify loops in every other faculty (brand fit, send-eligibility, groundedness). The prosecutor is graduated: it faults a specific reason and the chamber revises only that reason, preserving everything that survived. Most multi-agent systems vote or chain; ours argues, and the argument is reusable infrastructure.

**(b) Separation enforced by schema, not prompt.** kalai authors everything; kural delivers. This isn't a system-prompt request — kural's delivery-planner schema has no text field, and its assembler copies kalai's cleared variant byte-for-byte. The mouth structurally cannot author. A prompt can be jailbroken; a missing field cannot.

**(c) The witness.** The founder's single interface answers from tools over telemetry — `anyone_waiting`, `cost_today`, `whats_reversible`, `what_learned`, `whos_acting_now` — and refuses beyond its data by default. An agent system you can trust is one that knows what it doesn't know.

**(d) Governed irreversibility.** Exactly two human taps stand between the agents and the world: the company-decision gate and the publish gate. The executor fires only after approval; dry-run is the hardcoded default. We never pitch auto-publish — the human gate is the point, not a limitation.

---

## 6. Challenges we ran into

**Vertex Claude quota on a fresh project.** Our new GCP project's Claude-on-Vertex quota hasn't cleared yet; a resubmission is pending. Instead of faking it, we built hybrid mode: real Gemini drives the flywheel on prod today, while the 7 Claude seats run scripted replay of their transcripts. The same orchestration code runs in all three modes — only the token source changes. Credibility is a feature.

**Determinism vs. reality.** A demo that drifts between runs is a demo you can't trust. Keeping demo mode byte-identical — same day, same verdicts, same renders as `vertex://` placeholders — while the identical code paths go fully real in live mode forced a clean seam between orchestration and token generation, which is also what made hybrid mode possible.

**The a2a-sdk restructure.** Upstream package changes broke the planned integration path, so we serve A2A agent cards through our own API (`/api/{faculty}/agent-card`) instead. The cards are real and checked in per faculty.

---

## 7. Accomplishments we're proud of

- **Deployed and grounded on a real company.** saakshe.com runs on Cloud Run and boots already connected to AIKIZI — a real company, ingested through the product's own connect flow: live Gemini read its GitHub repo and website and extracted cited facts, voice, and brand rules into a versioned Context Pack.
- **kalai's hands are proven live.** A real Vertex Imagen render (`imagen-4.0-generate-001`), generated from a brand-grounded prompt, is checked into the repo at `docs/first_creation.png`.
- **316 tests pass (6 skipped), creds-free.** The full flywheel — both gates, fail-soft error paths, the separation contract — runs under test with no credentials.
- **Safety as tested structure.** The byte-for-byte copy in kural, the schema with no text field, gates that fail closed, dry-run as the hardcoded executor default — these are properties under test, not promises in a prompt.
- **Honest modes.** Demo, hybrid, and live share one codebase; what's real and what's replayed is explicit in every run.

**The business case, in hours.** A solo founder is simultaneously the company historian, the strategist, the designer-copywriter, and the channel manager — four roles competing for one person's week. saakshe gives those roles their own faculties and compresses the founder's part to two reviewed taps a day. Target: SaaS at $200–500/mo, with BYOK (your own Gemini, Claude-on-Vertex, and channel keys) on the roadmap — a fraction of any one of the hires it stands in for.

---

## 8. What we learned + what's next

**Learned.** Verification has to be structural. Every place we relied on a prompt to enforce a boundary, we eventually replaced it with a schema, a citation check, or a prosecutor — and the system got more trustworthy each time. We also learned that an honest demo (scripted where scripted, real where real) is easier to build and easier to defend than a flaky "all live" one.

**Next.**
- **Learning flywheel, deeper:** outcomes already commit back as cited facts; next is measuring downstream results and citing those too.
- **Precedent in the chamber:** let the prosecutor cite the company's own past verdicts, so decisions compound instead of repeating.
- **A code-exec agent:** a faculty that executes code, fed by arivu's sealed decision briefs — the manas pending-changes seam is designed as its entry point.
- **BYOK, two layers:** founders bring their own Vertex and channel keys, and connect their own generator APIs — image, video, audio models that kalai then uses. The witness's `cost_today` becomes a governor, not just a readout.
- **Sub-agent pods everywhere:** our depth bar is AIKIZI's production decode pipeline — one input fanned out to ~10 specialized parallel Gemini calls. Bring that depth to every faculty seat.
- **Marketplace / A2A:** the agent cards are already served; let outside agents petition the chamber through the same gates a faculty does.

---

## 9. Built with

Google ADK, Vertex AI, Gemini, Claude (via Vertex Model Garden), Imagen, Veo, Cloud Run, FastAPI, Supabase, OpenTelemetry, Python

---

## 10. Testing access for judges

**Live:** https://saakshe.com — gated for judging. Sign in on the cockpit with the judge credentials (Supabase email auth; no Google account needed):

- **email:** `judge@saakshe.com`
- **password:** *(filled in on Devpost's private testing-instructions field — this repo is public, the password is not)*

It boots already grounded on AIKIZI, a real company connected through the product's own ingest flow (live Gemini read its repo and website and extracted cited facts).

Three things to try:

1. **Ask the witness a grounded question** — e.g. "what's the verdict?" or "what do we know about pricing?" Answers come with citations; ask something outside the corpus and watch it refuse instead of guess.
2. **Run the day.** Start the flywheel and watch the chamber work a real question: panel, debate, verdict, prosecutor.
3. **Approve the two gates.** Tap the company-decision gate, watch kalai's creative and kural's verbatim delivery plan, then tap the publish gate. Nothing fires before your taps.

Note on what's real today: prod runs in hybrid mode — Gemini seats are live; the 7 Claude seats replay scripted transcripts while our Vertex quota resubmission is pending. The UI doesn't hide this.

**Local, creds-free:** clone the repo and follow the README quickstart — demo mode runs the entire orchestration deterministically with zero credentials on `:8000`.

---

## 11. Video

[VIDEO LINK — 1-2 min, to be added]
