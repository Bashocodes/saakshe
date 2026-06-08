"""arivu — checked-in ADK eval set.

A board-grade regression set of PAST founder decisions, encoded in the
google-adk `EvalSet` schema (adk >= 1.34). `test_eval.py` points
`AgentEvaluator.evaluate` at `evalset.json` and grades each case on two rubric
tracks — verdict quality and prosecution soundness (the defensibility >= 0.80
hard gate). It runs for real only with live creds (ARIVU_MODE=live + Vertex
ADC); see the module docstring in `test_eval.py`.
"""
