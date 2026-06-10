-- saakshe base schema — the operational tables SupabaseStore/SupabaseEventStream
-- expect (projects + children, the ordered event stream, the HITL gate queue).
-- This documents the schema that was applied ad-hoc to ref mttlgjztpkzcklbiqkxj
-- before 2026-06-09; IF NOT EXISTS throughout so re-applying there is a no-op,
-- and a FRESH project gets the full base before the later migrations run.
-- RLS: deny-by-default everywhere — the backend uses the service_role key (which
-- bypasses RLS); no anon/authenticated policies until owner policies land.

-- projects: one row per founder (user_id = 'founder' in demo, JWT sub in live).
CREATE TABLE IF NOT EXISTS public.projects (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    text NOT NULL UNIQUE,
  status     text NOT NULL DEFAULT 'empty',   -- empty|connecting|ingesting|needs_answers|grounded
  version    text NOT NULL DEFAULT 'v0',
  grounded   boolean NOT NULL DEFAULT false,
  org        jsonb NOT NULL DEFAULT '{}'::jsonb,
  assets     jsonb NOT NULL DEFAULT '[]'::jsonb,  -- brand-asset vault index (bytes live in Storage)
  created_at timestamptz NOT NULL DEFAULT now()
);

-- connections: the founder's connected sources (repo, site, docs, social).
CREATE TABLE IF NOT EXISTS public.connections (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  kind       text NOT NULL,
  ref        text NOT NULL,
  status     text NOT NULL DEFAULT 'connected',
  meta       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_connections_project ON public.connections(project_id, created_at);

-- context_packs: manas's versioned, source-cited memory (append-only).
CREATE TABLE IF NOT EXISTS public.context_packs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  version     text NOT NULL,
  facts       jsonb NOT NULL DEFAULT '[]'::jsonb,
  voice_rules jsonb NOT NULL DEFAULT '[]'::jsonb,
  brand_rules jsonb NOT NULL DEFAULT '[]'::jsonb,
  grounded    boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_packs_project ON public.context_packs(project_id, created_at DESC);

-- questions: manas's clarifying questions (open|answered lifecycle).
CREATE TABLE IF NOT EXISTS public.questions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  qid        text NOT NULL,
  text       text NOT NULL DEFAULT '',
  why        text NOT NULL DEFAULT '',
  trigger    text NOT NULL DEFAULT '',
  blocks     text NOT NULL DEFAULT '',
  status     text NOT NULL DEFAULT 'open',
  answer     text NOT NULL DEFAULT '',
  options    jsonb NOT NULL DEFAULT '[]'::jsonb,
  sources    jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_questions_project ON public.questions(project_id, status);

-- messages: the witness chat transcript.
CREATE TABLE IF NOT EXISTS public.messages (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  run_id     text,
  role       text NOT NULL,
  text       text NOT NULL DEFAULT '',
  meta       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_project ON public.messages(project_id, created_at);

-- events: the ordered operational stream (user_id column + indexes arrive in
-- 20260609_000003_events_gates_user_scope.sql).
CREATE TABLE IF NOT EXISTS public.events (
  id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id text NOT NULL,
  seq    int NOT NULL,
  source text NOT NULL DEFAULT '',
  agent  text NOT NULL DEFAULT '',
  span   text NOT NULL DEFAULT 'agent_run',
  kind   text NOT NULL DEFAULT 'note',
  text   text NOT NULL DEFAULT '',
  meta   jsonb NOT NULL DEFAULT '{}'::jsonb,
  ts     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_run ON public.events(run_id, seq);

-- gates: the HITL gate queue (user_id column + indexes arrive in migration 3).
CREATE TABLE IF NOT EXISTS public.gates (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id     text NOT NULL,
  gate_id    text NOT NULL,
  quadrant   text NOT NULL DEFAULT '',
  agent      text NOT NULL DEFAULT '',
  gate_kind  text NOT NULL DEFAULT '',
  proposal   text NOT NULL DEFAULT '',
  reversible boolean NOT NULL DEFAULT false,
  detail     jsonb NOT NULL DEFAULT '{}'::jsonb,
  status     text NOT NULL DEFAULT 'open',     -- open|approved|rejected
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gates_run ON public.gates(run_id, gate_id);

ALTER TABLE public.projects      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.connections   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.context_packs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gates         ENABLE ROW LEVEL SECURITY;
