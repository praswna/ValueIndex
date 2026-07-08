"""JS↔Python parity: runs the JS ports in Chromium against Python-computed
fixtures. Run explicitly (needs playwright + chromium):

    pytest -m e2e
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = json.loads((ROOT / "tests" / "e2e" / "fixtures.json").read_text())
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def site():
    """Serve the repo root; yield (page, base_url) with harness loaded."""
    from playwright.sync_api import sync_playwright

    port = _free_port()
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=str(ROOT), **kw
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    with sync_playwright() as p:
        import os

        exe = CHROMIUM if Path(CHROMIUM).exists() else None
        browser = p.chromium.launch(executable_path=exe)
        page = browser.new_page()
        base = f"http://127.0.0.1:{port}"
        page.goto(f"{base}/tests/e2e/harness.html")
        page.wait_for_function("window.VI && window.VI.ready")
        page.evaluate(
            """async (base) => {
                const resp = await fetch(base + "/docs/data/panel.json");
                window.PANEL = await resp.json();
            }""",
            base,
        )
        yield page, base
        browser.close()
    server.shutdown()


class TestStatsParity:
    @pytest.mark.parametrize(
        "case", [c for c in FIXTURES["stats"] if c["fn"] == "summary"],
        ids=lambda c: f"{c['args']['key']}@{c['args']['asof']}",
    )
    def test_summary(self, site, case):
        page, _ = site
        got = page.evaluate(
            """(args) => {
                const s = window.VI.stats;
                const raw = window.PANEL.series[args.key];
                const {dates, values} = s.cleanPairs(window.PANEL.dates, raw);
                return s.summary(dates, values, args.asof);
            }""",
            case["args"],
        )
        exp = case["expected"]
        assert got["asof"] == exp["asof"]
        assert got["start"] == exp["start"]
        for field in ("current", "mean", "std", "pctile", "z"):
            assert got[field] == pytest.approx(exp[field], abs=1e-9), field
        if exp["delta_1y"] is None:
            assert got["delta_1y"] is None
        else:
            assert got["delta_1y"] == pytest.approx(exp["delta_1y"], abs=1e-9)

    def test_drawdown_stats(self, site):
        page, _ = site
        case = next(c for c in FIXTURES["stats"] if c["fn"] == "drawdown")
        got = page.evaluate(
            """() => {
                const s = window.VI.stats;
                const raw = window.PANEL.series.real_tri;
                const {dates, values} = s.cleanPairs(window.PANEL.dates, raw);
                const dd = s.drawdown(values);
                let min = Infinity, argmin = 0, nZero = 0;
                dd.forEach((x, i) => {
                    if (x < min) { min = x; argmin = i; }
                    if (x === 0) nZero++;
                });
                return {min, argmin_date: dates[argmin], last: dd[dd.length-1], n_zero: nZero};
            }"""
        )
        exp = case["expected"]
        assert got["min"] == pytest.approx(exp["min"], abs=1e-9)
        assert got["argmin_date"] == exp["argmin_date"]
        assert got["last"] == pytest.approx(exp["last"], abs=1e-9)
        assert got["n_zero"] == exp["n_zero"]


NEEDS_REGISTRY = """() => fetch("/docs/data/registry.json")
    .then(r => r.json()).then(reg => { window.REGISTRY = reg; return true; })"""


class TestQuantParity:
    @pytest.fixture(scope="class", autouse=True)
    def registry_loaded(self, site):
        page, _ = site
        page.evaluate(NEEDS_REGISTRY)

    @pytest.mark.parametrize(
        "case", [c for c in FIXTURES["quant"] if c["fn"] == "pca_composite"],
        ids=lambda c: f"pca@{c['args']['asof']}",
    )
    def test_pca(self, site, case):
        page, _ = site
        got = page.evaluate(
            """(args) => {
                const q = window.VI.quant;
                const az = q.alignedZFromPanel(window.PANEL, window.REGISTRY, args.asof);
                const res = q.pcaComposite(window.REGISTRY.valuation_keys.filter(
                    k => k in az.columns), az.columns);
                const valid = res.composite.filter(x => x !== null);
                return {
                    usable: res.usable,
                    weights: res.weights,
                    explained: res.explained,
                    composite_last: valid[valid.length - 1],
                    n_valid: valid.length,
                };
            }""",
            case["args"],
        )
        exp = case["expected"]
        assert got["usable"] == exp["usable"]
        assert got["n_valid"] == exp["n_valid"]
        assert got["explained"] == pytest.approx(exp["explained"], abs=1e-6)
        assert got["composite_last"] == pytest.approx(exp["composite_last"], abs=1e-6)
        for k, w in exp["weights"].items():
            assert got["weights"][k] == pytest.approx(w, abs=1e-6), k

    @pytest.mark.parametrize(
        "case", [c for c in FIXTURES["quant"] if c["fn"] == "nearest_analogs"],
        ids=lambda c: f"analogs@{c['args']['asof']}",
    )
    def test_analogs(self, site, case):
        page, _ = site
        got = page.evaluate(
            """(args) => {
                const q = window.VI.quant;
                const az = q.alignedZFromPanel(window.PANEL, window.REGISTRY, args.asof);
                return q.nearestAnalogs(
                    window.REGISTRY.valuation_keys, az.columns, az.dates);
            }""",
            case["args"],
        )
        exp = case["expected"]
        assert [a["date"] for a in got] == [a["date"] for a in exp]
        for g, e in zip(got, exp):
            assert g["distance"] == pytest.approx(e["distance"], abs=1e-6)


class TestBacktestParity:
    @pytest.fixture(scope="class", autouse=True)
    def spx_loaded(self, site):
        page, _ = site
        page.evaluate(
            """() => fetch("/docs/data/spx_daily.json")
                .then(r => r.json()).then(d => { window.SPX = d; return true; })"""
        )

    @pytest.mark.parametrize(
        "case", FIXTURES["backtest"],
        ids=lambda c: f"{c['args']['rule']}@{c['args']['cost_bps']}bp",
    )
    def test_rule(self, site, case):
        page, _ = site
        got = page.evaluate(
            """(args) => {
                const bt = window.VI.backtest;
                const close = window.SPX.close;
                const positions = bt.RULES[args.rule].fn(close, window.SPX.dates);
                const r = bt.evaluate(positions, close, args.cost_bps);
                return {
                    n_trades: r.n_trades, n_days_in_market: r.n_days_in_market,
                    win_rate: r.win_rate, mean_daily_ret: r.mean_daily_ret,
                    t_stat: r.t_stat, total_costs_pct: r.total_costs_pct,
                    equity_last: r.equityCurve[r.equityCurve.length - 1],
                    buyhold_last: r.buyHoldCurve[r.buyHoldCurve.length - 1],
                };
            }""",
            case["args"],
        )
        exp = case["expected"]
        assert got["n_trades"] == exp["n_trades"]
        assert got["n_days_in_market"] == exp["n_days_in_market"]
        for f in ("win_rate", "mean_daily_ret", "t_stat", "total_costs_pct",
                  "equity_last", "buyhold_last"):
            assert got[f] == pytest.approx(exp[f], rel=1e-8, abs=1e-10), f


class TestMcParity:
    def test_statistical_percentiles(self, site):
        """Different RNGs -> statistical agreement of the distribution."""
        page, _ = site
        case = FIXTURES["mc"][0]
        got = page.evaluate(
            """(args) => {
                const s = window.VI.stats;
                const mc = window.VI.mc;
                const {values} = s.cleanPairs(window.PANEL.dates, window.PANEL.series.real_tri);
                const rets = s.pctChange(values).slice(1);
                const res = mc.simulateDca(rets, args.contrib, args.years,
                                           {nSims: args.n_sims});
                const sorted = res.finalWealth.slice().sort((a, b) => a - b);
                return {
                    total_contributed: res.totalContributed,
                    final_p5: mc.percentileLinear(sorted, 5),
                    final_p50: mc.percentileLinear(sorted, 50),
                    final_p95: mc.percentileLinear(sorted, 95),
                };
            }""",
            case["args"],
        )
        exp = case["expected"]
        assert got["total_contributed"] == exp["total_contributed"]
        assert got["final_p50"] == pytest.approx(exp["final_p50"], rel=0.06)
        assert got["final_p5"] == pytest.approx(exp["final_p5"], rel=0.12)
        assert got["final_p95"] == pytest.approx(exp["final_p95"], rel=0.12)

    def test_bogle_formula_exact(self, site):
        page, _ = site
        got = page.evaluate(
            "() => window.VI.mc.bogleExpectedReturn(2.0, 3.0, 40.0, 20.0)")
        from valueindex.indicators import bogle_expected_return
        assert got == pytest.approx(bogle_expected_return(2.0, 3.0, 40.0, 20.0),
                                    abs=1e-12)
