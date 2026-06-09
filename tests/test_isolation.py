"""saakshe.tests.test_isolation — per-user multi-tenancy (spec §7.6).

The contract: a flywheel run bound to user A reads + writes ONLY A's store, and
user B is byte-for-byte untouched — even though the closing manas.learn, the
kalai/kural org reads and the corpus grounding all go through module-global call
sites. This is the test that proves the request-scoped ``current_store()`` seam
(not just a balance check) — a full two-user flywheel, asserting B's pack/facts/
connection state never move.
"""

from __future__ import annotations

import pytest

from common import project
from common.project import ProjectStore
from common.stream import EventStream
import orchestrator

A_FACTS = [
    {"claim": "Pro list price is $29/mo today.", "source": "README.md"},
    {"claim": "We grandfather existing subscribers on any price change.", "source": "docs/trust.md"},
]


@pytest.fixture
def alice_and_bob(_isolate_store):
    """A grounded (connected + a committed pack) + B empty — two distinct tenants."""
    a = ProjectStore(user="iso_alice")
    a.reset()
    a.add_connection("github", "git@github.com:alice/app.git", {"mechanism": "ssh"})
    a.set_org(name="Alice Co", kind="small product", one_liner="for makers")
    a.commit_pack(A_FACTS, ["plain, warm"], ["no dark patterns"], note="seed A")
    b = ProjectStore(user="iso_bob")
    b.reset()
    yield a, b
    a.reset()
    b.reset()


async def test_flywheel_bound_to_A_never_touches_B(alice_and_bob):
    a, b = alice_and_bob
    assert a.is_grounded() and a.version == "v1"
    assert not b.is_connected() and b.version == "v0"

    stream = EventStream()
    started = await orchestrator.start(
        question="Should we raise the Pro price?", stream=stream, store=a)
    rid = started["run_id"]
    await orchestrator.approve(rid, "g1", stream=stream, store=a)
    g2 = await orchestrator.approve(rid, "g2", stream=stream, store=a)
    assert g2["status"] == "completed"

    # Reload both from disk: A's memory ticked (manas.learn wrote to A); B untouched.
    a_re = ProjectStore(user="iso_alice")
    b_re = ProjectStore(user="iso_bob")
    assert a_re.version != "v0", "A's pack must have ticked — the run wrote to A"
    assert b_re.version == "v0", "B's version must NOT move — isolation breach"
    assert not b_re.is_connected(), "B must stay unconnected"
    assert b_re.all_facts() == [], "B must have no facts — A's facts must not leak"
    # The global founder store is also untouched (the run was bound to A, not STORE).
    assert project.STORE.version == "v0"


def test_corpus_grounding_resolves_the_bound_store(alice_and_bob):
    """manas.ground's deep read (corpus.context_pack) must follow the bound store —
    A grounded, B ungrounded, and B never sees A's facts."""
    from manas.tools import corpus

    tok = project.set_current_store(a := alice_and_bob[0])
    try:
        assert corpus.context_pack("pricing").grounded is True
    finally:
        project.reset_current_store(tok)

    tok = project.set_current_store(b := alice_and_bob[1])
    try:
        cp = corpus.context_pack("pricing")
        assert cp.grounded is False and cp.facts == []
    finally:
        project.reset_current_store(tok)


def test_current_store_defaults_to_global_when_unbound():
    """Unbound (the 135 demo tests + every existing call site) → the global STORE,
    so demo behaviour is byte-identical."""
    assert project.current_store() is project.STORE
