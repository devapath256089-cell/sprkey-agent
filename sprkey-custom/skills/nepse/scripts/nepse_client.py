#!/usr/bin/env python3
"""NEPSE (Nepal Stock Exchange) market data client.

Stdlib only. Multi-source with automatic fallback:
  1. nepalstock.com.np official API  (clean JSON; blocked on many cloud IPs)
  2. merolagani.com server-rendered pages (works where the API is blocked)
A last-good cache under ~/.sprkey/cache/nepse/ keeps queries working offline
or on non-trading days (stale results are flagged).

Commands: index, summary, price, gainers, losers, volume, search
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
ML_LATEST = "https://www.merolagani.com/LatestMarket.aspx"
ML_INDEX = "https://www.merolagani.com/Indices.aspx"
NS_BASE = "https://www.nepalstock.com.np/api/nots/nepse-data"
SS_TODAY = "https://www.sharesansar.com/today-share-price"
ML_INDEX_NAME = "NEPSE Index"

NPT = timezone(timedelta(hours=5, minutes=45))
CACHE_TTL = {"latest_market": 600, "index_history": 600, "companies": 7 * 86400}
MAX_NS_PAGES = 10
_REQ_TIMEOUT = [25]


class NepseError(Exception):
    pass


def _timeout():
    return _REQ_TIMEOUT[0]


# ---------------------------------------------------------------- helpers

def _now_npt():
    return datetime.now(NPT)


def _f(v):
    """Parse a numeric string ('528.70', '60,404', '-0.45%') to float."""
    if v is None:
        return None
    v = str(v).replace(",", "").replace("%", "").strip()
    if v in ("", "-", "--"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _http_get(url, referer=None, timeout=None):
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout or _timeout()) as resp:
        return resp.read().decode("utf-8", errors="replace").lstrip("\ufeff")


def _cache_dir(override=None):
    base = override or os.environ.get("SPRKEY_CACHE_DIR") or \
        str(Path.home() / ".sprkey" / "cache" / "nepse")
    d = Path(base)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path(tempfile.gettempdir()) / "sprkey-nepse-cache"
        d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_read(name, ttl, cache_dir):
    p = Path(cache_dir) / f"{name}.json"
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    age = time.time() - obj.get("fetched_at", 0)
    return {"stale": age > ttl, "age": age, "payload": obj.get("payload")}


def _cache_write(name, payload, cache_dir):
    p = Path(cache_dir) / f"{name}.json"
    obj = {"fetched_at": time.time(), "fetched_at_npt": _now_npt().isoformat(),
           "payload": payload}
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def _cached(name, ttl, fetch_fn, cache_dir, use_cache=True):
    """Return (payload, meta). Falls back to stale cache when fetch fails
    (only when caching is enabled; --no-cache never serves cache)."""
    if use_cache:
        hit = _cache_read(name, ttl, cache_dir)
        if hit and not hit["stale"] and hit.get("payload") is not None:
            return hit["payload"], {"cache": "hit", "age": hit["age"]}
    try:
        payload = fetch_fn()
        if use_cache:
            _cache_write(name, payload, cache_dir)
        return payload, {"cache": "miss"}
    except (NepseError, urllib.error.URLError, OSError, ValueError) as exc:
        if use_cache:
            hit = _cache_read(name, ttl, cache_dir)
            if hit and hit.get("payload") is not None:
                return hit["payload"], {"cache": "stale" if hit["stale"] else "fresh",
                                        "age": hit.get("age"), "error": str(exc)}
        if isinstance(exc, NepseError):
            raise
        raise NepseError(f"fetch failed and no cache available: {exc}") from exc


# ---------------------------------------------------------------- parsers

TAG_RE = re.compile(r"<[^>]+>")
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
SYMBOL_RE = re.compile(r"symbol=([A-Za-z0-9_.-]+)['\"]")
# sharesansar embeds its full scrip list as JSON for the search autocomplete
COMPANIES_RE = re.compile(
    r'\[\s*{"id":\d+,"symbol":"[^"]+","companyname":"[^"]+"[^\]]*?\]')
DATE_RE = re.compile(r"\d{4}/\d{2}/\d{2}")


def _cells(td_html):
    return [unescape(TAG_RE.sub("", c)).replace(",", "").strip()
            for c in CELL_RE.findall(td_html)]


def parse_latest_market(html, source="merolagani"):
    """Parse LatestMarket.aspx.

    Empirically verified cell order (differs from the displayed header!):
      symbol, LTP, %Change, High, Low, Open, Qty, PClose, Diff
    """
    rows = {}
    for m in ROW_RE.finditer(html):
        body = m.group(1)
        sm = SYMBOL_RE.search(body)
        if not sm:
            continue
        cells = _cells(body)
        if len(cells) < 7:
            continue
        ltp = _f(cells[1])
        if ltp is None or ltp <= 0:
            continue
        pct = _f(cells[2]) or 0.0
        high, low, opn, qty = (_f(cells[3]), _f(cells[4]),
                               _f(cells[5]), _f(cells[6]))
        pclose = _f(cells[7]) if len(cells) > 7 else None
        if pclose is None and pct:
            pclose = round(ltp / (1 + pct / 100.0), 2)
        rows[sm.group(1).upper()] = {
            "symbol": sm.group(1).upper(), "ltp": ltp, "pct_change": pct,
            "open": opn, "high": high, "low": low,
            "qty": int(qty) if qty else 0, "prev_close": pclose,
        }
    if not rows:
        raise NepseError("merolagani: no scrip rows found (page layout changed?)")
    return {"source": source, "rows": rows,
            "fetched_at_npt": _now_npt().isoformat()}


def parse_index_history(html, source="merolagani"):
    """Parse Indices.aspx: # | Date (AD) | Index Value | Abs Change | % Change."""
    out = []
    for m in ROW_RE.finditer(html):
        cells = _cells(m.group(1))
        if len(cells) < 5 or not DATE_RE.fullmatch(cells[1]):
            continue
        val = _f(cells[2])
        if val is None:
            continue
        out.append({"date_ad": cells[1], "value": val,
                    "abs_change": _f(cells[3]), "pct_change": _f(cells[4])})
    if not out:
        raise NepseError("merolagani: no index rows found (page layout changed?)")
    out.sort(key=lambda r: r["date_ad"], reverse=True)
    return {"source": source, "name": ML_INDEX_NAME, "history": out,
            "fetched_at_npt": _now_npt().isoformat()}


def parse_companies(html, source="sharesansar"):
    m = COMPANIES_RE.search(html)
    if not m:
        raise NepseError("sharesansar: company list not found in page")
    try:
        data = json.loads(m.group(0))
    except ValueError as exc:
        raise NepseError(f"sharesansar: company JSON parse failed: {exc}") from exc
    return {"source": source,
            "companies": [{"symbol": c["symbol"].upper(),
                           "name": c["companyname"]} for c in data],
            "fetched_at_npt": _now_npt().isoformat()}


def _ns_pick(item, *keys, default=None):
    for k in keys:
        if k in item and item[k] not in (None, ""):
            return item[k]
    return default


def parse_ns_index(payload, source="nepalstock"):
    """Defensive parser for the official nepseIndex endpoint (shape drifts)."""
    data = payload if isinstance(payload, list) else (
        payload.get("content") if isinstance(payload, dict) else None)
    if isinstance(data, dict):
        data = data.get("dataList") or data.get("data") or data.get("content")
    if not isinstance(data, list) or not data:
        raise NepseError("nepalstock: unexpected nepseIndex shape")
    it = data[0]
    value = _f(_ns_pick(it, "indexValue", "value", "nepseIndex"))
    if value is None:
        raise NepseError("nepalstock: index value missing")
    entry = {"date_ad": _ns_pick(it, "businessDate", "date", "createdAt"),
             "value": value,
             "abs_change": _f(_ns_pick(it, "difference", "absChange", "change")),
             "pct_change": _f(_ns_pick(it, "percentageChange", "percentChange"))}
    return {"source": source,
            "name": _ns_pick(it, "indexName", default=ML_INDEX_NAME),
            "value": value,
            "abs_change": entry["abs_change"], "pct_change": entry["pct_change"],
            "turnover": _f(_ns_pick(it, "turnover")),
            "volume": _f(_ns_pick(it, "volume", "totalTurnoverVolume")),
            "date_ad": entry["date_ad"],
            "history": [entry],
            "fetched_at_npt": _now_npt().isoformat()}


def parse_ns_table(payload, source="nepalstock"):
    """Defensive parser for the official todaysPrice endpoint."""
    content = payload.get("content") if isinstance(payload, dict) else None
    if isinstance(content, dict):
        items = (content.get("dataList") or content.get("data")
                 or content.get("content"))
    elif isinstance(payload, list):
        items = payload
    else:
        items = None
    if not isinstance(items, list) or not items:
        raise NepseError("nepalstock: unexpected todaysPrice shape")
    rows = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        sym = _ns_pick(it, "symbol", "stockSymbol", "securitySymbol")
        ltp = _f(_ns_pick(it, "ltp", "lastTradedPrice", "close", "lastMinPrice"))
        if not sym or ltp is None or ltp <= 0:
            continue
        pct = _f(_ns_pick(it, "percentageChange", "percentChange", "pctChange")) or 0.0
        prev = _f(_ns_pick(it, "previousClose", "prevClose", "prevClosingPrice"))
        if prev is None and pct:
            prev = round(ltp / (1 + pct / 100.0), 2)
        rows[str(sym).upper()] = {
            "symbol": str(sym).upper(), "ltp": ltp, "pct_change": pct,
            "open": _f(_ns_pick(it, "open", "openPrice")),
            "high": _f(_ns_pick(it, "high", "highPrice")),
            "low": _f(_ns_pick(it, "low", "lowPrice")),
            "qty": int(_f(_ns_pick(it, "volume", "shareTradedVolume",
                                   "quantity")) or 0),
            "prev_close": prev,
            "turnover": _f(_ns_pick(it, "turnover", "turnOverValue")),
        }
    if not rows:
        raise NepseError("nepalstock: todaysPrice gave no usable rows")
    return {"source": source, "rows": rows,
            "fetched_at_npt": _now_npt().isoformat()}


# ---------------------------------------------------------------- fetchers

def _ns_get(path):
    url = f"{NS_BASE}/{path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json",
        "Referer": "https://www.nepalstock.com.np/",
        "Origin": "https://www.nepalstock.com.np"})
    try:
        with urllib.request.urlopen(req, timeout=_timeout()) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise NepseError(f"nepalstock API HTTP {exc.code} "
                         f"(common on cloud/datacenter IPs)") from exc
    except (urllib.error.URLError, ValueError) as exc:
        raise NepseError(f"nepalstock API unreachable: {exc}") from exc


def fetch_ns_index():
    return parse_ns_index(_ns_get("nepseIndex"))


def fetch_ns_market():
    rows, page = {}, 1
    while page <= MAX_NS_PAGES:
        payload = _ns_get(
            f"todaysPrice?&page={page}&size=500&sort=symbol&direction=ASC")
        parsed = parse_ns_table(payload)
        rows.update(parsed["rows"])
        content = payload.get("content") if isinstance(payload, dict) else {}
        pag = (content or {}).get("pagination") or {}
        try:
            total_pages = int(pag.get("totalPages") or pag.get("total_Page") or 1)
        except (TypeError, ValueError):
            total_pages = 1
        if page >= total_pages or not parsed["rows"]:
            break
        page += 1
    if not rows:
        raise NepseError("nepalstock: no rows across pages")
    return {"source": "nepalstock", "rows": rows,
            "fetched_at_npt": _now_npt().isoformat()}


def fetch_ml_market():
    return parse_latest_market(_http_get(ML_LATEST))


def fetch_ml_index():
    return parse_index_history(_http_get(ML_INDEX))


def fetch_companies():
    return parse_companies(_http_get(SS_TODAY))


# ------------------------------------------------- source-selected fetches

def get_market(args, cache_dir):
    """Official API first (works on residential IPs), merolagani fallback.
    Cache is keyed per forced source so --source nepalstock never serves a
    mirror-fetched cache entry."""
    name = f"latest_market_{args.source}"
    if args.source != "merolagani":
        try:
            return _cached(name, CACHE_TTL["latest_market"],
                           fetch_ns_market, cache_dir,
                           use_cache=not args.no_cache)
        except NepseError:
            if args.source == "nepalstock":
                raise
    return _cached(name, CACHE_TTL["latest_market"],
                   fetch_ml_market, cache_dir, use_cache=not args.no_cache)


def get_index(args, cache_dir):
    name = f"index_history_{args.source}"
    if args.source != "merolagani":
        try:
            return _cached(name, CACHE_TTL["index_history"],
                           fetch_ns_index, cache_dir,
                           use_cache=not args.no_cache)
        except NepseError:
            if args.source == "nepalstock":
                raise
    return _cached(name, CACHE_TTL["index_history"],
                   fetch_ml_index, cache_dir, use_cache=not args.no_cache)


def get_companies(args, cache_dir):
    return _cached("companies", CACHE_TTL["companies"],
                   fetch_companies, cache_dir, use_cache=not args.no_cache)


# ---------------------------------------------------------------- output

def _fmt(v, nd=2):
    if v is None:
        return "-"
    if nd == 0:
        return f"{int(round(v)):,}"
    return f"{v:,.{nd}f}"


def _row_line(r):
    return (f"{r['symbol']:<12} LTP {_fmt(r['ltp']):>10}  "
            f"{r['pct_change']:>+7.2f}%  "
            f"H {_fmt(r['high']):>9}  L {_fmt(r['low']):>9}  "
            f"O {_fmt(r['open']):>9}  Qty {_fmt(float(r['qty']), 0):>12}")


def _movers(rows, key, top, best_first):
    have = [r for r in rows.values() if r.get("qty")]
    have.sort(key=lambda r: r[key], reverse=best_first)
    return have[:top]


def _market_stats(rows):
    up = sum(1 for r in rows.values() if r["pct_change"] > 0)
    down = sum(1 for r in rows.values() if r["pct_change"] < 0)
    return {"scrips": len(rows), "advancers": up, "decliners": down,
            "unchanged": len(rows) - up - down,
            "total_volume": sum(r["qty"] for r in rows.values())}


def _json_out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _meta(payload, meta):
    return {"source_used": payload.get("source"), "cache": meta.get("cache", "-"),
            "fetched_at_npt": payload.get("fetched_at_npt"),
            "cache_age_sec": round(meta["age"]) if "age" in meta else None}


def _suggest(rows):
    return ", ".join(sorted(rows)[:8]) + ", ..."


def _print_meta(meta):
    bits = [f"source={meta.get('source_used')}"]
    if meta.get("cache") and meta["cache"] != "-":
        bits.append(f"cache={meta['cache']}")
    if meta.get("cache_age_sec") is not None:
        bits.append(f"age={meta['cache_age_sec']}s")
    print(f"[{' '.join(bits)}]", file=sys.stderr)


# ---------------------------------------------------------------- commands

def cmd_index(args, cache_dir):
    payload, meta = get_index(args, cache_dir)
    hist = payload.get("history") or []
    latest = hist[0] if hist else payload
    out = {"command": "index", "name": payload.get("name", ML_INDEX_NAME),
           "value": latest.get("value"),
           "abs_change": latest.get("abs_change") or 0.0,
           "pct_change": latest.get("pct_change") or 0.0,
           "date_ad": latest.get("date_ad") or latest.get("date"),
           "turnover": latest.get("turnover"), "volume": latest.get("volume"),
           "meta": _meta(payload, meta)}
    if args.history:
        out["history"] = hist[:args.history]
    if args.json:
        _json_out(out)
        return
    print(f"{out['name']}: {out['value']} "
          f"({out['abs_change']:+.2f}, {out['pct_change']:+.2f}%)  "
          f"as of {out['date_ad']}")
    if out.get("turnover"):
        print(f"turnover Rs {_fmt(out['turnover'], 0)}   "
              f"volume {_fmt(out['volume'] or 0, 0)}")
    if args.history:
        print("\nrecent trading days:")
        for r in out["history"][:args.history]:
            print(f"  {r['date_ad']}  {r['value']:>10,.2f}  "
                  f"{(r['abs_change'] or 0):>+9.2f}  "
                  f"{(r['pct_change'] or 0):>+6.2f}%")
    _print_meta(out["meta"])


def cmd_summary(args, cache_dir):
    mkt, mmeta = get_market(args, cache_dir)
    rows = mkt["rows"]
    stats = _market_stats(rows)
    g = _movers(rows, "pct_change", 1, True)
    l = _movers(rows, "pct_change", 1, False)
    latest = None
    try:
        idx, _ = get_index(args, cache_dir)
        hist = idx.get("history") or []
        latest = hist[0] if hist else idx
    except NepseError:
        pass
    out = {"command": "summary", "market": stats,
           "index": ({"value": latest.get("value"),
                      "pct_change": latest.get("pct_change"),
                      "date_ad": latest.get("date_ad") or latest.get("date")}
                     if latest else None),
           "top_gainer": g[0] if g else None, "top_loser": l[0] if l else None,
           "meta": _meta(mkt, mmeta)}
    if args.json:
        _json_out(out)
        return
    if latest:
        print(f"NEPSE Index {latest.get('value')} "
              f"({(latest.get('pct_change') or 0):+.2f}%)  "
              f"as of {latest.get('date_ad') or latest.get('date')}")
    print(f"scrips {stats['scrips']}: {stats['advancers']} up / "
          f"{stats['decliners']} down / {stats['unchanged']} flat")
    print(f"total volume {stats['total_volume']:,}")
    if g:
        print(f"top gainer {g[0]['symbol']} {g[0]['pct_change']:+.2f}%   "
              f"top loser {l[0]['symbol']} {l[0]['pct_change']:+.2f}%")
    _print_meta(out["meta"])


def cmd_price(args, cache_dir):
    mkt, meta = get_market(args, cache_dir)
    rows = mkt["rows"]
    found, missing = {}, []
    for sym in args.symbols:
        s = sym.upper().strip()
        if s in rows:
            found[s] = rows[s]
        else:
            missing.append(s)
    out = {"command": "price", "quotes": [found[s] for s in found],
           "missing": missing, "meta": _meta(mkt, meta)}
    if args.json:
        _json_out(out)
        return
    for r in out["quotes"]:
        print(_row_line(r))
    if missing:
        print(f"not found: {', '.join(missing)}  "
              f"(try: search <company name>; some symbols: "
              f"{_suggest(rows)})", file=sys.stderr)
    if not out["quotes"]:
        sys.exit(1)
    _print_meta(out["meta"])


def cmd_movers(args, cache_dir, kind):
    mkt, meta = get_market(args, cache_dir)
    picks = _movers(mkt["rows"], "pct_change", args.top, kind == "gainers")
    out = {"command": kind, "items": picks, "meta": _meta(mkt, meta)}
    if args.json:
        _json_out(out)
        return
    print(f"top {kind} (only scrips with traded volume):")
    for i, r in enumerate(picks, 1):
        print(f"{i:>3}. {_row_line(r)}")
    _print_meta(out["meta"])


def cmd_volume(args, cache_dir):
    mkt, meta = get_market(args, cache_dir)
    rows = list(mkt["rows"].values())
    rows.sort(key=lambda r: r.get("turnover") or r["qty"], reverse=True)
    picks = rows[:args.top]
    out = {"command": "volume", "items": picks, "meta": _meta(mkt, meta)}
    if args.json:
        _json_out(out)
        return
    print("top scrips by traded quantity:")
    for i, r in enumerate(picks, 1):
        extra = f"  Rs {_fmt(r['turnover'], 0)}" if r.get("turnover") else ""
        print(f"{i:>3}. {_row_line(r)}{extra}")
    _print_meta(out["meta"])


def cmd_search(args, cache_dir):
    comp, meta = get_companies(args, cache_dir)
    q = args.query.lower().strip()
    hits = [c for c in comp["companies"]
            if q in c["symbol"].lower() or q in c["name"].lower()][:args.limit]
    out = {"command": "search", "query": args.query, "results": hits,
           "meta": _meta(comp, meta)}
    if args.json:
        _json_out(out)
        return
    if not hits:
        print(f"no scrip matches '{args.query}'")
        return
    for c in hits:
        print(f"{c['symbol']:<12} {c['name']}")
    _print_meta(out["meta"])


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="nepse_client.py", description="NEPSE market data (multi-source)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--no-cache", action="store_true",
                    help="skip cache read/write")
    ap.add_argument("--source", choices=["auto", "merolagani", "nepalstock"],
                    default="auto", help="force a source (default: auto-fallback)")
    ap.add_argument("--cache-dir", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--timeout", type=int, default=25, help="request timeout (s)")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("index", help="NEPSE index (optionally recent history)")
    p.add_argument("--history", type=int, default=0, metavar="N")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("summary", help="one-screen market overview")
    p.set_defaults(fn=cmd_summary)

    p = sub.add_parser("price", help="quote one or more scrips")
    p.add_argument("symbols", nargs="+", metavar="SYMBOL")
    p.set_defaults(fn=cmd_price)

    p = sub.add_parser("gainers", help="top gainers")
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(fn=lambda a, c: cmd_movers(a, c, "gainers"))

    p = sub.add_parser("losers", help="top losers")
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(fn=lambda a, c: cmd_movers(a, c, "losers"))

    p = sub.add_parser("volume", help="most traded scrips")
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(fn=cmd_volume)

    p = sub.add_parser("search", help="find a scrip symbol by company name")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(fn=cmd_search)

    args = ap.parse_args(argv)
    _REQ_TIMEOUT[0] = args.timeout
    cache_dir = _cache_dir(args.cache_dir)
    try:
        args.fn(args, cache_dir)
    except NepseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
