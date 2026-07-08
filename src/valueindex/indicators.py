"""Derived indicators and monthly alignment into a wide panel."""
from __future__ import annotations

import numpy as np
import pandas as pd

QUARTER_FFILL_LIMIT = 3  # never fabricate more than one quarter forward


def to_monthly(df: pd.DataFrame, how: str = "last") -> pd.Series:
    """(date, value) frame -> month-start series; daily data is averaged."""
    s = df.set_index("date")["value"].sort_index()
    if how == "mean":
        return s.resample("MS").mean()
    return s.resample("MS").last()


def quarterly_to_monthly(s: pd.Series) -> pd.Series:
    """Upsample quarterly points to a monthly grid, gaps left as NaN.

    Filling happens once, at panel level, with QUARTER_FFILL_LIMIT.
    """
    return s.dropna().resample("MS").last()


def buffett_ratio(equities: pd.Series, gdp: pd.Series) -> pd.Series:
    """Corporate equities (millions USD) over GDP (billions USD), as a ratio.

    The unit trap: NCBEILQ027S is millions, GDP is billions -> divide the
    numerator by 1000.
    """
    return (equities / 1000.0) / gdp


def fed_spread(pe: pd.Series, y10: pd.Series) -> pd.Series:
    """Earnings yield (100/PE) minus 10Y Treasury yield, in pct points."""
    return 100.0 / pe - y10


def splice_yields(gs10: pd.Series, dgs10_monthly: pd.Series) -> pd.Series:
    """Shiller GS10 before DGS10 exists (1962), DGS10 after."""
    if dgs10_monthly.dropna().empty:
        return gs10
    start = dgs10_monthly.dropna().index[0]
    return pd.concat([gs10.loc[: start - pd.DateOffset(months=1)], dgs10_monthly.dropna()])


def excess_cape_yield(cape: pd.Series, gs10: pd.Series, cpi: pd.Series) -> pd.Series:
    """Fallback ECY: 1/CAPE - (GS10 - trailing 10y CPI inflation), pct points."""
    infl_10y = (cpi / cpi.shift(120)) ** (1 / 10) - 1
    real_y10 = gs10 - infl_10y * 100
    return 100.0 / cape - real_y10


def trend_deviation(real_price: pd.Series) -> pd.Series:
    """Percent deviation of real price from its full-sample log-linear trend."""
    s = real_price.dropna()
    x = np.arange(len(s), dtype=float)
    slope, intercept = np.polyfit(x, np.log(s.values), 1)
    trend = np.exp(intercept + slope * x)
    return pd.Series((s.values / trend - 1) * 100, index=s.index)


def aiae(inputs: pd.DataFrame) -> pd.Series:
    """Aggregate Investor Allocation to Equities (Philosophical Economics).

    equities / (equities + liabilities of real-economy borrowers). All Z.1
    series are in the same unit (millions USD), so the ratio is unit-
    invariant — no scaling needed. Result is a fraction in [0, 1].
    """
    df = inputs.set_index("date").sort_index()
    equities = df["equities_nonfin"] + df["equities_fin"]
    debt = (
        df["debt_business"]
        + df["debt_household"]
        + df["debt_federal"]
        + df["debt_state_local"]
        + df["debt_world"]
    )
    out = equities / (equities + debt)
    return out.dropna()


def drawdown(total_return_index: pd.Series) -> pd.Series:
    """Drawdown from running peak, in percent (0 at peaks, negative below)."""
    s = total_return_index.dropna()
    return (s / s.cummax() - 1) * 100


def real_total_return_index(real_price: pd.Series, real_dividend: pd.Series) -> pd.Series:
    """Monthly real total-return index from Shiller real price + dividends."""
    monthly_ret = real_price.pct_change() + (real_dividend / 12) / real_price.shift(1)
    return (1 + monthly_ret.fillna(0)).cumprod() * 100


def forward_10y_return(total_return_index: pd.Series) -> pd.Series:
    """Annualized real total return over the NEXT 10 years, in percent."""
    fwd = (total_return_index.shift(-120) / total_return_index) ** (1 / 10) - 1
    return fwd * 100


def bogle_expected_return(
    div_yield_pct: float, growth_pct: float, cape_now: float, cape_future: float
) -> float:
    """Bogle decomposition: dividend yield + growth + annualized CAPE change."""
    valuation_change = ((cape_future / cape_now) ** (1 / 10) - 1) * 100
    return div_yield_pct + growth_pct + valuation_change


def build_panel(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Wide monthly panel with one column per indicator key.

    ``sources`` maps source names (loader keys) to tidy frames. Indicators
    have different start dates; NaNs are preserved, never dropped across
    the panel.
    """
    sh = sources["shiller"].set_index("date").sort_index()

    cape = sh["cape"]
    # Shiller's downloadable file can lag by months; fill the gap with
    # multpl's current Shiller-PE values (file values win where present).
    if "multpl_shiller_pe" in sources:
        cape = cape.combine_first(to_monthly(sources["multpl_shiller_pe"]))
    ecy = sh["ecy"]
    if ecy.dropna().empty:
        ecy = excess_cape_yield(sh["cape"], sh["gs10"], sh["cpi"])

    gdp = quarterly_to_monthly(to_monthly(sources["fred_GDP"]))
    equities = quarterly_to_monthly(to_monthly(sources["fred_NCBEILQ027S"]))
    buffett = buffett_ratio(equities, gdp)

    pe = to_monthly(sources["multpl_pe"])
    pb = quarterly_to_monthly(to_monthly(sources["multpl_pb"]))
    div_yield = to_monthly(sources["multpl_div_yield"])

    dgs10 = to_monthly(sources["fred_DGS10"], how="mean")
    y10 = splice_yields(sh["gs10"], dgs10)
    fed = fed_spread(pe, y10)

    trend_dev = trend_deviation(sh["real_price"])
    aiae_series = quarterly_to_monthly(aiae(sources["aiae_inputs"]).resample("MS").last())

    panel = pd.DataFrame(
        {
            "cape": cape,
            "ecy": ecy,
            "buffett": buffett,
            "pe": pe,
            "pb": pb,
            "div_yield": div_yield,
            "fed_spread": fed,
            "trend_dev": trend_dev,
            "aiae": aiae_series,
        }
    )
    panel.index.name = "date"
    panel = panel.sort_index()
    # Quarterly series: carry the last release forward at most one quarter.
    for col in ("buffett", "pb", "aiae"):
        panel[col] = panel[col].ffill(limit=QUARTER_FFILL_LIMIT)
    return panel
