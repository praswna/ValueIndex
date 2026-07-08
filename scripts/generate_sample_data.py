"""Generate bundled sample data for offline use.

Series are interpolated between real published anchor values (e.g. CAPE 44
at the 2000 dot-com peak, 13 at the 2009 bottom), so shapes and levels are
historically plausible. They are clearly labeled as SAMPLE in the UI and
are NOT exact historical records. `scripts/refresh_sample_data.py` replaces
them with live data on a machine with network access.

Run: python scripts/generate_sample_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valueindex import config  # noqa: E402

OUT = config.SAMPLE_DATA_DIR
RNG = np.random.default_rng(42)


def decimal_year(idx: pd.DatetimeIndex) -> np.ndarray:
    return idx.year + (idx.month - 0.5) / 12 + (idx.day - 1) / 365.25


def interp(idx: pd.DatetimeIndex, anchors: dict[float, float], log: bool = False,
           noise: float = 0.0) -> pd.Series:
    """Piecewise-linear interpolation between (decimal year -> value) anchors."""
    x = decimal_year(idx)
    xs = np.array(sorted(anchors))
    ys = np.array([anchors[k] for k in sorted(anchors)])
    if log:
        vals = np.exp(np.interp(x, xs, np.log(ys)))
    else:
        vals = np.interp(x, xs, ys)
    if noise:
        # smooth AR(1) wiggle so lines don't look ruler-straight
        eps = RNG.normal(0, noise, len(x))
        wiggle = np.zeros(len(x))
        for i in range(1, len(x)):
            wiggle[i] = 0.95 * wiggle[i - 1] + eps[i]
        vals = vals * (1 + wiggle)
    return pd.Series(vals, index=idx)


MONTHLY = pd.date_range("1881-01-01", "2026-06-01", freq="MS")

# ---------------------------------------------------------------- shiller ----
CAPE_ANCHORS = {
    1881.5: 18.5, 1901.5: 25.2, 1921.7: 5.2, 1929.7: 32.6, 1932.5: 5.6,
    1937.2: 22.2, 1942.4: 8.5, 1949.5: 9.1, 1966.0: 24.1, 1974.9: 8.3,
    1982.6: 6.6, 1987.7: 18.3, 1990.5: 15.9, 1995.0: 20.2, 2000.2: 44.2,
    2003.2: 21.3, 2007.5: 27.5, 2009.2: 13.3, 2013.0: 21.9, 2015.0: 26.5,
    2018.1: 33.3, 2020.3: 24.8, 2021.9: 38.6, 2022.8: 27.1, 2024.0: 33.4,
    2025.0: 37.9, 2026.5: 40.4,
}
GS10_ANCHORS = {
    1881.5: 4.0, 1900.0: 3.3, 1920.5: 5.3, 1932.0: 3.7, 1941.0: 2.0,
    1950.0: 2.3, 1960.0: 4.1, 1970.0: 7.4, 1981.7: 15.3, 1990.0: 8.6,
    2000.0: 6.0, 2007.5: 5.0, 2012.5: 1.6, 2016.5: 1.5, 2020.5: 0.6,
    2023.8: 4.9, 2026.5: 4.3,
}
CPI_ANCHORS = {
    1881.5: 10.1, 1920.5: 20.0, 1933.0: 12.8, 1945.0: 18.0, 1960.0: 29.6,
    1970.0: 38.8, 1980.0: 82.4, 1990.0: 130.7, 2000.0: 172.2, 2010.0: 218.1,
    2020.0: 258.8, 2023.0: 304.7, 2026.5: 330.0,
}
# real earnings trend with recession dips (drives realistic PE spikes)
REAL_EARN_ANCHORS = {
    1881.5: 12.0, 1916.0: 22.0, 1921.5: 8.0, 1929.5: 28.0, 1932.5: 9.0,
    1937.0: 22.0, 1945.0: 20.0, 1960.0: 35.0, 1974.0: 50.0, 1982.5: 40.0,
    1990.0: 55.0, 1991.5: 40.0, 2000.5: 78.0, 2002.0: 45.0, 2007.5: 105.0,
    2009.2: 35.0, 2011.0: 95.0, 2019.5: 150.0, 2020.5: 110.0, 2021.9: 190.0,
    2026.5: 230.0,
}


def gen_shiller() -> pd.DataFrame:
    cape = interp(MONTHLY, CAPE_ANCHORS, log=True, noise=0.004)
    gs10 = interp(MONTHLY, GS10_ANCHORS, noise=0.004).clip(lower=0.3)
    cpi = interp(MONTHLY, CPI_ANCHORS, log=True)
    real_earnings = interp(MONTHLY, REAL_EARN_ANCHORS, log=True, noise=0.003)

    e10 = real_earnings.rolling(120, min_periods=12).mean()
    real_price = cape * e10
    cpi_last = cpi.iloc[-1]
    price = real_price * cpi / cpi_last
    earnings = real_earnings * cpi / cpi_last
    payout = interp(MONTHLY, {1881.5: 0.65, 1950.0: 0.55, 1990.0: 0.45, 2026.5: 0.35})
    dividend = earnings * payout

    infl_10y = ((cpi / cpi.shift(120)) ** (1 / 10) - 1) * 100
    ecy = 100.0 / cape - (gs10 - infl_10y)

    return pd.DataFrame(
        {
            "date": MONTHLY,
            "price": price.round(2),
            "dividend": dividend.round(2),
            "earnings": earnings.round(2),
            "cpi": cpi.round(3),
            "gs10": gs10.round(2),
            "real_price": real_price.round(2),
            "real_earnings": real_earnings.round(2),
            "cape": cape.round(2),
            "ecy": ecy.round(2),
        }
    )


# ------------------------------------------------------------------- fred ----
GDP_ANCHORS = {
    1947.0: 243, 1960.0: 542, 1970.0: 1073, 1980.0: 2857, 1990.0: 5963,
    2000.0: 10250, 2010.0: 15049, 2020.0: 21060, 2023.0: 27610, 2026.5: 31200,
}
BUFFETT_ANCHORS = {
    1947.0: 0.30, 1968.9: 0.75, 1974.9: 0.30, 1982.6: 0.28, 1990.0: 0.50,
    2000.2: 1.40, 2002.8: 0.75, 2007.8: 1.05, 2009.2: 0.55, 2015.0: 1.20,
    2020.3: 1.10, 2021.9: 2.05, 2022.8: 1.55, 2024.5: 1.90, 2026.5: 2.15,
}
AIAE_ANCHORS = {
    1951.8: 0.25, 1968.9: 0.37, 1974.9: 0.19, 1982.6: 0.18, 1990.0: 0.26,
    2000.2: 0.42, 2002.8: 0.30, 2007.8: 0.37, 2009.2: 0.26, 2015.0: 0.38,
    2020.3: 0.36, 2021.9: 0.48, 2022.8: 0.42, 2026.5: 0.49,
}

QUARTERLY = pd.date_range("1947-01-01", "2026-04-01", freq="QS")


def fred_frame(idx: pd.DatetimeIndex, s: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"date": idx, "value": s.values.round(4)})


def gen_fred() -> dict[str, pd.DataFrame]:
    gdp = interp(QUARTERLY, GDP_ANCHORS, log=True)
    buffett = interp(QUARTERLY, BUFFETT_ANCHORS, log=True, noise=0.006)
    equities_millions = buffett * gdp * 1000.0

    sh = gen_shiller().set_index("date")
    dgs10_idx = pd.date_range("1962-01-01", "2026-06-01", freq="MS")
    dgs10 = sh["gs10"].reindex(dgs10_idx)

    out = {
        "fred_GDP": fred_frame(QUARTERLY, gdp),
        "fred_NCBEILQ027S": fred_frame(QUARTERLY, equities_millions),
        "fred_DGS10": fred_frame(dgs10_idx, dgs10),
        "fred_USREC": gen_usrec(),
    }

    vix_idx = pd.date_range("1990-01-01", "2026-06-01", freq="MS")
    out["fred_VIXCLS"] = fred_frame(vix_idx, interp(vix_idx, {
        1990.0: 23, 1995.0: 12, 1998.8: 44, 2003.0: 30, 2006.5: 11,
        2008.9: 62, 2012.0: 17, 2017.5: 10, 2018.1: 25, 2020.3: 57,
        2021.5: 19, 2022.5: 27, 2024.0: 14, 2026.5: 18,
    }, noise=0.02).clip(lower=9))

    t_idx = pd.date_range("1976-06-01", "2026-06-01", freq="MS")
    out["fred_T10Y2Y"] = fred_frame(t_idx, interp(t_idx, {
        1976.5: 1.0, 1980.2: -2.0, 1984.0: 1.2, 1989.2: -0.2, 1992.5: 2.5,
        2000.3: -0.5, 2003.5: 2.5, 2006.8: -0.1, 2010.0: 2.7, 2019.7: -0.04,
        2021.3: 1.5, 2023.5: -1.05, 2025.0: 0.3, 2026.5: 0.6,
    }, noise=0.01))

    hy_idx = pd.date_range("1997-01-01", "2026-06-01", freq="MS")
    out["fred_BAMLH0A0HYM2"] = fred_frame(hy_idx, interp(hy_idx, {
        1997.0: 3.0, 1998.8: 6.0, 2000.5: 5.5, 2002.8: 10.6, 2007.3: 2.5,
        2008.95: 19.9, 2011.8: 8.0, 2014.5: 3.4, 2016.2: 8.4, 2020.3: 10.9,
        2021.5: 3.1, 2022.7: 5.5, 2024.0: 3.2, 2026.5: 3.5,
    }, log=True, noise=0.01))

    wti_idx = pd.date_range("1986-01-01", "2026-06-01", freq="MS")
    out["fred_DCOILWTICO"] = fred_frame(wti_idx, interp(wti_idx, {
        1986.0: 23, 1988.5: 15, 1990.8: 36, 1994.0: 17, 1998.9: 11,
        2000.7: 34, 2002.0: 20, 2008.5: 134, 2009.1: 40, 2011.3: 105,
        2014.5: 100, 2016.1: 30, 2018.7: 70, 2020.3: 17, 2022.4: 110,
        2024.0: 78, 2026.5: 70,
    }, log=True, noise=0.015))

    ums_idx = pd.date_range("1978-01-01", "2026-06-01", freq="MS")
    out["fred_UMCSENT"] = fred_frame(ums_idx, interp(ums_idx, {
        1978.0: 65, 1980.4: 52, 1984.0: 96, 1990.9: 63, 1994.0: 91,
        2000.0: 110, 2003.2: 78, 2007.0: 96, 2008.11: 55, 2011.8: 55,
        2015.0: 93, 2020.2: 101, 2020.4: 72, 2022.5: 50, 2024.0: 70,
        2026.5: 60,
    }, noise=0.01))

    ff_idx = pd.date_range("1954-07-01", "2026-06-01", freq="MS")
    out["fred_FEDFUNDS"] = fred_frame(ff_idx, interp(ff_idx, {
        1954.5: 1.0, 1969.0: 9.0, 1971.0: 4.7, 1974.6: 12.9, 1976.5: 4.8,
        1981.5: 19.1, 1986.0: 6.8, 1990.0: 8.1, 1993.5: 3.0, 2000.5: 6.5,
        2003.9: 1.0, 2006.6: 5.25, 2009.0: 0.15, 2015.9: 0.15, 2018.9: 2.4,
        2020.3: 0.05, 2022.2: 0.08, 2023.7: 5.33, 2025.0: 4.5, 2026.5: 4.3,
    }, noise=0.008).clip(lower=0.05))

    cpi_idx = pd.date_range("1947-01-01", "2026-06-01", freq="MS")
    out["fred_CPIAUCSL"] = fred_frame(cpi_idx, interp(cpi_idx, {
        1947.0: 21.5, 1970.0: 38.8, 1980.0: 82.4, 1990.0: 130.7, 2000.0: 172.2,
        2008.5: 219.0, 2009.5: 214.5, 2015.0: 237.0, 2020.0: 258.8, 2021.0: 262.0,
        2022.5: 296.0, 2023.5: 305.0, 2024.5: 314.0, 2026.5: 324.0,
    }, log=True))

    ur_idx = pd.date_range("1948-01-01", "2026-06-01", freq="MS")
    out["fred_UNRATE"] = fred_frame(ur_idx, interp(ur_idx, {
        1948.0: 3.8, 1953.5: 2.5, 1958.5: 7.4, 1969.0: 3.5, 1975.4: 9.0,
        1982.9: 10.8, 1989.0: 5.0, 1992.5: 7.8, 2000.3: 3.9, 2003.4: 6.3,
        2007.0: 4.4, 2009.8: 10.0, 2015.0: 5.0, 2019.7: 3.5, 2020.3: 14.7,
        2023.0: 3.5, 2026.5: 4.2,
    }, noise=0.01).clip(lower=2.4))

    m2_idx = pd.date_range("1959-01-01", "2026-05-01", freq="MS")
    out["fred_M2SL"] = fred_frame(m2_idx, interp(m2_idx, {
        1959.0: 290, 1980.0: 1600, 1990.0: 3200, 2000.0: 4600, 2008.0: 7700,
        2015.0: 11700, 2019.9: 15300, 2021.3: 20000, 2022.2: 21700, 2023.8: 20600,
        2025.0: 21400, 2026.4: 22100,
    }, log=True, noise=0.003))

    bei_idx = pd.date_range("2003-01-01", "2026-06-01", freq="MS")
    out["fred_T10YIE"] = fred_frame(bei_idx, interp(bei_idx, {
        2003.0: 1.9, 2005.5: 2.5, 2008.4: 2.6, 2008.95: 0.1, 2011.3: 2.5,
        2013.0: 2.2, 2015.9: 1.4, 2018.4: 2.15, 2020.2: 1.0, 2022.3: 3.0,
        2023.5: 2.2, 2026.5: 2.3,
    }, noise=0.01).clip(lower=0.1))
    return out


# --------------------------------------------------------------- sentiment ----
def gen_sentiment() -> dict[str, pd.DataFrame]:
    out = {}
    margin_idx = pd.date_range("1997-01-01", "2026-05-01", freq="MS")
    margin = interp(margin_idx, {
        1997.0: 100, 2000.2: 280, 2002.8: 130, 2007.6: 380, 2009.1: 175,
        2015.0: 500, 2020.3: 480, 2021.8: 935, 2022.11: 600, 2024.5: 800,
        2026.4: 1000,
    }, log=True, noise=0.008)
    out["finra_margin_debt"] = pd.DataFrame(
        {"date": margin_idx, "value": margin.values.round(1)}
    )

    fg_idx = pd.bdate_range("2021-01-04", "2026-06-30")
    fg = interp(fg_idx, {
        2021.1: 65, 2021.9: 45, 2022.1: 30, 2022.5: 12, 2022.9: 20,
        2023.2: 60, 2023.10: 25, 2024.1: 70, 2024.8: 30, 2025.0: 55,
        2025.4: 22, 2026.0: 60, 2026.5: 48,
    }, noise=0.05).clip(3, 97)
    out["cnn_fear_greed"] = pd.DataFrame(
        {"date": fg_idx, "value": fg.values.round(0)}
    )

    aaii_idx = pd.date_range("1987-07-02", "2026-06-25", freq="W-THU")
    aaii = interp(aaii_idx, {
        1987.6: 10, 1987.9: -20, 1990.9: -30, 1993.0: 15, 2000.1: 40,
        2003.2: -20, 2007.8: 15, 2009.2: -51, 2013.0: 30, 2016.1: -15,
        2018.1: 35, 2020.3: -30, 2021.4: 35, 2022.7: -43, 2024.0: 25,
        2025.3: -20, 2026.5: 8,
    }, noise=0.15)
    out["aaii_sentiment"] = pd.DataFrame(
        {"date": aaii_idx, "value": aaii.values.round(1)}
    )
    return out


NBER_RECESSIONS = [
    ("1882-04", "1885-05"), ("1887-04", "1888-04"), ("1890-08", "1891-05"),
    ("1893-02", "1894-06"), ("1895-12", "1897-06"), ("1899-06", "1900-12"),
    ("1902-09", "1904-08"), ("1907-05", "1908-06"), ("1910-01", "1912-01"),
    ("1913-01", "1914-12"), ("1918-08", "1919-03"), ("1920-01", "1921-07"),
    ("1923-05", "1924-07"), ("1926-10", "1927-11"), ("1929-08", "1933-03"),
    ("1937-05", "1938-06"), ("1945-02", "1945-10"), ("1948-11", "1949-10"),
    ("1953-07", "1954-05"), ("1957-08", "1958-04"), ("1960-04", "1961-02"),
    ("1969-12", "1970-11"), ("1973-11", "1975-03"), ("1980-01", "1980-07"),
    ("1981-07", "1982-11"), ("1990-07", "1991-03"), ("2001-03", "2001-11"),
    ("2007-12", "2009-06"), ("2020-02", "2020-04"),
]


def gen_usrec() -> pd.DataFrame:
    flag = pd.Series(0.0, index=MONTHLY)
    for start, end in NBER_RECESSIONS:
        flag.loc[start:end] = 1.0
    return pd.DataFrame({"date": MONTHLY, "value": flag.values})


# ------------------------------------------------------------------- aiae ----
def gen_aiae() -> pd.DataFrame:
    idx = pd.date_range("1951-10-01", "2026-04-01", freq="QS")
    ratio = interp(idx, AIAE_ANCHORS, noise=0.005).clip(0.05, 0.6)
    gdp = interp(idx, GDP_ANCHORS, log=True)
    # All Z.1 series are millions USD (match real FRED units).
    debt_mil = gdp * 2.6 * 1000  # rough total real-economy debt, millions
    equities_mil = ratio / (1 - ratio) * debt_mil
    return pd.DataFrame(
        {
            "date": idx,
            "equities_nonfin": (equities_mil * 0.75).round(0),
            "equities_fin": (equities_mil * 0.25).round(0),
            "debt_business": (debt_mil * 0.30).round(0),
            "debt_household": (debt_mil * 0.30).round(0),
            "debt_federal": (debt_mil * 0.25).round(0),
            "debt_state_local": (debt_mil * 0.08).round(0),
            "debt_world": (debt_mil * 0.07).round(0),
        }
    )


# ------------------------------------------------------------------ multpl ----
def gen_multpl(sh: pd.DataFrame) -> dict[str, pd.DataFrame]:
    s = sh.set_index("date")
    pe = (s["price"] / s["earnings"]).clip(5, 80)
    div_yield = (s["dividend"] / s["price"] * 100).clip(0.8, 10)

    pb_idx = pd.date_range("2000-03-01", "2026-06-01", freq="QS")
    pb = interp(pb_idx, {
        2000.2: 5.0, 2002.9: 2.4, 2007.5: 2.9, 2009.2: 1.8, 2013.0: 2.5,
        2018.0: 3.3, 2020.3: 2.9, 2021.9: 4.9, 2022.8: 3.6, 2024.5: 4.5,
        2026.5: 5.2,
    }, noise=0.005)

    return {
        "multpl_pe": pd.DataFrame({"date": pe.index, "value": pe.values.round(2)}),
        "multpl_pb": pd.DataFrame({"date": pb_idx, "value": pb.values.round(2)}),
        "multpl_div_yield": pd.DataFrame(
            {"date": div_yield.index, "value": div_yield.values.round(2)}
        ),
        "multpl_shiller_pe": pd.DataFrame(
            {"date": s.index, "value": s["cape"].values.round(2)}
        ),
    }


# ------------------------------------------------------------------- stooq ----
def gen_stooq(sh: pd.DataFrame) -> dict[str, pd.DataFrame]:
    days = pd.bdate_range("1980-01-02", "2026-06-30")
    monthly_price = sh.set_index("date")["price"]
    base = np.interp(decimal_year(days), decimal_year(monthly_price.index),
                     monthly_price.values)
    # daily noise around the monthly path, seeded and mean-reverting
    eps = RNG.normal(0, 0.008, len(days))
    dev = np.zeros(len(days))
    for i in range(1, len(days)):
        dev[i] = 0.98 * dev[i - 1] + eps[i]
    close = base * (1 + dev)
    spread = np.abs(RNG.normal(0, 0.004, len(days)))
    open_ = close * (1 + RNG.normal(0, 0.003, len(days)))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    spx = pd.DataFrame(
        {"date": days, "open": open_.round(2), "high": high.round(2),
         "low": low.round(2), "close": close.round(2)}
    )

    gold_days = pd.bdate_range("1990-01-02", "2026-06-30")
    gold_base = interp(gold_days, {
        1990.0: 390, 1999.6: 255, 2008.2: 920, 2011.7: 1890, 2015.9: 1060,
        2020.6: 2050, 2022.2: 1950, 2022.8: 1650, 2024.0: 2050, 2025.0: 2700,
        2026.5: 3300,
    }, log=True, noise=0.004)
    gold = pd.DataFrame(
        {"date": gold_days, "open": gold_base.values.round(1),
         "high": (gold_base * 1.005).values.round(1),
         "low": (gold_base * 0.995).values.round(1),
         "close": gold_base.values.round(1)}
    )
    return {"stooq_spx_daily": spx, "stooq_gold": gold}


# ------------------------------------------------------------------- korea ----
def gen_korea() -> dict[str, pd.DataFrame]:
    out = {}
    # KOSPI daily index
    days = pd.bdate_range("1996-01-02", "2026-06-30")
    kospi = interp(days, {
        1996.0: 880, 1998.8: 300, 2000.0: 1030, 2001.7: 490, 2007.9: 2060,
        2008.9: 940, 2011.4: 2210, 2016.0: 1830, 2018.1: 2600, 2020.2: 1460,
        2021.5: 3300, 2022.9: 2160, 2024.5: 2700, 2026.5: 3100,
    }, log=True, noise=0.01)
    out["stooq_kospi_daily"] = pd.DataFrame({
        "date": days, "open": kospi.values.round(1), "high": (kospi * 1.005).values.round(1),
        "low": (kospi * 0.995).values.round(1), "close": kospi.values.round(1),
    })
    # KRX valuation (PER/PBR/div), daily 2004+
    kdays = pd.bdate_range("2004-01-02", "2026-06-30")
    per = interp(kdays, {2004.0: 10, 2007.9: 16, 2008.9: 8, 2011.0: 13, 2015.0: 11,
                         2018.0: 10, 2020.2: 12, 2021.5: 18, 2022.9: 10, 2026.5: 13},
                 noise=0.01).clip(5, 30)
    pbr = interp(kdays, {2004.0: 1.1, 2007.9: 1.9, 2008.9: 0.8, 2011.0: 1.4, 2015.0: 1.0,
                         2018.0: 1.0, 2021.5: 1.2, 2022.9: 0.85, 2026.5: 1.0},
                 noise=0.008).clip(0.6, 2.2)
    dvd = (100 / per / pbr * 1.3).clip(0.8, 4)
    out["krx_valuation"] = pd.DataFrame({
        "date": kdays, "per": per.values.round(2), "pbr": pbr.values.round(2),
        "div_yield": dvd.values.round(2),
    })
    # World Bank GDP (annual, USD)
    gyears = pd.date_range("1960-12-31", "2024-12-31", freq="YE")
    gdp = interp(gyears, {1960.9: 4e9, 1980.9: 6.5e10, 2000.9: 5.8e11,
                          2010.9: 1.14e12, 2020.9: 1.64e12, 2024.9: 1.87e12}, log=True)
    out["worldbank_gdp"] = pd.DataFrame({"date": gyears, "value": gdp.values.round(0)})
    # FRED Korea series
    krw_idx = pd.date_range("1981-04-01", "2026-06-01", freq="MS")
    out["fred_DEXKOUS"] = fred_frame(krw_idx, interp(krw_idx, {
        1981.3: 685, 1997.9: 1700, 2001.0: 1300, 2008.9: 1500, 2014.0: 1050,
        2020.2: 1280, 2022.9: 1440, 2026.5: 1350}, noise=0.01))
    y10_idx = pd.date_range("2000-10-01", "2026-06-01", freq="MS")
    out["fred_IRLTLT01KRM156N"] = fred_frame(y10_idx, interp(y10_idx, {
        2000.8: 7.0, 2005.0: 4.5, 2008.9: 5.5, 2016.5: 1.4, 2020.5: 1.4,
        2022.9: 4.2, 2026.5: 3.3}, noise=0.01))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sh = gen_shiller()
    frames: dict[str, pd.DataFrame] = {"shiller": sh, "aiae_inputs": gen_aiae()}
    frames.update(gen_fred())
    frames.update(gen_sentiment())
    frames.update(gen_multpl(sh))
    frames.update(gen_stooq(sh))
    frames.update(gen_korea())
    for name, df in frames.items():
        path = OUT / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"wrote {path.name}: {len(df)} rows")
    # Interpolated data is NOT a real-data snapshot; drop the freshness meta
    # so the loader doesn't skip live fetches because of it.
    meta = OUT / "_meta.json"
    if meta.exists():
        meta.unlink()
        print("removed _meta.json (interpolated data is not a snapshot)")


if __name__ == "__main__":
    main()
