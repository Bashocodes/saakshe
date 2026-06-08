"""OpenTelemetry tracing setup for kural (optional, fully guarded).

When ``common.config.OTEL_CONSOLE`` is truthy this installs a global
``TracerProvider`` with a console span exporter, so every ADK span (the Claude
qualify, the two scouts fanning out in parallel, each write/fact-check loop turn,
the Claude Claim-Judge, the publish gate) is printed locally. In a deployed Agent
Engine ``enable_tracing=True`` already ships spans to Cloud Trace, so calling this
there is harmless but optional.

Every ``opentelemetry`` import is wrapped in try/except so ``from kural.callbacks
import otel`` succeeds regardless of what is installed — observability never
breaks a run. This mirrors arivu/callbacks/otel.py (the console-tracing layer).
"""

from __future__ import annotations

import logging

from common import config

logger = logging.getLogger("kural.otel")

try:  # pragma: no cover - import availability is environment-dependent
    from opentelemetry import trace as _otel_trace
    from opentelemetry.sdk.trace import TracerProvider as _TracerProvider
    from opentelemetry.sdk.trace.export import (
        ConsoleSpanExporter as _ConsoleSpanExporter,
        SimpleSpanProcessor as _SimpleSpanProcessor,
    )

    try:
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


_TRACING_CONFIGURED = False


def configure_tracing(force: bool = False) -> bool:
    """Install a console-exporting OpenTelemetry TracerProvider for kural.

    Idempotent and safe to call from server/runner startup. Returns ``True`` when
    a provider was installed, ``False`` when skipped (disabled, SDK missing, or
    already configured).
    """
    global _TRACING_CONFIGURED

    if not config.OTEL_CONSOLE:
        return False
    if not _OTEL_AVAILABLE:
        logger.info("OpenTelemetry SDK not importable; kural console tracing skipped.")
        return False
    if _TRACING_CONFIGURED and not force:
        return False

    try:
        if _Resource is not None:
            provider = _TracerProvider(resource=_Resource.create({"service.name": "kural"}))
        else:
            provider = _TracerProvider()
        provider.add_span_processor(_SimpleSpanProcessor(_ConsoleSpanExporter()))
        _otel_trace.set_tracer_provider(provider)
        _TRACING_CONFIGURED = True
        logger.info("kural OpenTelemetry console tracing enabled.")
        return True
    except Exception as exc:  # noqa: BLE001 - never let observability break a run
        logger.warning("Failed to configure kural tracing: %s", exc)
        return False


def tracing_status() -> dict:
    """Lightweight introspection for health endpoints / the cockpit."""
    return {
        "otel_sdk_available": _OTEL_AVAILABLE,
        "console_tracing_enabled": bool(config.OTEL_CONSOLE),
        "configured": _TRACING_CONFIGURED,
    }


__all__ = ["configure_tracing", "tracing_status"]
