"""manas — checked-in ADK eval set.

A regression set of memory-grounding cases encoded in the google-adk ``EvalSet``
schema (adk >= 1.34). ``test_eval.py`` points ``AgentEvaluator.evaluate`` at
``evalset.json`` and grades each case on the groundedness-with-refusal rubric
track (every committed claim cites a source & is non-contradictory; out-of-corpus
is refused, never fabricated) at threshold 0.80. It runs for real only with live
creds (SAAKSHE_MODE=live + Vertex ADC); see the module docstring in test_eval.py.
"""
