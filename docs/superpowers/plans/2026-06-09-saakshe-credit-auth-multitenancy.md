# saakshe — Credit-gated, Multi-tenant Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This build is driven by the **ultracode Workflow** orchestration (per the user's directive), phase-by-phase, each phase TDD'd and verified before the next.

**Goal:** Add Supabase Google login + per-user multi-tenancy (per-user Supabase store + a `SupabaseEventStream`) + a production-grade credit system (100 free credits, env-configurable costs, atomic idempotent spend/refund with refund-releases-claim + ledger + refund-on-failure) + manas live-edits charged & persisted as `pending_changes` — to `~/Desktop/Working/saakshe`, keeping the 135 file-store/demo tests green and the tree ZERO-aikizi.

**Architecture:** A request-scoped store is bound via a `contextvars.ContextVar` (`common/project.current_store()`) so every deep library read (`corpus.py`, `manas`, `kalai`, `kural`, `witness`) resolves the authenticated user's `SupabaseStore` without threading a `store=` param through twelve functions — the unset default returns the global file `STORE`, so demo/tests are byte-identical. Money moves ONLY through three `SECURITY DEFINER`, service-role-only, idempotent Postgres functions (`saakshe_spend`/`saakshe_refund`/`saakshe_grant_signup`) mirrored from aikizi's proven pattern (claim-first dedup, `FOR UPDATE`, P0001 insufficiency, refund clamp + claim-release-via-rename), called from a `common/credits.py` wrapper that no-ops in demo. Auth is a FastAPI JWKS dependency (`common/auth.py`, PyJWT ES256).

**Tech Stack:** Python 3.10–3.13, FastAPI, httpx (PostgREST), PyJWT[crypto], Supabase (Postgres + Auth + Realtime, ref `mttlgjztpkzcklbiqkxj`), Cloud Run, vanilla-JS cockpit + `@supabase/supabase-js` (ESM CDN).

---

## Key design decisions (locked before build)

1. **Request-scoped store via `contextvars`, NOT param-threading.** `corpus.py:65/72/101`, `manas/runner.py:255/333`, `kalai/runner.py:60`, `kural/runner.py:50`, `kural/grounding.py:59`, `witness/telemetry.py:87`, `orchestrator.py:83` all read the module-global `project.STORE`. Threading `store=` through all of them is a large, error-prone diff that the spec's literal wording ("start/approve take store=") doesn't fully cover. Instead: add `project.current_store()` (returns the contextvar value or the global `STORE`) and swap those reads to it. `orchestrator.start/approve` ALSO keep an explicit `store=`/`stream=` param (spec-compliant, testable) defaulting to `current_store()`/`STREAM`. Unset contextvar ⇒ global file store ⇒ the 135 tests are untouched. `contextvars` propagate across `await`, `asyncio.gather`, and `asyncio.to_thread`, so the manas ingest threads inherit the right store.

2. **Flywheel spend idempotency key is CLIENT-SUPPLIED, never the server-random `run_id`.** `run_id = "fw_"+uuid4()` is random ⇒ keying spend on it double-charges on a retry; a pure content hash over-dedups two legitimately distinct runs. The cockpit generates a stable `idem_key` (a per-attempt nonce) and sends it on `POST /api/hero/run`; the wrapper passes it to `spend` and reuses it as `p_spend_idem_key` on refund (which releases the claim so a deliberate retry re-charges). Reads/approve don't re-charge (spend is once per run, at start).

3. **The credit/auth wrapper is a true no-op in demo.** It short-circuits BEFORE any JWKS fetch or RPC when `config.mode() == "demo"` OR `SAAKSHE_STORE != "supabase"` OR the user is an owner. No pytest test uses `TestClient` (verified), so adding auth deps to routes cannot break the 135 tests.

4. **`SupabaseEventStream.emit` uses a per-run in-memory seq counter**, seeded once from `max(seq)` for resumed runs, then incremented locally — never `SELECT max(seq)` per emit (a run emits 30–60 events). Per-event PostgREST inserts are the correctness baseline; batching is a flagged production follow-up.

5. **saakshe SQL mirrors aikizi's pattern but is single-balance** (no packs/entitlements): `accounts.balance` only, `transactions(user_id, idem_key)` unique. Study aikizi (`/Users/cyberyogi/Projects/aikizi`, reference only); rename everything `saakshe_*`; keep the tree aikizi-free.

---

## File structure

**New files:**
- `supabase/migrations/20260609_000001_credit_accounts.sql` — accounts + transactions + pending_changes tables, RLS, indexes.
- `supabase/migrations/20260609_000002_credit_functions.sql` — `saakshe_spend`/`saakshe_refund`/`saakshe_grant_signup`, REVOKE/GRANT, `accounts_block_balance_writes` trigger.
- `common/auth.py` — JWKS fetch/cache, JWT verify, `get_current_user`/`optional_user` deps, `User` dataclass, owner check.
- `common/credits.py` — cost map (env), `spend()`/`refund()`/`grant_signup()`/`balance()` over the RPCs, the `charge()` context-manager wrapper, 402 helper, demo no-op.
- `common/supastream.py` — `SupabaseEventStream(EventStream)`.
- `common/pending.py` — `PendingChanges(user_id)` store over the `pending_changes` table.
- `web/auth-callback.html` — completes the OAuth round-trip.
- `tests/test_auth.py`, `tests/test_credits.py`, `tests/test_supastream.py`, `tests/test_supastore_surface.py`, `tests/test_isolation.py`, `tests/test_credit_routes.py`, `tests/test_pending.py` — new test modules.

**Modified files:**
- `common/project.py` — add `current_store()` + `set_current_store()` (contextvar) + `store_for(user_id)`.
- `common/supastore.py` — reconcile public surface to `ProjectStore` exactly.
- `common/stream.py` — extract a tiny `_GateProjection` mixin reuse (no behavior change) so `SupabaseEventStream` shares `open_gates` derivation if reading from memory; otherwise leave as-is and override in the subclass.
- `manas/tools/corpus.py`, `manas/runner.py`, `kalai/runner.py`, `kural/runner.py`, `kural/grounding.py`, `witness/telemetry.py`, `orchestrator.py` — swap `project.STORE` reads → `project.current_store()`.
- `service/app.py` — auth deps, per-request store+stream binding, inject Supabase URL/anon key + balance bootstrap into cockpit, `/api/me`, `/auth/callback`, manas-edit + pending-change routes, credit wrapper on chargeable routes.
- `web/cockpit.html` — Supabase-JS sign-in, balance display, attach Bearer on live-console fetches, gate live actions on a session.
- `requirements.txt` — add `pyjwt[crypto]==2.10.1`.
- `deploy_cloudrun.sh` — add the new env vars.

---

## Phase 1 — Supabase migrations (main loop, MCP)

**Files:** Create the two `.sql` migrations in-repo AND apply them to ref `mttlgjztpkzcklbiqkxj` via the Supabase MCP `apply_migration`. Verify with `execute_sql` + `get_advisors`.

### Migration 1 — `20260609_000001_credit_accounts`

- [ ] **Step 1: Tables + RLS (deny-default).** Apply this SQL:

```sql
-- accounts: one balance row per authenticated user (user_id = auth.uid).
CREATE TABLE IF NOT EXISTS public.accounts (
  user_id    uuid PRIMARY KEY,
  email      text,
  balance    int NOT NULL DEFAULT 0 CHECK (balance >= 0),
  is_owner   boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- transactions: append-only ledger. UNIQUE(user_id, idem_key) gives idempotency.
CREATE TABLE IF NOT EXISTS public.transactions (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id       uuid NOT NULL,
  kind          text NOT NULL,                 -- 'spend' | 'refund' | 'grant'
  amount        int NOT NULL,                  -- signed: spend negative, grant/refund positive
  reason        text DEFAULT '',
  idem_key      text NOT NULL,
  balance_after int,
  ref           jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, idem_key)
);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON public.transactions(user_id, created_at DESC);

-- pending_changes: manas live-edits, immutable payload + status lifecycle.
CREATE TABLE IF NOT EXISTS public.pending_changes (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL,
  source_run_id  text DEFAULT '',
  entity_type    text NOT NULL,
  old_json       jsonb NOT NULL DEFAULT '{}'::jsonb,
  new_json       jsonb NOT NULL DEFAULT '{}'::jsonb,
  diff_json      jsonb NOT NULL DEFAULT '{}'::jsonb,
  changed_fields text[] NOT NULL DEFAULT '{}',
  status         text NOT NULL DEFAULT 'pending',  -- pending|applied|rejected|superseded
  review_status  text NOT NULL DEFAULT 'unreviewed',
  ai_model       text DEFAULT '',
  cost_credits   int NOT NULL DEFAULT 0,
  idem_key       text NOT NULL,
  error_text     text DEFAULT '',
  deleted        boolean NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now(),
  applied_at     timestamptz,
  reviewed_by    text DEFAULT '',
  UNIQUE (user_id, idem_key)
);
CREATE INDEX IF NOT EXISTS idx_pending_user ON public.pending_changes(user_id, created_at DESC);

ALTER TABLE public.accounts        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pending_changes ENABLE ROW LEVEL SECURITY;

-- Deny-default: NO policies for anon/authenticated that allow spend/refund inserts.
-- The backend uses service_role (bypasses RLS). authenticated may READ own rows only.
CREATE POLICY accounts_read_own ON public.accounts
  FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY tx_read_own ON public.transactions
  FOR SELECT TO authenticated USING (user_id = auth.uid());
-- Ledger: authenticated may NEVER insert spend/refund (defense-in-depth; service_role bypasses RLS).
CREATE POLICY tx_no_money_insert ON public.transactions
  FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid() AND kind NOT IN ('spend','refund','grant'));
CREATE POLICY pending_read_own ON public.pending_changes
  FOR SELECT TO authenticated USING (user_id = auth.uid());
```

- [ ] **Step 2: Verify** with `execute_sql`: `SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('accounts','transactions','pending_changes');` → 3 rows. Run `get_advisors(type=security)` → no new "RLS disabled" notices on these tables.

### Migration 2 — `20260609_000002_credit_functions`

- [ ] **Step 3: spend/refund/grant functions + trigger.** Apply (single-balance mirror of aikizi `spend_tokens_v3`/`refund_tokens_v2`):

```sql
-- saakshe_grant_signup: create the account + initial grant once (idempotent).
CREATE OR REPLACE FUNCTION public.saakshe_grant_signup(
  p_user_id uuid, p_email text, p_grant int, p_is_owner boolean DEFAULT false
) RETURNS int LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_balance int; v_inserted int;
BEGIN
  INSERT INTO accounts (user_id, email, balance, is_owner)
  VALUES (p_user_id, p_email, GREATEST(p_grant, 0), p_is_owner)
  ON CONFLICT (user_id) DO NOTHING;
  GET DIAGNOSTICS v_inserted = ROW_COUNT;
  IF v_inserted = 1 THEN
    INSERT INTO transactions (user_id, kind, amount, reason, idem_key, balance_after)
    VALUES (p_user_id, 'grant', GREATEST(p_grant,0), 'signup grant',
            'grant:'||p_user_id::text, GREATEST(p_grant,0))
    ON CONFLICT (user_id, idem_key) DO NOTHING;
  END IF;
  SELECT balance INTO v_balance FROM accounts WHERE user_id = p_user_id;
  RETURN COALESCE(v_balance, 0);
END; $$;

-- saakshe_spend: claim-first idempotent debit. Returns new balance. P0001 on insufficiency.
CREATE OR REPLACE FUNCTION public.saakshe_spend(
  p_user_id uuid, p_amount int, p_reason text, p_idem_key text
) RETURNS int LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_balance int; v_inserted int;
BEGIN
  IF p_amount IS NULL OR p_amount <= 0 THEN RAISE EXCEPTION 'invalid_amount' USING ERRCODE='P0001'; END IF;
  IF p_idem_key IS NULL OR length(p_idem_key)=0 THEN RAISE EXCEPTION 'missing_idem_key' USING ERRCODE='P0001'; END IF;

  -- Claim the idempotency key race-safely. Duplicate ⇒ short-circuit (no second charge).
  INSERT INTO transactions (user_id, kind, amount, reason, idem_key, ref)
  VALUES (p_user_id, 'spend', 0, p_reason, p_idem_key, jsonb_build_object('status','claiming'))
  ON CONFLICT (user_id, idem_key) DO NOTHING;
  GET DIAGNOSTICS v_inserted = ROW_COUNT;
  IF v_inserted = 0 THEN
    SELECT balance INTO v_balance FROM accounts WHERE user_id = p_user_id;
    RETURN COALESCE(v_balance, 0);
  END IF;

  -- Lock the account row, check funds.
  SELECT balance INTO v_balance FROM accounts WHERE user_id = p_user_id FOR UPDATE;
  IF v_balance IS NULL THEN RAISE EXCEPTION 'account_not_found' USING ERRCODE='P0001'; END IF;
  IF v_balance < p_amount THEN
    RAISE EXCEPTION 'INSUFFICIENT_CREDITS' USING ERRCODE='P0001';  -- rolls back the claim too
  END IF;

  UPDATE accounts SET balance = balance - p_amount, updated_at = now() WHERE user_id = p_user_id
    RETURNING balance INTO v_balance;
  UPDATE transactions SET amount = -p_amount, balance_after = v_balance,
         ref = jsonb_build_object('reason', p_reason)
    WHERE user_id = p_user_id AND idem_key = p_idem_key AND kind = 'spend';
  RETURN v_balance;
END; $$;

-- saakshe_refund: idempotent credit, clamps to recorded spend, RELEASES the spend claim.
CREATE OR REPLACE FUNCTION public.saakshe_refund(
  p_user_id uuid, p_amount int, p_reason text, p_spend_idem_key text, p_refund_idem_key text
) RETURNS int LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_balance int; v_inserted int; v_spend_amt int; v_clamped int;
BEGIN
  IF p_amount IS NULL OR p_amount <= 0 THEN RAISE EXCEPTION 'invalid_amount' USING ERRCODE='P0001'; END IF;
  IF p_refund_idem_key IS NULL OR length(p_refund_idem_key)=0 THEN RAISE EXCEPTION 'missing_idem_key' USING ERRCODE='P0001'; END IF;

  -- Claim the refund key FIRST. Duplicate ⇒ short-circuit.
  INSERT INTO transactions (user_id, kind, amount, reason, idem_key, ref)
  VALUES (p_user_id, 'refund', p_amount, p_reason, p_refund_idem_key,
          jsonb_build_object('spend_idem_key', p_spend_idem_key))
  ON CONFLICT (user_id, idem_key) DO NOTHING;
  GET DIAGNOSTICS v_inserted = ROW_COUNT;
  IF v_inserted = 0 THEN
    SELECT balance INTO v_balance FROM accounts WHERE user_id = p_user_id;
    RETURN COALESCE(v_balance, 0);
  END IF;

  -- Clamp to the recorded spend amount — never trust a client-claimed amount.
  IF p_spend_idem_key IS NOT NULL THEN
    SELECT -amount INTO v_spend_amt FROM transactions
      WHERE user_id = p_user_id AND kind='spend' AND idem_key = p_spend_idem_key LIMIT 1;
  END IF;
  v_clamped := LEAST(p_amount, COALESCE(v_spend_amt, p_amount));

  SELECT balance INTO v_balance FROM accounts WHERE user_id = p_user_id FOR UPDATE;
  IF v_balance IS NULL THEN RAISE EXCEPTION 'account_not_found' USING ERRCODE='P0001'; END IF;
  UPDATE accounts SET balance = balance + v_clamped, updated_at = now() WHERE user_id = p_user_id
    RETURNING balance INTO v_balance;
  UPDATE transactions SET amount = v_clamped, balance_after = v_balance
    WHERE user_id = p_user_id AND idem_key = p_refund_idem_key AND kind='refund';

  -- Release the spend's claim (rename, don't delete) so a deliberate retry re-charges.
  IF p_spend_idem_key IS NOT NULL THEN
    UPDATE transactions
      SET idem_key = idem_key || ':refunded:' || p_refund_idem_key,
          ref = COALESCE(ref,'{}'::jsonb) || jsonb_build_object('refunded_by', p_refund_idem_key, 'released_at', now())
      WHERE user_id = p_user_id AND kind='spend' AND idem_key = p_spend_idem_key;
  END IF;
  RETURN v_balance;
END; $$;

-- Lock account balance writes to service_role (defense-in-depth beyond the CHECK).
CREATE OR REPLACE FUNCTION public.accounts_block_balance_writes()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF NEW.balance IS DISTINCT FROM OLD.balance
     AND COALESCE(current_setting('request.jwt.claims', true)::jsonb->>'role','') <> 'service_role'
     AND current_user <> 'service_role' THEN
    RAISE EXCEPTION 'balance writes are service_role only' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_accounts_block_balance ON public.accounts;
CREATE TRIGGER trg_accounts_block_balance BEFORE UPDATE ON public.accounts
  FOR EACH ROW EXECUTE FUNCTION public.accounts_block_balance_writes();

-- Grants: service_role ONLY. Supabase auto-grants EXECUTE to anon+authenticated, so REVOKE explicitly.
REVOKE ALL ON FUNCTION public.saakshe_spend(uuid,int,text,text)              FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.saakshe_refund(uuid,int,text,text,text)        FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.saakshe_grant_signup(uuid,text,int,boolean)    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.saakshe_spend(uuid,int,text,text)           TO service_role;
GRANT EXECUTE ON FUNCTION public.saakshe_refund(uuid,int,text,text,text)     TO service_role;
GRANT EXECUTE ON FUNCTION public.saakshe_grant_signup(uuid,text,int,boolean) TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
```

- [ ] **Step 4: Verify the money path with a throwaway user** via `execute_sql` (then clean up):

```sql
-- grant → spend → idempotent re-spend → insufficient → refund → claim released
SELECT public.saakshe_grant_signup('00000000-0000-0000-0000-0000000000aa','t@test',100,false); -- 100
SELECT public.saakshe_spend('00000000-0000-0000-0000-0000000000aa',20,'run','k1');              -- 80
SELECT public.saakshe_spend('00000000-0000-0000-0000-0000000000aa',20,'run','k1');              -- 80 (idempotent)
SELECT public.saakshe_refund('00000000-0000-0000-0000-0000000000aa',20,'fail','k1','r1');       -- 100, releases k1
SELECT public.saakshe_spend('00000000-0000-0000-0000-0000000000aa',20,'retry','k1');            -- 80 (re-charged)
DELETE FROM transactions WHERE user_id='00000000-0000-0000-0000-0000000000aa';
DELETE FROM accounts     WHERE user_id='00000000-0000-0000-0000-0000000000aa';
```
Expected: 100, 80, 80, 100, 80. Confirm a `999999`-credit spend raises P0001.

- [ ] **Step 5: Commit** the two `.sql` files: `git add supabase/migrations && git commit -m "feat(db): credit accounts + idempotent spend/refund/grant functions + RLS"`.

---

## Phase 2 — `common/auth.py` (JWT/JWKS) + `pyjwt` dep

**Files:** Create `common/auth.py`, `tests/test_auth.py`. Modify `requirements.txt`.

- [ ] **Step 1: Add the dep** (main loop): append `pyjwt[crypto]==2.10.1` to `requirements.txt`, `./.venv/bin/pip install 'pyjwt[crypto]==2.10.1'`.

- [ ] **Step 2: Write failing tests** `tests/test_auth.py` — generate an ES256 keypair in-test, build a JWKS dict, monkeypatch `auth._fetch_jwks` to return it, and assert:
  - valid token → `User(user_id=sub, email, is_owner=...)`;
  - expired token → `AuthError`/401; bad signature → 401; missing `Bearer` → `optional_user` returns `None`, `get_current_user` raises 401;
  - `OWNER_EMAILS` match → `is_owner=True`;
  - token cache: two verifies of the same token call `_fetch_jwks` at most once.
  (Use `cryptography` to mint EC P-256 keys; encode JWK from public numbers — `cryptography` is already an aikizi-style transitive dep via `pyjwt[crypto]`.)

- [ ] **Step 3: Implement `common/auth.py`:**
  - `User` dataclass `{user_id: str, email: str, is_owner: bool}`.
  - `_jwks_url()` derives `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` from `SAAKSHE_SUPABASE_URL` (or `SUPABASE_JWKS_URL` override). `_issuer()` = `<url>/auth/v1`.
  - `_fetch_jwks()` httpx GET + in-memory cache (5 min TTL); `verify_token(token)` → use `jwt.PyJWKClient`-style: decode header → find kid → `jwt.decode(token, key, algorithms=["ES256","RS256"], audience="authenticated", issuer=_issuer(), options={"verify_aud": True})`. 30s verified-token cache keyed by token.
  - `get_current_user(request) -> User` (FastAPI dep): extract Bearer, `verify_token`, owner check vs `OWNER_EMAILS` env (comma-split, lowercased); raise `HTTPException(401)` on any failure.
  - `optional_user(request) -> Optional[User]`: returns `None` when no/invalid header (no raise).
  - `auth_enabled()` → `bool(SAAKSHE_SUPABASE_URL and anon configured)`; used by the wrapper to no-op.

- [ ] **Step 4: Run** `./.venv/bin/pytest tests/test_auth.py -v` → PASS. Run full root suite `./.venv/bin/pytest` → still green.

- [ ] **Step 5: Commit** `feat(auth): Supabase JWKS/JWT verification + current_user deps`.

---

## Phase 3 — `common/credits.py` (cost map + spend/refund wrapper)

**Files:** Create `common/credits.py`, `tests/test_credits.py`.

- [ ] **Step 1: Failing tests** `tests/test_credits.py` (mock the RPC layer — inject a fake `rpc(fn, params)` callable, no network):
  - `COSTS` reads env (`COST_FLYWHEEL_RUN` etc.) with the spec §6 defaults (20/20/10/15/15) and `SIGNUP_GRANT=100`.
  - `spend(user_id, amount, reason, idem_key)` calls `saakshe_spend` and returns the new balance.
  - insufficient (RPC raises P0001 `INSUFFICIENT_CREDITS`) → `OutOfCredits` exception carrying the current balance.
  - `refund(user_id, amount, reason, spend_idem_key, refund_idem_key)` calls `saakshe_refund`.
  - `charge(user, cost_key, idem_key, reason)` context manager: on clean exit → spent, balance debited; on an exception inside the block → calls refund with the same spend key + a derived `refund_idem_key` and re-raises a `TemporaryFailure` (classified by error CODE, per `feedback_aikizi_error_handling`); owner or demo ⇒ a no-op yield (no RPC).

- [ ] **Step 2: Implement `common/credits.py`:**
  - `COSTS = {"flywheel_run": _int("COST_FLYWHEEL_RUN",20), "connect_ingest": _int("COST_CONNECT_INGEST",20), "manas_edit": _int("COST_MANAS_EDIT",10), "kalai_make": _int("COST_KALAI_MAKE",15), "kural_engage": _int("COST_KURAL_ENGAGE",15)}`; `SIGNUP_GRANT = _int("SIGNUP_GRANT",100)`.
  - `_rpc(fn, params)` → POST `SAAKSHE_SUPABASE_URL/rest/v1/rpc/<fn>` with the service-role key (reuse `supastore._read_key()`), parse P0001 from PostgREST's `{"code":"P0001","message":...}` JSON → raise `OutOfCredits`/`CreditError`.
  - `spend/refund/grant_signup/balance` thin wrappers.
  - `charge(user, cost_key, *, idem_key, reason)` `@contextmanager`: if `user.is_owner` or `config.mode()=="demo"` or `os.environ.get("SAAKSHE_STORE")!="supabase"` → `yield {"charged":False}` and return. Else `spend(...)`; `try: yield {"charged":True}` ; `except Exception: refund(user.user_id, COSTS[cost_key], "internal failure — not charged", idem_key, idem_key+":refund"); raise`.
  - `out_of_credits_response(balance)` → 402 JSON helper.

- [ ] **Step 3: Run** `./.venv/bin/pytest tests/test_credits.py -v` → PASS; full suite green.

- [ ] **Step 4: Commit** `feat(credits): cost map + idempotent spend/refund wrapper with refund-on-failure`.

---

## Phase 4 — `common/supastream.py` + `supastore.py` reconcile (parallel-safe, separate files)

**Files:** Create `common/supastream.py`, `tests/test_supastream.py`; modify `common/supastore.py`, create `tests/test_supastore_surface.py`.

### 4a — `SupabaseEventStream`

- [ ] **Step 1: Failing tests** `tests/test_supastream.py` (inject a fake PostgREST client / in-memory list, no network):
  - `emit(run_id, source, agent, text, ...)` returns an `Event`-shaped object and persists a row; per-run `seq` increments 0,1,2 within a run and is independent across run_ids;
  - `rows(cursor)` round-trips emitted rows in seq order; `gate()`/`open_gates()`/`resolve_gate()` open→resolve derive correctly;
  - inherited `a2a`/`action`/`emit_transcript` call through `emit` (persist rows).

- [ ] **Step 2: Implement** `SupabaseEventStream(EventStream)`: `__init__(user_id, client=None)` keeps a `dict[run_id]->int` seq counter; override `emit` to compute seq locally (seed from `max(seq)` once per unseen run via `events_since`), build the `Event`, `INSERT` into `events`, return it; override `rows(cursor)`/`since` to read from `events`; override `gate`→also `upsert_gate`, `open_gates`/`resolve_gate`→`gates` table. Keep `cursor` as the max seq seen. Reuse `supastore.SupabaseStore`'s low-level `_get/_insert/_patch` (compose, don't duplicate — accept a `store` or build one).

- [ ] **Step 3: Run** `./.venv/bin/pytest tests/test_supastream.py -v` → PASS.

### 4b — `SupabaseStore` reconcile to `ProjectStore` surface

- [ ] **Step 4: Failing test** `tests/test_supastore_surface.py` — a structural/contract test (no network): assert `SupabaseStore` exposes every public method/attr the file `ProjectStore` does with compatible signatures: `add_connection(kind,ref,meta)->obj with .as_dict()/.kind/.ref/.meta`, `set_org(name=,kind=,one_liner=)`, `set_status(s)`, `commit_pack(facts,voice_rules,brand_rules,*,topic=,note=,groundedness=)->version:str`, `pack(topic)->ContextPack`, `all_facts()`, `set_questions(list)`, `open_questions()`, `blocking_questions()`, `answer_question(qid,answer)`, `is_connected()`, `is_grounded()`, `version`, `org_for_flywheel()`, `status_dict()`, `reset()`, and a `connections` iterable of objects with `.kind/.ref/.meta`. Use `inspect.signature` comparison against `project.ProjectStore`.

- [ ] **Step 5: Reconcile `common/supastore.py`:** change `commit_pack` to `(facts, voice_rules, brand_rules, *, topic=TOPIC, note="", groundedness=None) -> str` (generate `vN+1` from the project row internally, write the pack + tick `projects.version/grounded/status`); change `set_org` to `(name="",kind="",one_liner="")` merging into the `org` jsonb; make `add_connection` return a `Connection`-like object (import `project.Connection`); add `set_status`, `all_facts`, `pack`, `set_questions`, `blocking_questions`, a `connections` property returning `Connection` objects, `ingest_status` property (from `projects.status`). Map the file store's `EMPTY/CONNECTING/INGESTING/NEEDS_ANSWERS/GROUNDED` onto `projects.status`. Keep all existing chat/event/gate methods.

- [ ] **Step 6: Run** `./.venv/bin/pytest tests/test_supastore_surface.py -v` → PASS; full suite green.

- [ ] **Step 7: Commit** `feat(supabase): SupabaseEventStream + reconcile SupabaseStore to ProjectStore surface`.

> **Workflow note:** 4a and 4b are independent files ⇒ build them in parallel subagents; the surface test in 4b imports only `project`/`supastore`. Do NOT use worktree isolation (the in-tree `.venv` won't exist in a worktree).

---

## Phase 5 — Per-user threading (contextvar store) + isolation

**Files:** Modify `common/project.py`, `manas/tools/corpus.py`, `manas/runner.py`, `kalai/runner.py`, `kural/runner.py`, `kural/grounding.py`, `witness/telemetry.py`, `orchestrator.py`. Create `tests/test_isolation.py`.

- [ ] **Step 1: Failing isolation test** `tests/test_isolation.py` — using two in-memory file stores bound via the contextvar (point `SAAKSHE_PROJECT_DIR` at a tmp dir, build `ProjectStore(user="A")` and `ProjectStore(user="B")`), assert: with `current_store` bound to A, `corpus.context_pack` / `manas.ground` / `orchestrator.start` read A's pack; B's pack is untouched after a full `start()`→`approve(g1)`→`approve(g2)` run bound to A (B's version stays v0, B's events empty). This is the **full two-user flywheel** isolation assertion (not balance-only).

- [ ] **Step 2: Add the contextvar** to `common/project.py`:

```python
import contextvars
_CURRENT: contextvars.ContextVar = contextvars.ContextVar("saakshe_store", default=None)
def current_store():
    return _CURRENT.get() or STORE
def set_current_store(s):
    return _CURRENT.set(s)
def reset_current_store(token):
    _CURRENT.reset(token)
def store_for(user_id: str):
    return _make_store(user_id)
```

- [ ] **Step 3: Swap global reads → `current_store()`** in: `corpus.py` (`project.STORE.all_facts/pack` → `project.current_store().…`, 3 sites), `manas/runner.py` (`learn` line 255 `store = project.current_store()`; `_run_pipeline` line 333 `project.current_store().org_for_flywheel()`), `kalai/runner.py:60`, `kural/runner.py:50`, `kural/grounding.py:59`, `witness/telemetry.py:87`, `orchestrator.py:83` (`org = org or dict(store.org_for_flywheel())` where `store` is the param, see Step 4).

- [ ] **Step 4: Add `store=` to `orchestrator.start/approve`** defaulting to `current_store()`; thread it into `manas.ground`-adjacent reads via the contextvar (already covered) and into the org default. `approve` re-resolves `state`'s store from `_RUNS` (store the bound store on `FlywheelState` at `start`). Pass `store` into `manas.learn`/`_run_pipeline` is unnecessary IF the request binds the contextvar — but ALSO accept an explicit `store=` on `learn` defaulting to `current_store()` for direct callers.

- [ ] **Step 5: Run** `./.venv/bin/pytest tests/test_isolation.py -v` → PASS; **full suite green (135 + new)** — the contextvar default must keep demo byte-identical.

- [ ] **Step 6: Commit** `feat(multitenancy): request-scoped store via contextvars + full two-user isolation test`.

---

## Phase 6 — Credit wrapper on chargeable routes + per-request binding

**Files:** Modify `service/app.py`. Create `tests/test_credit_routes.py`.

- [ ] **Step 1: Failing route tests** `tests/test_credit_routes.py` (use `fastapi.testclient.TestClient` — NEW for this module only; mock auth dep + credits RPC): in `SAAKSHE_STORE=supabase` mode with a fake authed user, `POST /api/hero/run` with an `idem_key` debits `COST_FLYWHEEL_RUN`; an insufficient balance → 402 `{error:"out of credits", balance}`; a forced internal failure mid-run → refunded + "temporary, not charged"; `GET /api/me` returns `{user_id,email,balance}`; in demo mode (default) all routes are free + need no auth (the 402/spend path is skipped).

- [ ] **Step 2: Implement in `service/app.py`:**
  - A `Session` dependency: `optional_user` → if authed + supabase mode, `store = project.store_for(user.user_id)`, `stream = SupabaseEventStream(user.user_id)`, bind `project.set_current_store(store)` for the request (reset in `finally`); else fall to globals. Expose `request.state.user/store/stream`.
  - Add `idem_key: Optional[str]` to `RunRequest`. Wrap `hero_run` body in `credits.charge(user, "flywheel_run", idem_key=idem_key or run-nonce, reason="flywheel run")`; pass `store`/`stream` to `orchestrator.start`. `connect_ingest` wrapped with `"connect_ingest"`. `ask` (when routing to flywheel) wrapped with `"flywheel_run"`.
  - `GET /api/me` → `{user_id, email, balance: credits.balance(user)}` (401 if unauth in supabase mode; demo → a synthetic `{balance: null, demo:true}`).
  - All read routes (`/api/stream`, `/api/gates`, `/api/witness/telemetry`, `/api/connect/status`) use the per-request `store`/`stream` (own data; no charge). Keep `GET /` + pages + `/api/saakshe/health` open.
  - On `OutOfCredits` → return 402 via `credits.out_of_credits_response`.

- [ ] **Step 3: Run** `./.venv/bin/pytest tests/test_credit_routes.py -v` → PASS; full suite green.

- [ ] **Step 4: Commit** `feat(routes): credit-gate chargeable routes + per-request store/stream binding + /api/me`.

---

## Phase 7 — manas live-edit → `pending_changes`

**Files:** Create `common/pending.py`, `tests/test_pending.py`. Modify `service/app.py` (routes).

- [ ] **Step 1: Failing tests** `tests/test_pending.py` (fake PostgREST client): `PendingChanges(user_id).create(entity_type, old, new, diff, changed_fields, source_run_id, ai_model, cost_credits, idem_key)` writes an immutable `status='pending'` row (idempotent on `idem_key`); `apply(id)` → `status='applied'`+`applied_at`; `reject(id)` → `status='rejected'`; `list_open()` filters `deleted=false, status='pending'`; `supersede(id, new_id)` never UPDATEs the payload. Error text capped at 500 chars.

- [ ] **Step 2: Implement `common/pending.py`** over the `pending_changes` table (reuse the PostgREST low-level client).

- [ ] **Step 3: Routes in `service/app.py`:** `POST /api/manas/edit` (authed, supabase mode) — `credits.charge(user,"manas_edit",idem_key=...)` → call Gemini (live) to produce the structured edit (demo: a scripted diff) → write the pending row → return the diff; `POST /api/manas/pending/{id}/apply` → status applied; `POST /api/manas/pending/{id}/reject` → status rejected + `credits.refund(...)`; `GET /api/manas/pending` → `list_open()`. Owner-checked, idempotent, soft-delete.

- [ ] **Step 4: Run** `./.venv/bin/pytest tests/test_pending.py -v` → PASS; full suite green.

- [ ] **Step 5: Commit** `feat(manas): charged live-edits persisted as immutable pending_changes`.

---

## Phase 8 — Cockpit Google-login + balance UI + `/auth/callback`

**Files:** Modify `web/cockpit.html`, `service/app.py` (inject config + `/auth/callback`). Create `web/auth-callback.html`.

- [ ] **Step 1: Inject Supabase config** into the cockpit: add `GET /api/public-config` → `{supabase_url, anon_key, store: SAAKSHE_STORE, mode}` (anon key is public-safe; read from `SUPABASE_ANON_KEY` env). The cockpit fetches it at boot.

- [ ] **Step 2: Cockpit JS** — load `@supabase/supabase-js` ESM from CDN, `createClient(url, anon, {auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}})`. Add a "Sign in with Google" affordance in the top bar (+ prompt when an unauthenticated user triggers the live console). On session: store the access token, attach `Authorization: Bearer <token>` to all `/api/*` live fetches, show the credit balance from `/api/me`, generate a per-attempt `idem_key` (crypto.randomUUID) for `hero/run`. Sign-out clears the session. Keep the scripted demo chat client-side/free. Keep it aikizi-free.

- [ ] **Step 3: `/auth/callback`** — `web/auth-callback.html` lets supabase-js parse the URL (`detectSessionInUrl`) then redirects to `/cockpit.html`. Route: served by the existing `/{page}` catch-all (file exists) — verify `auth-callback.html` resolves, and `service/app.py` returns it for `/auth/callback` (add an explicit `@app.get("/auth/callback")` returning the page since the catch-all is single-segment).

- [ ] **Step 4: Verify** by serving locally (`PYTHONPATH=. ./.venv/bin/uvicorn service.app:app --port 8000`) and confirming the cockpit boots, `/api/public-config` returns, the sign-in button renders, and demo chat still works without auth. (Real Google round-trip needs the user's console steps — deferred to the manual checklist.)

- [ ] **Step 5: Commit** `feat(cockpit): Supabase Google sign-in + credit balance + Bearer on live console`.

---

## Phase 9 — Full suite green + local hybrid acceptance

- [ ] **Step 1:** Run the entire suite exactly as the spec defines it: `cd ~/Desktop/Working/saakshe && ./.venv/bin/pytest` (root 13→+new), `./.venv/bin/pytest manas/tests kalai/tests kural/tests` (93), `cd arivu && ../.venv/bin/pytest tests/` (29). Expected: **135 originals still green + all new tests green.**
- [ ] **Step 2: Local hybrid acceptance** (creds permitting): with `SAAKSHE_STORE=supabase` + service key + a minted test JWT (or owner email), run an authed flywheel → assert balance debits by `COST_FLYWHEEL_RUN`; force an internal failure → refunded; exhaust credits → 402; confirm demo (default env) stays free. Document results.
- [ ] **Step 3: Adversarial self-check** (per `feedback_harness_self_validation`): plant a known-bad case — user B's token cannot read user A's `/api/me`/stream; a forged refund amount is clamped; a re-spend after refund re-charges. Capture outputs.
- [ ] **Step 4: Commit** `test: full suite + hybrid credit acceptance green`.

---

## Phase 10 — Deploy (§10) + MANUAL CHECKLIST

- [ ] **Step 1:** Create empty private `Bashocodes/saakshe` on GitHub (`gh repo create Bashocodes/saakshe --private`), `git push -u origin main`.
- [ ] **Step 2:** Add new env to `deploy_cloudrun.sh`: `SAAKSHE_STORE=supabase`, `SAAKSHE_SUPABASE_URL`, `SAAKSHE_SUPABASE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_JWKS_URL`, `OWNER_EMAILS`, the cost-map vars, `SIGNUP_GRANT=100` + existing hybrid Gemini vars.
- [ ] **Step 3:** `gcloud auth login` (if expired) → lift the project-scoped `iam.allowedPolicyMemberDomains` org policy on `gen-lang-client-0937789625` (reversible) → redeploy via `deploy_cloudrun.sh` → `gcloud run services add-iam-policy-binding … --member=allUsers --role=run.invoker`.
- [ ] **Step 4:** Curl-verify: `/api/saakshe/health` = live; `/api/me` = 401 when anon; cockpit reachable.
- [ ] **Step 5:** `gcloud run domain-mappings create … --domain saakshe.com` → collect the DNS records.
- [ ] **Step 6: PRINT the manual checklist** (spec §9) — the console steps the USER must do (Supabase Google provider + redirect URLs, Google OAuth client, Supabase URL config, provide anon key, confirm org-policy change, Cloudflare DNS). The agent does NOT perform these.

---

## Self-Review (against the spec)

- **§3.1 Auth** → Phase 2 (backend) + Phase 8 (frontend). ✓
- **§3.2 Credits / 402 / chargeable routes** → Phase 1 (functions), 3 (wrapper), 6 (routes). ✓
- **§3.3 per-user store + stream + threading** → Phase 4 (supastream + reconcile) + Phase 5 (contextvar threading, incl. the hidden corpus/manas/kalai/kural/witness reads). ✓ (improves on the spec's literal "start/approve take store=" by also fixing the deep global reads).
- **§3.4 manas pending_changes** → Phase 1 (table) + Phase 7. ✓
- **§3.5 / §10 Deploy** → Phase 10. ✓
- **§4 data model** → Phase 1. ✓  **§5 code files** → Phases 2–8. ✓  **§6 cost map** → Phase 3. ✓
- **§7 security (1–7)** → JWT-derived user_id (Phase 2/6), service-role-only definer + REVOKE + clamp + claim-release (Phase 1), stable client idem key (decision #2, Phase 6), CHECK>=0 + trigger (Phase 1), RLS deny-default + ledger-forbid (Phase 1), isolation test (Phase 5), demo unchanged (every phase runs the full suite). ✓
- **§8 testing/acceptance** → Phases 2–9. ✓
- **§12 build order** → Phases 1–10 follow it exactly, each its own workflow phase, verified before the next. ✓

**Placeholder scan:** no TBD/TODO; every SQL body + signature is concrete. **Type consistency:** `User{user_id,email,is_owner}`, `charge(user,cost_key,*,idem_key,reason)`, `saakshe_spend(uuid,int,text,text)`, `saakshe_refund(uuid,int,text,text,text)`, `current_store()` used consistently across phases.
