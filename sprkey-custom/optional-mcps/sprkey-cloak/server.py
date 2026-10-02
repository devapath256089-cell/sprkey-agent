#!/usr/bin/env python3
"""Sprkey Cloak - PII cloaking MCP server bundled with the Sprkey custom pack.

Inspired by the AgentCloak idea: private data never reaches the LLM.
Before sending sensitive text to the model, run ``cloak_text`` — emails,
phone numbers (incl. Nepali formats), IPs, API keys/secrets, credentials in
URLs, citizenship-style IDs and card-like numbers are replaced with
deterministic synthetic substitutes. After the model answers, run
``uncloak_text`` to swap the fakes back to the real values.

  cloak_text(text, session)   -> cloaked text + per-category counts
  uncloak_text(text, session) -> original text restored
  cloak_file(path, session)   -> cloak/uncloak a file (in place or write_path)
  cloak_status(session)       -> how many mappings a session holds
  purge_session(session)      -> delete a session's mapping file

Sessions live in ``$SPRKEY_HOME/cloak_sessions/<session>.json`` (default
home ``~/.sprkey``) so cloaking and uncloaking can happen in different turns.

Tool logic lives in plain functions below so it can be unit-tested without
the ``mcp`` package installed; the FastMCP wiring is isolated at the bottom.

Limitations (by design, keep it honest):
  - Person names are NOT detected (needs NER; too risky with regex).
  - Free-form addresses are NOT detected.
  - Regexes are conservative; always eyeball critical documents.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

# --------------------------------------------------------------------------
# detection patterns (order matters: most specific first)
# --------------------------------------------------------------------------

PATTERNS: list[tuple[str, str]] = [
    # API keys / tokens / secrets (recognizable prefixes)
    ("secret", r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})\b"),
    # URLs with embedded credentials  scheme://user:pass@host/...
    ("url_creds", r"[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@[^\s]+"),
    ("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # Nepal mobile: 98/97/96 + 8 digits, optional +977
    ("phone_np", r"(?:\+?977[- ]?)?\b9[678]\d{8}\b"),
    # Nepal landline: 01 + 6-7 digits (must carry 977 or leading 0)
    ("phone_landline", r"(?:\+?977[- ]?|\b0)1[- ]?\d{6,7}\b"),
    ("phone_intl", r"\+\d{1,3}[- ]\d{7,12}\b"),
    # Nepali citizenship-style IDs: 27-01-72-12345
    ("citizenship_np", r"\b\d{2}-\d{2}-\d{2}-\d{4,5}\b"),
    # card / bank-account-like long digit runs
    ("card_like", r"\b\d{13,19}\b"),
    ("ipv4", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
]

_COMPILED = [(cat, re.compile(rx)) for cat, rx in PATTERNS]

_FAKE_PREFIX = {
    "phone_np": "98",
    "phone_landline": "01-",
    "phone_intl": "+000",
    "card_like": "9900",
}


# --------------------------------------------------------------------------
# session storage
# --------------------------------------------------------------------------


def _sprkey_home() -> Path:
    home = os.environ.get("SPRKEY_HOME")
    return Path(home).expanduser() if home else Path.home() / ".sprkey"


def _session_file(session: str) -> Path:
    safe = "".join(c for c in session if c.isalnum() or c in "-_") or "default"
    return _sprkey_home() / "cloak_sessions" / f"{safe}.json"


def _load_session(session: str) -> dict:
    path = _session_file(session)
    if not path.exists():
        return {"forward": {}, "reverse": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"forward": {}, "reverse": {}}


def _save_session(session: str, data: dict) -> None:
    path = _session_file(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _digest(session: str, salt: str, original: str, width: int) -> str:
    h = hashlib.md5(f"{session}|{salt}|{original}".encode()).hexdigest()
    return str(int(h, 16) % (10**width)).zfill(width)


def _fake_for(session: str, category: str, original: str) -> str:
    """Deterministic synthetic substitute for one detected value."""
    digits = _digest(session, "fake", original, 12)
    if category == "secret":
        prefix = original[:4] if not original.startswith(("github_pat_", "xox")) else original.split("-")[0][:10]
        return f"{prefix}CLOAKED{digits[:10]}"
    if category == "email":
        return f"user{digits[:6]}@cloaked{digits[6:8]}.test"
    if category == "url_creds":
        scheme_end = original.find("://")
        at = original.rfind("@")
        return f"{original[:scheme_end + 3]}cloaked{digits[:4]}:cloaked@{original[at + 1:]}"
    if category == "citizenship_np":
        return f"{digits[0:2]}-{digits[2:4]}-{digits[4:6]}-{digits[6:11]}"
    if category == "ipv4":
        return f"10.{int(digits[0:2])}.{int(digits[2:4])}.{int(digits[4:6])}"
    width = {"phone_np": 8, "phone_landline": 6, "phone_intl": 9, "card_like": 12}.get(category, 8)
    return _FAKE_PREFIX.get(category, "") + digits[:width]


# --------------------------------------------------------------------------
# core cloak / uncloak
# --------------------------------------------------------------------------


def _cloak(text: str, session: str) -> tuple[str, dict]:
    data = _load_session(session)
    forward, reverse = data["forward"], data["reverse"]
    counts: dict[str, int] = {}

    def _sub(match: re.Match) -> str:
        original = match.group(0)
        if original in forward:
            cat = forward[original]["cat"]
            fake = forward[original]["fake"]
        else:
            cat = next(c for c, rx in _COMPILED if rx.fullmatch(original))
            fake = _fake_for(session, cat, original)
            for i in range(1, 100):  # avoid synthetic collisions, stay format-valid
                if fake not in reverse or reverse[fake] == original:
                    break
                fake = _fake_for(session, cat, f"{original}#{i}")
            forward[original] = {"cat": cat, "fake": fake}
            reverse[fake] = original
        counts[cat] = counts.get(cat, 0) + 1
        return fake

    out = text
    for _cat, rx in _COMPILED:
        out = rx.sub(_sub, out)
    if counts:
        _save_session(session, {"forward": forward, "reverse": reverse})
    return out, counts


def _uncloak(text: str, session: str) -> tuple[str, int]:
    """Restore real values. Iterates because fakes can nest: an earlier
    pattern's fake (e.g. a cloaked URL) may itself contain a later pattern's
    match (e.g. an email-looking userinfo), so restore from inside out."""
    data = _load_session(session)
    reverse = data["reverse"]
    total = 0
    for _pass in range(10):
        restored = 0
        for fake in sorted(reverse, key=len, reverse=True):
            if fake in text:
                text = text.replace(fake, reverse[fake])
                restored += 1
        total += restored
        if restored == 0:
            break
    return text, total


# --------------------------------------------------------------------------
# tool logic (plain functions)
# --------------------------------------------------------------------------


def cloak_text(text: str, session: str = "default") -> str:
    """Replace sensitive values with synthetic fakes (same session = same fake)."""
    if not text.strip():
        return "error: nothing to cloak (empty text)"
    out, counts = _cloak(text, session)
    if not counts:
        return "no sensitive values detected - text unchanged.\n---\n" + out
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    return f"cloaked [{summary}] in session '{session}'.\n---\n{out}"


def uncloak_text(text: str, session: str = "default") -> str:
    """Restore real values previously cloaked in the same session."""
    if not text.strip():
        return "error: nothing to uncloak (empty text)"
    out, restored = _uncloak(text, session)
    return f"restored {restored} value(s) from session '{session}'.\n---\n{out}"


def cloak_file(
    path: str, session: str = "default", write_path: str = "", uncloak: bool = False
) -> str:
    """Cloak (or uncloak) a text file; in place by default, or to write_path."""
    src = Path(path).expanduser()
    if not src.exists():
        return f"error: file not found: {src}"
    content = src.read_text(encoding="utf-8", errors="replace")
    if uncloak:
        out, n = _uncloak(content, session)
        note = f"uncloaked {n} value(s)"
    else:
        out, counts = _cloak(content, session)
        note = "cloaked " + (", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "nothing")
    dest = Path(write_path).expanduser() if write_path else src
    dest.write_text(out, encoding="utf-8")
    return f"{note} in session '{session}' -> {dest}"


def cloak_status(session: str = "default") -> str:
    """Show how many mappings a cloak session holds, by category."""
    data = _load_session(session)
    if not data["forward"]:
        return f"session '{session}' is empty"
    by_cat: dict[str, int] = {}
    for v in data["forward"].values():
        by_cat[v["cat"]] = by_cat.get(v["cat"], 0) + 1
    summary = ", ".join(f"{k}: {n}" for k, n in sorted(by_cat.items()))
    return f"session '{session}': {len(data['forward'])} mapping(s) [{summary}]"


def purge_session(session: str = "default") -> str:
    """Delete a cloak session's mapping file (fakes become unrestorable)."""
    path = _session_file(session)
    if path.exists():
        path.unlink()
        return f"session '{session}' purged ({path})"
    return f"session '{session}' has nothing to purge"


# --------------------------------------------------------------------------
# FastMCP wiring (isolated so logic above stays dependency-free)
# --------------------------------------------------------------------------


def build_server():
    """Return a FastMCP instance with all tools registered."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:  # standalone fastmcp package fallback
        from fastmcp import FastMCP  # type: ignore

    mcp = FastMCP(
        "sprkey-cloak",
        instructions="PII cloaking: synthetic data goes to the model, real data comes back after.",
    )
    for fn in (cloak_text, uncloak_text, cloak_file, cloak_status, purge_session):
        mcp.tool()(fn)
    return mcp


def main() -> int:
    try:
        build_server().run()
    except ImportError as exc:
        print(
            f"sprkey-cloak requires the 'mcp' package (already a Sprkey "
            f"dependency): pip install mcp  ({exc})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
