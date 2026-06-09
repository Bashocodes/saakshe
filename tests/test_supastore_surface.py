"""saakshe.tests.test_supastore_surface — SupabaseStore ⇄ ProjectStore parity.

A STRUCTURAL contract test (zero network): the Supabase store must expose every
public method/attribute the file ProjectStore does, with compatible signatures, so
the orchestrator / manas / corpus / service call either one unchanged. The live
read/write behaviour is proven separately in the hybrid acceptance run.
"""

from __future__ import annotations

import inspect

from common.project import ProjectStore
from common.supastore import SupabaseStore


# Methods the running system calls on the store, with the positional params each
# caller passes. SupabaseStore must accept at least these.
REQUIRED_METHODS = {
    "add_connection": ["kind", "ref"],
    "set_status": ["status"],
    "set_org": ["name", "kind", "one_liner"],
    "commit_pack": ["facts", "voice_rules", "brand_rules"],
    "pack": ["topic"],
    "all_facts": [],
    "set_questions": ["questions"],
    "open_questions": [],
    "blocking_questions": [],
    "answer_question": ["qid", "answer"],
    "is_connected": [],
    "is_grounded": [],
    "org_for_flywheel": [],
    "status_dict": [],
    "reset": [],
}

# Attributes/properties the system reads off the store.
REQUIRED_ATTRS = ["version", "ingest_status", "org", "connections", "user", "user_id"]


def _params(cls, name):
    sig = inspect.signature(getattr(cls, name))
    return [p for p in sig.parameters if p != "self"]


def test_supabase_store_has_every_required_method():
    for name in REQUIRED_METHODS:
        assert callable(getattr(SupabaseStore, name, None)), f"SupabaseStore missing method {name!r}"
        # ProjectStore has it too (sanity: the contract is anchored to the file store).
        assert callable(getattr(ProjectStore, name, None)), f"ProjectStore missing method {name!r}"


def test_required_positional_params_are_accepted():
    for name, needed in REQUIRED_METHODS.items():
        got = _params(SupabaseStore, name)
        for p in needed:
            assert p in got, f"SupabaseStore.{name} must accept {p!r}; signature has {got}"


def test_commit_pack_keyword_only_extras_match():
    got = _params(SupabaseStore, "commit_pack")
    for kw in ("topic", "note", "groundedness"):
        assert kw in got, f"SupabaseStore.commit_pack must accept keyword {kw!r}"


def test_set_org_params_have_defaults():
    sig = inspect.signature(SupabaseStore.set_org)
    for p in ("name", "kind", "one_liner"):
        assert sig.parameters[p].default == "", f"set_org.{p} should default to ''"


def test_required_attributes_present():
    for name in REQUIRED_ATTRS:
        assert hasattr(SupabaseStore, name) or name in ("user", "user_id"), \
            f"SupabaseStore should expose {name!r}"


def test_version_ingest_status_org_connections_are_properties():
    for name in ("version", "ingest_status", "org", "connections"):
        attr = inspect.getattr_static(SupabaseStore, name)
        assert isinstance(attr, property), f"SupabaseStore.{name} should be a property"


def test_constructor_keys_on_user_id():
    sig = inspect.signature(SupabaseStore.__init__)
    assert "user_id" in sig.parameters, "SupabaseStore must key on user_id"
