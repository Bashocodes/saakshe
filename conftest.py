"""Test isolation for the connected-project store.

The whole company reads ONE ``common.project.STORE``. Tests must not leak a
connection or a Context Pack version into each other (or onto the developer's real
~/.saakshe), so this:
  * points the store at a throwaway tmp dir (set BEFORE common.project imports), and
  * resets the store to empty before and after every test.

It also offers a ``grounded_company`` fixture: an obviously-synthetic, brand-free
company (NO real brand, NO Sundara) for the tests that need manas already grounded.
The product itself is always empty until a real source is connected; this fixture
just stands in for that connect so a unit test can exercise the grounded path.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("SAAKSHE_MODE", "demo")
os.environ.setdefault("SAAKSHE_PROJECT_DIR", tempfile.mkdtemp(prefix="saakshe_pytest_"))

import pytest

from common import project

# A synthetic grounded company — brand-free, covers the dimensions manas needs.
_SYNTH_FACTS = [
    {"claim": "Pro list price is $29/mo today.", "source": "README.md"},
    {"claim": "We grandfather existing subscribers on any price change.", "source": "docs/trust.md"},
    {"claim": "Contribution margin holds at 71%.", "source": "docs/econ.md"},
    {"claim": "The product is for independent makers and small teams.", "source": "homepage"},
]
_SYNTH_VOICE = ["plain and warm, never hypey"]
_SYNTH_BRAND = ["honor grandfathering", "no dark-pattern urgency"]


@pytest.fixture(autouse=True)
def _isolate_store():
    project.STORE.reset()
    yield
    project.STORE.reset()


@pytest.fixture(autouse=True)
def _drain_rate_buckets():
    """Every TestClient request shares one client IP, so the per-IP token buckets
    on /api/saakshe/ask + /api/hero/run would otherwise leak 429s across tests."""
    yield
    try:
        from service.app import _BUCKETS
        _BUCKETS.clear()
    except Exception:  # noqa: BLE001 — service may not be importable in unit suites
        pass


@pytest.fixture
def grounded_company(_isolate_store):
    """A connected + grounded synthetic company (stands in for a real connect)."""
    project.STORE.add_connection("github", "git@github.com:example/app.git", {"mechanism": "ssh"})
    project.STORE.add_connection("website", "https://example.test")
    project.STORE.set_org(name="Example Co", kind="small subscription product",
                          one_liner="for independent makers")
    project.STORE.commit_pack(_SYNTH_FACTS, _SYNTH_VOICE, _SYNTH_BRAND, note="test seed")
    return project.STORE
