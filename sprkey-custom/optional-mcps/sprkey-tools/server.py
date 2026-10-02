#!/usr/bin/env python3
"""Sprkey Tools - a local stdio MCP server bundled with the Sprkey custom pack.

Practical everyday tools for the Sprkey agent:

  - remember / recall / forget : persistent key-value memory (JSON backed)
  - worklog_append             : append a structured block to a worklog file
  - github_repo_stats          : public repo stats via the GitHub REST API
  - sysinfo                    : host snapshot (platform, disk, memory, load)

The server speaks MCP over stdio and is registered in ``~/.sprkey/config.yaml``::

    mcp_servers:
      sprkey-tools:
        command: "python3"
        args: ["/path/to/sprkey-custom/optional-mcps/sprkey-tools/server.py"]

Tool logic lives in plain functions below so it can be unit-tested without
the ``mcp`` package installed; the FastMCP wiring is isolated at the bottom.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import shutil
import sys
import urllib.request
from pathlib import Path

__version__ = "1.0.0"

# --------------------------------------------------------------------------
# storage helpers
# --------------------------------------------------------------------------


def _sprkey_home() -> Path:
    home = os.environ.get("SPRKEY_HOME")
    return Path(home).expanduser() if home else Path.home() / ".sprkey"


def _memory_file() -> Path:
    return _sprkey_home() / "sprkey_tools_memory.json"


def _load_memory() -> dict:
    path = _memory_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # corrupt or unreadable file: keep a backup rather than destroying it
        backup = path.with_suffix(".json.bak")
        try:
            shutil.copy2(path, backup)
        except OSError:
            pass
        return {}


def _save_memory(data: dict) -> None:
    path = _memory_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------
# tool logic (plain functions, no MCP dependency)
# --------------------------------------------------------------------------


def remember(key: str, value: str) -> str:
    """Store a persistent note under a key. Overwrites existing keys."""
    key = key.strip()
    if not key:
        return "error: key must not be empty"
    data = _load_memory()
    data[key] = {
        "value": value,
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    _save_memory(data)
    return f"remembered '{key}' ({len(data)} entries total)"


def recall(key: str = "") -> str:
    """Read a stored note by key, or list all keys when key is empty."""
    data = _load_memory()
    if not key:
        if not data:
            return "memory is empty"
        lines = [
            f"- {k}  (updated {v.get('updated_at', '?')})" for k, v in sorted(data.items())
        ]
        return f"{len(data)} entries:\n" + "\n".join(lines)
    entry = data.get(key)
    if entry is None:
        return f"no entry for '{key}'"
    return entry["value"]


def forget(key: str) -> str:
    """Delete a stored note by key."""
    data = _load_memory()
    if key not in data:
        return f"no entry for '{key}'"
    del data[key]
    _save_memory(data)
    return f"forgot '{key}' ({len(data)} entries remain)"


WORKLOG_BLOCK = """\
---
Task ID: {task_id}
Agent: {agent}
Task: {task}

Work Log:
{work_log}

Stage Summary:
- {stage_summary}
"""


def worklog_append(
    task_id: str,
    task: str,
    work_log: str,
    stage_summary: str,
    agent: str = "Sprkey",
    worklog_path: str = "",
) -> str:
    """Append a structured Task block to the worklog markdown file."""
    path = Path(worklog_path).expanduser() if worklog_path else Path("worklog.md")
    if path.parent and str(path.parent):
        path.parent.mkdir(parents=True, exist_ok=True)
    bullets = "\n".join(f"- {line.strip()}" for line in work_log.splitlines() if line.strip())
    block = WORKLOG_BLOCK.format(
        task_id=task_id.strip(),
        agent=agent.strip() or "Sprkey",
        task=task.strip(),
        work_log=bullets or "- (no steps recorded)",
        stage_summary=stage_summary.strip(),
    )
    sep = "" if not path.exists() else "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(sep + block + "\n")
    return f"appended task '{task_id}' to {path}"


def github_repo_stats(repo: str) -> str:
    """Fetch public stats for a GitHub repo, e.g. 'octocat/Hello-World'."""
    repo = repo.strip().strip("/")
    if repo.count("/") != 1:
        return "error: repo must look like 'owner/name'"
    url = f"https://api.github.com/repos/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sprkey-tools-mcp",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001 - report network errors as text
        return f"error fetching {repo}: {exc}"
    pushed = (data.get("pushed_at") or "?")[:10]
    return (
        f"{data.get('full_name', repo)}\n"
        f"  stars: {data.get('stargazers_count', '?')}  "
        f"forks: {data.get('forks_count', '?')}  "
        f"open issues: {data.get('open_issues_count', '?')}\n"
        f"  default branch: {data.get('default_branch', '?')}  "
        f"last push: {pushed}\n"
        f"  {(data.get('description') or '').strip()}"
    )


def sysinfo() -> str:
    """One-shot host snapshot: platform, disk, memory, load, time."""
    mem_total = mem_free = "?"
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            info = {k: v for k, v in (ln.split(":", 1) for ln in fh if ":" in ln)}
        mem_total = info.get("MemTotal", "? GB").strip()
        mem_free = info.get("MemAvailable", "? GB").strip()
    except OSError:
        pass
    du = shutil.disk_usage("/")
    now = _dt.datetime.now().astimezone()
    return (
        f"host: {platform.node() or '?'}  os: {platform.system()} "
        f"{platform.release()} ({platform.machine()})\n"
        f"python: {platform.python_version()}\n"
        f"disk /: {du.used // (2**30)} GiB used / {du.total // (2**30)} GiB\n"
        f"memory: total {mem_total}, available {mem_free}\n"
        f"load: {os.getloadavg()[0]:.2f}  local time: {now.isoformat(timespec='seconds')}"
    )


# --------------------------------------------------------------------------
# FastMCP wiring (isolated so logic above stays dependency-free)
# --------------------------------------------------------------------------


def build_server():
    """Return a FastMCP instance with all tools registered."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:  # standalone fastmcp package fallback
        from fastmcp import FastMCP  # type: ignore

    mcp = FastMCP("sprkey-tools", instructions=__doc__.split("Practical")[0])

    mcp.tool()(remember)
    mcp.tool()(recall)
    mcp.tool()(forget)
    mcp.tool()(worklog_append)
    mcp.tool()(github_repo_stats)
    mcp.tool()(sysinfo)
    return mcp


def main() -> int:
    try:
        build_server().run()
    except ImportError as exc:
        print(
            f"sprkey-tools requires the 'mcp' package (already a Sprkey "
            f"dependency): pip install mcp  ({exc})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
