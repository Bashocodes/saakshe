-- Per-user isolation for the operational stream: stamp user_id on events + gates
-- so a SupabaseEventStream(user_id) reads/queries only its own tenant's rows
-- (random run_ids are obscurity, not isolation -- spec §7.6 requires A-can't-read-B).
-- text (not uuid) to match projects.user_id ('founder' in demo, JWT sub in live).
ALTER TABLE public.events ADD COLUMN IF NOT EXISTS user_id text NOT NULL DEFAULT 'founder';
ALTER TABLE public.gates  ADD COLUMN IF NOT EXISTS user_id text NOT NULL DEFAULT 'founder';
CREATE INDEX IF NOT EXISTS idx_events_user_run ON public.events(user_id, run_id, seq);
CREATE INDEX IF NOT EXISTS idx_gates_user_run  ON public.gates(user_id, run_id);
