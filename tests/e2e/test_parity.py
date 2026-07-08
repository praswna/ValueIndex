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

    def test_drawdown(self, site):
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
