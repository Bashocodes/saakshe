# Copyright 2025 saakshe
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Deployment script for kural (ENGAGES) — Vertex AI Agent Engine.

Packages the full ADK mouth pipeline (Claude Coordinator → ParallelAgent research
→ send-eligibility gate, halting before the publish gate) and pushes it to a managed
Agent Engine with tracing on. kural authors nothing — it carries kalai's cleared
master untouched. The world-facing publish stays human-gated (tap 2); the deployed
engine runs the qualify-then-halt spine.

Run from the saakshe project root (PYTHONPATH=. so `kural` and `common` import):

    PYTHONPATH=. python kural/deployment/deploy.py --create
    PYTHONPATH=. python kural/deployment/deploy.py --list
    PYTHONPATH=. python kural/deployment/deploy.py --delete --resource_id <id>
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import vertexai
from absl import app, flags
from dotenv import load_dotenv
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

from kural.agent import root_agent

FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCP staging bucket (name only, no gs://).")
flags.DEFINE_string("resource_id", None, "ReasoningEngine resource ID.")
flags.DEFINE_bool("list", False, "List all agents.")
flags.DEFINE_bool("create", False, "Creates a new agent.")
flags.DEFINE_bool("delete", False, "Deletes an existing agent.")
flags.mark_bool_flags_as_mutual_exclusive(["create", "delete"])

REQUIREMENTS = [
    "google-adk (>=1.31.0)",
    "google-cloud-aiplatform[agent_engines] (>=1.93.0,<2.0.0)",
    "google-genai (>=1.9.0,<2.0.0)",
    "anthropic[vertex] (>=0.49.0)",
    "pydantic (>=2.10.6,<3.0.0)",
    "python-dotenv (>=1.0.0)",
    "absl-py (>=2.2.1,<3.0.0)",
]
EXTRA_PACKAGES = ["./kural", "./common"]


def create() -> None:
    adk_app = AdkApp(agent=root_agent, enable_tracing=True)
    remote_agent = agent_engines.create(
        adk_app, display_name=root_agent.name,
        requirements=REQUIREMENTS, extra_packages=EXTRA_PACKAGES,
    )
    print(f"Created remote agent: {remote_agent.resource_name}")


def delete(resource_id: str) -> None:
    agent_engines.get(resource_id).delete(force=True)
    print(f"Deleted remote agent: {resource_id}")


def list_agents() -> None:
    TEMPLATE = '\n{agent.name} ("{agent.display_name}")\n- Create time: {agent.create_time}\n- Update time: {agent.update_time}\n'
    print("All remote agents:\n" + "\n".join(TEMPLATE.format(agent=a) for a in agent_engines.list()))


def main(argv: list[str]) -> None:
    del argv
    load_dotenv()
    project_id = FLAGS.project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = FLAGS.location or os.getenv("GOOGLE_CLOUD_LOCATION")
    bucket = FLAGS.bucket or os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")
    print(f"PROJECT: {project_id}\nLOCATION: {location}\nBUCKET: {bucket}")
    if not project_id:
        print("Missing required environment variable: GOOGLE_CLOUD_PROJECT"); return
    if not location:
        print("Missing required environment variable: GOOGLE_CLOUD_LOCATION"); return
    if not bucket:
        print("Missing required environment variable: GOOGLE_CLOUD_STORAGE_BUCKET"); return
    vertexai.init(project=project_id, location=location, staging_bucket=f"gs://{bucket}")
    if FLAGS.list:
        list_agents()
    elif FLAGS.create:
        create()
    elif FLAGS.delete:
        if not FLAGS.resource_id:
            print("resource_id is required for delete"); return
        delete(FLAGS.resource_id)
    else:
        print("Unknown command")


if __name__ == "__main__":
    app.run(main)
