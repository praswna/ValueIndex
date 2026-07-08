"""End-to-end offline pipeline: sample data -> panel -> summaries."""
import pandas as pd
import pytest

from valueindex import config, indicators, loader, registry, stats


@pytest.fixture(scope="module")
def panel(monkeypatch_module):
    monkeypatch_module.setattr(config, "OFFLINE", True)
    # Point the cache away from any real cache dir.
    data = {name: loader._load_sample(name) for name in loader.SOURCES}
    assert all(df is not None for df in data.values()), "missing sample csvs"
    return indicators.build_panel(data)


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


class TestOfflinePipeline:
    def test_all_indicators_present(self, panel):
        assert set(registry.VALUATION_KEYS) <= set(panel.columns)
        assert panel.index.is_monotonic_increasing

    def test_no_all_nan_columns(self, panel):
        assert not panel.isna().all().any()

    def test_sample_values_plausible(self, panel):
        # Each indicator's own latest value (sources may lag differently).
        current = {k: panel[k].dropna().iloc[-1] for k in panel.columns}
        assert 25 < current["cape"] < 55
        assert 1.2 < current["buffett"] < 3.0
        assert 15 < current["pe"] < 45
        assert 0.2 < current["aiae"] < 0.6

    def test_summaries_work_for_all_valuation_keys(self, panel):
        panel_end = panel.dropna(how="all").index[-1]
        for key in registry.VALUATION_KEYS:
            s = stats.summary(panel[key])
            assert 0 <= s.pctile <= 100
            # Real sources lag by varying amounts; anything within ~3 years
            # of the panel end is a live series, not a broken one.
            assert s.asof >= panel_end - pd.DateOffset(months=36)

    def test_time_machine_no_lookahead(self, panel):
        """Percentile at a past date must use only data up to that date."""
        asof = pd.Timestamp("2000-03-01")
        s_full = panel["cape"].dropna()
        s_past = s_full.loc[:asof]
        p_past = stats.summary(s_past).pctile
        # dot-com peak: should be at/near its own historical max at the time
        assert p_past > 97

    def test_cape_splice_extends_past_shiller_file(self):
        """When multpl's Shiller-PE runs past the Shiller file's end, the
        panel CAPE is extended (file values win where both exist)."""
        data = {name: loader._load_sample(name) for name in loader.SOURCES}
        sh = data["shiller"]
        last = sh["date"].max()
        ext_dates = pd.date_range(last + pd.DateOffset(months=1), periods=6, freq="MS")
        extension = pd.DataFrame({"date": ext_dates, "value": [39.9] * 6})
        data["multpl_shiller_pe"] = pd.concat(
            [data["multpl_shiller_pe"], extension], ignore_index=True
        )
        panel = indicators.build_panel(data)
        cape = panel["cape"].dropna()
        assert cape.index[-1] >= ext_dates[-1]
        assert cape.iloc[-1] == pytest.approx(39.9)
        # File value preserved where both sources overlap.
        assert cape.loc[last] != 39.9

    def test_recessions_flagged(self):
        usrec = loader._load_sample("fred_USREC")
        s = usrec.set_index("date")["value"]
        assert s.loc["2008-06-01"] == 1
        assert s.loc["2019-06-01"] == 0
