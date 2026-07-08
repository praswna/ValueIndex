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
from valueindex import stats  # noqa: E402

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


def main() -> None:
    panel = json.loads((DATA / "panel.json").read_text(encoding="utf-8"))
    fixtures = {
        "stats": stats_cases(panel) + [drawdown_case(panel)],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixtures, indent=1), encoding="utf-8")
    n = sum(len(v) for v in fixtures.values())
    print(f"wrote {n} parity cases to {OUT}")


if __name__ == "__main__":
    main()
