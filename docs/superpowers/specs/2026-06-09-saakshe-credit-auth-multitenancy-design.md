# saakshe — Credit-gated, multi-tenant auth (design spec)

**Date:** 2026-06-09 · **Status:** APPROVED (shape) — ready for `writing-plans` → implementation.
**Build with ultracode (workflows) + TDD. saakshe must contain ZERO aikizi references (study aikizi as a reference only).**

---

## 0 · Context & current state (READ FIRST)

**What saakshe is:** one FastAPI service (`service/app.py`) serving a website (`web/*.html`: landing at `/`, cockpit at
`/cockpit.html`, faculty pages `/manas.html` … via a `/{page}` catch-all) + JSON APIs + `/ws/voice`, over four real-ADK
quadrants (**manas** knows · **arivu** decides · **kalai** makes · **kural** engages) + the **witness**, driven by a
resumable **2-gate flywheel** (`orchestrator.py`). State today is a **global** `common.project.STORE` (file-based,
`~/.saakshe`) + a **global** in-memory `common.stream.STREAM` (`EventStream`).

**Repo:** `~/Desktop/Working/saakshe` — git, **single commit**, **NOT pushed** yet (TODO: create empty **private**
`Bashocodes/saakshe` on github.com, then `git push -u origin main`; SSH remote already wired). **135 tests green**
(`pytest` from root = 13, `manas/tests kalai/tests kural/tests` = 93, `cd arivu && pytest tests/` = 29). Run locally:
`PYTHONPATH=. ./.venv/bin/uvicorn service.app:app --port 8000` (demo, creds-free).

**Already done this session:** repo created + aikizi-scrubbed (0 aikizi in tree); 3 witness bugs fixed + 6 regression
tests; 11 site pages wired into `web/` + routes; `Dockerfile` + `.dockerignore` + `deploy_cloudrun.sh`; deployed once to
Cloud Run **hybrid** → `https://saakshe-yjmtbpqejq-uc.a.run.app` but it **403s** (org policy `iam.allowedPolicyMemberDomains`
on the `aikizi.com` Workspace blocks `allUsers`). We are NOT going public-ungated — we build THIS gate, then deploy.

**Modes:** `demo` (default, creds-free, scripted models, real orchestration) · `hybrid` (`SAAKSHE_MODE=live` +
`SAAKSHE_CLAUDE_MODE=demo` → real Gemini, scripted Claude — Claude Vertex quota pending) · `live`.

**Supabase:** project **`saakshe`** ref **`mttlgjztpkzcklbiqkxj`** (us-west-1, ACTIVE). Has 7 RLS-enabled tables
(`projects, connections, context_packs, questions, messages, events, gates`). **No credit tables/functions yet.**
Service key at `~/.saakshe_supabase_key`. `common/supastore.py` = a `SupabaseStore(user_id)` adapter — keyed by user_id
(good) but **NOT a drop-in**: its `commit_pack/set_org/add_connection` signatures DRIFT from the file `ProjectStore`, and
it does **NOT** implement the `EventStream` interface (it has raw `append_event/events_since/upsert_gate` instead).

**GCP:** project `gen-lang-client-0937789625`, gcloud account `hello@aikizi.com` (token expires → user re-runs
`gcloud auth login`). Secrets in **gitignored** `.env.local`: `GOOGLE_CLOUD_PROJECT`, `SAAKSHE_SUPABASE_URL`.

**aikizi reference (study only, do not copy names):** `/Users/cyberyogi/Projects/aikizi` —
`supabase/migrations/20260530071954_studio_spend_v3_refund_v2.sql`,
`…20260603000000_refund_releases_spend_idem_key.sql`, `…20260602120000_security_fix_is_privileged_caller.sql`,
`…120100_security_revoke_definer_execute.sql`, `…120200_security_lock_transactions_writes.sql`,
`…001_users_and_auth.sql`; `src/worker/lib/{auth.ts,jwks.ts,token-spending.ts}`, `src/worker/config/pricing.ts`,
`src/contexts/AuthContext.tsx`, `src/lib/supabase.ts`. (aikizi skills also exist: `aikizi-auth`, `aikizi-pricing`,
`aikizi-rls`, `aikizi-payments` — reference only.)

---

## 1 · Goals / non-goals

**Goals:** (1) Google login gate; (2) per-user isolated company (own Supabase store + event stream + flywheel runs);
(3) production-grade **credit system** — 100 free credits/account, configurable per-action costs, **atomic idempotent
spend/refund** + ledger, **refund-on-failure**; (4) **manas AI edits** are charged + persisted as **pending changes**;
(5) saakshe.com live in **hybrid**, gated. **Robust — this launches as a real product, not a hackathon toy.**

**Non-goals (now):** payments / credit-packs / subscriptions (single balance only — leave hooks); BYOK (note as future);
actual code-execution of pending changes (just persist them — the "reminder"); CAPTCHA/Turnstile (optional later).

---

## 2 · The aikizi blueprint (distilled — replicate the PATTERN, neutral names)

**Credit spend/refund (the crown jewel):** money moves ONLY through `SECURITY DEFINER` Postgres functions that are
service-role-only and **idempotent**:
- `saakshe_spend(p_user_id uuid, p_amount int, p_reason text, p_idem_key text) → int` (new balance):
  dedup-insert a claim into `transactions` `ON CONFLICT (user_id, idem_key) DO NOTHING`; if already claimed → return
  current balance (short-circuit). Lock the account row `FOR UPDATE`. If `balance < p_amount` → `RAISE EXCEPTION USING
  ERRCODE='P0001'` (rolls back the claim too). Else `balance -= p_amount`; finalize the txn row
  (`kind='spend', amount=-p_amount, reason, balance_after`); return balance.
- `saakshe_refund(p_user_id uuid, p_amount int, p_reason text, p_spend_idem_key text, p_refund_idem_key text) → int`:
  dedup on `p_refund_idem_key`; **clamp** `p_amount` to the recorded spend's amount (`LEAST(p_amount, spend.amount)`) —
  never trust a client-claimed amount; `balance += clamped`; insert `kind='refund'` txn with `balance_after`. **CRITICAL:
  release the spend's claim** — `UPDATE transactions SET idem_key = idem_key || ':refunded:' || p_refund_idem_key WHERE
  user_id=p_user_id AND kind='spend' AND idem_key=p_spend_idem_key` — so a genuine retry re-charges (prevents
  "retry-a-failed-op-for-free"). Return balance.
- `saakshe_grant_signup(p_user_id uuid)` → insert account `balance = SIGNUP_GRANT` (default 100) if not exists.
- **Refund-on-failure flow:** wrap each chargeable action: `spend(idem=stable_hash)`; run the action; on internal
  failure → `refund(spend_idem_key=stable_hash)` and return "temporary, not charged" (saakshe error rule — classify by
  error CODE not substring; only a true user/BYOK error blames the user). Idem key MUST be stable across retries
  (content/run hash, never random/timestamp).

**Auth:** frontend `supabase.auth.signInWithOAuth({provider:'google', redirectTo:`${origin}/auth/callback`})` (PKCE,
`persistSession+autoRefreshToken+detectSessionInUrl`); attach `Authorization: Bearer <access_token>` on every API call.
Backend validates the JWT against the project **JWKS** (`https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`,
asymmetric ES256 on new Supabase — fetch+cache JWKS, verify sig + `iss`/`exp`; `sub` = the user id = `auth.uid`). Cache
verified tokens ~30s. `OWNER_EMAILS` allowlist → unlimited credits. First sign-in auto-creates account + grant.

**RLS / privilege:** deny-by-default RLS on every table; **`REVOKE EXECUTE … FROM PUBLIC, anon, authenticated`** on all
SECURITY DEFINER functions + `GRANT EXECUTE … TO service_role` + `ALTER DEFAULT PRIVILEGES … REVOKE EXECUTE FROM PUBLIC`
(aikizi's #1 footgun was anon-callable definer functions). Ledger policy: authenticated may never insert
`kind IN ('spend','refund')`. Backend uses the **service_role** key (bypasses RLS) and **derives `user_id` from the JWT
server-side — NEVER from a client param/body**. A `BEFORE UPDATE` trigger on `accounts` blocks any `balance` change not
made by service_role (defense-in-depth). Refund clamping + stable idempotency are mandatory.

**Pending changes (manas edits):** a queue row with an **immutable** payload + a status lifecycle
(`pending → applied/rejected/superseded`), `source_run_id`, owner check, idempotency, full audit. Never UPDATE the
payload — supersede with a new row. Cap error text. Soft-delete (keep for audit).

---

## 3 · Design (5 parts)

### 3.1 Auth (Supabase Google)
- **Frontend (cockpit.html, vanilla JS):** load `@supabase/supabase-js` (CDN/ESM) with `SUPABASE_URL` + **anon** key
  (injected by the server into the page — anon key is public/safe). A "Sign in with Google" affordance in the cockpit
  (top bar + prompted when an unauthenticated user triggers a live action). On session, store + attach the access token
  on all backend fetches; show the **credit balance**. `/auth/callback` page completes the OAuth round-trip
  (Supabase parses the URL). Sign-out clears the session.
- **Backend (FastAPI):** a `current_user` dependency (`get_current_user(request) -> User`) validates the Bearer JWT via
  JWKS, returns `{user_id=sub, email}`; `optional_user` returns `None` when unauthenticated (for open routes). New
  module e.g. `common/auth.py` (PyJWT + httpx for JWKS, in-memory JWKS+token cache). `OWNER_EMAILS` env → owner flag.

### 3.2 Credits (the gate)
- `accounts(user_id, email, balance, is_owner, created_at, updated_at)` + `transactions(id, user_id, kind, amount,
  reason, idem_key, balance_after, ref jsonb, created_at; UNIQUE(user_id, idem_key))`.
- A backend `credits.py` helper wrapping the `saakshe_spend`/`saakshe_refund` RPCs (called via the service-role Supabase
  client / supastore's PostgREST `rpc`), with a **cost map** from env/config.
- A small wrapper (decorator or explicit calls) on each chargeable route: spend(before) → run → refund(on internal fail).
  Owners + demo mode bypass spend. Insufficient → **HTTP 402** `{error:"out of credits", balance}`.
- **Chargeable routes** (live mode only — demo is free): `POST /api/hero/run`, `POST /api/hero/approve` (the flywheel
  spends per run, not per gate — spend once at run start, key=run_id), `POST /api/saakshe/ask` when it routes to the
  flywheel (decision), `POST /api/connect/ingest` (real clone+Gemini), the manas-edit route (§3.4). Reads
  (`status/stream/gates/telemetry/agent-cards`) require auth (own data) but cost nothing. Open (no auth): `GET /` +
  pages, `GET /api/saakshe/health`. The cockpit's **scripted demo chat** stays client-side/free; the **live console**
  (`● live`) requires sign-in.

### 3.3 Per-user stores + stream (the refactor)
- Reconcile **`SupabaseStore`** to match the file `ProjectStore` public surface EXACTLY (so manas/orchestrator/service
  call it unchanged): align `commit_pack(facts, voice_rules, brand_rules, groundedness=, note=)` (generate version
  internally), `set_org(name=, kind=, one_liner=)`, `add_connection(...)→object with .as_dict()`, and add the missing
  methods the file store has (`set_status`, `set_questions`, `all_facts`, `org_for_flywheel`, etc.). Compare against
  `common/project.py`'s `ProjectStore` and make them interchangeable.
- New **`SupabaseEventStream(user_id)`** — an `EventStream` subclass persisting to the `events`/`gates` tables:
  override `emit` (→ `append_event`, compute per-run `seq` = max(seq for run_id)+1 from DB or a per-request counter),
  `rows(cursor)` (→ `events_since`), `gate`/`open_gates`/`resolve_gate` (→ `gates` table). The convenience methods
  (`a2a`, `action`, `emit_transcript`) inherit (they call `emit`/`gate`). Keep the in-memory `EventStream` for
  demo/local + the 135 tests.
- **User-context threading:** each request resolves `user_id` from the JWT → builds `SupabaseStore(user_id)` +
  `SupabaseEventStream(user_id)` (a small per-request `Session`/dependency). Routes + `orchestrator.start/approve` take
  `store` + `stream` params (start already takes `stream=`; add `store=`; default to the globals for local/demo). The
  witness telemetry reads the request's stream. **File store + in-memory stream remain the default when
  `SAAKSHE_STORE != supabase`** (local dev + the 135 tests untouched). Supabase path activates when
  `SAAKSHE_STORE=supabase` + keys present + an authenticated user.

### 3.4 manas live-edits → pending changes
- `pending_changes(id, user_id, source_run_id, entity_type, old_json, new_json, diff_json, changed_fields text[],
  status, review_status, ai_model, cost_credits, error_text, created_at, applied_at, reviewed_by, immutable payload)`.
- The manas edit route: charge credits (spend) → call Gemini to produce the structured edit → write an **immutable**
  pending row (`status='pending'`) → return the diff to the UI. `apply` → status `applied` (the "reminder" for the
  later code-exec you'll wire elsewhere; saakshe does NOT execute it). `reject` before apply → status `rejected` +
  **refund**. Owner-checked, idempotent, error text capped, soft-delete.

### 3.5 Deploy
- New env on Cloud Run: `SAAKSHE_STORE=supabase`, `SAAKSHE_SUPABASE_URL`, `SAAKSHE_SUPABASE_KEY` (service_role),
  `SUPABASE_ANON_KEY`, `SUPABASE_JWKS_URL` (or derive from URL), `OWNER_EMAILS`, the cost-map vars, `SIGNUP_GRANT=100`
  — plus the existing hybrid Gemini env (`deploy_cloudrun.sh` already sets the model vars).
- The org-policy block: lift `iam.allowedPolicyMemberDomains` **scoped to gen-lang-client** (project-level org policy,
  reversible) so `allUsers` invoker works → the app is reachable, the **app's** Google-login gate protects credits.
- Sequence: migrations applied (via Supabase MCP `apply_migration`) → build green locally → set Cloud Run env →
  `gcloud run services add-iam-policy-binding … allUsers run.invoker` (after policy lift) → verify → map saakshe.com
  (`gcloud run domain-mappings create … --domain saakshe.com` → hand DNS records for Cloudflare).

---

## 4 · Data model — new Supabase migrations (apply to ref `mttlgjztpkzcklbiqkxj`)

Create via the Supabase MCP (`apply_migration`). Tables (all RLS deny-default):
1. `accounts(user_id uuid PK, email text, balance int NOT NULL DEFAULT 0 CHECK(balance>=0), is_owner bool DEFAULT false,
   created_at, updated_at)`.
2. `transactions(id bigint identity PK, user_id uuid, kind text, amount int, reason text, idem_key text,
   balance_after int, ref jsonb DEFAULT '{}', created_at; UNIQUE(user_id, idem_key))`.
3. `pending_changes(…§3.4…)`.
Functions (SECURITY DEFINER, service_role-only, REVOKE from PUBLIC/anon/authenticated): `saakshe_spend`,
`saakshe_refund`, `saakshe_grant_signup`. Trigger: `accounts_block_balance_writes` (BEFORE UPDATE, raise 42501 unless
service_role). `ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC`. (See §2 for bodies.)

---

## 5 · Code changes (files)

- **NEW** `common/auth.py` — JWKS fetch/cache, JWT verify, `get_current_user` / `optional_user` FastAPI deps, owner check.
- **NEW** `common/credits.py` — cost map (env-tunable), `spend()/refund()` wrappers over the RPCs, the charge wrapper,
  402 helper.
- **NEW** `common/supastream.py` — `SupabaseEventStream(EventStream)`.
- **EDIT** `common/supastore.py` — reconcile surface to `ProjectStore` (see §3.3) + add `append_event` seq handling if
  needed.
- **EDIT** `common/project.py` — `store()` already routes on `SAAKSHE_STORE=supabase`; add per-user keying (factory
  `store_for(user_id)`); keep the global file store default.
- **EDIT** `service/app.py` — add the `current_user` dependency to the gated routes; per-request `store`+`stream`
  resolution; inject `SUPABASE_URL`/anon key + the balance bootstrap into the cockpit page; `/auth/callback`; new routes:
  `GET /api/me` (balance+identity), the manas-edit + pending-change routes.
- **EDIT** `orchestrator.py` — `start(... , store=STORE, stream=STREAM)` / `approve(..., store=, stream=)` take the
  per-user store+stream (default to globals — keeps tests green).
- **EDIT** `web/cockpit.html` — Supabase-JS + "Sign in with Google" + balance display + attach Bearer on the live-console
  fetches + gate the live actions on a session. (Other session is done — safe to edit; keep it aikizi-free.)
- **NEW** `web/auth-callback.html` (or a `/auth/callback` route) — completes OAuth.
- **EDIT** `requirements.txt` — add `pyjwt[crypto]` (or `python-jose[cryptography]`).
- **NEW** `supabase/migrations/*.sql` — the §4 migrations (also keep them in-repo for version control).

---

## 6 · Cost map / config (env, defaults LOW — tune later)
`SIGNUP_GRANT=100` · `COST_FLYWHEEL_RUN=20` · `COST_CONNECT_INGEST=20` · `COST_MANAS_EDIT=10` · `COST_KALAI_MAKE=15`
· `COST_KURAL_ENGAGE=15`. Owners (`OWNER_EMAILS`) + demo mode = free. (User: "keep low/vague; we have $500 hackathon
credit, be generous; ~5 reports per 100." Charge per flywheel RUN, not per gate.)

---

## 7 · Security requirements (MUST)
1. `user_id` always derived from the verified JWT server-side; never from request body/params.
2. spend/refund are service-role-only SECURITY DEFINER, REVOKE'd from PUBLIC/anon/authenticated; idempotent; refund
   clamps to the recorded spend; refund releases the spend claim.
3. Stable idem keys (run/content hash). No random/timestamp keys.
4. `accounts.balance` `CHECK(>=0)` + service-role-only write trigger.
5. RLS deny-default on all new tables; ledger forbids client `spend`/`refund` inserts.
6. Per-user isolation verified by test (user A cannot read/spend user B's store/stream/balance).
7. Demo/local path unchanged — the 135 tests stay green.

---

## 8 · Testing & acceptance (TDD)
- Unit: JWT verify (valid/expired/missing/bad-sig → 401); spend (ok/insufficient→P0001/idempotent-double→single charge);
  refund (clamp, release-claim → retry re-charges, idempotent); grant-once; cost-map lookup; owner bypass.
- `SupabaseEventStream`: emit→rows roundtrip, per-run seq, gates open/resolve. `SupabaseStore` ⇄ `ProjectStore`
  interchangeability (same calls, same shapes).
- Isolation: two users → separate balances/stores/streams; A can't touch B.
- Integration: signed-in user runs the flywheel → balance debits by COST_FLYWHEEL_RUN; a forced internal failure →
  refunded ("not charged"); insufficient → 402.
- Regression: full existing suite green (135). **Acceptance:** local hybrid run as an authed user debits/refunds
  correctly; demo stays free; per-user isolation holds.

---

## 9 · MANUAL STEPS for the user (do AFTER the build; the agent will print these)
1. **Supabase → Auth → Providers → Google:** enable; create a Google OAuth client (Google Cloud console → OAuth consent
   + credentials), paste Client ID/Secret into Supabase; add redirect URLs: `https://saakshe.com/auth/callback`,
   `https://<cloud-run-url>/auth/callback`, `http://localhost:8000/auth/callback`. Add the same to the Google client's
   "Authorized redirect URIs" (Supabase callback `https://mttlgjztpkzcklbiqkxj.supabase.co/auth/v1/callback`).
2. **Supabase → Auth → URL config:** add saakshe.com + the run.app URL to allowed redirect/site URLs.
3. **gcloud:** `gcloud auth login` (hello@aikizi.com) when the token's expired.
4. **(After agent lifts the org policy)** confirm the project-level org-policy change if prompted.
5. Provide the Supabase **anon** key (Settings → API) to put in env (`SUPABASE_ANON_KEY`).

---

## 10 · Deploy sequence (agent)
Migrations (Supabase MCP) → reconcile/build/test green → push to GitHub (create `Bashocodes/saakshe` private first) →
set Cloud Run env (incl. Supabase + OWNER_EMAILS + cost map + hybrid Gemini) → lift org policy (project-scoped) →
redeploy (`deploy_cloudrun.sh` + the new env) → `allUsers run.invoker` → curl-verify (health=live, /api/me 401 when
anon) → domain-map saakshe.com → hand Cloudflare DNS records to the user.

---

## 11 · Open / configurable (not blocking)
Exact credit costs (env, keep low); whether reads require auth or are anon-readable (default: require auth); BYOK +
payments (future); CAPTCHA (future); pending-change auto-apply vs manual (default: manual).

---

## 12 · Build order (ultracode workflows + TDD)
1. Supabase migrations (tables + spend/refund/grant + RLS/REVOKE/trigger) — apply + verify.
2. `common/auth.py` (+ tests). 3. `common/credits.py` (+ tests, mock RPC). 4. `common/supastream.py` +
`supastore.py` reconcile (+ tests). 5. user-context threading in `service/app.py` + `orchestrator.py` (+ isolation
tests). 6. credit wrapper on the chargeable routes + refund-on-fail (+ integration tests). 7. manas-edit +
pending-changes route (+ tests). 8. cockpit Google-login + balance UI + `/auth/callback`. 9. full suite green +
local hybrid acceptance. 10. deploy (§10). Keep each step its own workflow phase; verify before moving on.
