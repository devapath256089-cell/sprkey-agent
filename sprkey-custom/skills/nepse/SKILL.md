---
name: nepse
description: Live share market data: index, quotes, movers, volume.
version: 1.0.0
author: Momkey (devapath256089-cell), Sprkey Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  sprkey:
    tags: [Nepal, NEPSE, Stocks, Finance, Market]
    category: finance
    related_skills: [stocks]
---

# Nepse Skill

Fetch Nepal Stock Exchange (NEPSE) market data: the NEPSE index with recent
history, individual scrip quotes, top gainers/losers, most-traded scrips, and
company-name-to-symbol lookup. Read-only, stdlib-only client script; no API
key and no pip installs. The official NEPSE API is tried first and the client
automatically falls back to a mirror site, then to a last-good cache — so
queries keep working offline or on non-trading days (stale results are
flagged, never silently presented as live).

## When to Use

- User asks for the NEPSE index value or its recent trend
- User asks the price of a listed scrip (NABIL, NICA, HIDCL, ...)
- User asks for today's top gainers, losers, or most-traded scrips
- User knows a company name but not its trading symbol

## Prerequisites

Python 3.8+ stdlib only. Network access is needed for live data; without it
the command falls back to the cache (flagged as stale). NEPSE trades on the
Nepal business week — outside trading days the CLI still returns the last
session's data, tagged with its business date.

## How to Run

Invoke through the `terminal` tool. Once installed:

```
SCRIPT=~/.sprkey/skills/finance/nepse/scripts/nepse_client.py
python3 $SCRIPT index
```

All commands accept `--json` for machine-readable output; a one-line
`[source=... cache=...]` provenance note goes to stderr in human mode.

## Quick Reference

```
python3 $SCRIPT index --history 10
python3 $SCRIPT summary
python3 $SCRIPT price NABIL NICA HIDCL
python3 $SCRIPT gainers --top 10
python3 $SCRIPT losers --top 10
python3 $SCRIPT volume --top 10
python3 $SCRIPT search "hydro"
```

## Procedure

1. `search "<company name>"` when the symbol is unknown (matches symbol and
   company name, case-insensitive).
2. `price SYMBOL ...` for quotes; unknown symbols are listed as `missing` on
   stderr while known ones still print.
3. `gainers`/`losers`/`volume` rank only scrips with traded volume, so
   untraded rows cannot pollute the top list.
4. `summary` combines index, advancers/decliners, total volume and the top
   mover — good default when the user just says "market kasto chha?".
5. Prefer `--json` when feeding the data into further processing by the
   agent (charts, reports) instead of parsing human output.

## Pitfalls

- **NEPSE's official API blocks cloud/datacenter IPs** (HTTP 401 "WARNING:
  UNAUTHORIZED ACCESS"). On such hosts the client automatically uses the
  mirror; on residential IPs the clean official JSON is used. Force with
  `--source merolagani|nepalstock` if needed.
- The mirror's table header claims an `Open, High, Low` order, but the actual
  cell order is **High, Low, Open** — verified empirically against hundreds
  of rows with sanity constraints; do not "fix" the parser back to the
  header order.
- Per-scrip turnover (Rs) is only available from the official API source;
  on the mirror path `volume` ranks by traded quantity.
- Index history dates are AD (yyyy/mm/dd) as published; convert with the
  `nepali-calendar` skill if the user wants BS dates.
- Cache TTL is 10 minutes for market data; pass `--no-cache` when the user
  explicitly wants a forced refresh.

## Verification

- `python3 $SCRIPT index` prints a plausible index value (~2000-3000 range
  in recent years) with a business date matching the last trading day.
- `python3 $SCRIPT price NABIL` returns an LTP within ±15% of its day range
  and a `[source=...]` note showing which source served the data.
- Run the offline test suite: `python3 tests/test_nepse_client.py`
  (no network needed) — all PASS cases must pass before publishing changes.
