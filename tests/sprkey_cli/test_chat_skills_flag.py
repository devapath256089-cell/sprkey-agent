import sys


def test_top_level_skills_flag_defaults_to_chat(monkeypatch):
    import sprkey_cli.main as main_mod

    captured = {}

    def fake_cmd_chat(args):
        captured["skills"] = args.skills
        captured["command"] = args.command

    monkeypatch.setattr(main_mod, "cmd_chat", fake_cmd_chat)
    monkeypatch.setattr(
        sys,
        "argv",
        ["sprkey", "-s", "sprkey-agent-dev,github-auth"],
    )

    main_mod.main()

    assert captured == {
        "skills": ["sprkey-agent-dev,github-auth"],
        "command": None,
    }


def test_continue_worktree_and_skills_flags_work_together(monkeypatch):
    import sprkey_cli.main as main_mod

    captured = {}

    def fake_cmd_chat(args):
        captured["continue_last"] = args.continue_last
        captured["worktree"] = args.worktree
        captured["skills"] = args.skills
        captured["command"] = args.command

    monkeypatch.setattr(main_mod, "cmd_chat", fake_cmd_chat)
    monkeypatch.setattr(
        sys,
        "argv",
        ["sprkey", "-c", "-w", "-s", "sprkey-agent-dev"],
    )

    main_mod.main()

    assert captured == {
        "continue_last": True,
        "worktree": True,
        "skills": ["sprkey-agent-dev"],
        "command": "chat",
    }
