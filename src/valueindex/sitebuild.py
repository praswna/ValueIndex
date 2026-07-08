"""Python→JSON bridge for the static site (docs/).

Everything the browser needs is produced here from the existing data and
math modules, so all Korean text, colors, and statistics stay
single-sourced in Python. `scripts/build_site_data.py` is the CLI wrapper;
the GitHub Actions workflow runs it daily after the data refresh.

No streamlit imports — this module is shared by the build script and
`webui.py`.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config, indicators, loader, quant, registry, stats

SCHEMA_VERSION = 1

# Decimal places per display unit (mirrors the Streamlit pages' FMT).
UNIT_DECIMALS = {
    "배": 1, "%": 2, "%p": 2, "비율": 2, "pt": 1, "$B": 1, "$/oz": 0, "$/bbl": 1,
}

# Chart chrome shared with charts.js (kept in sync with webui constants).
CHROME = {
    "grid": "#e1e0d9",
    "muted": "#898781",
    "recession_fill": "rgba(137, 135, 129, 0.15)",
}

SERIES_COLORS = {
    "cape": "#2a78d6", "ecy": "#1baf7a", "buffett": "#eda100", "pe": "#008300",
    "pb": "#4a3aa7", "div_yield": "#e34948", "fed_spread": "#e87ba4",
    "trend_dev": "#eb6834", "aiae": "#0d9488",
    "vix": "#2a78d6", "t10y2y": "#4a3aa7", "hy_spread": "#e34948",
    "gold": "#eda100", "wti": "#008300",
    "fear_greed": "#2a78d6", "aaii_spread": "#4a3aa7", "margin_debt": "#e34948",
    "umcsent": "#008300",
    "fedfunds": "#2a78d6", "cpi_yoy": "#e34948", "unrate": "#eb6834",
    "m2_yoy": "#008300", "t10yie": "#4a3aa7",
}

DISCLAIMER = (
    "이 앱은 교육용 정보 도구이며 투자 자문이 아닙니다. "
    "모든 투자 판단과 책임은 본인에게 있습니다."
)


# ------------------------------------------------------------- shared build --

def yoy(level: pd.Series) -> pd.Series:
    """Year-over-year percent change of a monthly level series."""
    return (level / level.shift(12) - 1) * 100


def build_extras(frames: dict[str, pd.DataFrame]) -> dict:
    """Context series, real total-return index, recessions, daily closes.

    Shared by the Streamlit app (webui._load) and the static-site builder.
    """
    sh = frames["shiller"].set_index("date").sort_index()
    tri = indicators.real_total_return_index(
        sh["real_price"], sh["dividend"] / sh["cpi"] * sh["cpi"].iloc[-1]
    )
    return {
        "usrec": frames["fred_USREC"].set_index("date")["value"],
        "real_tri": tri,
        "spx_daily": frames["stooq_spx_daily"],
        "context": {
            "vix": indicators.to_monthly(frames["fred_VIXCLS"], how="mean"),
            "t10y2y": indicators.to_monthly(frames["fred_T10Y2Y"], how="mean"),
            "hy_spread": indicators.to_monthly(frames["fred_BAMLH0A0HYM2"], how="mean"),
            "gold": frames["stooq_gold"].set_index("date")["close"].resample("MS").mean(),
            "wti": indicators.to_monthly(frames["fred_DCOILWTICO"], how="mean"),
            "fear_greed": indicators.to_monthly(frames["cnn_fear_greed"], how="mean"),
            "aaii_spread": indicators.to_monthly(frames["aaii_sentiment"], how="mean"),
            "margin_debt": indicators.to_monthly(frames["finra_margin_debt"]),
            "umcsent": indicators.to_monthly(frames["fred_UMCSENT"]),
            "fedfunds": indicators.to_monthly(frames["fred_FEDFUNDS"]),
            "cpi_yoy": yoy(indicators.to_monthly(frames["fred_CPIAUCSL"])),
            "unrate": indicators.to_monthly(frames["fred_UNRATE"]),
            "m2_yoy": yoy(indicators.to_monthly(frames["fred_M2SL"])),
            "t10yie": indicators.to_monthly(frames["fred_T10YIE"], how="mean"),
        },
    }


# -------------------------------------------------------------- json helpers --

def _num(v):
    """Round to 6 significant digits; NaN/inf -> None (JSON null)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    if f == 0:
        return 0
    return float(f"{f:.6g}")


def _nums(values) -> list:
    return [_num(v) for v in values]


def _dates(idx) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in idx]


def _write(out_dir: Path, name: str, payload) -> None:
    path = out_dir / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )


def aligned_z_panel(panel: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            k: (stats.zscore(panel[k].dropna())
                * (1 if registry.INDICATORS[k].higher_is_expensive else -1))
            for k in registry.VALUATION_KEYS
        }
    )


# ------------------------------------------------------------ file builders --

def registry_payload() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "indicators": {k: asdict(m) for k, m in registry.INDICATORS.items()},
        "valuation_keys": registry.VALUATION_KEYS,
        "context_keys": registry.CONTEXT_KEYS,
        "ratings": [
            {"max_z": (None if upper == float("inf") else upper),
             "key": r.key, "label_ko": r.label_ko, "color": r.color}
            for upper, r in stats.RATINGS
        ],
        "series_colors": SERIES_COLORS,
        "chrome": CHROME,
        "unit_decimals": UNIT_DECIMALS,
        "time_machine_presets": registry.TIME_MACHINE_PRESETS,
        "guide_lines": {k: list(v) for k, v in registry.GUIDE_LINES.items()},
        "disclaimer": DISCLAIMER,
    }


def panel_payload(panel: pd.DataFrame, tri: pd.Series) -> dict:
    tri_on_grid = tri.reindex(panel.index)
    return {
        "dates": _dates(panel.index),
        "series": {
            **{k: _nums(panel[k].values) for k in registry.VALUATION_KEYS},
            "real_tri": _nums(tri_on_grid.values),
        },
    }


def context_payload(context: dict[str, pd.Series]) -> dict:
    out = {}
    for key, s in context.items():
        s = s.dropna()
        out[key] = {"dates": _dates(s.index), "values": _nums(s.values)}
    return out


def _recession_ranges(usrec: pd.Series) -> list[list[str]]:
    s = usrec.sort_index()
    flag = s > 0
    edges = flag.astype(int).diff().fillna(0)
    starts = list(s.index[edges == 1])
    ends = list(s.index[edges == -1])
    if len(flag) and flag.iloc[0]:
        starts.insert(0, s.index[0])
    if len(ends) < len(starts):
        ends.append(s.index[-1])
    return [[a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")] for a, b in zip(starts, ends)]


def overview_payload(panel: pd.DataFrame, tri: pd.Series, usrec: pd.Series) -> dict:
    summaries = {}
    for key in registry.VALUATION_KEYS:
        s = panel[key].dropna()
        summ = stats.summary(s)
        meta = registry.INDICATORS[key]
        z = summ.z if meta.higher_is_expensive else -summ.z
        pct = summ.pctile if meta.higher_is_expensive else 100 - summ.pctile
        half_life = quant.ar1_half_life_months(s)
        summaries[key] = {
            "current": _num(summ.current), "asof": summ.asof.strftime("%Y-%m-%d"),
            "mean": _num(summ.mean), "std": _num(summ.std),
            "pctile": _num(summ.pctile), "z": _num(summ.z),
            "aligned_z": _num(z), "aligned_pctile": _num(pct),
            "rating": stats.rating(z).key,
            "delta_1y": _num(summ.delta_1y),
            "hist_min": _num(summ.hist_min), "hist_max": _num(summ.hist_max),
            "start_year": int(summ.start.year),
            "half_life_months": _num(half_life),
        }

    az = aligned_z_panel(panel)
    pca = quant.pca_composite(az)
    pca_now = float(pca.composite.iloc[-1])

    analogs = []
    for a in quant.nearest_analogs(az):
        cape_then = panel["cape"].asof(a.date)
        fwd = {}
        base = tri.asof(a.date)
        for label, months in (("1y", 12), ("5y", 60), ("10y", 120)):
            fut_idx = a.date + pd.DateOffset(months=months)
            fut = tri.asof(fut_idx) if fut_idx <= tri.index[-1] else None
            fwd[label] = (
                _num(((fut / base) ** (12 / months) - 1) * 100)
                if fut is not None and pd.notna(base) and base > 0 else None
            )
        seg = tri.loc[a.date: a.date + pd.DateOffset(months=120)].dropna()
        months_axis = [
            (d.year - a.date.year) * 12 + (d.month - a.date.month) for d in seg.index
        ]
        analogs.append({
            "date": a.date.strftime("%Y-%m-%d"),
            "distance": _num(a.distance),
            "cape_then": _num(cape_then),
            "fwd": fwd,
            "path_months": months_axis,
            "path_values": _nums((seg / seg.iloc[0] * 100).values) if len(seg) else [],
        })

    aligned_pct = pd.DataFrame(
        {
            k: (p if registry.INDICATORS[k].higher_is_expensive else 100 - p)
            for k in registry.VALUATION_KEYS
            for p in [stats.percentile_rank(panel[k].dropna())]
        }
    )
    corr = aligned_pct.corr()

    return {
        "latest_month": panel.dropna(how="all").index[-1].strftime("%Y-%m-%d"),
        "summaries": summaries,
        "pca": {
            "dates": _dates(pca.composite.index),
            "values": _nums(pca.composite.values),
            "weights": {k: _num(w) for k, w in pca.weights.items()},
            "explained_ratio": _num(pca.explained_ratio),
            "current": _num(pca_now),
            "rating": stats.rating(pca_now).key,
        },
        "analogs": analogs,
        "corr": {"keys": list(corr.columns), "matrix": [_nums(row) for row in corr.values]},
        "recessions": _recession_ranges(usrec),
    }


def guide_payload(panel: pd.DataFrame, tri: pd.Series) -> dict:
    fwd = indicators.forward_10y_return(tri)
    df = pd.DataFrame({"cape": panel["cape"], "fwd": fwd}).dropna()
    fan = quant.conditional_quantiles(df["cape"], df["fwd"])
    return {
        "scatter": {"cape": _nums(df["cape"].values), "fwd": _nums(df["fwd"].values)},
        "fan": {
            "x": _nums(fan.index.values),
            **{c: _nums(fan[c].values) for c in fan.columns},
        },
        "current_cape": _num(panel["cape"].dropna().iloc[-1]),
    }


def spx_payload(spx_daily: pd.DataFrame) -> dict:
    df = spx_daily.sort_values("date")
    return {"dates": _dates(df["date"]), "close": _nums(df["close"].values)}


def content_payload() -> dict:
    import markdown

    out = {}
    for name in ("investing_guide_ko", "discipline_ko", "resources_ko"):
        text = (config.CONTENT_DIR / f"{name}.md").read_text(encoding="utf-8")
        out[name] = markdown.markdown(text, extensions=["tables"])
    return out


def meta_payload(statuses: dict[str, str], panel: pd.DataFrame) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_month": panel.dropna(how="all").index[-1].strftime("%Y-%m-%d"),
        "sources": statuses,
    }


# --------------------------------------------------------------- orchestrator --

def build_site(out_dir: Path, force: bool = False) -> dict[str, str]:
    """Build every docs/data file. Returns per-source statuses."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = loader.load_all(force=force)
    frames = {k: v[0] for k, v in data.items()}
    statuses = {k: v[1].value for k, v in data.items()}

    panel = indicators.build_panel(frames)
    extras = build_extras(frames)
    tri, usrec = extras["real_tri"], extras["usrec"]

    _write(out_dir, "meta.json", meta_payload(statuses, panel))
    _write(out_dir, "registry.json", registry_payload())
    _write(out_dir, "panel.json", panel_payload(panel, tri))
    _write(out_dir, "context.json", context_payload(extras["context"]))
    _write(out_dir, "overview.json", overview_payload(panel, tri, usrec))
    _write(out_dir, "guide.json", guide_payload(panel, tri))
    _write(out_dir, "spx_daily.json", spx_payload(extras["spx_daily"]))
    _write(out_dir, "content.json", content_payload())
    panel.to_csv(out_dir / "valueindex_panel.csv")
    return statuses
