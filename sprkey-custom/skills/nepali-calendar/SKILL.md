---
name: nepali-calendar
description: Convert dates between Bikram Sambat and Gregorian calendars.
version: 1.0.0
author: Momkey (devapath256089-cell), Sprkey Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  sprkey:
    tags: [Nepal, Bikram-Sambat, Date, Calendar, NPT]
    category: productivity
    related_skills: []
---

# Nepali Calendar (Bikram Sambat)

Convert dates between Bikram Sambat (BS) and Gregorian (AD) calendars, get
today's date in Nepal Time (NPT, UTC+5:45), and inspect BS month lengths.
Conversion is offline and deterministic — the bundled script embeds the
official month-length table for BS 1975-2100 (from the MIT-licensed
`nepali-datetime` project), so no network access is needed.

## When to Use

- The user mentions a Nepali date ("आसोज १६", "2083-06-16") and you need the
  AD equivalent, or the reverse.
- Filling forms, invoices, or documents that require dates in BS.
- Answering "आज कति गते हो?" or checking how many days a BS month has.

## Prerequisites

None. The helper script is pure Python standard library and fully offline.

## How to Run

All work goes through `scripts/bs_calendar.py` via `terminal` (resolve its
absolute path relative to this skill directory first):

```bash
python3 scripts/bs_calendar.py today              # today: BS + AD, NPT
python3 scripts/bs_calendar.py to-ad 2082-06-15   # BS -> AD
python3 scripts/bs_calendar.py to-bs 2026-10-02   # AD -> BS
python3 scripts/bs_calendar.py month 2083         # month lengths of BS year
```

For bulk or in-process use, import it instead of shelling out repeatedly:

```python
import sys
sys.path.insert(0, "<skill-dir>/scripts")
import bs_calendar
bs_calendar.ad_to_bs(datetime.date(2026, 10, 2))  # -> (2083, 6, 16)
bs_calendar.format_bs(2083, 6, 16, nepali=True)    # -> "असोज १६, २०८३"
```

## Quick Reference

- Supported range: BS 1975-01-01 (AD 1918-04-13) through BS 2100-12-30.
- Dates use ISO-like `YYYY-MM-DD` in **BS month order**: 1=वैशाख, 2=जेठ,
  3=असार, 4=साउन, 5=भदौ, 6=असोज, 7=कात्तिक, 8=मंसिर, 9=पुस, 10=माघ,
  11=फागुन, 12=चैत.
- Nepali New Year falls on the 1st of Baisakh, around mid-April AD.
- NPT is UTC+5:45 — one of only two quarter-hour offsets, so never guess it
  from the map.

## Procedure

1. Decide the direction of conversion and the input format.
2. Run `scripts/bs_calendar.py` with `terminal` using the matching subcommand
   (`to-ad` or `to-bs`).
3. Report both the numeric date and the readable form (`Asoj 16, 2083` or
   `असोज १६, २०८३`), and mention NPT when "today" is involved.

## Pitfalls

- BS months are 29-32 days and do not align with AD months — never compute a
  BS date by adding or subtracting days by hand; always use the script.
- Dates outside BS 1975-2100 raise `BsOutOfRange`; say so plainly instead of
  approximating.
- Do not confuse "साउन/श्रावण" (month 4) with "साल" (year) when the user mixes
  Nepali and digits, e.g. "साउन १५, २०८३" is month 4 day 15, not August.
- The script's "today" uses NPT regardless of the machine's local timezone.

## Verification

- Round-trip check: convert BS -> AD -> BS and confirm you get the original
  date (the script is exact within the supported range).
- Sanity anchors: BS 2082-01-01 is AD 2025-04-14 and BS 2083-01-01 is AD
  2026-04-14; if a result contradicts these, re-check the input format.
