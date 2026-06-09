#!/usr/bin/env bash
# Deploy the saakshe site to Google Cloud Run — HYBRID mode (real Gemini, scripted
# Claude while the Vertex Anthropic quota is pending). One command, idempotent.
#
# Two profiles (SAAKSHE_DEPLOY_PROFILE, default "demo"):
#   demo     — what saakshe.com runs today: the open, no-sign-in judged demo.
#              File store, no auth, no billing, SEALED mutations + rate limits
#              (SAAKSHE_PUBLIC_DEMO=1). Needs NO Supabase config.
#   billing  — the multi-tenant SaaS deploy: Supabase store, Google sign-in,
#              credits. Requires the Supabase env below.
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

# ── the model/mode env both profiles share (hybrid: real Gemini, scripted Claude) ─
COMMON_ENV="SAAKSHE_MODE=live@ARIVU_MODE=live@SAAKSHE_CLAUDE_MODE=demo@ARIVU_CLAUDE_MODE=demo"
COMMON_ENV+="@GOOGLE_CLOUD_PROJECT=${PROJECT}@GOOGLE_CLOUD_LOCATION=global"
COMMON_ENV+="@SAAKSHE_CLAUDE_LOCATION=global@ARIVU_CLAUDE_LOCATION=global@GOOGLE_GENAI_USE_VERTEXAI=TRUE"
COMMON_ENV+="@SAAKSHE_MODEL_PRO=gemini-3.1-pro-preview@SAAKSHE_MODEL_FLASH=gemini-3.5-flash"
COMMON_ENV+="@ARIVU_MODEL_CHAIR=gemini-3.1-pro-preview@ARIVU_MODEL_MANTRI=gemini-3.5-flash"

case "$PROFILE" in
  demo)
    # The open judged demo: shared file store seeded in the image, mutations sealed,
    # model routes rate-limited. No Supabase needed; no sign-in shown.
    ENV_VARS="^@^${COMMON_ENV}@SAAKSHE_STORE=file@SAAKSHE_PUBLIC_DEMO=1"
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
    ENV_VARS="^@^${COMMON_ENV}@SAAKSHE_STORE=supabase"
    ENV_VARS+="@SAAKSHE_SUPABASE_URL=${SAAKSHE_SUPABASE_URL}@SAAKSHE_SUPABASE_KEY=${SAAKSHE_SUPABASE_KEY}"
    ENV_VARS+="@SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}@OWNER_EMAILS=${OWNER_EMAILS}@SIGNUP_GRANT=${SIGNUP_GRANT}"
    ENV_VARS+="@COST_FLYWHEEL_RUN=${COST_FLYWHEEL_RUN}@COST_CONNECT_INGEST=${COST_CONNECT_INGEST}"
    ENV_VARS+="@COST_MANAS_EDIT=${COST_MANAS_EDIT}@COST_KALAI_MAKE=${COST_KALAI_MAKE}@COST_KURAL_ENGAGE=${COST_KURAL_ENGAGE}"
    ;;
  *)
    echo "unknown SAAKSHE_DEPLOY_PROFILE '$PROFILE' (use demo | billing)" >&2; exit 1
    ;;
esac
echo "→ profile: $PROFILE"

echo "→ enabling APIs (Run · Build · Artifact Registry · Vertex)…"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com --project "$PROJECT"

echo "→ granting the compute SA the roles it needs (Vertex at runtime + Cloud Build at deploy)…"
PN=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")
SA="${PN}-compute@developer.gserviceaccount.com"
for ROLE in roles/aiplatform.user roles/cloudbuild.builds.builder; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${SA}" --role="$ROLE" --condition=None >/dev/null
done

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
