"""Yahoo Finance daily-chart fetcher (keyless JSON, datacenter-friendly).

Replaces Stooq for the daily index/commodity series — Stooq serves a
JavaScript browser-verification wall to datacenter IPs (GitHub Actions),
whereas Yahoo's v8 chart endpoint returns JSON with a browser UA.

Tidy output columns: date, open, high, low, close.
"""
from __future__ import annotations

import json

import pandas as pd

from .. import config
from . import http

CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?range=max&interval=1d"
)


def _parse_chart_json(text: str) -> pd.DataFrame:
    payload = json.loads(text)
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise ValueError(f"Yahoo chart error: {chart['error']}")
    results = chart.get("result")
    if not results:
        raise ValueError("Yahoo chart: no result")
    res = results[0]
    ts = res.get("timestamp")
    quote = (res.get("indicators", {}).get("quote") or [{}])[0]
    if not ts or "close" not in quote:
        raise ValueError("Yahoo chart: missing timestamps/quotes")
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(ts, unit="s", utc=True).tz_localize(None).normalize(),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "close": quote.get("close"),
        }
    )
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def fetch_chart(symbol: str) -> pd.DataFrame:
    from urllib.parse import quote

    resp = http.get(CHART_URL.format(symbol=quote(symbol)))
    return _parse_chart_json(resp.text)
