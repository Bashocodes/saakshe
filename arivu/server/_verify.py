"""Inline TestClient check for the arivu live bridge (no real server, no creds).

Run from the project root:
    ARIVU_MODE=demo python -m server._verify
or:
    ARIVU_MODE=demo python server/_verify.py
"""

from fastapi.testclient import TestClient

from server.app import app

client = TestClient(app)

# health
h = client.get("/api/arivu/health")
assert h.status_code == 200, h.status_code
hb = h.json()
assert hb["mode"] == "demo", hb["mode"]
assert "models" in hb and isinstance(hb["models"], dict), hb
print("health      :", hb["mode"], "| models.mode =", hb["models"]["mode"])

# agent-card (no agent-card.json present → inline fallback)
ac = client.get("/api/arivu/agent-card")
assert ac.status_code == 200, ac.status_code
acb = ac.json()
assert acb.get("name") == "arivu", acb
assert acb.get("skills"), acb
print("agent-card  : name =", acb["name"], "| skills =", len(acb["skills"]))

# run
r = client.post("/api/arivu/run", json={})
assert r.status_code == 200, r.status_code
rb = r.json()
run_id = rb["run_id"]
assert rb["gate_status"] == "awaiting_approval", rb["gate_status"]
assert rb["transcript"] and len(rb["transcript"]) > 0, "transcript empty"
assert rb["survived"] is True, rb["survived"]
print(
    "run         :", run_id,
    "| gate =", rb["gate_status"],
    "| survived =", rb["survived"],
    "| defensibility =", rb["defensibility"],
    "| transcript lines =", len(rb["transcript"]),
)

# approve (dry-run)
a = client.post("/api/arivu/approve", json={"run_id": run_id})
assert a.status_code == 200, a.status_code
ab = a.json()
res = ab["result"]
assert res["dry_run"] is True, res["dry_run"]
url = res["resolution"]["url"]
assert url, "resolution url missing"
assert url.startswith("https://example.com/docs/draft/"), url
# executor.execute() advances the gate to "executed" on a successful run.
assert ab["gate_status"] == "executed", ab["gate_status"]
print(
    "approve     : gate =", ab["gate_status"],
    "| dry_run =", res["dry_run"],
    "| commit.flag =", res["commit"]["flag"],
)
print("            : resolution url =", url)

# unknown run_id → 404
nf = client.post("/api/arivu/approve", json={"run_id": "nope"})
assert nf.status_code == 404, nf.status_code
print("404 unknown : status =", nf.status_code)

print("\nALL CHECKS PASSED")
