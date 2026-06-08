"""kalai deterministic test suite.

Every test runs in demo mode (SAAKSHE_MODE=demo) with no live credentials: the
full ADK studio orchestration runs (Creative Director → Parallel(Designer, Copy)
→ Brand-Fidelity loop → fail-closed Compliance gate), only LLM token generation is
replayed. These tests pin the studio's *safety property* — the Brand-Fidelity loop
exits exactly on the numeric threshold, compliance is fail-closed (a planted-unsafe
brief is BLOCKED with no handoff), and kalai NEVER returns channel keys / never
publishes — so a model can never talk the studio past the brand bar or ship an
unsafe master.
"""
