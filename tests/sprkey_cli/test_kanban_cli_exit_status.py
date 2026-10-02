"""Regression coverage for Kanban CLI process exit status propagation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]


def _run_sprkey(home: Path, *args: str, marker: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SPRKEY_HOME"] = str(home)
    env["SPRKEY_KANBAN_HOME"] = str(home)
    for name in (
        "SPRKEY_KANBAN_BOARD",
        "SPRKEY_KANBAN_DB",
        "SPRKEY_KANBAN_WORKSPACES_ROOT",
    ):
        env.pop(name, None)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    if marker:
        env["SPRKEY_DELEGATED_CHILD_CONTEXT"] = "1"
    else:
        env.pop("SPRKEY_DELEGATED_CHILD_CONTEXT", None)
    return subprocess.run(
        [sys.executable, "-m", "sprkey_cli.main", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_delegated_child_kanban_cli_refusal_returns_nonzero_exit_status(tmp_path):
    """A printed Kanban mutation refusal must not look like CLI success."""
    home = tmp_path / "sprkey"
    home.mkdir()

    created = _run_sprkey(home, "kanban", "create", "exit status probe", "--json")
    assert created.returncode == 0, created.stderr
    task_id = json.loads(created.stdout)["id"]

    refused = _run_sprkey(
        home,
        "kanban",
        "comment",
        task_id,
        "must be refused",
        marker=True,
    )

    assert refused.returncode == 1
    assert "delegate_task" in refused.stderr
