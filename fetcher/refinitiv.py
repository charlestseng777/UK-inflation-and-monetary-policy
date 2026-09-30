"""
Optional Refinitiv / LSEG Data Platform (RDP) feed: MPC-dated SONIA OIS.

Runs only when credentials are set as GitHub Actions secrets (never commit
them): REFINITIV_USERNAME + REFINITIV_PASSWORD + REFINITIV_APP_KEY, or a
service account's REFINITIV_CLIENT_ID + REFINITIV_CLIENT_SECRET.

MPC-dated OIS contracts run from one MPC meeting to the next, so each quote is
the average SONIA the market expects between two meetings — the step it
prices at each meeting, directly. This is shown *alongside* the synthetic
MPC OIS curve (fetcher/market.py), which bootstraps the same thing from the
Bank's public curve; it does not replace it. RICs are in
config/refinitiv.json.

Uses the historical-pricing service (last close) rather than real-time
snapshots, which many RDP licences don't cover.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.refinitiv.com"
TIMEOUT = 60


def configured() -> bool:
    env = os.environ
    return bool(
        (env.get("REFINITIV_CLIENT_ID") and env.get("REFINITIV_CLIENT_SECRET"))
        or (env.get("REFINITIV_USERNAME") and env.get("REFINITIV_PASSWORD") and env.get("REFINITIV_APP_KEY"))
    )


def _request(url: str, data: dict | None = None, token: str | None = None):
    headers = {"Accept": "application/json", "User-Agent": "uk-inflation-dashboard/1.0"}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"{url.split('?')[0]} -> HTTP {exc.code}: {detail}") from None


def _token() -> str:
    env = os.environ
    if env.get("REFINITIV_CLIENT_ID") and env.get("REFINITIV_CLIENT_SECRET"):
        payload = _request(f"{BASE}/auth/oauth2/v2/token", {
            "grant_type": "client_credentials", "client_id": env["REFINITIV_CLIENT_ID"],
            "client_secret": env["REFINITIV_CLIENT_SECRET"], "scope": "trapi"})
    else:
        payload = _request(f"{BASE}/auth/oauth2/v1/token", {
            "grant_type": "password", "username": env["REFINITIV_USERNAME"],
            "password": env["REFINITIV_PASSWORD"], "client_id": env["REFINITIV_APP_KEY"],
            "scope": "trapi", "takeExclusiveSignOnControl": "true"})
    if not payload.get("access_token"):
        raise RuntimeError("RDP token response had no access_token")
    return payload["access_token"]


def _last_close(token: str, ric: str, start: str) -> tuple[str, float] | None:
    q = urllib.parse.urlencode({"interval": "P1D", "start": start, "count": "20"})
    url = f"{BASE}/data/historical-pricing/v1/views/interday-summaries/{urllib.parse.quote(ric, safe='')}?{q}"
    payload = _request(url, token=token)
    block = payload[0] if isinstance(payload, list) and payload else payload
    headers = [h.get("name") for h in block.get("headers", [])]
    for row in block.get("data", []):  # newest first
        rec = dict(zip(headers, row))
        for f in ("MID_PRICE", "PRIMACT_1", "TRDPRC_1", "SETTLE", "HST_CLOSE"):
            v = rec.get(f)
            if isinstance(v, (int, float)):
                return str(rec.get("DATE", ""))[:10], float(v)
        bid, ask = rec.get("BID"), rec.get("ASK")
        if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
            return str(rec.get("DATE", ""))[:10], (bid + ask) / 2
    return None


def mpc_dated_ois(config_path: Path, meetings: list[str], sonia: float | None,
                  bank_rate: float | None, start: str, log) -> dict:
    cfg = json.loads(config_path.read_text())
    token = _token()
    rows, errors = [], []
    for i, ric in enumerate(cfg.get("mpc_ois", [])):
        try:
            got = _last_close(token, ric, start)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ric}: {exc}")
            continue
        if got:
            rows.append({"ric": ric, "date": got[0], "rate": round(got[1], 4),
                         "meeting": meetings[i] if i < len(meetings) else None})
    if errors:
        log(f"RDP  {len(errors)} MPC OIS RIC(s) failed; first: {errors[0]}")
    if not rows:
        raise RuntimeError(errors[0] if errors else "no MPC-dated OIS prices returned")

    # Each quote is SONIA-space; express moves against today's SONIA, the
    # same basis the synthetic curve's SONIA-space forward starts from.
    ref = sonia
    prev = ref
    for r in rows:
        r["cumulative_bp"] = round((r["rate"] - ref) * 100, 1) if ref is not None else None
        r["change_bp"] = round((r["rate"] - prev) * 100, 1) if prev is not None else None
        prev = r["rate"]
    return {"source": "refinitiv", "reference_sonia": sonia, "bank_rate": bank_rate, "meetings": rows}
