"""File cache: CSV payload + JSON sidecar with the fetch timestamp."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from . import config


@dataclass(frozen=True)
class CacheInfo:
    name: str
    fetched_at: datetime

    @property
    def age(self) -> timedelta:
        return datetime.now(timezone.utc) - self.fetched_at


def _paths(name: str) -> tuple[Path, Path]:
    base = config.CACHE_DIR
    return base / f"{name}.csv", base / f"{name}.meta.json"


def info(name: str) -> CacheInfo | None:
    csv_path, meta_path = _paths(name)
    if not (csv_path.exists() and meta_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text())
        fetched_at = datetime.fromisoformat(meta["fetched_at"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
    return CacheInfo(name=name, fetched_at=fetched_at)


def _read(name: str) -> pd.DataFrame | None:
    csv_path, _ = _paths(name)
    try:
        df = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get(name: str, ttl: timedelta) -> pd.DataFrame | None:
    """Return the cached frame if present and younger than ttl."""
    meta = info(name)
    if meta is None or meta.age > ttl:
        return None
    return _read(name)


def get_stale(name: str) -> pd.DataFrame | None:
    """Return the cached frame regardless of age (offline fallback)."""
    if info(name) is None:
        return None
    return _read(name)


def put(name: str, df: pd.DataFrame) -> None:
    csv_path, meta_path = _paths(name)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    meta_path.write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat()})
    )
