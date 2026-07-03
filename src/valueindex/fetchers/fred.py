"""FRED fetcher using the keyless fredgraph.csv endpoint.

Returns tidy frames with columns: date, value.
"""
from __future__ import annotations

import io

import pandas as pd

from .. import config
from . import http


def _parse_fredgraph_csv(text: str, series_id: str) -> pd.DataFrame:
    """Parse a fredgraph CSV body into a tidy (date, value) frame.

    Handles both header variants (``DATE`` pre-2024, ``observation_date``
    after) and ``.`` used by FRED for missing observations.
    """
    df = pd.read_csv(io.StringIO(text))
    date_col = next(
        (c for c in df.columns if c.lower() in ("date", "observation_date")), None
    )
    if date_col is None:
        raise ValueError(f"FRED CSV for {series_id}: no date column in {list(df.columns)}")
    value_col = next((c for c in df.columns if c != date_col), None)
    if value_col is None:
        raise ValueError(f"FRED CSV for {series_id}: no value column")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col]),
            "value": pd.to_numeric(df[value_col].replace(".", None), errors="coerce"),
        }
    )
    return out.dropna(subset=["value"]).reset_index(drop=True)


def fetch_series(series_id: str) -> pd.DataFrame:
    resp = http.get(config.FRED_CSV_URL.format(sid=series_id))
    return _parse_fredgraph_csv(resp.text, series_id)


def fetch_aiae_inputs() -> pd.DataFrame:
    """Fetch all Z.1 series needed for AIAE, wide by component key."""
    frames = {}
    for key, sid in config.AIAE_SERIES.items():
        frames[key] = fetch_series(sid).set_index("date")["value"].rename(key)
    wide = pd.concat(frames.values(), axis=1).sort_index()
    return wide.reset_index()
