-- saakshe credit system — accounts + ledger + pending_changes (RLS deny-default).
-- Applied to ref mttlgjztpkzcklbiqkxj 2026-06-09. The backend uses the service_role
-- key (bypasses RLS); authenticated may READ own rows only and may never insert
-- money rows. All balance mutation goes through the SECURITY DEFINER functions in
-- 20260609_000002_credit_functions.sql.

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

CREATE POLICY accounts_read_own ON public.accounts
  FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY tx_read_own ON public.transactions
  FOR SELECT TO authenticated USING (user_id = auth.uid());
-- Ledger: authenticated may NEVER insert spend/refund/grant (service_role bypasses RLS).
CREATE POLICY tx_no_money_insert ON public.transactions
  FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid() AND kind NOT IN ('spend','refund','grant'));
CREATE POLICY pending_read_own ON public.pending_changes
  FOR SELECT TO authenticated USING (user_id = auth.uid());
