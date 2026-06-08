# saakshe — the one FastAPI service (the whole site + API + /ws/voice on one port).
# Demo mode by default (creds-free, real ADK orchestration with scripted model output).
# For hybrid/live on Vertex, set SAAKSHE_MODE=live + GOOGLE_CLOUD_PROJECT at deploy time;
# on Cloud Run the service account provides Vertex credentials automatically.
FROM python:3.12-slim

WORKDIR /app

# git: manas clones a connected GitHub repo during the live connect flow.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The quadrants are imported from the repo root; arivu is bootstrapped onto sys.path
# by common/__init__.py. Cloud Run injects $PORT (8080).
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080

CMD exec uvicorn service.app:app --host 0.0.0.0 --port ${PORT}
