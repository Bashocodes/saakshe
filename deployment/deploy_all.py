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

"""Company-level deploy — push all FOUR quadrant agents to Vertex AI Agent Engine.

saakshe ships as one company: four ADK agents (manas · arivu · kalai · kural), each
a managed Agent Engine with tracing on, discoverable by the others over A2A. This
deploys (or lists, or deletes) all four in one command. arivu is the untouched
reference module; the other three import the shared `common` substrate, so each
ships `./common` alongside its own package.

Run from the saakshe project root:

    PYTHONPATH=. python deployment/deploy_all.py --create
    PYTHONPATH=. python deployment/deploy_all.py --list
    PYTHONPATH=. python deployment/deploy_all.py --delete-all

The Gemini-many + Claude-via-Vertex-few split, the deterministic loop termination,
and the single HITL gate per agent are all in the packaged code; the world-facing
publish (kural) and any real spend stay dry-run until explicitly enabled.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common  # noqa: F401 — bootstraps arivu onto sys.path
import vertexai
from absl import app, flags
from dotenv import load_dotenv
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCP staging bucket (name only, no gs://).")
flags.DEFINE_bool("list", False, "List all remote agents.")
flags.DEFINE_bool("create", False, "Create all four quadrant agents.")
flags.DEFINE_bool("delete_all", False, "Delete every saakshe quadrant agent.")

REQUIREMENTS = [
    "google-adk (>=1.31.0)",
    "google-cloud-aiplatform[agent_engines] (>=1.93.0,<2.0.0)",
    "google-genai (>=1.9.0,<2.0.0)",
    "anthropic[vertex] (>=0.49.0)",
    "pydantic (>=2.10.6,<3.0.0)",
    "python-dotenv (>=1.0.0)",
    "absl-py (>=2.2.1,<3.0.0)",
]


def _quadrants() -> list[tuple[str, object, list[str]]]:
    """(display_name, root_agent, extra_packages) for each of the four quadrants."""
    from arivu.agent import root_agent as arivu_root
    from manas.agent import root_agent as manas_root
    from kalai.agent import root_agent as kalai_root
    from kural.agent import root_agent as kural_root
    return [
        ("arivu", arivu_root, ["./arivu/arivu"]),
        ("manas", manas_root, ["./manas", "./common"]),
        ("kalai", kalai_root, ["./kalai", "./common"]),
        ("kural", kural_root, ["./kural", "./common"]),
    ]


def create_all() -> None:
    for name, root, extra in _quadrants():
        print(f"\n— deploying {name} —")
        adk_app = AdkApp(agent=root, enable_tracing=True)
        remote = agent_engines.create(
            adk_app, display_name=root.name,
            requirements=REQUIREMENTS, extra_packages=extra,
        )
        print(f"  created: {remote.resource_name}")
    print("\nAll four quadrants deployed. They discover each other over A2A by agent card.")


def delete_all() -> None:
    names = {n for n, _, _ in _quadrants()}
    for agent in agent_engines.list():
        if agent.display_name in names:
            agent_engines.get(agent.name).delete(force=True)
            print(f"deleted: {agent.display_name} ({agent.name})")


def list_agents() -> None:
    TEMPLATE = '\n{a.name} ("{a.display_name}")\n- Create: {a.create_time}\n- Update: {a.update_time}\n'
    print("All remote agents:\n" + "\n".join(TEMPLATE.format(a=a) for a in agent_engines.list()))


def main(argv: list[str]) -> None:
    del argv
    load_dotenv()
    project_id = FLAGS.project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = FLAGS.location or os.getenv("GOOGLE_CLOUD_LOCATION")
    bucket = FLAGS.bucket or os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")
    print(f"PROJECT: {project_id}\nLOCATION: {location}\nBUCKET: {bucket}")
    if not (project_id and location and bucket):
        print("Set GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_CLOUD_STORAGE_BUCKET "
              "(in .env or the environment).")
        return
    vertexai.init(project=project_id, location=location, staging_bucket=f"gs://{bucket}")
    if FLAGS.list:
        list_agents()
    elif FLAGS.create:
        create_all()
    elif FLAGS.delete_all:
        delete_all()
    else:
        print("Pick one: --create | --list | --delete-all")


if __name__ == "__main__":
    app.run(main)
