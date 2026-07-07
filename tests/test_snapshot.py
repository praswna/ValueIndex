"""Snapshot-first loading: a recently refreshed bundled file skips the
network on cold start and is labeled SNAPSHOT."""
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from valueindex import config, loader


@pytest.fixture()
def snapshot_env(tmp_path, monkeypatch):
    """Isolated sample dir + cache dir with one source's csv."""
    sample_dir = tmp_path / "sample"
    sample_dir.mkdir()
    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=3, freq="MS"),
                       "value": [1.0, 2.0, 3.0]})
    df.to_csv(sample_dir / "fred_GDP.csv", index=False)
    monkeypatch.setattr(config, "SAMPLE_DATA_DIR", sample_dir)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "OFFLINE", False)
    return sample_dir


def write_meta(sample_dir, age: timedelta):
    ts = (datetime.now(timezone.utc) - age).isoformat()
    (sample_dir / "_meta.json").write_text(json.dumps({"fred_GDP": ts}))


class TestSnapshotFirstLoading:
    def test_fresh_snapshot_skips_network(self, snapshot_env, monkeypatch):
        write_meta(snapshot_env, age=timedelta(hours=12))

        def boom():  # any network attempt is a failure of the test
            raise AssertionError("network fetch attempted despite fresh snapshot")

        monkeypatch.setitem(loader.SOURCES, "fred_GDP", (boom, "fred"))
        df, status = loader.load_source("fred_GDP")
        assert status == loader.DataStatus.SNAPSHOT
        assert len(df) == 3

    def test_stale_meta_falls_back_to_sample_after_fetch_fails(self, snapshot_env, monkeypatch):
        write_meta(snapshot_env, age=timedelta(days=10))  # older than SNAPSHOT_TTL

        def fail():
            raise ConnectionError("blocked")

        monkeypatch.setitem(loader.SOURCES, "fred_GDP", (fail, "fred"))
        df, status = loader.load_source("fred_GDP")
        assert status == loader.DataStatus.SAMPLE  # not SNAPSHOT: meta too old
        assert len(df) == 3

    def test_missing_meta_is_plain_sample(self, snapshot_env, monkeypatch):
        def fail():
            raise ConnectionError("blocked")

        monkeypatch.setitem(loader.SOURCES, "fred_GDP", (fail, "fred"))
        df, status = loader.load_source("fred_GDP")
        assert status == loader.DataStatus.SAMPLE

    def test_force_refresh_bypasses_snapshot(self, snapshot_env, monkeypatch):
        write_meta(snapshot_env, age=timedelta(hours=1))
        live = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=5, freq="MS"),
                             "value": range(5)})
        monkeypatch.setitem(loader.SOURCES, "fred_GDP", ((lambda: live), "fred"))
        df, status = loader.load_source("fred_GDP", force=True)
        assert status == loader.DataStatus.LIVE
        assert len(df) == 5
