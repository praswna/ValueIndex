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
