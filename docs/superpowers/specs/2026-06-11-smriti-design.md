# smriti — temporal decision memory + recency-weighted outcomes

**Date:** 2026-06-11 · **Status:** approved direction (founder: "use that and integrate
that cleanly freshly in our own way") · **Inspiration:** mnemosyne's TripleStore
valid-from/until version chains and recency decay — lifted as *techniques*, zero
dependency added.

## Problem

1. Decisions are remembered as flat facts (`"Decided: …" · source: founder decision · today`).
   Two runs deciding the same question leave two contradictory "current" rulings; arivu's
   chamber has no precedent line to cite ("we already ruled on this, on day N").
2. Outcomes (kural.measure → manas.learn) carry no observation time. Grounding picks
   `facts[:8]` — pack order, so yesterday's numbers can lose the bundle seat to month-old ones.

## Doctrine (saakshe's own way — non-negotiable)

- **No new storage.** Temporal keys ride the existing cited-fact dicts through BOTH stores
  (file + Supabase store facts as JSON; extra keys survive verbatim).
- **Nothing decays away, nothing is deleted.** Decay only weights *selection into grounding
  bundles*. A superseded decision stays in memory, closed with `valid_until` +
  `superseded_by` — the citation chain, not an erasure.
- **Deterministic triggers only.** Supersede fires on same normalized *subject* (the question
  asked, else the claim's content words) — code, never model judgment. Mirrors `manas/doubts.py`.
- **Fail-soft.** A smriti error must never break `learn()` or a grounding fetch.

## Module: `common/smriti.py` (pure functions over fact dicts)

```
HALFLIFE_HOURS                         # env SAAKSHE_SMRITI_HALFLIFE_HOURS, default 168
subject_of(text) -> str               # sha1[:8] of lowercase content words (stopwords dropped)
decision_fact(claim, *, question="", source="", now=None) -> dict
fold_decision(facts, claim, *, question="", source="", now=None) -> list[dict]
stamp_outcomes(results, now=None) -> list[dict]      # + kind:"outcome", observed_at
outcome_weight(fact, *, now=None, halflife_hours=None) -> float   # 0.5^(age_h/halflife)
precedents(facts, now=None) -> list[dict]            # OPEN decisions, newest first, chain depth
precedents_text(facts, *, limit=4, now=None) -> str  # one citable line for prompts
select_facts(facts, *, limit=8, now=None, halflife_hours=None) -> list[dict]
```

Decision fact shape (added keys): `kind:"decision" · subject · sid:"d-<sha8>" ·
valid_from:iso · valid_until:None|iso · superseded_by:None|sid · asked:<question ≤140>`.
`fold_decision` closes every OPEN same-subject decision (valid_until=now,
superseded_by=new sid) then appends the new fact — the version chain.

`select_facts` returns the bundle seats: outcomes by recency weight desc, then plain facts
in pack order. **Decisions are excluded** — they travel on the dedicated `precedents` line,
so a dead ruling can never be cited as evidence and a live one is named as a ruling.

## Integration seams (3 files)

1. `manas/runner.py · learn()` — decision branch folds via `fold_decision` (claim strings
   byte-preserved: `"Decided: {decision}"` / `"A decision was committed today."`); results
   branch stamps via `stamp_outcomes`.
2. `orchestrator.py · line ~333` — pass the run's question: `{"decision": …, "question": state.question}`
   (the deterministic supersede subject).
3. `arivu/arivu/tools/grounding.py · _real_memory_section()` — `facts[:8]` →
   `smriti.select_facts(...)`; add `section["precedents"] = smriti.precedents_text(...)`
   when non-empty (renders automatically through `grounding_text`'s kvs join).
   Imported inside the function, try/except — an import failure degrades to today's behavior.

`kural/grounding.py` passes the whole pack already — riders flow, no change.

## Testing

- `common/tests/test_smriti.py` — fold/supersede chain, determinism (injected `now`),
  stamp, weight halflife math, select ordering + decision exclusion, precedents text.
- `manas/tests` — learn() same-question twice → second supersedes first; results stamped.
- `arivu/tests/test_live_grounding.py` — memory section carries precedents + weighted facts.

## Out of scope (named, deliberate)

Embeddings/semantic recall (revisit when a real pack outgrows the context window) ·
cockpit/grasped chain UI (follow-up) · witness cross-session memory · the mnemosyne package itself.
