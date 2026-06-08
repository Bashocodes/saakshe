"""arivu deterministic test suite.

Every test here runs in demo mode (ARIVU_MODE=demo) with no live credentials:
the full ADK orchestration runs, only LLM token generation is replayed. These
tests pin the chamber's *safety property* — the deterministic thresholds and the
billing-safe executor — so a model can never talk the chamber past a numeric bar
or into a silent price/revenue write.
"""
