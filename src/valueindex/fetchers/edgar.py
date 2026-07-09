"""SEC EDGAR 13F holdings — the "whale tracker" data source.

For each institution in ``config.WHALES`` we read its EDGAR submissions
index, take the two most recent 13F-HR filings, and parse the information
table XML into holdings. Downstream (sitebuild.whales_payload) computes the
quarter-over-quarter changes.

EDGAR is keyless but requires a descriptive User-Agent with a contact
address, and rate-limits to ~10 req/s. Reachable from GitHub Actions; this
sandbox's egress policy blocks data.sec.gov, so the parser is fixture-tested
and the first Actions run validates live (same as KRX/FINRA/AAII).
"""
from __future__ import annotations

import json
import sys
import time
import xml.etree.ElementTree as ET

import pandas as pd

from .. import config
from . import http

COLUMNS = ["whale", "quarter", "filed", "cusip", "name", "class",
           "put_call", "value_usd", "shares"]

# SEC asks callers to stay under 10 requests/second; a small gap keeps the
# whole run (a few dozen requests) comfortably polite and avoids 429s.
_REQUEST_GAP = 0.15


def _get(url: str) -> str:
    """GET with the SEC-required contact User-Agent (overrides the session's
    browser UA for this request only)."""
    time.sleep(_REQUEST_GAP)
    resp = http.get_session().get(
        url,
        headers={"User-Agent": config.EDGAR_UA, "Accept-Encoding": "gzip, deflate"},
        timeout=config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.text


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _recent_13f(subs: dict, n: int = 2) -> list[dict]:
    """Newest-first list of the last ``n`` 13F-HR filings from a submissions
    JSON: accession number, report (quarter-end) date, filed date."""
    recent = subs["filings"]["recent"]
    forms = recent["form"]
    accs = recent["accessionNumber"]
    rdates = recent["reportDate"]
    fdates = recent["filingDate"]
    out = []
    for i, form in enumerate(forms):
        if form != "13F-HR":
            continue
        out.append({"accession": accs[i], "report_date": rdates[i],
                    "filed": fdates[i]})
        if len(out) >= n:
            break
    return out


def _infotable_files(cik_int: str, acc_nodash: str) -> list[str]:
    base = config.EDGAR_ARCHIVE_URL.format(cik=cik_int, acc=acc_nodash)
    idx = json.loads(_get(f"{base}/index.json"))
    return [it["name"] for it in idx["directory"]["item"]]


def _parse_infotable(xml_text: str, scale: float) -> pd.DataFrame:
    """13F information table XML -> (cusip, name, class, put_call, value_usd,
    shares). Namespace-agnostic (matches on local element names)."""
    root = ET.fromstring(xml_text)
    rows = []
    for el in root.iter():
        if _localname(el.tag) != "infoTable":
            continue
        rec = {"name": "", "class": "", "cusip": "", "put_call": "",
               "value": None, "shares": None}
        for ch in el.iter():
            ln = _localname(ch.tag)
            txt = (ch.text or "").strip()
            if ln == "nameOfIssuer":
                rec["name"] = txt
            elif ln == "titleOfClass":
                rec["class"] = txt
            elif ln == "cusip":
                rec["cusip"] = txt
            elif ln == "value":
                rec["value"] = txt
            elif ln == "sshPrnamt":
                rec["shares"] = txt
            elif ln == "putCall":
                rec["put_call"] = txt
        if rec["name"]:
            rows.append(rec)
    if not rows:
        raise ValueError("13F information table had no infoTable rows")
    df = pd.DataFrame(rows)
    df["value_usd"] = pd.to_numeric(df["value"], errors="coerce") * scale
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce")
    return df[["cusip", "name", "class", "put_call", "value_usd", "shares"]]


def _fetch_filing_holdings(cik_int: str, accession: str, scale: float) -> pd.DataFrame:
    """Find and parse the information-table XML inside one 13F filing folder.

    The holdings live in an XML that is not the ``primary_doc.xml`` cover
    page; try each candidate .xml and return the first that parses.
    """
    acc_nodash = accession.replace("-", "")
    base = config.EDGAR_ARCHIVE_URL.format(cik=cik_int, acc=acc_nodash)
    names = _infotable_files(cik_int, acc_nodash)
    candidates = [n for n in names
                  if n.lower().endswith(".xml") and n.lower() != "primary_doc.xml"]
    # Prefer names that look like an info table, then fall back to any xml.
    candidates.sort(key=lambda n: 0 if "table" in n.lower() or "info" in n.lower() else 1)
    last_exc: Exception | None = None
    for name in candidates + ["primary_doc.xml"]:
        try:
            return _parse_infotable(_get(f"{base}/{name}"), scale)
        except Exception as exc:  # noqa: BLE001 - try the next candidate xml
            last_exc = exc
    raise ValueError(f"no parsable information table in {accession}: {last_exc}")


def _fetch_whale(slug: str, cik: str) -> pd.DataFrame:
    cik10 = str(cik).zfill(10)
    cik_int = str(int(cik10))
    subs = json.loads(_get(config.EDGAR_SUBMISSIONS_URL.format(cik10=cik10)))
    filings = _recent_13f(subs, n=2)
    if not filings:
        raise ValueError(f"{slug}: no 13F-HR filings")
    frames = []
    for f in filings:
        scale = 1.0 if f["filed"] >= config.EDGAR_DOLLARS_FROM else 1000.0
        holdings = _fetch_filing_holdings(cik_int, f["accession"], scale)
        holdings["whale"] = slug
        holdings["quarter"] = f["report_date"]
        holdings["filed"] = f["filed"]
        frames.append(holdings)
    return pd.concat(frames, ignore_index=True)[COLUMNS]


def fetch_13f_holdings() -> pd.DataFrame:
    """All whales in one long frame. Whales that fail (blocked, kill CIK,
    format change) are skipped so the others still populate; sitebuild
    backfills any missing whale from the bundled sample."""
    frames = []
    for slug, w in config.WHALES.items():
        try:
            frames.append(_fetch_whale(slug, w["cik"]))
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"[edgar] {slug} (CIK {w['cik']}) failed: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)
    if not frames:
        raise RuntimeError("EDGAR: no whales fetched")
    return pd.concat(frames, ignore_index=True)
