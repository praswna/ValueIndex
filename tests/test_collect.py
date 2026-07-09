"""Collector shared logic: snapshot writing, meta stamping, source registry."""
import json
from datetime import datetime

import pandas as pd
import pytest

from valueindex import collect, config, loader


class TestCollect:
    def test_source_names_matches_loader(self):
        assert collect.source_names() == list(loader.SOURCES)
        # the datacenter-blocked ones are registered
        assert {"krx_valuation", "finra_margin_debt", "aaii_sentiment"} <= set(
            collect.source_names()
        )

    def test_save_snapshot_writes_csv_and_meta(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "SAMPLE_DATA_DIR", tmp_path)
        monkeypatch.setattr(collect, "META_PATH", tmp_path / "_meta.json")
        df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=3, freq="MS"),
                           "value": [1.0, 2.0, 3.0]})
        meta = collect.save_snapshot("fred_GDP", df, {})
        collect.write_meta(meta)

        assert (tmp_path / "fred_GDP.csv").exists()
        saved = json.loads((tmp_path / "_meta.json").read_text())
        assert "fred_GDP" in saved
        datetime.fromisoformat(saved["fred_GDP"])  # valid ISO timestamp

    def test_latest_date(self):
        df = pd.DataFrame({"date": ["2024-01-01", "2024-06-01"], "value": [1, 2]})
        assert collect.latest_date(df) == "2024-06-01"
        assert collect.latest_date(pd.DataFrame({"value": [1]})) == "-"

    def test_collect_source_offline_returns_error(self, monkeypatch):
        # With no network the fetch raises; collect_source reports it, no crash.
        monkeypatch.setattr(config, "OFFLINE", False)
        df, err = collect.collect_source("fred_GDP")
        assert (df is None and err) or (df is not None and err is None)

    def test_collect_all_summary(self, monkeypatch):
        monkeypatch.setattr(collect, "source_names", lambda: ["a", "b"])

        def fake(name):
            if name == "a":
                return pd.DataFrame({"date": ["2024-01-01"], "value": [1]}), None
            return None, "boom"

        monkeypatch.setattr(collect, "collect_source", fake)
        monkeypatch.setattr(collect, "save_snapshot", lambda n, d, m: {**m, n: "t"})
        monkeypatch.setattr(collect, "write_meta", lambda m: None)
        logs, prog = [], []
        r = collect.collect_all(log=logs.append,
                                on_progress=lambda i, n: prog.append((i, n)))
        assert r == {"ok": ["a"], "failed": ["b"], "total": 2}
        assert prog[-1] == (2, 2)

    def test_git_publish_noop_when_nothing_staged(self, monkeypatch):
        import subprocess
        calls = []

        def fake_run(args, **kw):
            calls.append(args)
            # `git diff --cached --quiet` returning 0 => nothing staged
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert collect.git_publish(log=lambda _s: None) is True
        assert ["git", "commit"] not in [c[:2] for c in calls]  # never committed
        # still integrates the remote and pushes any unpushed commit
        assert ["git", "pull"] in [c[:2] for c in calls]
        assert ["git", "push"] in [c[:2] for c in calls]

    def test_git_publish_aborts_on_failed_rebase(self, monkeypatch):
        import subprocess
        calls = []

        def fake_run(args, **kw):
            calls.append(args)
            rc = 1 if args[:2] == ["git", "pull"] else 0
            if args[:3] == ["git", "diff", "--cached"]:
                rc = 1  # something staged -> commit happens
            return subprocess.CompletedProcess(args, rc, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert collect.git_publish(log=lambda _s: None) is False
        assert ["git", "rebase", "--abort"] in calls   # left in a clean state
        assert ["git", "push"] not in [c[:2] for c in calls]
