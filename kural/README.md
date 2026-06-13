# kural — the only mouth

> _kural · Tamil — the spoken word, the utterance; speech made to carry weight (as in Thirukkural, the classic of couplets). The faculty that says the right thing, once, and means it._

**kural is a company's WORD faculty made operational** (the name is the spoken word
itself). It discovers who to talk to, researches them, **authors the founder-voice
copy and fact-checks every claim** (the Outreach Writer + Claim Judge, at
`claim_support ≥ 0.80`), sends as the buyer (never a blast), and publishes kalai's
approved media **only behind the founder's sign-off**. The channel keys are
custodied by manas; kural wields a scoped use. It never edits kalai's creative,
never blasts, and never publishes without the gate.

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
  → gate            (HALT)              the founder's publish sign-off — NOT auto-published
```

kural **authors nothing**: in the separation fix the old Outreach Writer +
Claim-Judge were retired. kalai owns all copy (caption + every channel variant,
fact-checked in its own brand-fidelity loop); kural reads that cleared master and
carries it **untouched**. One company, one author.

**Parallel is earned here, not decorative:** the two research lenses are genuinely
disjoint and independent (*who* the audience is + their consent vs. *when* the feed
is open), so they run in parallel as an anti-serialization fan-out.

**The gate exits on a property, never on vibes.** It opens only when the engagement
is qualified **and** the send is eligible — a real recipient, recorded consent, and
within the per-send value cap (`SEND_VALUE_CAP_USD`), fail-closed. Miss any and the
mouth stays shut ("no safe message"). The eligibility logic lives in pure functions
in `kural/tools/analyst.py` so the tests pin it to exact literals — a model can
never talk the mouth past the bar.

**One Claude-via-Vertex seat, everything else Gemini.** The highest-stakes judgment
— *is this worth saying* (Envoy Lead) — runs on Claude via Vertex Model Garden,
forced through an ADK `output_schema` (pydantic) so a live reply can never collapse
to prose and silently zero the numeric gate. The four routine seats (the two
scouts, the sender, the publisher) run on Gemini.

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

# the ADK eval set (creds-gated — grades engagement quality + send-eligibility)
SAAKSHE_MODE=live GOOGLE_CLOUD_PROJECT=... \
  ./.venv/bin/python -m pytest kural/eval/test_eval.py -s
```

In **demo** the deterministic offline replay reproduces the sealed canon (the
Coordinator qualifies the engagement, the scouts cite the consented/topic-fit slice
and the open window; the post announces Pro → $34, carrying kalai's cleared words)
and never presents a forbidden value (0.62 / 0.81) as canon. **Live** is the
product; the replay is the net that lets the whole flywheel demo creds-free and
survive a 429 mid-demo — the orchestration (Parallel / escalate / HITL / ledger /
A2A) is fully real either way.
