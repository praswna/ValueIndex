"""Robert Shiller's ie_data.xls fetcher and parser.

Tidy output columns:
    date, price, dividend, earnings, cpi, gs10, real_price, real_earnings,
    cape, ecy

The Data sheet is a legacy .xls with ~7 header rows, footer notes, and a
fractional date format where the decimal part is the month: ``1871.1`` means
October 1871 (NOT January), ``1871.01`` means January.
"""
from __future__ import annotations

import io

import pandas as pd

from .. import config
from . import http

# Positional layout of the Data sheet (stable for many years):
# 0 Date | 1 P | 2 D | 3 E | 4 CPI | 5 Date Fraction | 6 GS10 | 7 Real Price
# 8 Real Dividend | 9 Real TR Price | 10 Real Earnings | 11 Real TR Earnings
# 12 CAPE | 13 (blank) | 14 TR CAPE | 15 (blank) | 16 Excess CAPE Yield ...
_COLUMN_POSITIONS = {
    "date": 0,
    "price": 1,
    "dividend": 2,
    "earnings": 3,
    "cpi": 4,
    "gs10": 6,
    "real_price": 7,
    "real_earnings": 10,
    "cape": 12,
    "ecy": 16,
}


def _parse_shiller_date(value) -> pd.Timestamp | None:
    """Parse Shiller's fractional year-month.

    The month lives in the decimal digits as a *string*: "1871.01" = Jan,
    "1871.1" = Oct (trailing zero dropped by Excel). Anything unparseable
    (footer notes, blanks) returns None.
    """
    text = str(value).strip()
    if not text or "." not in text:
        return None
    year_part, _, month_part = text.partition(".")
    if not (year_part.isdigit() and len(year_part) == 4):
        return None
    if month_part == "1":
        month = 10
    elif month_part.isdigit() and 1 <= int(month_part) <= 12 and len(month_part) <= 2:
        month = int(month_part)
    else:
        return None
    return pd.Timestamp(year=int(year_part), month=month, day=1)


def _clean_data_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn the raw Data-sheet grid (no headers) into the tidy frame."""
    out = pd.DataFrame()
    for name, pos in _COLUMN_POSITIONS.items():
        if pos < raw.shape[1]:
            out[name] = raw.iloc[:, pos]
        else:
            out[name] = pd.NA
    out["date"] = out["date"].map(_parse_shiller_date)
    out = out.dropna(subset=["date"])  # kills header remnants and footer notes
    for col in out.columns:
        if col != "date":
            out[col] = pd.to_numeric(out[col], errors="coerce")
    # Trailing partial-month rows lack price; drop rows with no price at all.
    out = out.dropna(subset=["price"]).reset_index(drop=True)
    return out


def _parse_ie_data(content: bytes) -> pd.DataFrame:
    raw = pd.read_excel(
        io.BytesIO(content), sheet_name="Data", header=None, skiprows=8
    )
    return _clean_data_sheet(raw)


def fetch_shiller() -> pd.DataFrame:
    last_exc: Exception | None = None
    for url in config.SHILLER_URLS:
        try:
            resp = http.get(url)
            df = _parse_ie_data(resp.content)
            if len(df) > 100:  # sanity: the real file has 1800+ rows
                return df
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            last_exc = exc
    raise RuntimeError(f"All Shiller URLs failed (last error: {last_exc})")
