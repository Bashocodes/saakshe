-- flywheel_runs: restart-proofing for the orchestrator. The in-memory _RUNS map
-- is a CACHE; this table is the system of record — a charged run survives a
-- Cloud Run restart and the founder can still tap it to completion (or be
-- refunded via spend_idem_key). One row per run, upserted at every transition.
-- RLS deny-by-default; the backend's service_role key bypasses it.

CREATE TABLE IF NOT EXISTS public.flywheel_runs (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id        text NOT NULL DEFAULT 'founder',
  run_id         text NOT NULL,
  status         text NOT NULL DEFAULT 'running',   -- running|awaiting_approval|completed|no_safe_decision
  step           text NOT NULL DEFAULT 'start',
  charged        boolean NOT NULL DEFAULT false,
  spend_idem_key text NOT NULL DEFAULT '',
  snapshot       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, run_id)
);
CREATE INDEX IF NOT EXISTS idx_flywheel_runs_user ON public.flywheel_runs(user_id, created_at DESC);

ALTER TABLE public.flywheel_runs ENABLE ROW LEVEL SECURITY;
