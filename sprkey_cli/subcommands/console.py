"""``sprkey console`` subcommand parser."""

from __future__ import annotations

from typing import Callable


def build_console_parser(subparsers, *, cmd_console: Callable) -> None:
    """Attach the safe Sprkey Console REPL subcommand."""
    console_parser = subparsers.add_parser(
        "console", help="Open the safe Sprkey command console",
        description="Open a curated Sprkey command REPL. This is not a raw shell and "
            "does not expose the full Sprkey CLI.")
    console_parser.set_defaults(func=cmd_console)
