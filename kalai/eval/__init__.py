"""kalai — checked-in ADK eval set.

A brand-grade regression set of PAST launch briefs, encoded in the google-adk
``EvalSet`` schema. ``test_eval.py`` points ``AgentEvaluator.evaluate`` at
``evalset.json`` and grades each case on a brand-fidelity rubric @0.80 (the
LLM-judge threshold — distinct from the in-loop FIDELITY_THRESHOLD of 8.5, which
is the deterministic loop bar). It runs for real only with live creds
(SAAKSHE_MODE=live + Vertex ADC); see the module docstring in ``test_eval.py``.
"""
