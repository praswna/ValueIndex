"""Shared data-collection helpers used by both the CLI refresh script and
the local GUI collector (collector.py).

Running from a home/residential IP reaches sources that block datacenter
IPs (KRX, FINRA, AAII), so the GUI is the way to keep those live.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from . import config, loader

META_PATH = config.SAMPLE_DATA_DIR / "_meta.json"

# Sources that datacenter IPs (GitHub Actions) get blocked from — these
# only refresh from a home run. The rest work anywhere.
LOCAL_ONLY = {"krx_valuation", "finra_margin_debt", "aaii_sentiment"}


def source_names() -> list[str]:
    return list(loader.SOURCES)


def collect_source(name: str) -> tuple[pd.DataFrame | None, str | None]:
    """Fetch one source live. Returns (dataframe, error_message)."""
    fetch_fn, _ = loader.SOURCES[name]
    try:
        df = fetch_fn()
        if df is None or df.empty:
            return None, "빈 응답 (0 rows)"
        return df, None
    except Exception as exc:  # noqa: BLE001 - report every failure to the UI
        return None, f"{type(exc).__name__}: {exc}"


def load_meta() -> dict:
    if META_PATH.exists():
        try:
            return json.loads(META_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_snapshot(name: str, df: pd.DataFrame, meta: dict | None = None) -> dict:
    """Write one source's CSV and stamp its refresh time in _meta.json."""
    config.SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.SAMPLE_DATA_DIR / f"{name}.csv", index=False)
    meta = load_meta() if meta is None else meta
    meta[name] = datetime.now(timezone.utc).isoformat()
    return meta


def write_meta(meta: dict) -> None:
    META_PATH.write_text(json.dumps(meta, indent=1, sort_keys=True))


def latest_date(df: pd.DataFrame) -> str:
    if "date" in df.columns:
        try:
            return str(pd.to_datetime(df["date"]).max().date())
        except Exception:  # noqa: BLE001
            return "-"
    return "-"
