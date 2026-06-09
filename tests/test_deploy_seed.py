"""The demo seed — the file-store pack baked into the deploy image.

The Cloud Run demo boots GROUNDED: the Dockerfile copies ``deploy/seed/
project_founder.json`` into the container's ``~/.saakshe`` so a visitor lands
on a connected, grounded company instead of an empty connect gate. A restart
resets the container back to this seed (the demo self-heals). These tests pin
the contract: the seed parses, and a fresh ProjectStore booted on it reports
connected + grounded with real cited facts.
"""

import json
import shutil
from pathlib import Path

import common.project as project

SEED = Path(__file__).resolve().parents[1] / "deploy" / "seed" / "project_founder.json"


def test_seed_exists_and_has_a_grounded_shape():
    data = json.loads(SEED.read_text())
    assert data["org"]["name"], "seed must name the demo company"
    company = data["packs"]["company"]
    assert company["facts"], "seed must carry cited facts"
    assert all(f.get("claim") and f.get("source") for f in company["facts"])
    assert data["connections"], "seed must show its real sources"


def test_seed_boots_a_grounded_store(tmp_path, monkeypatch):
    shutil.copy(SEED, tmp_path / "project_founder.json")
    monkeypatch.setattr(project, "_DIR", tmp_path)
    store = project.ProjectStore("founder")
    status = store.status_dict()
    assert status["connected"] is True
    assert status["grounded"] is True
    assert status["fact_count"] > 0
    assert store.org_for_flywheel()["name"] == status["org"]["name"]


def test_dockerfile_bakes_the_seed():
    dockerfile = (SEED.parents[2] / "Dockerfile").read_text()
    assert "deploy/seed/project_founder.json" in dockerfile
    assert "/root/.saakshe" in dockerfile
