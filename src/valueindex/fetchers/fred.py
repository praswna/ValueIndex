"""FRED fetcher: keyless fredgraph.csv endpoint, or the official API when
FRED_API_KEY is set (free key from fred.stlouisfed.org/docs/api/api_key.html
— needed on datacenter IPs like GitHub Actions, which the CSV endpoint
blocks).

Returns tidy frames with columns: date, value.
"""
from __future__ import annotations

import io
import json
import os

import pandas as pd

from .. import config
from . import http

FRED_API_URL = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id={sid}&api_key={key}&file_type=json"
)


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


def _parse_api_json(text: str, series_id: str) -> pd.DataFrame:
    """Parse the official API's observations JSON into (date, value)."""
    payload = json.loads(text)
    obs = payload.get("observations")
    if not obs:
        raise ValueError(f"FRED API for {series_id}: no observations")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime([o["date"] for o in obs]),
            "value": pd.to_numeric(
                [None if o["value"] == "." else o["value"] for o in obs],
                errors="coerce",
            ),
        }
    )
    return out.dropna(subset=["value"]).reset_index(drop=True)


def fetch_series(series_id: str) -> pd.DataFrame:
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if api_key:
        resp = http.get(FRED_API_URL.format(sid=series_id, key=api_key))
        return _parse_api_json(resp.text, series_id)
    resp = http.get(config.FRED_CSV_URL.format(sid=series_id))
    return _parse_fredgraph_csv(resp.text, series_id)


def fetch_aiae_inputs() -> pd.DataFrame:
    """Fetch all Z.1 series needed for AIAE, wide by component key."""
    frames = {}
    for key, sid in config.AIAE_SERIES.items():
        frames[key] = fetch_series(sid).set_index("date")["value"].rename(key)
    wide = pd.concat(frames.values(), axis=1).sort_index()
    return wide.reset_index()
