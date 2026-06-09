"""kural deterministic test suite.

Every test runs in demo mode (SAAKSHE_MODE=demo) with no live credentials: the
full ADK pipeline (Coordinator → ParallelAgent research → publish gate) runs, only
LLM token generation is replayed. These tests pin the mouth's *safety property* —
that kural carries kalai's cleared master untouched (authoring is retired), the send
eligibility/value-cap before_tool gate, and the no-double-send ledger — so a model
can never make the mouth re-author words, blast an unconsented list, or publish twice.
"""
