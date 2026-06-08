"""saakshe.common — the shared substrate behind the one witness.

Importing this package also makes the untouched, already-green ``arivu`` module
importable from the unified service regardless of cwd: arivu lives at
``<root>/arivu/arivu`` with its project root at ``<root>/arivu``, so we add that
project root to ``sys.path``. arivu's own files are never modified.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent          # <root>/saakshe
_ARIVU_ROOT = _ROOT / "arivu"                            # holds the `arivu` package
if _ARIVU_ROOT.is_dir() and str(_ARIVU_ROOT) not in sys.path:
    sys.path.insert(0, str(_ARIVU_ROOT))

from . import a2a, config, models, stream  # noqa: E402,F401

__all__ = ["a2a", "config", "models", "stream"]
