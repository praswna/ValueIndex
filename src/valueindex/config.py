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
    "fedfunds": "FEDFUNDS",          # effective federal funds rate, monthly, %
    "cpi_index": "CPIAUCSL",         # CPI index (for YoY inflation), monthly
    "unrate": "UNRATE",              # unemployment rate, monthly, %
    "m2": "M2SL",                    # M2 money stock, monthly, $B (for YoY)
    "t10yie": "T10YIE",              # 10Y breakeven inflation, daily, %
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
    # Extends CAPE past the end of Shiller's own file (the pinned download
    # can lag by many months; multpl publishes the current monthly value).
    "shiller_pe": "https://www.multpl.com/shiller-pe/table/by-month",
}

# --- Stooq (daily OHLC / gold) --------------------------------------------------
STOOQ_CSV_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"
STOOQ_SYMBOLS = {
    "spx_daily": "^spx",     # S&P 500 daily OHLC
    "gold": "xauusd",        # gold spot, USD/oz
    "kospi_daily": "^kospi",  # KOSPI index daily OHLC
}

# Yahoo Finance chart symbols — primary source for daily prices (Stooq
# blocks datacenter IPs). ^GSPC goes back to 1927, better than Stooq.
YAHOO_SYMBOLS = {
    "spx_daily": "^GSPC",    # S&P 500 index
    "gold": "GC=F",          # COMEX gold futures (USD/oz proxy)
    "kospi_daily": "^KS11",  # KOSPI index
}

# --- Korea market -------------------------------------------------------------
# KRX 정보데이터시스템 (data.krx.co.kr) — keyless but needs a POST with a
# referer header; the endpoint id changes rarely. Tolerant parser + sample
# fallback (verified live only by the Actions run, not this sandbox).
KRX_OTP_URL = "http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
KRX_DATA_URL = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
KRX_PER_PBR_BLD = "dbms/MDC/STAT/standard/MDCSTAT03501"  # 지수 PER/PBR/배당수익률
KRX_REFERER = "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd"

# World Bank nominal GDP (current US$), keyless JSON, annual.
WORLDBANK_GDP_URL = (
    "https://api.worldbank.org/v2/country/KR/indicator/NY.GDP.MKTP.CD"
    "?format=json&per_page=200"
)

FRED_KR_SERIES = {
    "krw": "DEXKOUS",              # KRW/USD exchange rate, daily
    "kr_10y": "IRLTLT01KRM156N",   # Korea 10Y govt bond yield, monthly (OECD)
}

# --- SEC EDGAR 13F ("whale" institutional holdings) --------------------------
# Keyless JSON/XML. SEC policy requires a descriptive User-Agent carrying a
# contact address; requests without one get 403. Reachable from GitHub Actions
# runners but blocked by this sandbox's egress policy, so the parser is
# fixture-tested and the first Actions run does the live validation (same
# pattern as KRX/FINRA/AAII). Quarterly data; a wrong/kill CIK simply falls
# back to the bundled sample for that one whale.
EDGAR_UA = "ValueIndex research (praswna@gmail.com)"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
EDGAR_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"
# 13F value column switched from $1000s to whole dollars for filings on/after
# this date (SEC 2022 amendments); older filings are scaled up by 1000.
EDGAR_DOLLARS_FROM = "2023-01-01"

# slug -> display + CIK (validated on the first Actions run). region "KR"
# gets the "US-listed holdings only" caveat rendered in the UI.
WHALES = {
    "berkshire": {
        "name_ko": "버크셔 해서웨이 (버핏)", "cik": "0001067983", "region": "US",
        "note": "워런 버핏의 지주회사. 현금비중 변화와 집중 베팅이 핵심 관전 포인트.",
    },
    "nps": {
        "name_ko": "국민연금공단 (NPS)", "cik": "0001608046", "region": "KR",
        "note": "13F는 미국 상장주식만 공시합니다 — 국민연금의 국내 주식·채권·"
                "부동산은 여기에 나오지 않습니다(전체 기금의 일부만 보임).",
    },
    "bridgewater": {
        "name_ko": "브리지워터 (레이 달리오)", "cik": "0001350694", "region": "US",
        "note": "세계 최대 헤지펀드. ETF 중심의 분산형이라 개별 종목보다 자산배분 흐름을 봄.",
    },
    "scion": {
        "name_ko": "사이온 자산운용 (마이클 버리)", "cik": "0001649339", "region": "US",
        "note": "'빅쇼트'의 마이클 버리. 종목 수가 적어 분기마다 포트폴리오가 크게 바뀜.",
    },
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
    "krx": timedelta(days=1),
    "worldbank": timedelta(days=30),
    "edgar": timedelta(days=1),
}

REQUEST_TIMEOUT = 15
# A bundled snapshot younger than this counts as real data and skips the
# network on cold start (refreshed daily by the GitHub Actions workflow).
SNAPSHOT_TTL = timedelta(days=3)
# Hard wall-clock budget (seconds) for the first cold load of all sources.
# Sources that don't finish in time fall back to bundled sample data so the
# app always renders quickly (esp. on Streamlit Cloud). Override via env.
LOAD_BUDGET = float(os.environ.get("VALUEINDEX_LOAD_BUDGET", "25"))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
