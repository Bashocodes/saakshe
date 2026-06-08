"""kural deterministic test suite.

Every test runs in demo mode (SAAKSHE_MODE=demo) with no live credentials: the
full ADK pipeline (Coordinator → ParallelAgent research → Writer → Claim-Judge
loop → publish gate) runs, only LLM token generation is replayed. These tests pin
the mouth's *safety property* — the numeric Claim-Judge gate, the bounded rewrite
rollback, the send eligibility/value-cap before_tool gate, and the no-double-send
ledger — so a model can never talk the mouth past the fact-check bar, blast an
unconsented list, or publish twice.
"""
