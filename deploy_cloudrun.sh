#!/usr/bin/env bash
# Deploy the saakshe site to Google Cloud Run — HYBRID mode (every seat LIVE; the
# Claude seats run on a live Gemini understudy while the Vertex Anthropic quota is
# pending — never scripted replay in prod). One command, idempotent.
#
# Three profiles (SAAKSHE_DEPLOY_PROFILE, default "demo"):
#   demo     — the open, no-sign-in demo. File store, no auth, no billing,
#              SEALED mutations + rate limits (SAAKSHE_PUBLIC_DEMO=1).
#              Needs NO Supabase config.
#   gated    — the demo profile EXACTLY, plus SAAKSHE_REQUIRE_SIGNIN=1: every API
#              route needs a Supabase sign-in (email judge credentials go in the
#              Devpost testing instructions). The seeded judge demo stays on the
#              baked file store; every OTHER signed-in account gets a durable
#              Supabase sandbox + 500 signup credits, billed per action
#              (SAAKSHE_BILLING=1). Requires the Supabase URL + anon + service key.
#   billing  — the multi-tenant SaaS deploy: Supabase store, Google sign-in,
#              credits. Requires the full Supabase env below.
#
# Prereqs:  gcloud auth login   ·   a GCP project with billing + Vertex AI
#           GOOGLE_CLOUD_PROJECT comes from .env.local (gitignored) or the environment.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env.local ] && { set -a; . ./.env.local; set +a; }
: "${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT in .env.local (see .env.local.example)}"
PROJECT="$GOOGLE_CLOUD_PROJECT"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-saakshe}"
PROFILE="${SAAKSHE_DEPLOY_PROFILE:-demo}"

# ── the model/mode env both profiles share (hybrid: all live; CLAUDE_MODE=demo
#    puts the Claude seats on a live Gemini understudy, NOT scripted replay) ─
COMMON_ENV="SAAKSHE_MODE=live|ARIVU_MODE=live|SAAKSHE_CLAUDE_MODE=demo|ARIVU_CLAUDE_MODE=demo"
COMMON_ENV+="|GOOGLE_CLOUD_PROJECT=${PROJECT}|GOOGLE_CLOUD_LOCATION=global"
COMMON_ENV+="|SAAKSHE_CLAUDE_LOCATION=global|ARIVU_CLAUDE_LOCATION=global|GOOGLE_GENAI_USE_VERTEXAI=TRUE"
COMMON_ENV+="|SAAKSHE_MODEL_PRO=gemini-3.1-pro-preview|SAAKSHE_MODEL_FLASH=gemini-3.5-flash"
COMMON_ENV+="|ARIVU_MODEL_CHAIR=gemini-3.1-pro-preview|ARIVU_MODEL_MANTRI=gemini-3.5-flash"
# Deep grasp ON in prod (founder call, 2026-06-11): connects interview at Brand-Pack
# depth (manas/grasp_schema.py tier-1, capped at 8) instead of the classic 4 dims.
# CI/pytest stay classic (env unset there) — demo determinism intact.
COMMON_ENV+="|SAAKSHE_DEEP_GRASP=1"
# Deploy provenance — surfaced by /api/public-config + the cockpit sidebar, so
# "is the latest deployed?" is answerable at a glance (the Workers-dashboard itch).
COMMON_ENV+="|SAAKSHE_GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
COMMON_ENV+="|SAAKSHE_DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

case "$PROFILE" in
  demo)
    # The open judged demo: shared file store seeded in the image, mutations sealed,
    # model routes rate-limited. No Supabase needed; no sign-in shown.
    ENV_VARS="^|^${COMMON_ENV}|SAAKSHE_STORE=file|SAAKSHE_PUBLIC_DEMO=1"
    ;;
  gated)
    # The judged demo behind sign-in: same seeded file store + sealing, but every
    # API route requires a Supabase JWT (judge email credentials in the testing
    # instructions). Auth verification is JWKS-only — no service key at runtime.
    : "${SAAKSHE_SUPABASE_URL:?set SAAKSHE_SUPABASE_URL in .env.local}"
    : "${SUPABASE_ANON_KEY:?set SUPABASE_ANON_KEY in .env.local (Supabase → Settings → API → anon/public)}"
    # OWNER_EMAILS: founder accounts get the seal lifted + an isolated sandbox
    # store — the seeded judge demo stays pristine while the founder runs the
    # real connect→ingest flywheel live.
    : "${OWNER_EMAILS:=workzenyogi@gmail.com,hello@aikizi.com}"
    # JUDGE_EMAILS ride the SHARED seeded store read-only (the Devpost demo);
    # every OTHER signed-in account gets an isolated sandbox + the signup grant.
    : "${JUDGE_EMAILS:=judge@saakshe.com}"
    ENV_VARS="^|^${COMMON_ENV}|SAAKSHE_STORE=file|SAAKSHE_PUBLIC_DEMO=1|SAAKSHE_REQUIRE_SIGNIN=1"
    ENV_VARS+="|SAAKSHE_SUPABASE_URL=${SAAKSHE_SUPABASE_URL}|SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}"
    ENV_VARS+="|OWNER_EMAILS=${OWNER_EMAILS}|JUDGE_EMAILS=${JUDGE_EMAILS}"
    # Everyone-access billing (2026-06-11): any signed-in founder works in their
    # own durable Supabase store with 500 signup credits — grasp a repo 100,
    # every other action 1. Needs the service key for the money RPCs + stores.
    : "${SAAKSHE_OWNER_STORE:=supabase}"
    SAAKSHE_SUPABASE_KEY="${SAAKSHE_SUPABASE_KEY:-$(cat ~/.saakshe_supabase_key 2>/dev/null || true)}"
    : "${SAAKSHE_SUPABASE_KEY:?the gated profile needs SAAKSHE_SUPABASE_KEY (or ~/.saakshe_supabase_key) for billing + durable stores}"
    ENV_VARS+="|SAAKSHE_OWNER_STORE=${SAAKSHE_OWNER_STORE}|SAAKSHE_SUPABASE_KEY=${SAAKSHE_SUPABASE_KEY}"
    ENV_VARS+="|SAAKSHE_BILLING=1"
    ;;
  billing)
    # ── credit/auth (multi-tenant) config — secrets come from the gitignored .env.local
    # (NEVER committed). The service_role key falls back to ~/.saakshe_supabase_key.
    # For hardening, move SAAKSHE_SUPABASE_KEY into Google Secret Manager + --set-secrets.
    : "${SAAKSHE_SUPABASE_URL:?set SAAKSHE_SUPABASE_URL in .env.local}"
    SAAKSHE_SUPABASE_KEY="${SAAKSHE_SUPABASE_KEY:-$(cat ~/.saakshe_supabase_key 2>/dev/null || true)}"
    : "${SAAKSHE_SUPABASE_KEY:?set SAAKSHE_SUPABASE_KEY in .env.local or ~/.saakshe_supabase_key}"
    : "${SUPABASE_ANON_KEY:?set SUPABASE_ANON_KEY in .env.local (Supabase → Settings → API → anon/public)}"
    : "${OWNER_EMAILS:=}"
    : "${SIGNUP_GRANT:=100}"
    : "${COST_FLYWHEEL_RUN:=20}"; : "${COST_CONNECT_INGEST:=20}"; : "${COST_MANAS_EDIT:=10}"
    : "${COST_KALAI_MAKE:=15}"; : "${COST_KURAL_ENGAGE:=15}"
    ENV_VARS="^|^${COMMON_ENV}|SAAKSHE_STORE=supabase"
    ENV_VARS+="|SAAKSHE_SUPABASE_URL=${SAAKSHE_SUPABASE_URL}|SAAKSHE_SUPABASE_KEY=${SAAKSHE_SUPABASE_KEY}"
    ENV_VARS+="|SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}|OWNER_EMAILS=${OWNER_EMAILS}|SIGNUP_GRANT=${SIGNUP_GRANT}"
    ENV_VARS+="|COST_FLYWHEEL_RUN=${COST_FLYWHEEL_RUN}|COST_CONNECT_INGEST=${COST_CONNECT_INGEST}"
    ENV_VARS+="|COST_MANAS_EDIT=${COST_MANAS_EDIT}|COST_KALAI_MAKE=${COST_KALAI_MAKE}|COST_KURAL_ENGAGE=${COST_KURAL_ENGAGE}"
    ;;
  *)
    echo "unknown SAAKSHE_DEPLOY_PROFILE '$PROFILE' (use demo | gated | billing)" >&2; exit 1
    ;;
esac

# ── the channel surface (kural's real outbound + the outcome read-back) ──────
# Pure founder configuration, profile-independent: unset = the mouth dry-runs and
# no stats are pulled, exactly as before. These three are passed through ONLY
# when the deployer's environment carries them. SAAKSHE_ALLOW_LIVE_SEND is the
# deliberate exception of the triple AND-gate (env ∧ founder tap ∧ registered
# client): it is passed through but NEVER defaulted — arming a real send is an
# explicit per-deploy act, not a side effect of configuring the webhook.
for CH in SAAKSHE_CHANNEL_WEBHOOK_URL SAAKSHE_CHANNEL_WEBHOOK_TOKEN \
          SAAKSHE_CHANNEL_STATS_URL SAAKSHE_ALLOW_LIVE_SEND; do
  V="${!CH:-}"
  [ -n "$V" ] && ENV_VARS+="|${CH}=${V}"
done

echo "→ profile: $PROFILE"

# ── one-time project setup, OFF the hot path (≈30s of ceremony every deploy) ──
# Run once per project with SAAKSHE_DEPLOY_BOOTSTRAP=1; every later deploy skips it.
if [ -n "${SAAKSHE_DEPLOY_BOOTSTRAP:-}" ]; then
  echo "→ bootstrap: enabling APIs (Run · Build · Artifact Registry · Vertex)…"
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com aiplatform.googleapis.com --project "$PROJECT"
  echo "→ bootstrap: granting the compute SA its roles (Vertex runtime + Cloud Build)…"
  PN=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")
  SA="${PN}-compute@developer.gserviceaccount.com"
  for ROLE in roles/aiplatform.user roles/cloudbuild.builds.builder; do
    gcloud projects add-iam-policy-binding "$PROJECT" \
      --member="serviceAccount:${SA}" --role="$ROLE" --condition=None >/dev/null
  done
fi

# ── the cached image build (the actual speed-up) ──────────────────────────────
# Build via cloudbuild.yaml with --cache-from the previous image, then deploy by
# image ref. Repeat deploys reuse the apt/pip layers: ~1 min instead of ~7.
# Escape hatch: SAAKSHE_DEPLOY_SOURCE=1 restores the old --source path.
AR_REPO="${AR_REPO:-saakshe}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/app"
TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"

if [ -z "${SAAKSHE_DEPLOY_SOURCE:-}" ]; then
  # The AR repo is auto-created when missing (cheap describe; no bootstrap needed).
  gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" \
    --project "$PROJECT" >/dev/null 2>&1 || \
    gcloud artifacts repositories create "$AR_REPO" --repository-format=docker \
      --location "$REGION" --project "$PROJECT" \
      --description "saakshe service images (cached deploys)"
  echo "→ building ${IMAGE}:${TAG} (layer cache from :latest)…"
  gcloud builds submit --config cloudbuild.yaml \
    --substitutions "_IMAGE=${IMAGE},_TAG=${TAG}" \
    --project "$PROJECT" --quiet .
fi

if [ -z "${SAAKSHE_DEPLOY_SOURCE:-}" ]; then
  echo "→ deploying $SERVICE to Cloud Run ($REGION) from ${IMAGE}:${TAG}…"
  gcloud run deploy "$SERVICE" --quiet \
    --image "${IMAGE}:${TAG}" --region "$REGION" --allow-unauthenticated \
    --memory 2Gi --cpu 2 --timeout 300 --max-instances 1 --min-instances 1 --project "$PROJECT" \
    --set-env-vars "$ENV_VARS"
  echo "→ live at:"
  gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format="value(status.url)"
  exit 0
fi

echo "→ deploying $SERVICE to Cloud Run ($REGION) — Cloud Build runs server-side…"
# NOTE: --allow-unauthenticated needs allUsers run.invoker, which the aikizi.com
# Workspace org policy (iam.allowedPolicyMemberDomains) BLOCKS. Lift it project-scoped
# FIRST (reversible) or the service deploys but 403s to the public:
#   gcloud resource-manager org-policies disable-enforce iam.allowedPolicyMemberDomains --project "$PROJECT"
# The app's OWN Google-login gate then protects credits — the policy lift only makes
# the gated app reachable.
# --max-instances=1 --min-instances=1: the resumable flywheel keeps run state in an
# in-process dict (orchestrator._RUNS), so start() and approve() MUST land on the same
# warm instance — otherwise approve 404s "unknown run" and the refund can't fire. One
# warm instance is correct for launch; persisting run state (Supabase) is the follow-up
# that lets this scale out.
gcloud run deploy "$SERVICE" --quiet \
  --source . --region "$REGION" --allow-unauthenticated \
  --memory 2Gi --cpu 2 --timeout 300 --max-instances 1 --min-instances 1 --project "$PROJECT" \
  --set-env-vars "$ENV_VARS"

echo "→ live at:"
gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format="value(status.url)"
