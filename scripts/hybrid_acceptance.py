"""Local hybrid acceptance: a full flywheel through the REAL Supabase store + event
stream + credit RPCs (scripted models, creds-free) for a synthetic tenant — proving
the multi-tenant credit-gated path end-to-end against ref mttlgjztpkzcklbiqkxj.

Run:  SAAKSHE_STORE=supabase SAAKSHE_SUPABASE_URL=https://mttlgjztpkzcklbiqkxj.supabase.co \
      SAAKSHE_MODE=demo PYTHONPATH=. ./.venv/bin/python scripts/hybrid_acceptance.py
(the service_role key is read from ~/.saakshe_supabase_key)
"""

from __future__ import annotations

import asyncio
import sys

from common import credits, project, supastore
from common.supastream import SupabaseEventStream
import orchestrator

# user_id = the JWT sub (a uuid) in production — valid for both the text-keyed store
# and the uuid-keyed credit tables. Synthetic uuids here, purged on cleanup.
UID = "aCCe7700-0000-4000-8000-00000000acc7".replace("aCCe7700", "acce7700")
OTHER_UID = "b0b0b0b0-0000-4000-8000-00000000b0b0"
FACTS = [{"claim": "Pro is $29/mo.", "source": "README"},
         {"claim": "We grandfather subscribers.", "source": "docs/trust"}]


def ok(label, cond):
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        raise SystemExit(f"ACCEPTANCE FAILED: {label}")


async def main():
    assert supastore.available(), "no service key / URL — set SAAKSHE_SUPABASE_URL + ~/.saakshe_supabase_key"

    store = supastore.SupabaseStore(UID)
    stream = SupabaseEventStream(UID, client=store)

    import httpx
    _h = {"apikey": store.key, "Authorization": f"Bearer {store.key}"}
    def purge(u):
        for t in ("transactions", "accounts"):
            httpx.request("DELETE", f"{store.url}/rest/v1/{t}?user_id=eq.{u}", headers=_h)
    purge(UID); purge(OTHER_UID)        # idempotent: clear any prior run's ledger
    store.reset()                       # clean slate (also clears this user's events/gates)

    print("1) signup grant (real RPC)")
    bal = credits.grant_signup(UID, "accept@test", is_owner=False)
    ok(f"granted {bal} credits", bal == credits.SIGNUP_GRANT)

    print("2) ground the tenant's company (real store writes)")
    store.add_connection("github", "git@github.com:x/app.git", {"mechanism": "ssh"})
    store.set_org(name="Accept Co", kind="product", one_liner="for makers")
    store.commit_pack(FACTS, ["warm"], ["no urgency"], note="seed")
    ok("store grounded", store.is_grounded())
    v_before = store.version

    print("3) spend for a flywheel run (real RPC)")
    spend_key = "accept_run_1"
    bal = credits.spend(UID, credits.cost("flywheel_run"), "flywheel run", spend_key)
    ok(f"debited to {bal}", bal == 100 - credits.cost("flywheel_run"))

    print("4) run the full flywheel bound to the Supabase store+stream (events persist)")
    started = await orchestrator.start(question="Should we raise the Pro price?", stream=stream,
                                       store=store, user_id=UID, spend_idem_key=spend_key, charged=True)
    rid = started["run_id"]
    ok("awaiting gate 1", started["status"] == "awaiting_approval")
    g1 = await orchestrator.approve(rid, "g1", stream=stream, store=store)
    ok("awaiting gate 2", g1["status"] == "awaiting_approval")
    g2 = await orchestrator.approve(rid, "g2", stream=stream, store=store)
    ok("flywheel completed", g2["status"] == "completed")

    print("5) the run persisted to the REAL events table (tenant-scoped)")
    rows = stream.rows(0)
    ok(f"{len(rows)} events persisted", len(rows) >= 10)
    ok("manas.learn ticked the pack", store.version != v_before)
    ok("balance unchanged after a successful run", credits.balance(UID) == 80)

    print("6) refund-on-failure + claim release (real RPCs)")
    credits.spend(UID, credits.cost("flywheel_run"), "run 2", "accept_run_2")          # 60
    ok("debited to 60", credits.balance(UID) == 60)
    credits.refund(UID, credits.cost("flywheel_run"), "fail", "accept_run_2", "accept_run_2:refund")  # 80
    ok("refunded to 80", credits.balance(UID) == 80)
    credits.spend(UID, credits.cost("flywheel_run"), "retry 2", "accept_run_2")          # 60 (re-charged)
    ok("retry re-charged to 60 (claim released)", credits.balance(UID) == 60)

    print("7) insufficient → OutOfCredits (HTTP 402 at the route)")
    raised = False
    try:
        credits.spend(UID, 9999, "too big", "accept_big")
    except credits.OutOfCredits as exc:
        raised = True
        ok(f"OutOfCredits carries balance {exc.balance}", exc.balance == 60)
    ok("insufficient raised", raised)

    print("8) cross-tenant isolation: a DIFFERENT user can't read this stream")
    other = SupabaseEventStream(OTHER_UID, client=supastore.SupabaseStore(OTHER_UID))
    ok("other tenant sees none of this run's events", other.rows(0) == [])

    print("cleanup")
    store.reset()
    # purge the synthetic account + ledger so prod data stays clean
    import httpx
    h = {"apikey": store.key, "Authorization": f"Bearer {store.key}"}
    for u in (UID, OTHER_UID):
        httpx.request("DELETE", f"{store.url}/rest/v1/transactions?user_id=eq.{u}", headers=h)
        httpx.request("DELETE", f"{store.url}/rest/v1/accounts?user_id=eq.{u}", headers=h)
    print("\nHYBRID ACCEPTANCE: ALL CHECKS PASSED ✓")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as e:
        print(e); sys.exit(1)
