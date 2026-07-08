"""Source orchestration: fresh cache -> live fetch -> stale cache -> sample.

Never raises to the UI; every source always yields a frame plus a status
badge so the dashboard can show where its data came from.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

import pandas as pd

from . import cache, config
from .fetchers import fred, korea, multpl, sentiment, shiller, stooq


class DataStatus(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    SNAPSHOT = "snapshot"        # bundled real-data file, recently auto-refreshed
    STALE_CACHE = "stale_cache"
    SAMPLE = "sample"


# source name -> (fetch function, ttl key)
SOURCES: dict[str, tuple[Callable[[], pd.DataFrame], str]] = {
    "shiller": (shiller.fetch_shiller, "shiller"),
    "aiae_inputs": (fred.fetch_aiae_inputs, "aiae_inputs"),
    "finra_margin_debt": (sentiment.fetch_margin_debt, "finra"),
    "cnn_fear_greed": (sentiment.fetch_fear_greed, "cnn"),
    "aaii_sentiment": (sentiment.fetch_aaii, "aaii"),
    "krx_valuation": (korea.fetch_krx_valuation, "krx"),
    "worldbank_gdp": (korea.fetch_worldbank_gdp, "worldbank"),
    **{
        f"fred_{sid}": ((lambda s=sid: fred.fetch_series(s)), "fred")
        for sid in config.FRED_SERIES.values()
    },
    **{
        f"multpl_{key}": ((lambda k=key: multpl.fetch_table(k)), "multpl")
        for key in config.MULTPL_PAGES
    },
    **{
        f"stooq_{key}": ((lambda k=key: stooq.fetch_daily(k)), "stooq")
        for key in config.STOOQ_SYMBOLS
    },
    **{
        f"fred_{sid}": ((lambda s=sid: fred.fetch_series(s)), "fred")
        for sid in config.FRED_KR_SERIES.values()
    },
}


def _load_sample(name: str) -> pd.DataFrame | None:
    path = config.SAMPLE_DATA_DIR / f"{name}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def _snapshot_fresh(name: str) -> bool:
    """True if the bundled file for this source is real data refreshed
    recently (by scripts/refresh_sample_data.py or the GitHub Actions
    workflow), so a network fetch on cold start is unnecessary."""
    meta_path = config.SAMPLE_DATA_DIR / "_meta.json"
    if not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text())
        refreshed = datetime.fromisoformat(meta[name])
    except (json.JSONDecodeError, KeyError, ValueError):
        return False
    return datetime.now(timezone.utc) - refreshed < config.SNAPSHOT_TTL


def load_source(name: str, force: bool = False) -> tuple[pd.DataFrame, DataStatus]:
    fetch_fn, ttl_key = SOURCES[name]
    ttl = config.CACHE_TTL[ttl_key]

    if not force:
        fresh = cache.get(name, ttl)
        if fresh is not None:
            return fresh, DataStatus.CACHED
        # A recently auto-refreshed bundled snapshot is real data; use it
        # without touching the network so cold starts render instantly.
        if _snapshot_fresh(name):
            snapshot = _load_sample(name)
            if snapshot is not None and len(snapshot):
                return snapshot, DataStatus.SNAPSHOT

    if not config.OFFLINE:
        try:
            df = fetch_fn()
            if df is not None and len(df):
                cache.put(name, df)
                return df, DataStatus.LIVE
        except Exception:  # noqa: BLE001 - fall through the resilience chain
            pass

    stale = cache.get_stale(name)
    if stale is not None:
        return stale, DataStatus.STALE_CACHE

    sample = _load_sample(name)
    if sample is not None:
        return sample, DataStatus.SAMPLE

    raise RuntimeError(f"source {name!r}: no live data, no cache, no sample")


def _sample_or_stale(name: str) -> tuple[pd.DataFrame, DataStatus]:
    stale = cache.get_stale(name)
    if stale is not None:
        return stale, DataStatus.STALE_CACHE
    sample = _load_sample(name)
    if sample is not None:
        status = DataStatus.SNAPSHOT if _snapshot_fresh(name) else DataStatus.SAMPLE
        return sample, status
    return pd.DataFrame(), DataStatus.SAMPLE


def load_all(force: bool = False) -> dict[str, tuple[pd.DataFrame, DataStatus]]:
    """Load every source, bounded by a total wall-clock budget.

    Offline mode is trivially fast (no network), so it stays sequential.
    Online, sources are fetched in parallel and any that don't finish
    within ``config.LOAD_BUDGET`` seconds fall back to cache/sample — this
    keeps the first cold load snappy on Streamlit Cloud even when a few
    sources are slow or blocked.
    """
    if config.OFFLINE:
        return {name: load_source(name, force=force) for name in SOURCES}

    results: dict[str, tuple[pd.DataFrame, DataStatus]] = {}
    executor = ThreadPoolExecutor(max_workers=min(len(SOURCES), 12))
    futures = {name: executor.submit(load_source, name, force) for name in SOURCES}
    deadline = time.monotonic() + config.LOAD_BUDGET
    for name, fut in futures.items():
        remaining = max(0.1, deadline - time.monotonic())
        try:
            results[name] = fut.result(timeout=remaining)
        except Exception:  # timeout or fetch error -> cache/sample fallback
            results[name] = _sample_or_stale(name)
    # Don't block on stragglers; their sockets time out on their own and any
    # late success still warms the on-disk cache for the next load.
    executor.shutdown(wait=False)
    return results
