#!/usr/bin/env python3
"""Offline tests for the nepse skill client — stdlib only, no network.

Run:  python3 tests/test_nepse_client.py
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import nepse_client as nc  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


# ------------------------------------------------------------ fixtures

FIX_MARKET = """
<table><thead><tr><th>Symbol</th></tr></thead><tbody>
<tr><td><a href='CompanyDetail.aspx?symbol=NABIL' title='NABIL (Nabil Bank Limited)'>NABIL</a></td>
<td class='text-right'>528.70</td><td class='text-right'>0.04</td><td class='text-right'>533.00</td>
<td class='text-right'>525.00</td><td class='text-right'>529.00</td><td class='text-right'>60,404</td>
<td class='text-right'></td><td class='text-right'></td>
<td><a href='javascript:void(0);' title='Add to Watchlist' onclick='addToWatchlist("NABIL");'></a></td></tr>
<tr><td><a href='CompanyDetail.aspx?symbol=ACLBSL' title='ACLBSL (Agriculture Dev Bank Ltd)'>ACLBSL</a></td>
<td class='text-right'>869.00</td><td class='text-right'>-0.34</td><td class='text-right'>872.00</td>
<td class='text-right'>866.80</td><td class='text-right'>866.80</td><td class='text-right'>381</td></tr>
<tr><td><a href='CompanyDetail.aspx?symbol=EMPTY' title='x'>EMPTY</a></td>
<td class='text-right'></td><td class='text-right'></td><td class='text-right'></td>
<td class='text-right'></td><td class='text-right'></td><td class='text-right'></td></tr>
<tr><td><a href="CompanyDetail.aspx?symbol=DQUOT">DQUOT</a></td>
<td class='text-right'>100.00</td><td class='text-right'>1.00</td><td class='text-right'>101.00</td>
<td class='text-right'>99.50</td><td class='text-right'>100.50</td><td class='text-right'>10</td></tr>
</tbody></table>
"""

FIX_INDEX = """
<table><thead><tr><th>#</th><th>Date (AD)</th><th>Index Value</th>
<th>Absolute Change</th><th>Percentage Change</th></tr></thead><tbody>
<tr><td>2</td><td>2026/10/01</td><td>2,599.15</td><td>0.26</td><td>0.01%</td></tr>
<tr><td>1</td><td>2026/10/02</td><td>2,587.25</td><td>-11.90</td><td>-0.45%</td></tr>
<tr><td>3</td><td>2026/09/30</td><td>2,598.89</td><td>-4.82</td><td>-0.18%</td></tr>
</tbody></table>
"""

FIX_COMPANIES = """
<script>var x = [{"id":16,"symbol":"NABIL","companyname":"Nabil Bank Limited"},
{"id":255,"symbol":"NABILP","companyname":"NABIL Bank Limited Promoter Share"},
{"id":431,"symbol":"NABILINV","companyname":"Nabil Investment Banking Limited"}];</script>
"""

FIX_NS_INDEX = ('[{"indexName":"Nepal Stock Exchange Limited","indexValue":2587.25,'
                '"turnover":1234567890.5,"volume":9876543,"difference":-11.90,'
                '"percentageChange":-0.45,"businessDate":"2026-10-02"}]')

FIX_NS_PRICE = {
    "content": {
        "pagination": {"page": 1, "totalPages": 2},
        "dataList": [
            {"stockSymbol": "nabil", "lastTradedPrice": 528.7,
             "percentChange": 0.04, "highPrice": 533.0, "lowPrice": 525.0,
             "openPrice": 529.0, "shareTradedVolume": 60404,
             "turnOverValue": 31950000.0},
            {"stockSymbol": "NICA", "ltp": 500.0, "percentageChange": -1.5,
             "previousClose": 507.6, "volume": 100},
        ],
    }
}

# ------------------------------------------------------------ tests

mkt = nc.parse_latest_market(FIX_MARKET)
rows = mkt["rows"]
check("market: 3 usable rows (untraded skipped)", len(rows) == 3, str(sorted(rows)))
n = rows.get("NABIL", {})
check("market: NABIL ltp", n.get("ltp") == 528.70, str(n.get("ltp")))
check("market: NABIL pct", n.get("pct_change") == 0.04, str(n.get("pct_change")))
check("market: NABIL high=533 (cell order B)", n.get("high") == 533.0)
check("market: NABIL low=525", n.get("low") == 525.0)
check("market: NABIL open=529", n.get("open") == 529.0)
check("market: NABIL qty=60404", n.get("qty") == 60404)
check("market: NABIL prev_close derived",
      abs((n.get("prev_close") or 0) - 528.49) < 0.02, str(n.get("prev_close")))
check("market: NABIL high>=open>=low",
      n.get("high", 0) >= n.get("open", 0) >= n.get("low", 9999))
check("market: double-quoted symbol link parsed", "DQUOT" in rows)

idx = nc.parse_index_history(FIX_INDEX)
hist = idx["history"]
check("index: 3 rows sorted desc", len(hist) == 3 and hist[0]["date_ad"] == "2026/10/02")
check("index: latest value 2587.25", hist[0]["value"] == 2587.25)
check("index: latest pct -0.45", hist[0]["pct_change"] == -0.45)

comp = nc.parse_companies(FIX_COMPANIES)
check("companies: 3 entries", len(comp["companies"]) == 3)
syms = {c["symbol"] for c in comp["companies"]}
check("companies: NABILP upper-cased", "NABILP" in syms)
q = "nabilinv"
hits = [c for c in comp["companies"]
        if q in c["symbol"].lower() or q in c["name"].lower()]
check("search filter: 'nabilinv' -> NABILINV only",
      [c["symbol"] for c in hits] == ["NABILINV"])

nsi = nc.parse_ns_index(json.loads(FIX_NS_INDEX))
check("ns index: value", nsi["value"] == 2587.25)
check("ns index: turnover", nsi["turnover"] == 1234567890.5)
check("ns index: history entry built", nsi["history"][0]["value"] == 2587.25)

nst = nc.parse_ns_table(FIX_NS_PRICE)
check("ns table: 2 rows", len(nst["rows"]) == 2)
check("ns table: lowercase symbol up-cased", "NABIL" in nst["rows"])
check("ns table: alt key ltp", nst["rows"]["NABIL"]["ltp"] == 528.7)
check("ns table: alt key qty", nst["rows"]["NABIL"]["qty"] == 60404)
check("ns table: prev_close present", nst["rows"]["NICA"]["prev_close"] == 507.6)
check("ns table: turnover mapped",
      nst["rows"]["NABIL"]["turnover"] == 31950000.0)

up = nc._movers(rows, "pct_change", 2, True)
check("movers: gainers order DQUOT first",
      [r["symbol"] for r in up] == ["DQUOT", "NABIL"])
lo = nc._movers(rows, "pct_change", 2, False)
check("movers: losers order ACLBSL first",
      [r["symbol"] for r in lo] == ["ACLBSL", "NABIL"])
up3 = nc._movers(rows, "pct_change", 5, True)
check("movers: top respects N limit", len(up3) == 3)
st = nc._market_stats(rows)
check("stats: advancers=2 decliners=1", st["advancers"] == 2 and st["decliners"] == 1)
check("stats: total volume", st["total_volume"] == 60404 + 381 + 10)

check("_f: percent", nc._f("-0.45%") == -0.45)
check("_f: comma", nc._f("60,404") == 60404.0)
check("_f: empty", nc._f("") is None and nc._f("-") is None)

with tempfile.TemporaryDirectory() as td:
    nc._cache_write("x", {"a": 1}, td)
    got = nc._cache_read("x", 600, td)
    check("cache: roundtrip fresh", got and got["payload"] == {"a": 1}
          and not got["stale"])
    obj = json.loads((Path(td) / "x.json").read_text())
    obj["fetched_at"] = time.time() - 9999
    (Path(td) / "x.json").write_text(json.dumps(obj))
    got2 = nc._cache_read("x", 600, td)
    check("cache: stale flagged after TTL", got2 and got2["stale"])
    empty = nc._cache_read("missing", 600, td)
    check("cache: missing -> None", empty is None)

    def _boom():
        raise nc.NepseError("blocked")

    try:
        payload, meta = nc._cached("x", 600, _boom, td, use_cache=True)
        check("cache: error fallback serves stale when cache on",
              payload == {"a": 1} and meta.get("cache") == "stale", str(meta))
    except nc.NepseError:
        check("cache: error fallback serves stale when cache on", False,
              "raised instead")

    try:
        nc._cached("x", 600, _boom, td, use_cache=False)
        check("cache: --no-cache never serves cache on error", False, "no raise")
    except nc.NepseError:
        check("cache: --no-cache never serves cache on error", True)

skill_md = (Path(__file__).resolve().parent.parent / "SKILL.md").read_text()
import re as _re  # noqa: E402
dm = _re.search(r"^description: (.*)$", skill_md, _re.M)
desc = dm.group(1) if dm else ""
check("SKILL.md: description <= 60 chars, ends period",
      0 < len(desc) <= 60 and desc.endswith("."), f"len={len(desc)}")
check("SKILL.md: author human first",
      skill_md.find("Momkey") != -1 and
      skill_md.find("Momkey") < skill_md.find("Sprkey Agent"))

r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent
                                        / "scripts" / "nepse_client.py"), "--help"],
                   capture_output=True, text=True, timeout=30)
check("CLI: --help exits 0", r.returncode == 0)

# ------------------------------------------------------------ report

fails = [x for x in RESULTS if not x[1]]
for name, ok, detail in RESULTS:
    print(f"{'PASS' if ok else 'FAIL':4} {name}"
          + (f"  [{detail}]" if detail and not ok else ""))
print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} PASS"
      + (f" — {len(fails)} FAIL" if fails else ""))
sys.exit(1 if fails else 0)
