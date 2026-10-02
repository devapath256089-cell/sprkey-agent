"""Integration of the verify subsystem with the existing verification stack.

Covers the closed loop the rescoped PR is about:

- ``sprkey verify`` records into the evidence ledger (pass and fail),
- a passing run satisfies the verify-on-stop guard,
- the verify-on-stop nudge names ``sprkey verify --json`` when the workspace
  has a runnable recipe (start command or saved manifest),
- the CLI's detect path merges ``detect_project_facts`` verify commands the
  recipe missed.
"""

import argparse
import json

import pytest

from agent.verification_evidence import (
    mark_workspace_edited,
    record_verify_run,
    verification_status,
)
from agent.verification_stop import build_verify_on_stop_nudge
from sprkey_cli.verify_cmd import run_verify_command

@pytest.fixture(autouse=True)
def _ledger_on(monkeypatch):
    """The ledger is inert unless verify-on-stop is enabled; these tests exercise the ledger."""
    monkeypatch.setenv("SPRKEY_VERIFY_ON_STOP", "1")



def make_args(path, **overrides):
    defaults = dict(
        path=str(path),
        detect_only=False,
        save=False,
        skip_start=False,
        phase=None,
        port=None,
        timeout=60.0,
        ready_timeout=5.0,
        json=True,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def sprkey_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SPRKEY_HOME", str(tmp_path / ".sprkey-home"))
    monkeypatch.delenv("SPRKEY_SESSION_ID", raising=False)
    return tmp_path


def _workspace(tmp_path, *, scripts=None, manifest_recipe=None):
    """A marker-rooted workspace (package.json) with an optional saved recipe."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text(
        json.dumps({"scripts": scripts} if scripts else {}), encoding="utf-8"
    )
    if manifest_recipe is not None:
        sprkey_dir = project / ".sprkey"
        sprkey_dir.mkdir()
        (sprkey_dir / "environment.json").write_text(
            json.dumps({"version": 1, "recipe": manifest_recipe}), encoding="utf-8"
        )
    return project


# ---------------------------------------------------------------------------
# ledger recording
# ---------------------------------------------------------------------------


def test_record_verify_run_marks_workspace_passed(sprkey_home):
    project = _workspace(sprkey_home)
    event = record_verify_run(root=project, session_id="s1", ok=True, output="all green")
    assert event is not None
    assert event["status"] == "passed"
    assert event["kind"] == "verify"
    status = verification_status(session_id="s1", cwd=project)
    assert status["status"] == "passed"
    assert status["evidence"]["canonical_command"] == "sprkey verify"


def test_record_verify_run_records_failure(sprkey_home):
    project = _workspace(sprkey_home)
    record_verify_run(root=project, session_id="s1", ok=False, output="boom")
    status = verification_status(session_id="s1", cwd=project)
    assert status["status"] == "failed"


def test_cli_passing_run_writes_ledger_evidence(sprkey_home, capsys):
    project = _workspace(sprkey_home, manifest_recipe={"name": "Fake", "test": ["echo ok"]})
    code = run_verify_command(make_args(project))
    assert code == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    status = verification_status(session_id=None, cwd=project)
    assert status["status"] == "passed"
    assert status["evidence"]["scope"] == "full"


def test_cli_failing_run_writes_failed_evidence(sprkey_home, capsys):
    project = _workspace(sprkey_home, manifest_recipe={"name": "Fake", "test": ["false"]})
    code = run_verify_command(make_args(project))
    assert code == 1
    status = verification_status(session_id=None, cwd=project)
    assert status["status"] == "failed"


def test_cli_partial_run_records_targeted_scope(sprkey_home, capsys):
    # --skip-start / --phase subsets must never present as full workspace green.
    project = _workspace(sprkey_home, manifest_recipe={"name": "Fake", "test": ["echo ok"]})
    code = run_verify_command(make_args(project, skip_start=True))
    assert code == 0
    status = verification_status(session_id=None, cwd=project)
    assert status["evidence"]["scope"] == "targeted"


def test_cli_run_uses_sprkey_session_id_env(sprkey_home, capsys, monkeypatch):
    monkeypatch.setenv("SPRKEY_SESSION_ID", "sess-42")
    project = _workspace(sprkey_home, manifest_recipe={"name": "Fake", "test": ["echo ok"]})
    run_verify_command(make_args(project))
    assert verification_status(session_id="sess-42", cwd=project)["status"] == "passed"


# ---------------------------------------------------------------------------
# closed loop: edit -> stop guard nudge -> sprkey verify -> guard satisfied
# ---------------------------------------------------------------------------


def test_passing_verify_run_satisfies_stop_guard(sprkey_home, capsys):
    project = _workspace(sprkey_home, manifest_recipe={"name": "Fake", "test": ["echo ok"]})
    changed = str(project / "src" / "app.ts")
    mark_workspace_edited(session_id="default", cwd=project, paths=[changed])
    assert build_verify_on_stop_nudge(session_id="default", changed_paths=[changed]) is not None

    assert run_verify_command(make_args(project)) == 0

    assert build_verify_on_stop_nudge(session_id="default", changed_paths=[changed]) is None


# ---------------------------------------------------------------------------
# nudge wording: recipe-aware `sprkey verify --json` suggestion
# ---------------------------------------------------------------------------


def test_nudge_mentions_sprkey_verify_when_recipe_has_start(sprkey_home):
    project = _workspace(sprkey_home, scripts={"test": "vitest", "dev": "vite"})
    changed = str(project / "src" / "app.ts")
    mark_workspace_edited(session_id="s1", cwd=project, paths=[changed])
    nudge = build_verify_on_stop_nudge(session_id="s1", changed_paths=[changed])
    assert nudge is not None
    assert "sprkey verify --json" in nudge
    # The cheap verify commands are still listed first.
    assert "npm run test" in nudge


def test_nudge_mentions_sprkey_verify_when_manifest_exists(sprkey_home):
    # No start script, but a saved .sprkey/environment.json qualifies.
    project = _workspace(
        sprkey_home,
        scripts={"test": "vitest"},
        manifest_recipe={"name": "Fake", "test": ["echo ok"]},
    )
    changed = str(project / "src" / "app.ts")
    mark_workspace_edited(session_id="s1", cwd=project, paths=[changed])
    nudge = build_verify_on_stop_nudge(session_id="s1", changed_paths=[changed])
    assert nudge is not None
    assert "sprkey verify --json" in nudge


def test_nudge_keeps_plain_wording_without_recipe_start(sprkey_home):
    # Verify commands but no start script and no manifest: today's wording.
    project = _workspace(sprkey_home, scripts={"test": "vitest"})
    changed = str(project / "src" / "app.ts")
    mark_workspace_edited(session_id="s1", cwd=project, paths=[changed])
    nudge = build_verify_on_stop_nudge(session_id="s1", changed_paths=[changed])
    assert nudge is not None
    assert "sprkey verify" not in nudge


def test_nudge_recipe_detection_failure_is_silent(sprkey_home, monkeypatch):
    # A broken recipe detector must never break the nudge path.
    import agent.verify.recipes as recipes

    def boom(_root):
        raise RuntimeError("detector exploded")

    monkeypatch.setattr(recipes, "detect_recipe", boom)
    project = _workspace(sprkey_home, scripts={"test": "vitest", "dev": "vite"})
    changed = str(project / "src" / "app.ts")
    mark_workspace_edited(session_id="s1", cwd=project, paths=[changed])
    nudge = build_verify_on_stop_nudge(session_id="s1", changed_paths=[changed])
    assert nudge is not None
    assert "sprkey verify" not in nudge


# ---------------------------------------------------------------------------
# detection unification: project-facts commands merged into detected recipes
# ---------------------------------------------------------------------------


def test_detect_path_merges_project_facts_commands(sprkey_home, capsys):
    project = _workspace(sprkey_home)  # package.json with no scripts
    scripts_dir = project / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "run_tests.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    code = run_verify_command(make_args(project, detect_only=True))
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "detected"
    tests = payload["recipe"]["test"]
    assert "scripts/run_tests.sh" in tests
    assert "pytest" in tests


def test_manifest_recipe_is_not_merged(sprkey_home, capsys):
    # A saved manifest is the user-edited source of truth; leave it alone.
    project = _workspace(sprkey_home, manifest_recipe={"name": "Fake", "test": ["echo ok"]})
    (project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    code = run_verify_command(make_args(project, detect_only=True))
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "manifest"
    assert payload["recipe"]["test"] == ["echo ok"]


def test_merge_skips_commands_recipe_already_has(sprkey_home, capsys):
    project = _workspace(sprkey_home, scripts={"test": "vitest"})
    code = run_verify_command(make_args(project, detect_only=True))
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["recipe"]["test"].count("npm run test") == 1
