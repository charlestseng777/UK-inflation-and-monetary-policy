"""SDMX REST sources that speak SDMX-CSV: the ECB Data Portal and the
Deutsche Bundesbank. Codes are 'FLOW/KEY', e.g. 'EXR/D.USD.EUR.SP00.A'."""

from __future__ import annotations

import io

import pandas as pd

from .base import HttpClient, SourceError, clean_series

ECB = "https://data-api.ecb.europa.eu/service/data/{flow}/{key}"
BUNDESBANK = "https://api.statistiken.bundesbank.de/rest/data/{flow}/{key}"
CSV_ACCEPT = "application/vnd.sdmx.data+csv;version=1.0.0"


def parse_sdmx_csv(text: str, code: str) -> pd.Series:
    frame = pd.read_csv(io.StringIO(text))
    if "TIME_PERIOD" not in frame.columns or "OBS_VALUE" not in frame.columns:
        raise SourceError(f"SDMX {code}: no TIME_PERIOD/OBS_VALUE columns")
    return clean_series(dict(zip(frame["TIME_PERIOD"], pd.to_numeric(frame["OBS_VALUE"], errors="coerce"))), code)


def _split(code: str) -> tuple[str, str]:
    if "/" not in code:
        raise SourceError(f"SDMX code must be FLOW/KEY, got {code!r}")
    flow, key = code.split("/", 1)
    return flow, key


def fetch_ecb(http: HttpClient, code: str, start: str) -> pd.Series:
    flow, key = _split(code)
    text = http.get_text(ECB.format(flow=flow, key=key), params={"startPeriod": start, "format": "csvdata"})
    return parse_sdmx_csv(text, code)


def fetch_bundesbank(http: HttpClient, code: str, start: str) -> pd.Series:
    flow, key = _split(code)
    text = http.get_text(BUNDESBANK.format(flow=flow, key=key), params={"startPeriod": start},
                         headers={"Accept": CSV_ACCEPT})
    return parse_sdmx_csv(text, code)
