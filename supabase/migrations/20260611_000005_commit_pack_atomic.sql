-- 20260611_000005_commit_pack_atomic — atomic Context Pack commit.
--
-- commit_pack() used to be TWO PostgREST calls (insert context_packs row, then
-- patch the projects manifest). A crash between them orphaned the pack: the
-- founder's memory was written but invisible to every subsequent read. This
-- function does both writes in ONE transaction; the store calls it via
-- /rest/v1/rpc and falls back to the two-step path (with heal-on-read) only
-- when the function is missing.
--
-- service_role only — same deny-by-default posture as the credit functions.

CREATE OR REPLACE FUNCTION public.saakshe_commit_pack(
  p_project_id    uuid,
  p_version       text,
  p_facts         jsonb,
  p_voice_rules   jsonb,
  p_brand_rules   jsonb,
  p_pack_grounded boolean,
  p_grounded      boolean,
  p_status        text
) RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.context_packs
    (project_id, version, facts, voice_rules, brand_rules, grounded)
  VALUES
    (p_project_id, p_version,
     COALESCE(p_facts, '[]'::jsonb),
     COALESCE(p_voice_rules, '[]'::jsonb),
     COALESCE(p_brand_rules, '[]'::jsonb),
     p_pack_grounded);

  UPDATE public.projects
     SET version  = p_version,
         grounded = p_grounded,
         status   = p_status
   WHERE id = p_project_id;

  RETURN p_version;
END;
$$;

REVOKE ALL ON FUNCTION public.saakshe_commit_pack(uuid, text, jsonb, jsonb, jsonb, boolean, boolean, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.saakshe_commit_pack(uuid, text, jsonb, jsonb, jsonb, boolean, boolean, text) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.saakshe_commit_pack(uuid, text, jsonb, jsonb, jsonb, boolean, boolean, text) TO service_role;
