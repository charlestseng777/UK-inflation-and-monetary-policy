"""
Gilt market panel: nominal, real and implied-inflation spot curves plus the
OIS curve, all from the Bank of England's published yield curves — the same
release the synthetic MPC OIS curve is built from (fetcher/market.py), just
the long-end sheets instead of the short end.

Produces one row per business day with the points the rates tab plots:

  gilt_2y/5y/10y/30y   nominal gilt spot yields
  s2s10, s5s30         curve spreads (bp)
  be_5y, be_10y        implied RPI inflation (breakevens)
  be_5y5y              5y5y forward implied inflation
  real_10y             real (index-linked) spot yield
  ois_1y/2y/5y         SONIA OIS spot
  gilt_ois_2y          2Y gilt minus 2Y OIS (bp) — the UK's go-to read on
                       supply / term-premium pressure, since there is no
                       public UK equivalent of the NY Fed's ACM model
  priced_12m           change in SONIA the OIS curve prices over the next
                       12 months (bp): the 1-year-ahead forward minus SONIA

Everything reads the curves in discount-factor space via market.curve_rate,
the same convention the synthetic curve uses.
"""

from __future__ import annotations

import datetime as dt
import io
import math
import re
import zipfile

from . import market
from .xlsx import Workbook, excel_date

BASE = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/"
ARCHIVES = {
    "nominal": BASE + "glcnominalddata.zip",
    "real": BASE + "glcrealddata.zip",
    "inflation": BASE + "glcinflationddata.zip",
}
LATEST = BASE + "latest-yield-curve-data.zip"

# Which tenors (years) to keep from each curve — the full 0.5y-40y grid for
# every day since 2018 would be most of a gigabyte of floats for no benefit.
KEEP = {
    "nominal": (2.0, 5.0, 10.0, 30.0),
    "real": (5.0, 10.0),
    "inflation": (5.0, 10.0),
}


def _long_sheet(book: Workbook) -> str:
    """The full-maturity spot sheet ('4. spot curve'), not the short end."""
    names = [n for n in book.sheet_names if "spot" in n.lower()]
    for n in names:
        if "short" not in n.lower():
            return n
    if names:
        return names[0]
    raise RuntimeError(f"no spot sheet in workbook ({', '.join(book.sheet_names)})")


def parse_curve_workbook(payload: bytes, start: dt.date, keep: tuple[float, ...],
                         out: dict[str, dict[float, float]]) -> None:
    """Read one GLC workbook into out[ISO date][tenor] = rate (percent)."""
    book = Workbook(payload)
    columns: dict[int, float] | None = None
    for cells in book.rows(_long_sheet(book)):
        label = str(cells.get(0) or "").strip().lower()
        if label.startswith("years"):
            columns = {}
            for column, value in cells.items():
                if column == 0:
                    continue
                try:
                    tenor = float(value)
                except (TypeError, ValueError):
                    continue
                if any(abs(tenor - k) < 1e-9 for k in keep):
                    columns[column] = tenor
            continue
        if not columns:
            continue
        when = excel_date(cells.get(0))
        if when is None or when < start:
            continue
        row = {}
        for column, tenor in columns.items():
            try:
                row[tenor] = float(cells.get(column))
            except (TypeError, ValueError):
                continue
        if row:
            out.setdefault(when.isoformat(), {}).update(row)


def _era_is_needed(name: str, start: dt.date) -> bool:
    """Archive files are named by era ('..._2016 to 2024.xlsx', '..._2025 to
    present.xlsx'); skip eras that end before `start` without opening them."""
    if "present" in name.lower():
        return True
    years = [int(y) for y in re.findall(r"(19\d{2}|20\d{2})", name)]
    return not years or max(years) >= start.year


def parse_zip(payload: bytes, kind: str, start: dt.date,
              out: dict[str, dict[float, float]]) -> list[str]:
    problems = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            low = name.lower()
            if not low.endswith(".xlsx") or kind not in low or not _era_is_needed(name, start):
                continue
            try:
                parse_curve_workbook(archive.read(name), start, KEEP[kind], out)
            except Exception as error:  # noqa: BLE001 - one bad era, not all of them
                problems.append(f"{name}: {error}")
    return problems


def fetch_curves(http_get, start: dt.date, log) -> dict[str, dict[str, dict[float, float]]]:
    """{kind: {date: {tenor: rate}}} for nominal / real / inflation."""
    latest = http_get(LATEST)
    curves: dict[str, dict[str, dict[float, float]]] = {}
    for kind, url in ARCHIVES.items():
        out: dict[str, dict[float, float]] = {}
        problems = parse_zip(http_get(url), kind, start, out)
        problems += parse_zip(latest, kind, start, out)
        for p in problems:
            log(f"BoE  {kind} curve: skipped {p}")
        log(f"BoE  {kind} curve: {len(out)} daily curves"
            + (f", latest {max(out)}" if out else ""))
        curves[kind] = out
    return curves


def _r(v, places=3):
    return None if v is None else round(v + 0.0, places)


def forward(r1: float, t1: float, r2: float, t2: float) -> float:
    """Continuously-compounded forward rate between t1 and t2 (percent)."""
    return (r2 * t2 - r1 * t1) / (t2 - t1)


def build_daily(curves: dict, ois: dict[str, list[tuple[float, float]]],
                sonia: dict[str, float], bank_rate: dict[str, float], start: str) -> list[dict]:
    nominal = curves.get("nominal", {})
    real = curves.get("real", {})
    infl = curves.get("inflation", {})
    dates = sorted(d for d in set(nominal) | set(ois) if d >= start)

    rows = []
    rate = None
    last_sonia = None
    for d in dates:
        # SONIA publishes T+1, so the latest curve date usually has no fixing
        # yet — carry the last one rather than drop the day's pricing.
        last_sonia = sonia.get(d, last_sonia)
        n = nominal.get(d, {})
        row: dict = {"date": d}
        for t, key in ((2.0, "gilt_2y"), (5.0, "gilt_5y"), (10.0, "gilt_10y"), (30.0, "gilt_30y")):
            row[key] = _r(n.get(t))
        if n.get(2.0) is not None and n.get(10.0) is not None:
            row["s2s10"] = _r((n[10.0] - n[2.0]) * 100, 1)
        if n.get(5.0) is not None and n.get(30.0) is not None:
            row["s5s30"] = _r((n[30.0] - n[5.0]) * 100, 1)

        i = infl.get(d, {})
        row["be_5y"] = _r(i.get(5.0))
        row["be_10y"] = _r(i.get(10.0))
        if i.get(5.0) is not None and i.get(10.0) is not None:
            row["be_5y5y"] = _r(forward(i[5.0], 5.0, i[10.0], 10.0))
        row["real_10y"] = _r(real.get(d, {}).get(10.0))

        curve = ois.get(d)
        if curve:
            o1, o2, o5 = (market.curve_rate(curve, t) for t in (1.0, 2.0, 5.0))
            row["ois_1y"], row["ois_2y"], row["ois_5y"] = _r(o1), _r(o2), _r(o5)
            # The Bank's OIS curve only runs to a few years, so the gilt-swap
            # spread is taken at 2Y, where both curves are always populated.
            if o2 is not None and n.get(2.0) is not None:
                row["gilt_ois_2y"] = _r((n[2.0] - o2) * 100, 1)
            # 1y-ahead forward (11m→13m window, DF space) vs today's SONIA.
            a, b = market.curve_rate(curve, 11 / 12), market.curve_rate(curve, 13 / 12)
            s = last_sonia
            if a is not None and b is not None and s is not None:
                row["priced_12m"] = _r((forward(a, 11 / 12, b, 13 / 12) - s) * 100, 1)

        row["sonia"] = _r(last_sonia)
        rate = bank_rate.get(d, rate)
        row["bank_rate"] = rate
        clean = {k: v for k, v in row.items() if v is not None}
        if len(clean) > 2:
            rows.append(clean)
    return rows


def ois_term_curve(curve: list[tuple[float, float]] | None, sonia: float | None) -> list[dict]:
    """Latest SONIA OIS term structure at standard tenors, for the table."""
    if not curve:
        return []
    out = []
    for label, t in (("1M", 1 / 12), ("3M", 0.25), ("6M", 0.5), ("1Y", 1.0), ("18M", 1.5),
                     ("2Y", 2.0), ("3Y", 3.0), ("5Y", 5.0)):
        v = market.curve_rate(curve, t)
        if v is not None:
            out.append({"tenor": label, "rate": _r(v),
                        "vs_sonia_bp": _r((v - sonia) * 100, 1) if sonia is not None else None})
    return out


def snapshot(rows: list[dict]) -> dict:
    """Latest level and 1w / 1m change for every series in the panel."""
    keys = sorted({k for r in rows for k in r if k != "date"})
    out = {}
    for key in keys:
        hist = [(r["date"], r[key]) for r in rows if key in r]
        if not hist:
            continue
        when, value = hist[-1]
        last = dt.date.fromisoformat(when)

        def ago(days):
            cutoff = (last - dt.timedelta(days=days)).isoformat()
            prior = [v for d, v in hist if d <= cutoff]
            return prior[-1] if prior else None

        w, m = ago(7), ago(30)
        out[key] = {"value": value, "date": when,
                    "chg_1w": _r(value - w) if w is not None else None,
                    "chg_1m": _r(value - m) if m is not None else None}
    return out


def isfinite(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))
