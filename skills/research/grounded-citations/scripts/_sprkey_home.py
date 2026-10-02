"""Resolve SPRKEY_HOME for standalone skill scripts.

Skill scripts may run outside the Sprkey process (system Python, nix env,
CI) where ``sprkey_constants`` is not importable.  This module provides the
same ``get_sprkey_home()`` contract without requiring it on ``sys.path``.

When ``sprkey_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from sprkey_constants import get_sprkey_home as get_sprkey_home
except (ModuleNotFoundError, ImportError):

    def get_sprkey_home() -> Path:
        """Return the Sprkey home directory (default: ``~/.sprkey``)."""
        val = os.environ.get("SPRKEY_HOME", "").strip()
        return Path(val) if val else Path.home() / ".sprkey"
