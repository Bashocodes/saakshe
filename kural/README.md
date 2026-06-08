# kural — the only mouth

> _kural · Tamil — the spoken word, the utterance; speech made to carry weight (as in Thirukkural, the classic of couplets). The faculty that says the right thing, once, and means it._

**kural is a company's ENGAGE faculty made operational.** It discovers who to
talk to, researches them, writes outreach worth reading in the founder's voice,
**fact-checks every claim before it says it**, sends as the buyer (never a blast),
and publishes the studio's approved creative **only behind the founder's
sign-off**. It holds the channel keys. It never edits the creative, never says
unverified things, never blasts, and never publishes without the gate.

Built on the **Google Agent Development Kit (ADK)**. Submitted to the
**Google for Startups AI Agents Challenge — Track 1 · Build**.

---

## Where it sits in the flywheel

kural is the company's **second** human gate (tap 2). The flywheel is:

```
manas grounds → arivu decides → [founder tap 1] → kalai makes →
  kural ENGAGES → [founder tap 2: publish] → manas learns
```

arivu hands kural an approved decision and kalai hands kural a compliance-cleared
master. kural turns that into a message a real customer would want to read,
proves every claim, and then **stops** — the world only hears it after a human
taps. The mouth is the company's reputation; it is the most-gated faculty for a
reason.

---

## Architecture — the ONE earned engagement pipeline

`root_agent` (`kural.agent`) is a `SequentialAgent` named **kural**:

```
envoy_lead          (Claude · Vertex)   qualify the engagement + ground · spine entry
  → research_fanout (ParallelAgent)     Prospect Scout ∥ Market Watcher  (Gemini, disjoint)
  → message_loop    (LoopAgent)         Outreach Writer (Gemini)
                                          → Claim-Judge (Claude · Vertex, fact-checks)
                                          → ClaimCheck (deterministic numeric gate)
  → gate            (HALT)              the founder's publish sign-off — NOT auto-published
```

**Parallel and Loop are earned here, not decorative:**

- **ParallelAgent** — the two research lenses are genuinely disjoint and
  independent (*who* the audience is + their consent vs. *when* the feed is open),
  so they run in parallel as an anti-serialization fan-out.
- **LoopAgent** — the write↔fact-check is a real loop: a failed claim sends the
  draft **back to the writer to re-ground**, bounded by `MAX_CLAIM_ROUNDS`. It is
  not a one-shot "looks good."

**Every loop exits on a number, never on vibes.** The Claim-Judge is an
LLM-as-judge (Claude), but the *gate* is a pure threshold:
`claim_support >= CLAIM_THRESHOLD` (0.80; the demo verifies at the sealed canon
**0.86**). Below the bar with rounds left → loop back; at the bound without
crossing → stop **unverified** ("no safe message" — the mouth stays shut). The
numeric logic lives in pure functions in `kural/tools/analyst.py` so the tests
pin it to exact literals — a model can never talk the mouth past the bar.

**Two Claude-via-Vertex seats, everything else Gemini.** The two highest-stakes
judgments — *is this worth saying* (Envoy Lead) and *is every claim true*
(Claim-Judge) — run on Claude via Vertex Model Garden, each forced through an ADK
`output_schema` (pydantic) so a live reply can never collapse to prose and silently
zero the numeric gate. The five routine seats (the two scouts, the writer, the
sender, the publisher) run on Gemini.

**The world-facing acts are NOT in `root_agent`.** Send and publish fire only
through `kural/tools/channels.py`, each wrapped in two rails:

1. a **before_tool eligibility / value-cap gate** (`channels.send_guard` →
   `analyst.send_eligibility`) — no recipient / no consent / over the per-send
   value cap is blocked, fail-closed; the mouth never blasts, and
2. a **no-double-send ledger** (`analyst.SendLedger`) — every send is marked
   before it fires, so a retry / re-run can never post the same thing twice.

`publish()` is `dry_run=True` by default; the real OAuth publish fires only when
`dry_run=False`, which the server sets only after the founder's tap-2.

---

## The locked interface (what the orchestrator calls)

```python
async def engage(stream, run_id, master, context_pack) -> QuadrantResult
    # status "awaiting_approval", gate = GateRequest(g2, "publish", reversible=False)
async def publish(stream, run_id, state, dry_run=True) -> dict
    # the post-tap-2 side effect (dry-run by default)
# A2A skill: kural.launch_campaign(brief, ...) -> dict   (accepts + holds at the gate)
```

`engage()` drives the real ADK `root_agent` and HALTS before publish (the way
`arivu.runner.deliberate` drives arivu's chamber and halts at its gate);
`publish()` is the separate, human-approved step. The integration test
`tests/test_flywheel.py` pins this seam.

---

## Run it

```bash
# from the saakshe repo root, demo mode (no creds — full orchestration, replayed LLM)
SAAKSHE_MODE=demo PYTHONPATH=. ./.venv/bin/python -m pytest kural/tests -q

# the company-level integration guard (must stay green)
SAAKSHE_MODE=demo PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_flywheel.py -q

# the ADK eval set (creds-gated — grades outreach quality + claim soundness @0.80)
SAAKSHE_MODE=live GOOGLE_CLOUD_PROJECT=... \
  ./.venv/bin/python -m pytest kural/eval/test_eval.py -s
```

In **demo** the deterministic offline replay reproduces the sealed canon (the
Claim-Judge re-grounds once at 0.72, then verifies at 0.86; the post announces
Pro → $34) and never presents a forbidden value (0.62 / 0.81) as canon. **Live**
is the product; the replay is the net that lets the whole flywheel demo creds-free
and survive a 429 mid-demo — the orchestration (Parallel / Loop / escalate / HITL
/ ledger / A2A) is fully real either way.
