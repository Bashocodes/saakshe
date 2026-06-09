"""common.tests — unit tests for the shared substrate.

These exercise the reusable primitives (the chamber skeleton, etc.) in isolation,
independent of any faculty. They run in demo mode (no live credentials): the full
ADK orchestration runs; only token generation is replayed via a scripted resolver
registered under a throwaway test namespace.
"""
