"""
Positioning and flows for the UK rates tab:

  * CFTC Traders in Financial Futures for sterling (CME British pound) and
    any CME SONIA futures — gilt futures trade on ICE, which the CFTC does not
    cover, so FX and STIR positioning is the closest public read.
  * DMO gilt auction results.

Both are best-effort: failures are logged and the tab says what is missing.
"""

from __future__ import annotations

import json
import re
import statistics
import urllib.parse
import xml.etree.ElementTree as ET

CFTC_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
ZSCORE_WEEKS = 156

DMO_URLS = [
    "https://www.dmo.gov.uk/data/XmlDataReport?reportCode=D2.1E",
    "https://www.dmo.gov.uk/data/XmlDataReport?reportCode=D2.1A",
]


def _num(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _net(row, lo, sh):
    a, b = _num(row.get(lo)), _num(row.get(sh))
    return None if a is None or b is None else round(a - b)


def _z(values):
    w = [v for v in values[-ZSCORE_WEEKS:] if v is not None]
    if len(w) < 26:
        return None
    sd = statistics.pstdev(w)
    return round((w[-1] - statistics.fmean(w)) / sd, 2) if sd else None


def _pctile(values):
    w = [v for v in values[-ZSCORE_WEEKS:] if v is not None]
    if len(w) < 26:
        return None
    return round(100 * sum(v <= w[-1] for v in w) / len(w))


def _label(name: str) -> str:
    """'BRITISH POUND - CHICAGO MERCANTILE EXCHANGE' -> 'British pound'."""
    base = name.split(" - ")[0].strip()
    if not base.isupper():
        return base
    words = base.capitalize().split()
    return " ".join(w.upper() if w.lower() in ("sonia", "gbp", "uk") else w for w in words)


def cftc_sterling(http_get, start: str) -> dict:
    where = ("(upper(market_and_exchange_names) like '%BRITISH POUND%' "
             "OR upper(market_and_exchange_names) like '%SONIA%') "
             f"AND report_date_as_yyyy_mm_dd >= '{start}'")
    query = {"$where": where, "$order": "report_date_as_yyyy_mm_dd", "$limit": "50000"}
    rows = json.loads(http_get(f"{CFTC_URL}?{urllib.parse.urlencode(query)}"))
    if not rows:
        raise RuntimeError("CFTC returned no sterling / SONIA rows")

    series: dict[str, dict[str, dict]] = {}
    labels: dict[str, str] = {}
    for row in rows:
        code = str(row.get("cftc_contract_market_code", "")).strip()
        day = str(row.get("report_date_as_yyyy_mm_dd", ""))[:10]
        labels[code] = _label(row.get("market_and_exchange_names", code))
        oi = _num(row.get("open_interest_all"))
        lev = _net(row, "lev_money_positions_long", "lev_money_positions_short")
        series.setdefault(code, {})[day] = {
            "oi": round(oi) if oi is not None else None,
            "lev_net": lev,
            "am_net": _net(row, "asset_mgr_positions_long", "asset_mgr_positions_short"),
            "dealer_net": _net(row, "dealer_positions_long_all", "dealer_positions_short_all"),
            "lev_pct_oi": round(100 * lev / oi, 2) if lev is not None and oi else None,
        }

    # Drop contracts that stopped reporting long ago (renamed/delisted).
    latest_date = max(d for s in series.values() for d in s)
    codes = [c for c, s in series.items() if max(s) >= latest_date[:4]]
    codes.sort(key=lambda c: (0 if "pound" in labels[c].lower() else 1, labels[c]))

    ids = {c: f"c{c}" for c in codes}
    dates = sorted({d for c in codes for d in series[c]})
    weekly = []
    for d in dates:
        row = {"date": d}
        for c in codes:
            p = series[c].get(d)
            if p:
                row[f"{ids[c]}_lev"] = p["lev_net"]
                row[f"{ids[c]}_am"] = p["am_net"]
        weekly.append({k: v for k, v in row.items() if v is not None})

    latest = []
    for c in codes:
        pts = [series[c][d] for d in sorted(series[c])]
        cur, prev = pts[-1], (pts[-2] if len(pts) > 1 else {})
        latest.append({
            "id": ids[c], "label": labels[c], "code": c, "as_of": max(series[c]),
            "lev_net": cur["lev_net"], "am_net": cur["am_net"], "dealer_net": cur["dealer_net"],
            "oi": cur["oi"], "lev_pct_oi": cur["lev_pct_oi"],
            "lev_change": (cur["lev_net"] - prev["lev_net"])
            if cur["lev_net"] is not None and prev.get("lev_net") is not None else None,
            "am_change": (cur["am_net"] - prev["am_net"])
            if cur["am_net"] is not None and prev.get("am_net") is not None else None,
            "lev_z": _z([p["lev_net"] for p in pts]),
            "am_z": _z([p["am_net"] for p in pts]),
            "lev_pctile": _pctile([p["lev_net"] for p in pts]),
        })

    return {
        "as_of": latest_date,
        "contracts": [{"id": ids[c], "label": labels[c], "code": c} for c in codes],
        "weekly": weekly,
        "latest": latest,
    }


# --------------------------------------------------------------------------
# DMO gilt auctions
# --------------------------------------------------------------------------

def _records(root: ET.Element) -> list[dict]:
    """Every element whose children are all leaves, as {lower tag/attr: text}."""
    out = []
    for el in root.iter():
        kids = list(el)
        if kids and all(len(list(k)) == 0 for k in kids):
            rec = {k.tag.split("}")[-1].lower(): (k.text or "").strip() for k in kids}
            out.append(rec)
        elif not kids and el.attrib and len(el.attrib) >= 3:
            out.append({k.lower(): v for k, v in el.attrib.items()})
    return out


def _field(rec: dict, *needles: str, exclude: tuple[str, ...] = ()) -> str | None:
    for key, value in rec.items():
        if all(n in key for n in needles) and not any(x in key for x in exclude):
            return value
    return None


def _date(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()[:25]
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%d/%m/%Y", "%d-%b-%y"):
        try:
            import datetime as dt
            return dt.datetime.strptime(text.split("T")[0], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def dmo_auctions(http_get, log, since: str) -> dict:
    errors = []
    for url in DMO_URLS:
        try:
            root = ET.fromstring(http_get(url))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {exc}")
            continue
        recs = _records(root)
        if recs:
            log(f"DMO  {url.split('=')[-1]}: {len(recs)} records; fields {sorted(recs[0])[:14]}")
        out = []
        for rec in recs:
            day = _date(_field(rec, "date", exclude=("close", "redemption", "maturity", "settle", "issue")))
            name = _field(rec, "name") or _field(rec, "instrument") or _field(rec, "gilt")
            cover = _num(_field(rec, "cover"))
            if not day or not name or cover is None or day < since:
                continue
            if "index" in (name or "").lower() or "i/l" in (name or "").lower():
                continue  # index-linked: real yields, not comparable
            out.append({
                "date": day,
                "name": name,
                "cover": cover,
                "tail_bp": _num(_field(rec, "tail")),
                "yield": _num(_field(rec, "yield", exclude=("tail", "range"))),
                "size_bn": (lambda v: round(v / 1e9, 2) if v and v > 1e6 else v)(
                    _num(_field(rec, "nominal") or _field(rec, "amount"))),
            })
        if out:
            out.sort(key=lambda r: r["date"], reverse=True)
            return {"recent": out[:20], "source": url}
        errors.append(f"{url}: no auction records recognised")
    raise RuntimeError("; ".join(errors)[:300])
