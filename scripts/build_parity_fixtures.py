"""Generate tests/e2e/fixtures.json: expected values for the JS ports.

Expectations are computed by the *Python* implementations applied to the
rounded docs/data JSON (the exact numbers the browser sees), so
deterministic ports can be asserted near-exactly. Grows with each ported
module.

Run: python scripts/build_parity_fixtures.py   (after build_site_data.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valueindex import backtest, quant, registry, stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "tests" / "e2e" / "fixtures.json"

ASOF_DATES = [None, "2000-03-01", "1950-06-01"]


def series_from_panel(panel: dict, key: str) -> pd.Series:
    s = pd.Series(
        panel["series"][key],
        index=pd.to_datetime(panel["dates"]),
        dtype=float,
    ).dropna()
    return s


def num(v):
    if v is None:
        return None
    f = float(v)
    return None if f != f else f


def stats_cases(panel: dict) -> list[dict]:
    cases = []
    for key in ("cape", "buffett", "div_yield", "pb", "aiae"):
        for asof in ASOF_DATES:
            s = series_from_panel(panel, key)
            if asof is not None:
                s = s.loc[:asof]
            if s.empty:
                continue
            summ = stats.summary(s)
            cases.append(
                {
                    "fn": "summary",
                    "args": {"key": key, "asof": asof},
                    "expected": {
                        "current": num(summ.current),
                        "asof": summ.asof.strftime("%Y-%m-%d"),
                        "mean": num(summ.mean),
                        "std": num(summ.std),
                        "pctile": num(summ.pctile),
                        "z": num(summ.z),
                        "delta_1y": num(summ.delta_1y),
                        "start": summ.start.strftime("%Y-%m-%d"),
                    },
                }
            )
    return cases


def drawdown_case(panel: dict) -> dict:
    s = series_from_panel(panel, "real_tri")
    dd = (s / s.cummax() - 1) * 100
    return {
        "fn": "drawdown",
        "args": {"key": "real_tri"},
        "expected": {
            "min": float(dd.min()),
            "argmin_date": dd.idxmin().strftime("%Y-%m-%d"),
            "last": float(dd.iloc[-1]),
            "n_zero": int((dd == 0).sum()),
        },
    }


def aligned_z_from_panel(panel: dict, asof: str | None) -> pd.DataFrame:
    """Mirror quant.js alignedZFromPanel: grid-truncated, per-column z."""
    dates = pd.to_datetime(panel["dates"])
    cols = {}
    for key in registry.VALUATION_KEYS:
        sign = 1 if registry.INDICATORS[key].higher_is_expensive else -1
        s = pd.Series(panel["series"][key], index=dates, dtype=float)
        if asof is not None:
            s = s.loc[:asof]
        cols[key] = stats.zscore(s.dropna()) * sign
    return pd.DataFrame(cols)


PCA_ASOF_DATES = [None, "2009-03-01", "2000-03-01", "1950-06-01", "1929-09-01"]


def quant_cases(panel: dict) -> list[dict]:
    cases = []
    for asof in PCA_ASOF_DATES:
        az = aligned_z_from_panel(panel, asof)
        pca = quant.pca_composite(az)
        analogs = quant.nearest_analogs(az)
        cases.append(
            {
                "fn": "pca_composite",
                "args": {"asof": asof},
                "expected": {
                    "usable": list(pca.weights.index),
                    "weights": {k: float(w) for k, w in pca.weights.items()},
                    "explained": float(pca.explained_ratio),
                    "composite_last": float(pca.composite.iloc[-1]),
                    "n_valid": int(pca.composite.notna().sum()),
                },
            }
        )
        cases.append(
            {
                "fn": "nearest_analogs",
                "args": {"asof": asof},
                "expected": [
                    {"date": a.date.strftime("%Y-%m-%d"), "distance": float(a.distance)}
                    for a in analogs
                ],
            }
        )
    return cases


def backtest_cases(spx: dict) -> list[dict]:
    ohlc = pd.DataFrame(
        {"close": spx["close"]}, index=pd.to_datetime(spx["dates"])
    ).astype(float)
    cases = []
    for rule_key, (label, fn) in backtest.RULES.items():
        positions = fn(ohlc)
        for cost in (0, 10):
            res = backtest.evaluate(positions, ohlc["close"], cost_bps=cost)
            cases.append(
                {
                    "fn": "backtest",
                    "args": {"rule": rule_key, "cost_bps": cost},
                    "expected": {
                        "n_trades": res.n_trades,
                        "n_days_in_market": res.n_days_in_market,
                        "win_rate": float(res.win_rate),
                        "mean_daily_ret": float(res.mean_daily_ret),
                        "t_stat": float(res.t_stat),
                        "total_costs_pct": float(res.total_costs_pct),
                        "equity_last": float(res.equity_curve.iloc[-1]),
                        "buyhold_last": float(res.buy_hold_curve.iloc[-1]),
                    },
                }
            )
    return cases


def mc_cases(panel: dict) -> list[dict]:
    tri = series_from_panel(panel, "real_tri")
    rets = tri.pct_change().dropna()
    res = quant.simulate_dca(rets, 100.0, 20, n_sims=4000)
    import numpy as np

    return [
        {
            "fn": "simulate_dca",
            "args": {"contrib": 100.0, "years": 20, "n_sims": 4000},
            "expected": {
                "total_contributed": float(res.total_contributed),
                "final_p5": float(np.percentile(res.final_wealth, 5)),
                "final_p50": float(np.percentile(res.final_wealth, 50)),
                "final_p95": float(np.percentile(res.final_wealth, 95)),
            },
        }
    ]


def main() -> None:
    panel = json.loads((DATA / "panel.json").read_text(encoding="utf-8"))
    spx = json.loads((DATA / "spx_daily.json").read_text(encoding="utf-8"))
    fixtures = {
        "stats": stats_cases(panel) + [drawdown_case(panel)],
        "quant": quant_cases(panel),
        "backtest": backtest_cases(spx),
        "mc": mc_cases(panel),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixtures, indent=1), encoding="utf-8")
    n = sum(len(v) for v in fixtures.values())
    print(f"wrote {n} parity cases to {OUT}")


if __name__ == "__main__":
    main()
