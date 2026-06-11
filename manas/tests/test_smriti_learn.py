"""learn() writes TEMPORAL memory — decisions chain (smriti), results get an
observation stamp. The remembered claim strings stay byte-identical; only the
chain/stamp keys ride along on the same cited-fact dicts."""

from __future__ import annotations

from common import project
from common.stream import EventStream

from manas import runner


def _decisions():
    return [f for f in project.STORE.all_facts()
            if isinstance(f, dict) and f.get("kind") == "decision"]


async def test_second_ruling_on_the_same_question_supersedes_the_first():
    q = "Should we move the Pro tier to $34?"
    await runner.learn(EventStream(), "r1", {"decision": "Raise Pro to $34", "question": q})
    await runner.learn(EventStream(), "r2", {"decision": "Hold Pro at $29", "question": q})
    ds = _decisions()
    assert len(ds) == 2
    old = next(d for d in ds if d["claim"] == "Decided: Raise Pro to $34")
    new = next(d for d in ds if d["claim"] == "Decided: Hold Pro at $29")
    # the chain: the old ruling is CLOSED, never deleted
    assert old["valid_until"] is not None and old["superseded_by"] == new["sid"]
    assert new["valid_until"] is None


async def test_rulings_on_different_questions_coexist():
    await runner.learn(EventStream(), "r1",
                       {"decision": "Raise Pro to $34",
                        "question": "Should we move the Pro tier to $34?"})
    await runner.learn(EventStream(), "r2",
                       {"decision": "Launch on LinkedIn",
                        "question": "Should we launch on LinkedIn?"})
    assert all(d["valid_until"] is None for d in _decisions())


async def test_results_are_stamped_as_outcomes():
    results = [{"claim": "Published x/1 on x: reach 1240 · replies 3.",
                "source": "channel stats · x/1"}]
    await runner.learn(EventStream(), "r-results", {"results": results})
    fact = next(f for f in project.STORE.all_facts()
                if f.get("claim") == "Published x/1 on x: reach 1240 · replies 3.")
    assert fact["kind"] == "outcome" and fact.get("observed_at")


async def test_decision_without_question_still_chains_on_its_own_words():
    await runner.learn(EventStream(), "r1", {"decision": "Raise Pro to $34"})
    ds = _decisions()
    assert len(ds) == 1 and ds[0]["kind"] == "decision"
    assert ds[0]["claim"] == "Decided: Raise Pro to $34"  # byte-identical claim
