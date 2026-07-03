"""Central configuration: source URLs, series IDs, cache TTLs, paths."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent
SAMPLE_DATA_DIR = PACKAGE_DIR / "sample_data"
CONTENT_DIR = PACKAGE_DIR / "content"

# Repo-root data cache (works both for `pip install -e .` and source checkout).
CACHE_DIR = Path(os.environ.get("VALUEINDEX_CACHE_DIR", Path.cwd() / "data" / "cache"))

# When set, never touch the network (cache -> sample data only).
OFFLINE = os.environ.get("VALUEINDEX_OFFLINE", "") not in ("", "0", "false")

# --- Shiller ie_data.xls -----------------------------------------------------
# Ordered fallback list; the first URL that works wins.
SHILLER_URLS = [
    "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls",
    "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
]

# --- FRED (keyless CSV endpoint) ---------------------------------------------
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

FRED_SERIES = {
    "gdp": "GDP",                    # Nominal GDP, quarterly, billions USD
    "equities": "NCBEILQ027S",       # Nonfinancial corporate equities, quarterly, millions USD
    "dgs10": "DGS10",                # 10Y Treasury yield, daily, percent
    "usrec": "USREC",                # NBER recession indicator, monthly, 0/1
    "vix": "VIXCLS",                 # CBOE VIX, daily
    "t10y2y": "T10Y2Y",              # 10Y minus 2Y Treasury spread, daily, pct points
    "hy_spread": "BAMLH0A0HYM2",     # ICE BofA US High Yield OAS, daily, pct points
    "wti": "DCOILWTICO",             # WTI crude oil spot, daily, USD/bbl
    "umcsent": "UMCSENT",            # U. Michigan consumer sentiment, monthly
}

# --- Sentiment sources (no official APIs; parsers are tolerant and fall
# back to cache/sample data when the page formats change) -----------------------
FINRA_MARGIN_URL = (
    "https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics"
)
CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
AAII_SENTIMENT_URL = "https://www.aaii.com/files/surveys/sentiment.xls"

# AIAE (aggregate investor allocation to equities), quarterly Z.1 series.
# Formula (Philosophical Economics): equities / (equities + liabilities of
# real-economy borrowers). Values in millions (equities) / billions (debt);
# units are reconciled in indicators.aiae().
AIAE_SERIES = {
    "equities_nonfin": "NCBEILQ027S",   # nonfinancial corporate equities, millions
    "equities_fin": "FBCELLQ027S",      # financial corporate equities, millions
    "debt_business": "BCNSDODNS",       # nonfinancial business debt, billions
    "debt_household": "CMDEBT",         # household & nonprofit debt, billions
    "debt_federal": "FGSDODNS",         # federal government debt, billions
    "debt_state_local": "SLGSDODNS",    # state & local government debt, billions
    "debt_world": "DODFFSWCMI",         # rest-of-world US-dollar debt, billions
}

# --- multpl.com ----------------------------------------------------------------
MULTPL_PAGES = {
    "pe": "https://www.multpl.com/s-p-500-pe-ratio/table/by-month",
    "pb": "https://www.multpl.com/s-p-500-price-to-book/table/by-quarter",
    "div_yield": "https://www.multpl.com/s-p-500-dividend-yield/table/by-month",
}

# --- Stooq (daily OHLC / gold) --------------------------------------------------
STOOQ_CSV_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"
STOOQ_SYMBOLS = {
    "spx_daily": "^spx",     # S&P 500 daily OHLC
    "gold": "xauusd",        # gold spot, USD/oz
}

# --- Cache TTLs ------------------------------------------------------------------
CACHE_TTL = {
    "shiller": timedelta(days=7),
    "fred": timedelta(days=1),
    "multpl": timedelta(days=1),
    "stooq": timedelta(days=1),
    "aiae_inputs": timedelta(days=7),
    "finra": timedelta(days=7),
    "cnn": timedelta(days=1),
    "aaii": timedelta(days=7),
}

REQUEST_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
