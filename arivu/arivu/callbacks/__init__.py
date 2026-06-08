"""arivu observability callbacks.

Kept intentionally import-light: importing this package must never pull in the
OpenTelemetry SDK or the Vertex/BigQuery analytics plugin, both of which are
optional at runtime. The actual wiring lives in :mod:`arivu.callbacks.otel`, all
of whose heavy imports are guarded so this package imports cleanly in any
environment (tests, deploy-script parsing, demo mode).

Public entry point::

    from arivu.callbacks.otel import configure_tracing
    configure_tracing()  # idempotent; no-op without the otel SDK
"""

from __future__ import annotations

__all__ = ["configure_tracing"]


def __getattr__(name):
    # Lazily forward the one public symbol so `from arivu.callbacks import
    # configure_tracing` works without importing otel.py at package-import time.
    if name == "configure_tracing":
        from .otel import configure_tracing

        return configure_tracing
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
