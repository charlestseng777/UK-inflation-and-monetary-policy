"""
Refinitiv / LSEG Data Platform (RDP) REST client — optional.

Credentials come only from the environment:
  * a machine account:  REFINITIV_USERNAME + REFINITIV_PASSWORD + REFINITIV_APP_KEY
  * or a service account: REFINITIV_CLIENT_ID + REFINITIV_CLIENT_SECRET

An app key alone is not enough to sign in; RDP's password grant needs the
machine-account username and password as well.

Uses the historical-pricing interday-summaries view, which most RDP licences
include, rather than real-time snapshots.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse

import pandas as pd

from ..config import get_settings
from .base import HttpClient, SourceError, clean_series

log = logging.getLogger(__name__)
BASE = "https://api.refinitiv.com"

YIELD_FIELDS = ("MID_YLD_1", "B_YLD_1", "SEC_YLD_1", "PRIMACT_1", "TRDPRC_1", "HST_CLOSE")
PRICE_FIELDS = ("TRDPRC_1", "MID_PRICE", "SETTLE", "HST_CLOSE", "PRIMACT_1", "OFF_CLOSE")


class RefinitivSession:
    def __init__(self, http: HttpClient):
        self.http = http
        self._token: str | None = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def _login(self) -> None:
        s = get_settings()
        if s.refinitiv_client_id and s.refinitiv_client_secret:
            url, data = f"{BASE}/auth/oauth2/v2/token", {
                "grant_type": "client_credentials", "client_id": s.refinitiv_client_id,
                "client_secret": s.refinitiv_client_secret, "scope": "trapi"}
        elif s.refinitiv_username and s.refinitiv_password and s.refinitiv_app_key:
            url, data = f"{BASE}/auth/oauth2/v1/token", {
                "grant_type": "password", "username": s.refinitiv_username,
                "password": s.refinitiv_password, "client_id": s.refinitiv_app_key,
                "scope": "trapi", "takeExclusiveSignOnControl": "false"}
        else:
            raise SourceError("Refinitiv credentials not configured")
        payload = json.loads(self.http.request("POST", url, data=data, use_cache=False))
        if not payload.get("access_token"):
            raise SourceError("Refinitiv token response had no access_token")
        self._token = payload["access_token"]
        self._expires = time.time() + int(payload.get("expires_in", 300)) - 30

    def token(self) -> str:
        with self._lock:
            if not self._token or time.time() >= self._expires:
                self._login()
            return self._token  # type: ignore[return-value]


def parse_interday(text: str, ric: str, fields: tuple[str, ...]) -> pd.Series:
    payload = json.loads(text)
    block = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(block, dict) or "data" not in block:
        raise SourceError(f"Refinitiv {ric}: {str(block)[:160]}")
    headers = [h.get("name") for h in block.get("headers", [])]
    values = {}
    for row in block["data"]:
        rec = dict(zip(headers, row))
        for f in fields:
            v = rec.get(f)
            if isinstance(v, (int, float)):
                values[str(rec.get("DATE"))[:10]] = float(v)
                break
        else:
            bid, ask = rec.get("BID"), rec.get("ASK")
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
                values[str(rec.get("DATE"))[:10]] = (bid + ask) / 2
    return clean_series(values, ric)


def fetch(session: RefinitivSession, ric: str, start: str, kind: str) -> pd.Series:
    fields = YIELD_FIELDS if kind in {"yield", "rate", "spread"} else PRICE_FIELDS
    q = urllib.parse.urlencode({"interval": "P1D", "start": start, "count": "10000"})
    url = f"{BASE}/data/historical-pricing/v1/views/interday-summaries/{urllib.parse.quote(ric, safe='')}?{q}"
    body = session.http.request("GET", url, headers={"Authorization": f"Bearer {session.token()}",
                                                     "Accept": "application/json"}, use_cache=False)
    return parse_interday(body.decode("utf-8"), ric, fields)
