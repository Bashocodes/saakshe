"""kural — checked-in ADK eval set.

A regression set of outreach/claim cases encoded in the google-adk ``EvalSet``
schema. ``test_eval.py`` points ``AgentEvaluator.evaluate`` at ``evalset.json``
and grades each case on two rubric tracks — outreach quality (founder voice,
grounded, names the trade-off) and claim soundness (the claim_support >= 0.80
fact-check gate). It runs for real only with live creds (SAAKSHE_MODE=live +
Vertex ADC); see the module docstring in ``test_eval.py``.
"""
