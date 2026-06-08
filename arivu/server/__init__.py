"""arivu — FastAPI live bridge.

Turns the deliberation chamber into HTTP the cockpit (arivu.html) can call.
The ASGI app lives in ``server.app:app``.

    uvicorn server.app:app --port 8771   # run from the project root

Run-mode is whatever ``arivu.config.mode()`` resolves (set ARIVU_MODE=demo to
force the offline replay). All side effects stay dry-run unless
ARIVU_SERVER_ALLOW_LIVE_EXEC=true *and* config.is_live().
"""

from .app import app  # noqa: F401

__all__ = ["app"]
