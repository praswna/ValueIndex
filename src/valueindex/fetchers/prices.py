"""Daily price series with source failover.

Yahoo Finance (keyless JSON) is primary because Stooq blocks datacenter
IPs with a JS-verification wall; Stooq stays as a fallback for local runs
where it still works. Same tidy schema either way: date, open, high, low,
close.
"""
from __future__ import annotations

import pandas as pd

from .. import config
from . import stooq, yahoo


def fetch_daily(key: str) -> pd.DataFrame:
    symbol = config.YAHOO_SYMBOLS.get(key)
    last_exc: Exception | None = None
    if symbol:
        try:
            df = yahoo.fetch_chart(symbol)
            if len(df):
                return df
        except Exception as exc:  # noqa: BLE001 - fall back to Stooq
            last_exc = exc
    try:
        return stooq.fetch_daily(key)
    except Exception as exc:  # noqa: BLE001
        raise last_exc or exc
