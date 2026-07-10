"""Shared data-collection helpers used by both the CLI refresh script and
the local GUI collector (collector.py).

Running from a home/residential IP reaches sources that block datacenter
IPs (KRX, FINRA, AAII), so the GUI is the way to keep those live.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from . import config, loader

META_PATH = config.SAMPLE_DATA_DIR / "_meta.json"

# Sources that datacenter IPs (GitHub Actions) get blocked from — these
# only refresh from a home run. The rest work anywhere.
LOCAL_ONLY = {"krx_valuation", "finra_margin_debt", "aaii_sentiment"}


def source_names() -> list[str]:
    return list(loader.SOURCES)


def collect_source(name: str) -> tuple[pd.DataFrame | None, str | None]:
    """Fetch one source live. Returns (dataframe, error_message)."""
    fetch_fn, _ = loader.SOURCES[name]
    try:
        df = fetch_fn()
        if df is None or df.empty:
            return None, "빈 응답 (0 rows)"
        return df, None
    except Exception as exc:  # noqa: BLE001 - report every failure to the UI
        return None, f"{type(exc).__name__}: {exc}"


def load_meta() -> dict:
    if META_PATH.exists():
        try:
            return json.loads(META_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_snapshot(name: str, df: pd.DataFrame, meta: dict | None = None) -> dict:
    """Write one source's CSV and stamp its refresh time in _meta.json."""
    config.SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.SAMPLE_DATA_DIR / f"{name}.csv", index=False)
    if name == "edgar_whales":
        # 13F snapshots only keep the latest two quarters; fold their
        # summaries into the cumulative history so trends accumulate.
        from .fetchers import edgar
        edgar.update_history(df)
    meta = load_meta() if meta is None else meta
    meta[name] = datetime.now(timezone.utc).isoformat()
    return meta


def write_meta(meta: dict) -> None:
    META_PATH.write_text(json.dumps(meta, indent=1, sort_keys=True))


def latest_date(df: pd.DataFrame) -> str:
    if "date" in df.columns:
        try:
            return str(pd.to_datetime(df["date"]).max().date())
        except Exception:  # noqa: BLE001
            return "-"
    if "quarter" in df.columns:  # whale 13F frames use a quarter, not a date
        try:
            return str(df["quarter"].max())
        except Exception:  # noqa: BLE001
            return "-"
    return "-"


# --------------------------------------------------------------------------
# High-level operations shared by the local collector GUI (collector_gui.py).
# All three take a plain `log(str)` callback so any front end (Tkinter, CLI)
# can drive them without importing streamlit.

REPO_ROOT = config.PACKAGE_DIR.parents[1]
DOCS_DATA_DIR = REPO_ROOT / "docs" / "data"


def collect_all(log=lambda _s: None, on_progress=lambda _i, _n: None) -> dict:
    """Fetch every source live, save the ones that succeed, keep the previous
    file for the ones that fail. Returns {"ok": [...], "failed": [...], "total"}."""
    meta = load_meta()
    ok, failed = [], []
    names = source_names()
    for i, name in enumerate(names, 1):
        df, err = collect_source(name)
        on_progress(i, len(names))
        if df is not None:
            meta = save_snapshot(name, df, meta)
            log(f"  ✓ {name}: {len(df)} rows · 최신 {latest_date(df)}")
            ok.append(name)
        else:
            log(f"  ✗ {name}: {err}")
            failed.append(name)
    write_meta(meta)
    return {"ok": ok, "failed": failed, "total": len(names)}


def rebuild_site(log=lambda _s: None) -> dict:
    """Rebuild docs/data/*.json from the on-disk snapshots.

    Runs offline: the collect step already fetched everything it could, so
    the build just bakes the current CSVs (freshly collected where possible,
    last real data where a source failed) into JSON — no re-fetching, so it's
    instant and can't downgrade a kept source to interpolated sample."""
    from . import sitebuild  # lazy: pulls indicators/quant/markdown
    log("docs/data/*.json 생성 중… (디스크 스냅샷 사용, 재수집 안 함)")
    prev_offline = config.OFFLINE
    config.OFFLINE = True
    try:
        statuses = sitebuild.build_site(DOCS_DATA_DIR, force=False)
    finally:
        config.OFFLINE = prev_offline
    log(f"완료: {len(statuses)}개 소스로 사이트 데이터 생성")
    return statuses


def git_publish(log=lambda _s: None, message: str | None = None) -> bool:
    """git add (data only) → commit → push. No-op if nothing changed."""
    import subprocess
    from datetime import date

    msg = message or f"Refresh market data (local collect) {date.today().isoformat()}"
    paths = ["src/valueindex/sample_data", "docs/data"]

    def run(args) -> subprocess.CompletedProcess:
        log("$ " + " ".join(args))
        r = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
        for stream in (r.stdout, r.stderr):
            if stream and stream.strip():
                log(stream.strip())
        return r

    run(["git", "add", *paths])
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
    if staged.returncode != 0:
        if run(["git", "commit", "-m", msg]).returncode != 0:
            return False
    else:
        log("새 변경사항 없음 — 미푸시 커밋이 있으면 그것만 올립니다.")

    # The remote moves daily (Actions data refresh), so integrate it before
    # pushing. On conflicts prefer our side ("theirs" during a rebase = the
    # commits being replayed, i.e. the fresh local collect).
    if run(["git", "pull", "--rebase", "-X", "theirs"]).returncode != 0:
        run(["git", "rebase", "--abort"])
        log("원격 변경 통합 실패 — 터미널에서 `git pull --rebase` 후 다시 시도하세요.")
        return False
    return run(["git", "push"]).returncode == 0
