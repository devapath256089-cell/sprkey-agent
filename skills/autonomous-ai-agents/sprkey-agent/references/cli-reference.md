# Sprkey CLI Reference

Live sources when anything looks stale: `sprkey --help`, `sprkey <command> --help`,
https://sprkey-agent.nightrainbowresearch.com/docs/reference/cli-commands

### Global Flags

```
sprkey [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
sprkey chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
sprkey setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
sprkey model                Interactive model/provider picker
sprkey fallback [add|remove|list]  Fallback provider chain
sprkey config [show|edit|get|set|unset|path|env-path|check|migrate]
sprkey login / logout       OAuth sign-in / clear stored auth
sprkey doctor [--fix]       Check dependencies and config
sprkey status [--all]       Component status
```

### Tools & Skills

```
sprkey tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

sprkey skills list|browse|search QUERY|inspect ID
sprkey skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
sprkey skills config        Enable/disable skills per platform
sprkey skills check|update|uninstall|publish PATH
sprkey skills tap add REPO  Add a GitHub repo as a skill source
sprkey bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
sprkey mcp add NAME (--url or --command) | remove | list | test NAME
sprkey mcp catalog | install NAME     Curated catalog install
sprkey mcp configure NAME             Toggle tool selection
sprkey mcp serve                      Run Sprkey as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
sprkey gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `sprkey photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://sprkey-agent.nightrainbowresearch.com/docs/user-guide/messaging/

### Sessions

```
sprkey sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
sprkey cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
sprkey webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
sprkey profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
sprkey profile rename A B | alias NAME | export NAME | import FILE
sprkey profile migrate-identity A B   Retry a completed rename's session/routing identity migration
```

### Credentials & Pools

```
sprkey auth                 Interactive credential manager
sprkey auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
sprkey auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
sprkey desktop / gui        Native desktop app
sprkey dashboard            Web admin panel + embedded chat (--stop / --status)
sprkey proxy                OpenAI-compatible local proxy backed by an OAuth provider
sprkey portal               Quick setup / sign in via Nous Portal
sprkey kanban <verb>        Multi-agent work-queue board
sprkey project              Named multi-folder workspaces
sprkey skin list|use|set    Switch/tweak skins (see references/themes.md)
sprkey pets <verb>          Pet mascots (see references/petdex.md)
sprkey memory setup|status|off|reset   Memory provider
sprkey secrets bitwarden|onepassword   External secret stores
sprkey moa                  Mixture-of-Agents slots
sprkey hooks / security / backup / import / checkpoints / console
sprkey logs [-f] [errors]   View agent/error logs
sprkey send                 One-off message through a gateway platform
sprkey pairing / plugins / insights / journey / computer-use
sprkey acp                  ACP server (IDE integration)
sprkey completion bash|zsh|fish
sprkey update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `sprkey photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `sprkey config edit` · [Configuration docs](https://sprkey-agent.nightrainbowresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `sprkey tools list` · [Tools reference](https://sprkey-agent.nightrainbowresearch.com/docs/reference/tools-reference) |
| Skills catalog | `sprkey skills browse` · [Skills catalog](https://sprkey-agent.nightrainbowresearch.com/docs/reference/skills-catalog) |
| Provider setup | `sprkey model` · [Providers guide](https://sprkey-agent.nightrainbowresearch.com/docs/integrations/providers) |
| Env variables | `sprkey config env-path` · [Env vars reference](https://sprkey-agent.nightrainbowresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.sprkey/logs/gateway.log` (or `sprkey logs`) |
| Sessions | `sprkey sessions browse` (reads state.db) |
