"""multpl.com table scraper (S&P 500 P/E, P/B, dividend yield).

Tidy output columns: date, value.
"""
from __future__ import annotations

import io
import re

import pandas as pd

from .. import config
from . import http


def _parse_table_html(html: str) -> pd.DataFrame:
    """Parse the first 2-column (Date, Value) table on a multpl page.

    Values may carry '%' signs and estimate markers ('†', 'estimate');
    dates look like 'Dec 1, 2025'.
    """
    tables = pd.read_html(io.StringIO(html))
    table = next((t for t in tables if t.shape[1] >= 2), None)
    if table is None:
        raise ValueError("multpl page contained no data table")
    table = table.iloc[:, :2]
    table.columns = ["date", "value"]
    table["date"] = pd.to_datetime(table["date"], errors="coerce")
    cleaned = (
        table["value"]
        .astype(str)
        .map(lambda v: re.sub(r"[%†]|estimate", "", v, flags=re.IGNORECASE).strip())
    )
    table["value"] = pd.to_numeric(cleaned, errors="coerce")
    table = table.dropna().sort_values("date").reset_index(drop=True)
    return table


def fetch_table(key: str) -> pd.DataFrame:
    url = config.MULTPL_PAGES[key]
    resp = http.get(url)
    return _parse_table_html(resp.text)
