"""Sentiment sources without official APIs: FINRA margin debt, CNN
Fear & Greed, AAII survey.

These parse public web pages/files, so they are written tolerantly and the
loader falls back to cache/sample data whenever a format changes. Each
parser is a pure function over the raw payload for fixture testing.
"""
from __future__ import annotations

import io
import json

import pandas as pd

from .. import config
from . import http

# ------------------------------------------------------------ FINRA margin ----


def _parse_month_label(text: str) -> pd.Timestamp | None:
    """Parse FINRA month labels: 'May-26', 'April 2026', '2026-05', ..."""
    text = str(text).strip()
    for fmt in ("%b-%y", "%B-%y", "%b %Y", "%B %Y", "%Y-%m"):
        try:
            return pd.to_datetime(text, format=fmt)
        except ValueError:
            continue
    date = pd.to_datetime(text, errors="coerce")
    return None if pd.isna(date) else date


def _parse_margin_tables(html: str) -> pd.DataFrame:
    """FINRA margin-statistics page: yearly HTML tables of monthly rows.

    First column: month label; a column containing "Debit" holds margin
    debt in millions USD. Output: date, value (billions USD).
    """
    tables = pd.read_html(io.StringIO(html))
    rows = []
    for t in tables:
        debit_col = next((c for c in t.columns if "debit" in str(c).lower()), None)
        if debit_col is None or t.shape[1] < 2:
            continue
        month_col = t.columns[0]
        for _, r in t.iterrows():
            date = _parse_month_label(r[month_col])
            value = pd.to_numeric(
                str(r[debit_col]).replace(",", "").replace("$", ""), errors="coerce"
            )
            if date is not None and pd.notna(value):
                rows.append((date.replace(day=1), value / 1000.0))  # $M -> $B
    if not rows:
        raise ValueError("FINRA page contained no parsable margin tables")
    out = pd.DataFrame(rows, columns=["date", "value"])
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def fetch_margin_debt() -> pd.DataFrame:
    resp = http.get(config.FINRA_MARGIN_URL)
    return _parse_margin_tables(resp.text)


# -------------------------------------------------------- CNN Fear & Greed ----


def _parse_fear_greed_json(text: str) -> pd.DataFrame:
    """CNN graphdata JSON: fear_and_greed_historical.data = [{x: ms, y: score}]."""
    payload = json.loads(text)
    points = payload["fear_and_greed_historical"]["data"]
    out = pd.DataFrame(
        {
            "date": pd.to_datetime([p["x"] for p in points], unit="ms"),
            "value": [float(p["y"]) for p in points],
        }
    )
    out["date"] = out["date"].dt.normalize()
    return out.dropna().sort_values("date").reset_index(drop=True)


def fetch_fear_greed() -> pd.DataFrame:
    resp = http.get(config.CNN_FEAR_GREED_URL)
    return _parse_fear_greed_json(resp.text)


# ------------------------------------------------------------- AAII survey ----


def _clean_aaii_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """AAII sentiment sheet -> tidy (date, value) of bull-bear spread in %p.

    Columns are located by name ("Date", "Bullish", "Bearish"); percentages
    may be stored as fractions (0.38) or percents (38).
    """
    cols = {str(c).strip().lower(): c for c in raw.columns}
    date_col = next((cols[k] for k in cols if "date" in k), None)
    bull_col = next((cols[k] for k in cols if "bull" in k), None)
    bear_col = next((cols[k] for k in cols if "bear" in k), None)
    if not all((date_col is not None, bull_col is not None, bear_col is not None)):
        raise ValueError(f"AAII sheet: unexpected columns {list(raw.columns)}")
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(raw[date_col], errors="coerce"),
            "bull": pd.to_numeric(raw[bull_col], errors="coerce"),
            "bear": pd.to_numeric(raw[bear_col], errors="coerce"),
        }
    ).dropna()
    if df.empty:
        raise ValueError("AAII sheet: no parsable rows")
    if df["bull"].max() <= 1.5:  # stored as fractions
        df[["bull", "bear"]] *= 100
    df["value"] = df["bull"] - df["bear"]
    return df[["date", "value"]].sort_values("date").reset_index(drop=True)


def fetch_aaii() -> pd.DataFrame:
    resp = http.get(config.AAII_SENTIMENT_URL)
    raw = pd.read_excel(io.BytesIO(resp.content))
    return _clean_aaii_frame(raw)
