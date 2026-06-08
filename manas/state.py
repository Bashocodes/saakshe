"""manas — session-state keys for the memory pipeline.

``common/config`` deliberately holds no per-quadrant ``StateKeys`` (each quadrant
owns its own pipeline state), so manas defines its own here — mirroring arivu's
``config.StateKeys`` but scoped to the ingestion → curate → commit flow. Keeping
these in one place lets the deterministic check-agent and the pure curator math
share the exact same keys the LlmAgents write through their ``output_key``.
"""

from __future__ import annotations


class StateKeys:
    # Inputs / routing
    TOPIC = "topic"
    ORG = "org"
    OUTCOME = "outcome"                 # the day's decision learn() is asked to remember
    ROUTE = "route"                     # Mind Keeper's dispatch plan (output_key)

    # The four imbiber outputs — one per REAL connect channel (disjoint sources,
    # disjoint keys). Honest provenance: a repo goes through the Repo Reader, a
    # site through the Web Reader — never a fictitious "PDF imbiber".
    INGEST_REPO = "ingest_repo"
    INGEST_WEB = "ingest_web"
    INGEST_DOCS = "ingest_docs"
    INGEST_SOCIAL = "ingest_social"

    # The raw source text each imbiber reads (seeded from the connected sources;
    # in live the imbiber's Gemini extracts claims from this real text).
    SOURCE_REPO = "source_repo"
    SOURCE_WEB = "source_web"
    SOURCE_DOCS = "source_docs"
    SOURCE_SOCIAL = "source_social"

    # Curator verify-before-commit loop.
    CURATE_ROUND = "curate_round"
    CURATION = "curation"              # Claude curator's structured synthesis (output_key)
    GROUNDEDNESS = "groundedness"
    CURATE_DONE = "curate_done"
    CURATE_COMMITTED = "curate_committed"
    CURATE_HISTORY = "curate_history"

    # Commit result.
    PACK_FROM = "context_pack_from"
    PACK_TO = "context_pack_to"
    COMMIT_STATUS = "commit_status"    # "committed" | "no_safe_commit"


# Which imbiber reads which REAL connect channel and writes which key
# (role, display, source_key, ingest_key, channel description). One imbiber per
# channel keeps ParallelAgent's "disjoint sources" true and provenance honest.
IMBIBERS = (
    ("repo", "Repo Reader", StateKeys.SOURCE_REPO, StateKeys.INGEST_REPO,
     "the codebase — README, manifests, structure, in-repo docs"),
    ("web", "Web Reader", StateKeys.SOURCE_WEB, StateKeys.INGEST_WEB,
     "the public website — homepage, about, pricing, product copy"),
    ("docs", "Docs Reader", StateKeys.SOURCE_DOCS, StateKeys.INGEST_DOCS,
     "linked docs — handbooks, knowledge base, PDFs"),
    ("social", "Social Reader", StateKeys.SOURCE_SOCIAL, StateKeys.INGEST_SOCIAL,
     "the world's pulse — socials, audience and market signal"),
)
