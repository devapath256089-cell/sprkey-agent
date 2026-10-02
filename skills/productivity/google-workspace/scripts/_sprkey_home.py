"""Resolve SPRKEY_HOME for standalone skill scripts.

Skill scripts may run outside the Sprkey process (e.g. system Python,
nix env, CI) where ``sprkey_constants`` is not importable.  This module
provides the same ``get_sprkey_home()`` and ``display_sprkey_home()``
contracts as ``sprkey_constants`` without requiring it on ``sys.path``.

When ``sprkey_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``sprkey_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``SPRKEY_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from sprkey_constants import display_sprkey_home as display_sprkey_home
    from sprkey_constants import get_sprkey_home as get_sprkey_home
except (ModuleNotFoundError, ImportError):

    def get_sprkey_home() -> Path:
        """Return the Sprkey home directory (default: ~/.sprkey).

        Mirrors ``sprkey_constants.get_sprkey_home()``."""
        val = os.environ.get("SPRKEY_HOME", "").strip()
        return Path(val) if val else Path.home() / ".sprkey"

    def display_sprkey_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``sprkey_constants.display_sprkey_home()``."""
        home = get_sprkey_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(home)
