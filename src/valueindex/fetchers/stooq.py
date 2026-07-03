"""Stooq daily CSV fetcher (S&P 500 OHLC, gold spot).

Tidy output columns: date, open, high, low, close.
"""
from __future__ import annotations

import io

import pandas as pd

from .. import config
from . import http


def _parse_stooq_csv(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError(f"unexpected stooq columns: {list(df.columns)}")
    keep = [c for c in ("date", "open", "high", "low", "close") if c in df.columns]
    out = df[keep].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in keep[1:]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def fetch_daily(key: str) -> pd.DataFrame:
    symbol = config.STOOQ_SYMBOLS[key]
    resp = http.get(config.STOOQ_CSV_URL.format(symbol=symbol))
    return _parse_stooq_csv(resp.text)
