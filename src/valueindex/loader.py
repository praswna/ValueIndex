"""Source orchestration: fresh cache -> live fetch -> stale cache -> sample.

Never raises to the UI; every source always yields a frame plus a status
badge so the dashboard can show where its data came from.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Callable

import pandas as pd

from . import cache, config
from .fetchers import fred, multpl, sentiment, shiller, stooq


class DataStatus(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    STALE_CACHE = "stale_cache"
    SAMPLE = "sample"


# source name -> (fetch function, ttl key)
SOURCES: dict[str, tuple[Callable[[], pd.DataFrame], str]] = {
    "shiller": (shiller.fetch_shiller, "shiller"),
    "aiae_inputs": (fred.fetch_aiae_inputs, "aiae_inputs"),
    "finra_margin_debt": (sentiment.fetch_margin_debt, "finra"),
    "cnn_fear_greed": (sentiment.fetch_fear_greed, "cnn"),
    "aaii_sentiment": (sentiment.fetch_aaii, "aaii"),
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
}


def _load_sample(name: str) -> pd.DataFrame | None:
    path = config.SAMPLE_DATA_DIR / f"{name}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_source(name: str, force: bool = False) -> tuple[pd.DataFrame, DataStatus]:
    fetch_fn, ttl_key = SOURCES[name]
    ttl = config.CACHE_TTL[ttl_key]

    if not force:
        fresh = cache.get(name, ttl)
        if fresh is not None:
            return fresh, DataStatus.CACHED

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
        return sample, DataStatus.SAMPLE
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
