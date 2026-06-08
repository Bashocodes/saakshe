"""manas deterministic test suite.

Every test runs in demo mode (SAAKSHE_MODE=demo) with no live credentials: the
full ADK orchestration runs (Mind-Keeper route → ParallelAgent imbibers → Curator
LoopAgent → commit), only LLM token generation is replayed. These tests pin
manas's *safety property* — the deterministic groundedness threshold, the refusal
to commit a contradictory memory, and the Founder-Voice out-of-corpus refusal
contract — so a model can never talk the curator past the bar or fabricate a
founder opinion.
"""
