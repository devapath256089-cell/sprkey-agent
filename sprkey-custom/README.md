# sprkey-custom/

First-party additions to Sprkey that live outside the upstream tree.
Everything in this directory survives upstream syncs untouched
(`sprkey_upstream_sync.sh` preserves it), so it is the safe home for
customizations that upstream does not ship.

## What is inside

| Path | What it is |
|------|------------|
| `skills/worklog-keeper/` | Skill: structured session worklog with Task IDs, append discipline, and daily summaries. |
| `skills/nepali-calendar/` | Skill: Bikram Sambat <-> AD date conversion, NPT (+5:45) aware, with an offline converter script (`scripts/bs_calendar.py`, BS 1975-2100). |
| `optional-mcps/sprkey-tools/` | Local stdio MCP server: persistent memory (`remember`/`recall`/`forget`), `worklog_append`, `github_repo_stats`, `sysinfo`. |
| `optional-mcps/sprkey-cloak/` | Local stdio MCP server: PII cloaking (AgentCloak-style) — `cloak_text`/`uncloak_text`/`cloak_file`/`cloak_status`/`purge_session`. Synthetic data goes to the model, real values are restored from the session mapping afterwards. Offline, no external service. |

## Install

```bash
bash sprkey-custom/install.sh --with-mcp
```

- Skills are copied to `~/.sprkey/skills/productivity/` (the agent's skill
  source of truth) and load on the next session start.
- `--with-mcp` appends the `mcp_servers.sprkey-tools` and
  `mcp_servers.sprkey-cloak` blocks to `~/.sprkey/config.yaml`; without the
  flag the blocks are only printed.
- The MCP servers need the `mcp` package, which is already a Sprkey
  dependency — nothing extra to install.

## Cloaking workflow (sprkey-cloak)

1. `cloak_text` anything sensitive before it reaches the model — emails,
   Nepali/International phone numbers, IPs, API keys (`ghp_`, `sk-`, `AKIA`,
   `xox`), credentials in URLs, citizenship-style IDs, and card-like digit
   runs become consistent fake values within the session.
2. Ask the model to work on the cloaked text as usual.
3. `uncloak_text` the model's reply — real values are restored from the
   session mapping (`~/.sprkey/cloak_sessions/`).
4. `purge_session` when done, so mappings never linger.

Person names and free-form addresses are intentionally not detected
(regex-only design; NER would be needed and is riskier than helpful here).

## Notes

- Month-length data in `bs_calendar.py` comes from the MIT-licensed
  [nepali-datetime](https://pypi.org/project/nepali-datetime/) project.
- Skill files follow the repo authoring standards (`skills/AGENTS.md`):
  short descriptions, native tool references, and standard section order.
- Add new features here rather than editing upstream files, so rebrand and
  sync passes never lose them.
