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

## Install

```bash
bash sprkey-custom/install.sh --with-mcp
```

- Skills are copied to `~/.sprkey/skills/productivity/` (the agent's skill
  source of truth) and load on the next session start.
- `--with-mcp` appends the `mcp_servers.sprkey-tools` block to
  `~/.sprkey/config.yaml`; without the flag the block is only printed.
- The MCP server needs the `mcp` package, which is already a Sprkey
  dependency — nothing extra to install.

## Notes

- Month-length data in `bs_calendar.py` comes from the MIT-licensed
  [nepali-datetime](https://pypi.org/project/nepali-datetime/) project.
- Skill files follow the repo authoring standards (`skills/AGENTS.md`):
  short descriptions, native tool references, and standard section order.
- Add new features here rather than editing upstream files, so rebrand and
  sync passes never lose them.
