-- saakshe credit system — atomic, idempotent spend/refund/grant + balance guard.
-- Applied to ref mttlgjztpkzcklbiqkxj 2026-06-09. Mirrors aikizi's proven
-- spend_tokens_v3/refund_tokens_v2 pattern (claim-first dedup, FOR UPDATE,
-- P0001 insufficiency, refund clamp + claim-release-via-rename) but single-balance
-- (no packs/entitlements) and with neutral saakshe_* names. All three are
-- SECURITY DEFINER + service_role-only; balance writes are gated by a transaction-
-- local flag only these functions set, so even a raw service_role UPDATE is blocked.

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

  -- Claim the idempotency key race-safely. Duplicate => short-circuit (no second charge).
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

  PERFORM set_config('saakshe.allow_balance_write','1',true);
  UPDATE accounts SET balance = balance - p_amount, updated_at = now() WHERE user_id = p_user_id
    RETURNING balance INTO v_balance;
  PERFORM set_config('saakshe.allow_balance_write','0',true);

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

  -- Claim the refund key FIRST. Duplicate => short-circuit.
  INSERT INTO transactions (user_id, kind, amount, reason, idem_key, ref)
  VALUES (p_user_id, 'refund', p_amount, p_reason, p_refund_idem_key,
          jsonb_build_object('spend_idem_key', p_spend_idem_key))
  ON CONFLICT (user_id, idem_key) DO NOTHING;
  GET DIAGNOSTICS v_inserted = ROW_COUNT;
  IF v_inserted = 0 THEN
    SELECT balance INTO v_balance FROM accounts WHERE user_id = p_user_id;
    RETURN COALESCE(v_balance, 0);
  END IF;

  -- Clamp to the recorded spend amount -- never trust a client-claimed amount.
  IF p_spend_idem_key IS NOT NULL THEN
    SELECT -amount INTO v_spend_amt FROM transactions
      WHERE user_id = p_user_id AND kind='spend' AND idem_key = p_spend_idem_key LIMIT 1;
  END IF;
  v_clamped := LEAST(p_amount, COALESCE(v_spend_amt, p_amount));

  SELECT balance INTO v_balance FROM accounts WHERE user_id = p_user_id FOR UPDATE;
  IF v_balance IS NULL THEN RAISE EXCEPTION 'account_not_found' USING ERRCODE='P0001'; END IF;

  PERFORM set_config('saakshe.allow_balance_write','1',true);
  UPDATE accounts SET balance = balance + v_clamped, updated_at = now() WHERE user_id = p_user_id
    RETURNING balance INTO v_balance;
  PERFORM set_config('saakshe.allow_balance_write','0',true);

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

-- Balance guard: block any UPDATE that changes balance unless the audited money
-- functions authorized it via the transaction-local flag they set around their write.
CREATE OR REPLACE FUNCTION public.accounts_block_balance_writes()
RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
  IF NEW.balance IS DISTINCT FROM OLD.balance
     AND COALESCE(current_setting('saakshe.allow_balance_write', true), '0') <> '1' THEN
    RAISE EXCEPTION 'balance writes go through saakshe_spend/saakshe_refund only' USING ERRCODE='42501';
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
