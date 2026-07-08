"""Korea market data: KRX index PER/PBR/dividend yield, World Bank GDP.

KRX has no official API; its data.krx.co.kr JSON endpoints are keyless but
require a two-step OTP + POST with a referer header. Parsers are tolerant
and the loader falls back to cache/sample when the format changes. Live
behavior is verified by the GitHub Actions run, not this sandbox.
"""
from __future__ import annotations

import io
import json

import pandas as pd

from .. import config
from . import http


def _krx_post(bld: str, params: dict) -> str:
    session = http.get_session()
    otp = session.post(
        config.KRX_OTP_URL,
        data={"name": "form", "url": bld},
        headers={"Referer": config.KRX_REFERER},
        timeout=config.REQUEST_TIMEOUT,
    )
    otp.raise_for_status()
    resp = session.post(
        config.KRX_DATA_URL,
        data={**params, "code": otp.text},
        headers={"Referer": config.KRX_REFERER},
        timeout=config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.text


def _parse_per_pbr_json(text: str) -> pd.DataFrame:
    """KRX index PER/PBR/dividend JSON -> tidy (date, per, pbr, div_yield).

    Rows carry 'TRD_DD' (YYYY/MM/DD), 'PER', 'PBR', 'DVD_YLD'; numbers may
    contain commas and '-' for missing.
    """
    payload = json.loads(text)
    rows = payload.get("output") or payload.get("OutBlock_1") or []
    if not rows:
        raise ValueError("KRX response had no rows")

    def num(v):
        v = str(v).replace(",", "").strip()
        return pd.to_numeric(v, errors="coerce") if v not in ("", "-") else None

    recs = []
    for r in rows:
        date = pd.to_datetime(r.get("TRD_DD"), errors="coerce")
        if pd.isna(date):
            continue
        recs.append(
            {
                "date": date,
                "per": num(r.get("PER")),
                "pbr": num(r.get("PBR")),
                "div_yield": num(r.get("DVD_YLD")),
            }
        )
    if not recs:
        raise ValueError("KRX response had no parsable dated rows")
    out = pd.DataFrame(recs).dropna(subset=["per"], how="all")
    return out.sort_values("date").reset_index(drop=True)


def fetch_krx_valuation(index_code: str = "1") -> pd.DataFrame:
    """Daily KOSPI (index code '1') PER/PBR/dividend yield.

    KRX only serves a bounded date window per request, so this pulls the
    full available history in one wide query (strtDd..endDd)."""
    params = {
        "bld": config.KRX_PER_PBR_BLD,
        "locale": "ko_KR",
        "idxIndMidclssCd": "02",   # KOSPI series
        "trdDd": "",
        "tboxindTpCd_finder_equidx0_2": "코스피",
        "indTpCd": "1",
        "indTpCd2": index_code,
        "codeNmindTpCd_finder_equidx0_2": "코스피",
        "param1indTpCd_finder_equidx0_2": "",
        "strtDd": "20040101",
        "endDd": pd.Timestamp.now().strftime("%Y%m%d"),
        "share": "1",
        "money": "1",
        "csvxls_isNo": "false",
    }
    return _parse_per_pbr_json(_krx_post(config.KRX_PER_PBR_BLD, params))


def _parse_worldbank_gdp(text: str) -> pd.DataFrame:
    """World Bank indicator JSON -> tidy (date, value) annual GDP in USD."""
    payload = json.loads(text)
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        raise ValueError("World Bank response had no data page")
    recs = [
        {"date": pd.Timestamp(f"{row['date']}-12-31"), "value": row["value"]}
        for row in payload[1]
        if row.get("value") is not None
    ]
    if not recs:
        raise ValueError("World Bank response had no non-null values")
    return pd.DataFrame(recs).sort_values("date").reset_index(drop=True)


def fetch_worldbank_gdp() -> pd.DataFrame:
    resp = http.get(config.WORLDBANK_GDP_URL)
    return _parse_worldbank_gdp(resp.text)
