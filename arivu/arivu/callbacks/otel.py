"""OpenTelemetry tracing setup + Vertex/BigQuery analytics stub for arivu.

Two layers of observability, both optional and both fully guarded so this module
imports cleanly even when nothing is installed or configured:

  1. **OpenTelemetry console tracing** (``configure_tracing``) — when
     ``config.OTEL_CONSOLE`` is truthy this installs a global ``TracerProvider``
     with a console span exporter, so every ADK span (the frame step, the five
     mantris fanning out in parallel, each debate/prosecution loop turn, the
     chair's Claude verdict, the gate) is printed locally. This is the
     dev/demo lens; in a deployed Agent Engine ``enable_tracing=True`` already
     ships spans to Cloud Trace, so calling this there is harmless but optional.

  2. **Vertex / BigQuery agent analytics** (``configure_analytics_plugin``) — a
     documented STUB. ADK's ``BigQueryAgentAnalyticsPlugin`` streams structured
     run events into a BigQuery dataset for longitudinal analysis (which lens
     dissents most, how often verdicts survive prosecution, convergence-round
     distributions). It is gated on ``config.BIGQUERY_DATASET`` and imported
     lazily *inside* the function, because the plugin's exact import path is
     google-adk-version-sensitive and may not exist in every install — we never
     want a missing-plugin import to break this module's import.

Every ``opentelemetry`` / plugin import below is wrapped in try/except so that
``from arivu.callbacks import otel`` succeeds regardless of what is installed.
"""

from __future__ import annotations

import logging

from arivu import config

logger = logging.getLogger("arivu.otel")

# ── Guarded OpenTelemetry imports ────────────────────────────────────────────
# The SDK is an optional dependency. If any piece is missing we degrade to a
# no-op rather than raising at import time.
try:  # pragma: no cover - import availability is environment-dependent
    from opentelemetry import trace as _otel_trace
    from opentelemetry.sdk.trace import TracerProvider as _TracerProvider
    from opentelemetry.sdk.trace.export import (
        ConsoleSpanExporter as _ConsoleSpanExporter,
        SimpleSpanProcessor as _SimpleSpanProcessor,
    )

    try:
        # Resource is nice-to-have metadata; tolerate its absence.
        from opentelemetry.sdk.resources import Resource as _Resource
    except Exception:  # noqa: BLE001
        _Resource = None  # type: ignore[assignment]

    _OTEL_AVAILABLE = True
except Exception as _exc:  # noqa: BLE001
    _otel_trace = None  # type: ignore[assignment]
    _TracerProvider = None  # type: ignore[assignment]
    _ConsoleSpanExporter = None  # type: ignore[assignment]
    _SimpleSpanProcessor = None  # type: ignore[assignment]
    _Resource = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False
    logger.debug("OpenTelemetry SDK unavailable; tracing disabled (%s)", _exc)


# Module-level guard so repeated startup calls don't stack exporters / re-warn.
_TRACING_CONFIGURED = False


def configure_tracing(force: bool = False) -> bool:
    """Install a console-exporting OpenTelemetry TracerProvider for arivu.

    Idempotent and safe to call from server/runner startup. Returns ``True`` when
    a provider was actually installed, ``False`` when skipped (disabled by
    config, SDK missing, or already configured).

    Args:
        force: reinstall the provider even if one was already configured by us.
    """
    global _TRACING_CONFIGURED

    if not config.OTEL_CONSOLE:
        logger.debug("ARIVU_OTEL_CONSOLE is off; skipping tracer setup.")
        return False

    if not _OTEL_AVAILABLE:
        logger.info(
            "OpenTelemetry SDK not importable; arivu console tracing skipped."
        )
        return False

    if _TRACING_CONFIGURED and not force:
        logger.debug("arivu tracing already configured; skipping.")
        return False

    try:
        if _Resource is not None:
            resource = _Resource.create({"service.name": "arivu"})
            provider = _TracerProvider(resource=resource)
        else:
            provider = _TracerProvider()

        provider.add_span_processor(
            _SimpleSpanProcessor(_ConsoleSpanExporter())
        )
        # set_tracer_provider warns if a provider was already globally set; that
        # is benign — we only force-override when explicitly asked.
        _otel_trace.set_tracer_provider(provider)
        _TRACING_CONFIGURED = True
        logger.info("arivu OpenTelemetry console tracing enabled.")
        return True
    except Exception as exc:  # noqa: BLE001 - never let observability break a run
        logger.warning("Failed to configure arivu tracing: %s", exc)
        return False


def tracing_status() -> dict:
    """Lightweight introspection for health endpoints / the cockpit."""
    return {
        "otel_sdk_available": _OTEL_AVAILABLE,
        "console_tracing_enabled": bool(config.OTEL_CONSOLE),
        "configured": _TRACING_CONFIGURED,
        "bigquery_dataset": config.BIGQUERY_DATASET or None,
    }


def configure_analytics_plugin():
    """STUB: wire ADK's BigQuery agent-analytics plugin (gated on a dataset).

    This is intentionally a stub/note rather than a hard dependency.

    When ``config.BIGQUERY_DATASET`` is set, the intended integration is to
    construct ADK's ``BigQueryAgentAnalyticsPlugin`` and register it on the
    ``Runner`` (``Runner(..., plugins=[plugin])``) so each deliberation streams
    structured run events into the dataset for longitudinal analytics — e.g.
    survival rate of verdicts under prosecution, convergence-round distribution,
    and which mantri dissents most.

    The concrete import path is version-sensitive across google-adk releases
    (commonly ``google.adk.plugins.bigquery_agent_analytics_plugin`` or
    ``google.adk.plugins``), so we import lazily here and tolerate its absence.

    Returns the constructed plugin instance, or ``None`` when disabled or
    unavailable. The orchestrator is responsible for attaching the returned
    plugin to the Runner (see integration_points) — this function does not reach
    into any existing arivu module.
    """
    dataset = config.BIGQUERY_DATASET
    if not dataset:
        logger.debug("ARIVU_BIGQUERY_DATASET unset; analytics plugin disabled.")
        return None

    project = config.GOOGLE_CLOUD_PROJECT or None

    plugin_cls = None
    for module_path, attr in (
        ("google.adk.plugins.bigquery_agent_analytics_plugin",
         "BigQueryAgentAnalyticsPlugin"),
        ("google.adk.plugins", "BigQueryAgentAnalyticsPlugin"),
    ):
        try:  # pragma: no cover - depends on installed google-adk version
            module = __import__(module_path, fromlist=[attr])
            plugin_cls = getattr(module, attr, None)
            if plugin_cls is not None:
                break
        except Exception:  # noqa: BLE001
            continue

    if plugin_cls is None:
        logger.info(
            "BigQueryAgentAnalyticsPlugin not available in this google-adk "
            "install; skipping analytics (dataset=%s).",
            dataset,
        )
        return None

    try:  # pragma: no cover - constructor signature is version-sensitive
        try:
            return plugin_cls(project=project, dataset=dataset)
        except TypeError:
            # Fall back to a permissive call if kwargs differ across versions.
            return plugin_cls(dataset)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to construct BigQuery analytics plugin: %s", exc)
        return None


__all__ = [
    "configure_tracing",
    "configure_analytics_plugin",
    "tracing_status",
]
