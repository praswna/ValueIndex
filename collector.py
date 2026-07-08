"""ValueIndex 로컬 데이터 수집기 (GUI).

집 PC(주거용 IP)에서 실행하면 클라우드(GitHub Actions)가 막히는 소스
(KRX·FINRA·AAII)까지 포함해 **모든 데이터**를 수집합니다.

    pip install -e .
    streamlit run collector.py

수집 → 사이트 데이터 재생성 → 커밋·푸시까지 버튼으로 진행합니다.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd
import streamlit as st

from valueindex import collect, sitebuild

st.set_page_config(page_title="ValueIndex 수집기", page_icon="🛰️", layout="wide")
ROOT = Path(__file__).resolve().parent

st.title("🛰️ ValueIndex 로컬 데이터 수집기")
st.info(
    "이 도구는 **당신의 PC(집 인터넷)** 에서 실행되어, 클라우드 서버에서 차단되는 "
    "소스(🏠 KRX·FINRA·AAII)까지 포함해 모든 데이터를 실시간 수집합니다. "
    "수집 후 **사이트 데이터 재생성 → 커밋·푸시**까지 아래 버튼으로 진행하세요."
)

names = collect.source_names()


def run_collection():
    results = []
    meta = collect.load_meta()
    prog = st.progress(0.0, text="수집 시작...")
    table = st.empty()
    for i, name in enumerate(names):
        tag = "🏠 로컬 필요" if name in collect.LOCAL_ONLY else "☁️ 어디서나"
        prog.progress(i / len(names), text=f"수집 중: {name}")
        t0 = time.monotonic()
        df, err = collect.collect_source(name)
        elapsed = time.monotonic() - t0
        if df is not None:
            meta = collect.save_snapshot(name, df, meta)
            results.append({"소스": name, "구분": tag, "상태": "✅ 성공",
                            "행수": len(df), "최신": collect.latest_date(df),
                            "소요(초)": round(elapsed, 1), "메모": ""})
        else:
            results.append({"소스": name, "구분": tag, "상태": "❌ 실패",
                            "행수": 0, "최신": "-", "소요(초)": round(elapsed, 1),
                            "메모": err})
        table.dataframe(pd.DataFrame(results), width="stretch", hide_index=True)
    collect.write_meta(meta)
    prog.progress(1.0, text="완료")
    ok = sum(1 for r in results if r["상태"].startswith("✅"))
    st.session_state["last_results"] = results
    st.session_state["last_ok"] = ok


col1, col2 = st.columns([1, 3])
if col1.button("🔄 전체 수집 시작", type="primary", width="stretch"):
    run_collection()

if "last_ok" in st.session_state:
    ok = st.session_state["last_ok"]
    st.success(f"{ok}/{len(names)} 소스 수집 성공 · sample_data/ 에 저장됨")
    failed = [r for r in st.session_state["last_results"] if r["상태"].startswith("❌")]
    if failed:
        st.warning("실패한 소스(이전 파일 유지): "
                   + ", ".join(f"{r['소스']}({r['메모'][:40]})" for r in failed))

st.divider()
st.subheader("사이트 반영")
st.caption("수집한 데이터를 정적 사이트에 반영합니다. 순서대로 누르세요.")

c1, c2 = st.columns(2)
if c1.button("🏗️ 1) 사이트 데이터 재생성 (docs/data)", width="stretch"):
    with st.spinner("build_site_data 실행 중..."):
        statuses = sitebuild.build_site(ROOT / "docs" / "data", force=False)
    live = sum(1 for s in statuses.values() if s in ("live", "snapshot"))
    st.success(f"docs/data 재생성 완료 · {live}/{len(statuses)} 소스 실데이터")

if c2.button("📤 2) 커밋 & 푸시", width="stretch"):
    with st.spinner("git add / commit / push..."):
        out = []
        for cmd in (["git", "add", "-A"],
                    ["git", "commit", "-m", "chore: local data refresh (all sources)"],
                    ["git", "push"]):
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            out.append(f"$ {' '.join(cmd)}\n{r.stdout}{r.stderr}")
    st.code("\n".join(out))
    st.info("푸시되면 GitHub Pages가 자동 배포합니다 (1~2분).")

st.divider()
with st.expander("ℹ️ 소스 목록과 구분"):
    rows = [{"소스": n, "구분": "🏠 로컬 필요 (클라우드 차단)" if n in collect.LOCAL_ONLY
             else "☁️ 어디서나 가능"} for n in names]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
