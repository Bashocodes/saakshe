#!/usr/bin/env bash
# Deploy the saakshe site to Google Cloud Run — HYBRID mode (real Gemini, scripted
# Claude while the Vertex Anthropic quota is pending). One command, idempotent.
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

echo "→ enabling APIs (Run · Build · Artifact Registry · Vertex)…"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com --project "$PROJECT"

echo "→ granting the Cloud Run runtime service account Vertex access…"
PN=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${PN}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user" --condition=None >/dev/null

echo "→ deploying $SERVICE to Cloud Run ($REGION) — Cloud Build runs server-side…"
gcloud run deploy "$SERVICE" \
  --source . --region "$REGION" --allow-unauthenticated \
  --memory 2Gi --cpu 2 --timeout 300 --project "$PROJECT" \
  --set-env-vars "SAAKSHE_MODE=live,ARIVU_MODE=live,SAAKSHE_CLAUDE_MODE=demo,ARIVU_CLAUDE_MODE=demo,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=global,SAAKSHE_CLAUDE_LOCATION=global,ARIVU_CLAUDE_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=TRUE,SAAKSHE_MODEL_PRO=gemini-3.1-pro-preview,SAAKSHE_MODEL_FLASH=gemini-3.5-flash,ARIVU_MODEL_CHAIR=gemini-3.1-pro-preview,ARIVU_MODEL_MANTRI=gemini-3.5-flash"

echo "→ live at:"
gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format="value(status.url)"
