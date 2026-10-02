---
name: worklog-keeper
description: Maintain a structured worklog with task IDs and summaries.
version: 1.0.0
author: Momkey (devapath256089-cell), Sprkey Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  sprkey:
    tags: [Worklog, Journaling, Accountability]
    category: productivity
    related_skills: []
---

# Worklog Keeper

Keep a running, structured worklog of every working session so nothing gets
lost between conversations. The worklog is a plain markdown file that both the
agent and the user can read, append to, and back up. It records what was done,
how it was done, and what the outcome was — one block per task.

## When to Use

- At the start of a session, to catch up on what happened previously.
- After finishing a meaningful task, to record it before moving on.
- When the user asks "what did we do last time?" or asks for a daily summary.
- Before ending a session, so the next one can resume without re-explaining.

## Prerequisites

None. The worklog is a single markdown file; the default location is
`worklog.md` in the current working directory, overridable with the
`WORKLOG_PATH` environment variable.

## How to Run

1. Read the tail of the worklog with `read_file` (use an offset near the end
   for large files) to learn the existing format and the last Task ID.
2. Append new entries with `write_file` on a fresh file, or `patch` with an
   anchor at the end of an existing file. Prefer `patch` — it preserves the
   rest of the log untouched.
3. Confirm the write by re-reading the last few lines.

## Quick Reference

Entry template (append one block per task, never overwrite old blocks):

```markdown
---
Task ID: <short-unique-id>
Agent: <name>
Task: <one-line description of the task>

Work Log:
- <concrete step 1>
- <concrete step 2>

Stage Summary:
- <key results, decisions, and produced artifacts>
```

Rules of thumb:

- One block per task; multiple steps go in the `Work Log` bullet list.
- Task IDs stay short and descriptive (`invoice-fix`, `drive-backup-1012`).
- The `Stage Summary` carries the outcome: what changed, where it lives now.
- Never delete or rewrite previous entries; the log is append-only history.

## Procedure

1. **Catch up** — read the last 1-2 entries with `read_file` before starting
   work so you do not repeat finished tasks.
2. **Work** — do the task normally with the usual tools.
3. **Record** — append a block using the template above via `patch` anchored
   at the end of the file.
4. **Wrap up** — when the user asks for a day summary, group the day's blocks
   under a dated heading and read it back concisely.

## Pitfalls

- Do not paste large logs, secrets, tokens, or passwords into the worklog —
  reference them by location instead.
- Do not use `terminal` heredocs for appending; quoting bugs silently mangle
  markdown. Use `patch` or `write_file`.
- Do not start a "new log file per session" unless the user asks — one file
  per project keeps history greppable with `search_files`.
- If the file grew huge, read only the tail with `read_file` offsets instead
  of loading it whole.

## Verification

- After appending, `read_file` the last ~15 lines and check the block renders
  as valid markdown with all five template fields present.
- Run `search_files` with `target: "content"` for the new Task ID to confirm
  exactly one occurrence was added.
