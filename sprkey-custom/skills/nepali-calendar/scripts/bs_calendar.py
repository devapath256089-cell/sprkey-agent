#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bikram Sambat (Nepali) calendar converter - pure stdlib, self-contained.

Month-length data: official table from the MIT-licensed `nepali-datetime`
project (https://pypi.org/project/nepali-datetime/), covering BS 1975-2100.
Anchor: BS 1975-01-01 == AD 1918-04-13.

Usage:
  python3 bs_calendar.py today                     # today in BS (NPT) + AD
  python3 bs_calendar.py to-ad  <BS> 2082-06-15    # BS -> AD (YYYY-MM-DD)
  python3 bs_calendar.py to-bs  <AD> 2026-10-02    # AD -> BS (YYYY-MM-DD)
  python3 bs_calendar.py month <BS-year>           # month lengths of a BS year
"""

from __future__ import annotations

import datetime as _dt
import sys

# BS 1975-01-01 corresponds to AD 1918-04-13
_ANCHOR_BS = (1975, 1, 1)
_ANCHOR_AD = _dt.date(1918, 4, 13)

MONTH_NAMES_NE = [
    "वैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज",
    "कात्तिक", "मंसिर", "पुस", "माघ", "फागुन", "चैत",
]
MONTH_NAMES_EN = [
    "Baisakh", "Jestha", "Ashar", "Shrawan", "Bhadra", "Asoj",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chait",
]
NEPALI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")

NPT = _dt.timezone(_dt.timedelta(hours=5, minutes=45), name="NPT")

DATA = """\
Year,Baisakh,Jestha,Ashar,Shrawan,Bhadra,Asoj,Kartik,Mangsir,Poush,Magh,Falgun,Chait
1975,31,31,32,32,31,30,30,29,30,29,30,30
1976,31,32,31,32,31,30,30,30,29,29,30,31
1977,30,32,31,32,31,30,30,30,29,30,29,31
1978,31,31,32,31,31,31,30,29,30,29,30,30
1979,31,31,32,32,31,30,30,29,30,29,30,30
1980,31,32,31,32,31,30,30,30,29,29,30,31
1981,31,31,31,32,31,31,29,30,30,29,30,30
1982,31,31,32,31,31,31,30,29,30,29,30,30
1983,31,31,32,32,31,30,30,29,30,29,30,30
1984,31,32,31,32,31,30,30,30,29,29,30,31
1985,31,31,31,32,31,31,29,30,30,29,30,30
1986,31,31,32,31,31,31,30,29,30,29,30,30
1987,31,32,31,32,31,30,30,29,30,29,30,30
1988,31,32,31,32,31,30,30,30,29,29,30,31
1989,31,31,31,32,31,31,29,30,30,29,30,30
1990,31,31,32,31,31,31,30,29,30,29,30,30
1991,31,32,31,32,31,30,30,30,29,29,30,30
1992,31,32,31,32,31,30,30,30,29,30,29,31
1993,31,31,32,31,31,31,30,29,30,29,30,30
1994,31,31,32,31,31,31,30,29,30,29,30,30
1995,31,32,31,32,31,30,30,30,29,29,30,30
1996,31,32,31,32,31,30,30,30,29,30,29,31
1997,31,31,32,31,31,31,30,29,30,29,30,30
1998,31,31,32,31,31,31,30,29,30,29,30,30
1999,31,32,31,32,31,30,30,30,29,29,30,31
2000,30,32,31,32,31,30,30,30,29,30,29,31
2001,31,31,32,31,31,31,30,29,30,29,30,30
2002,31,31,32,32,31,30,30,29,30,29,30,30
2003,31,32,31,32,31,30,30,30,29,29,30,31
2004,30,32,31,32,31,30,30,30,29,30,29,31
2005,31,31,32,31,31,31,30,29,30,29,30,30
2006,31,31,32,32,31,30,30,29,30,29,30,30
2007,31,32,31,32,31,30,30,30,29,29,30,31
2008,31,31,31,32,31,31,29,30,30,29,29,31
2009,31,31,32,31,31,31,30,29,30,29,30,30
2010,31,31,32,32,31,30,30,29,30,29,30,30
2011,31,32,31,32,31,30,30,30,29,29,30,31
2012,31,31,31,32,31,31,29,30,30,29,30,30
2013,31,31,32,31,31,31,30,29,30,29,30,30
2014,31,31,32,32,31,30,30,29,30,29,30,30
2015,31,32,31,32,31,30,30,30,29,29,30,31
2016,31,31,31,32,31,31,29,30,30,29,30,30
2017,31,31,32,31,31,31,30,29,30,29,30,30
2018,31,32,31,32,31,30,30,29,30,29,30,30
2019,31,32,31,32,31,30,30,30,29,30,29,31
2020,31,31,31,32,31,31,30,29,30,29,30,30
2021,31,31,32,31,31,31,30,29,30,29,30,30
2022,31,32,31,32,31,30,30,30,29,29,30,30
2023,31,32,31,32,31,30,30,30,29,30,29,31
2024,31,31,31,32,31,31,30,29,30,29,30,30
2025,31,31,32,31,31,31,30,29,30,29,30,30
2026,31,32,31,32,31,30,30,30,29,29,30,31
2027,30,32,31,32,31,30,30,30,29,30,29,31
2028,31,31,32,31,31,31,30,29,30,29,30,30
2029,31,31,32,31,32,30,30,29,30,29,30,30
2030,31,32,31,32,31,30,30,30,29,29,30,31
2031,30,32,31,32,31,30,30,30,29,30,29,31
2032,31,31,32,31,31,31,30,29,30,29,30,30
2033,31,31,32,32,31,30,30,29,30,29,30,30
2034,31,32,31,32,31,30,30,30,29,29,30,31
2035,30,32,31,32,31,31,29,30,30,29,29,31
2036,31,31,32,31,31,31,30,29,30,29,30,30
2037,31,31,32,32,31,30,30,29,30,29,30,30
2038,31,32,31,32,31,30,30,30,29,29,30,31
2039,31,31,31,32,31,31,29,30,30,29,30,30
2040,31,31,32,31,31,31,30,29,30,29,30,30
2041,31,31,32,32,31,30,30,29,30,29,30,30
2042,31,32,31,32,31,30,30,30,29,29,30,31
2043,31,31,31,32,31,31,29,30,30,29,30,30
2044,31,31,32,31,31,31,30,29,30,29,30,30
2045,31,32,31,32,31,30,30,29,30,29,30,30
2046,31,32,31,32,31,30,30,30,29,29,30,31
2047,31,31,31,32,31,31,30,29,30,29,30,30
2048,31,31,32,31,31,31,30,29,30,29,30,30
2049,31,32,31,32,31,30,30,30,29,29,30,30
2050,31,32,31,32,31,30,30,30,29,30,29,31
2051,31,31,31,32,31,31,30,29,30,29,30,30
2052,31,31,32,31,31,31,30,29,30,29,30,30
2053,31,32,31,32,31,30,30,30,29,29,30,30
2054,31,32,31,32,31,30,30,30,29,30,29,31
2055,31,31,32,31,31,31,30,29,30,29,30,30
2056,31,31,32,31,32,30,30,29,30,29,30,30
2057,31,32,31,32,31,30,30,30,29,29,30,31
2058,30,32,31,32,31,30,30,30,29,30,29,31
2059,31,31,32,31,31,31,30,29,30,29,30,30
2060,31,31,32,32,31,30,30,29,30,29,30,30
2061,31,32,31,32,31,30,30,30,29,29,30,31
2062,31,31,31,32,31,31,29,30,29,30,29,31
2063,31,31,32,31,31,31,30,29,30,29,30,30
2064,31,31,32,32,31,30,30,29,30,29,30,30
2065,31,32,31,32,31,30,30,30,29,29,30,31
2066,31,31,31,32,31,31,29,30,30,29,29,31
2067,31,31,32,31,31,31,30,29,30,29,30,30
2068,31,31,32,32,31,30,30,29,30,29,30,30
2069,31,32,31,32,31,30,30,30,29,29,30,31
2070,31,31,31,32,31,31,29,30,30,29,30,30
2071,31,31,32,31,31,31,30,29,30,29,30,30
2072,31,32,31,32,31,30,30,29,30,29,30,30
2073,31,32,31,32,31,30,30,30,29,29,30,31
2074,31,31,31,32,31,31,30,29,30,29,30,30
2075,31,31,32,31,31,31,30,29,30,29,30,30
2076,31,32,31,32,31,30,30,30,29,29,30,30
2077,31,32,31,32,31,30,30,30,29,30,29,31
2078,31,31,31,32,31,31,30,29,30,29,30,30
2079,31,31,32,31,31,31,30,29,30,29,30,30
2080,31,32,31,32,31,30,30,30,29,29,30,30
2081,31,32,31,32,31,30,30,30,29,30,29,31
2082,31,31,32,31,31,31,30,29,30,29,30,30
2083,31,31,32,31,31,31,30,29,30,29,30,30
2084,31,31,32,31,31,30,30,30,29,30,30,30
2085,31,32,31,32,30,31,30,30,29,30,30,30
2086,30,32,31,32,31,30,30,30,29,30,30,30
2087,31,31,32,31,31,31,30,29,30,30,30,30
2088,30,31,32,32,30,31,30,30,29,30,30,30
2089,30,32,31,32,31,30,30,30,29,30,30,30
2090,30,32,31,32,31,30,30,30,29,30,30,30
2091,31,31,32,31,31,31,30,30,29,30,30,30
2092,30,31,32,32,31,30,30,30,29,30,30,30
2093,30,32,31,32,31,30,30,30,29,30,30,30
2094,31,31,32,31,31,30,30,30,29,30,30,30
2095,31,31,32,31,31,31,30,29,30,30,30,30
2096,30,31,32,32,31,30,30,29,30,29,30,30
2097,31,32,31,32,31,30,30,30,29,30,30,30
2098,31,31,32,31,31,31,29,30,29,30,29,31
2099,31,31,32,31,31,31,30,29,29,30,30,30
2100,31,32,31,32,30,31,30,29,30,29,30,30
"""

_ROWS = [
    row
    for row in DATA.strip().splitlines()
    if row and not row.startswith("Year,")
]
_MIN_YEAR = min(int(row.split(",")[0]) for row in _ROWS)
_MAX_YEAR = max(int(row.split(",")[0]) for row in _ROWS)
_MONTHS = {
    int(row.split(",")[0]): [int(x) for x in row.split(",")[1:]]
    for row in _ROWS
}


class BsOutOfRange(ValueError):
    """Raised when a date falls outside the embedded calendar table."""


def _check_bs(year: int, month: int, day: int) -> None:
    if not (_MIN_YEAR <= year <= _MAX_YEAR):
        raise BsOutOfRange(
            f"BS year {year} outside supported range {_MIN_YEAR}-{_MAX_YEAR}"
        )
    if not (1 <= month <= 12):
        raise BsOutOfRange(f"BS month must be 1-12, got {month}")
    if not (1 <= day <= _MONTHS[year][month - 1]):
        raise BsOutOfRange(
            f"BS day {day} invalid for {MONTH_NAMES_EN[month - 1]} {year} "
            f"(max {_MONTHS[year][month - 1]})"
        )


def _bs_ordinal(year: int, month: int, day: int) -> int:
    """Days elapsed since the BS epoch anchor (BS 1975-01-01 == day 0)."""
    _check_bs(year, month, day)
    days = 0
    for y in range(_MIN_YEAR, year):
        days += sum(_MONTHS[y])
    days += sum(_MONTHS[year][: month - 1])
    days += day - 1
    return days


def bs_to_ad(year: int, month: int, day: int) -> _dt.date:
    """Convert a Bikram Sambat date to the Gregorian (AD) date."""
    return _ANCHOR_AD + _dt.timedelta(days=_bs_ordinal(year, month, day))


def ad_to_bs(date_ad: _dt.date) -> tuple[int, int, int]:
    """Convert a Gregorian (AD) date to (year, month, day) in Bikram Sambat."""
    days = (date_ad - _ANCHOR_AD).days
    if days < 0:
        raise BsOutOfRange("AD date precedes BS 1975-01-01 (AD 1918-04-13)")
    year = _MIN_YEAR
    while True:
        year_len = sum(_MONTHS[year])
        if days < year_len:
            break
        days -= year_len
        year += 1
        if year > _MAX_YEAR:
            raise BsOutOfRange(
                f"AD date maps beyond BS {_MAX_YEAR}-12-30; extend the table"
            )
    month = 1
    while days >= _MONTHS[year][month - 1]:
        days -= _MONTHS[year][month - 1]
        month += 1
    return year, month, days + 1


def today_bs(now: _dt.datetime | None = None) -> tuple[int, int, int]:
    """Current date in Bikram Sambat (Nepal Time, UTC+5:45)."""
    now = now or _dt.datetime.now(NPT)
    return ad_to_bs(now.date())


def format_bs(year: int, month: int, day: int, nepali: bool = False) -> str:
    """Human-readable BS date, e.g. 'Asoj 15, 2083' or 'असोज १५, २०८३'."""
    if nepali:
        s = f"{MONTH_NAMES_NE[month - 1]} {day}, {year}"
        return s.translate(NEPALI_DIGITS)
    return f"{MONTH_NAMES_EN[month - 1]} {day}, {year}"


def month_lengths(year: int) -> list[int]:
    """Month lengths (in days) of a Bikram Sambat year."""
    if not (_MIN_YEAR <= year <= _MAX_YEAR):
        raise BsOutOfRange(
            f"BS year {year} outside supported range {_MIN_YEAR}-{_MAX_YEAR}"
        )
    return list(_MONTHS[year])


def main(argv: list[str]) -> int:
    try:
        if not argv or argv[0] in ("-h", "--help", "help"):
            print(__doc__.strip())
            return 0
        cmd = argv[0]
        if cmd == "today":
            y, m, d = today_bs()
            ad = bs_to_ad(y, m, d)
            print(f"BS: {format_bs(y, m, d)} ({y}-{m:02d}-{d:02d})")
            print(f"BS (ne): {format_bs(y, m, d, nepali=True)}")
            print(f"AD: {ad.isoformat()} ({ad.strftime('%A')})  [NPT]")
        elif cmd == "to-ad" and len(argv) == 2:
            y, m, d = (int(x) for x in argv[1].split("-"))
            print(bs_to_ad(y, m, d).isoformat())
        elif cmd == "to-bs" and len(argv) == 2:
            y, m, d = (int(x) for x in argv[1].split("-"))
            by, bm, bd = ad_to_bs(_dt.date(y, m, d))
            print(f"{by}-{bm:02d}-{bd:02d}  ({format_bs(by, bm, bd)})")
        elif cmd == "month" and len(argv) == 2:
            lens = month_lengths(int(argv[1]))
            total = sum(lens)
            rows = [
                f"  {i + 1:2d}. {MONTH_NAMES_EN[i]:8s} {MONTH_NAMES_NE[i]:6s} {n} din"
                for i, n in enumerate(lens)
            ]
            print(f"BS {argv[1]}: {total} days")
            print("\n".join(rows))
        else:
            print(__doc__.strip())
            return 2
    except (BsOutOfRange, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
