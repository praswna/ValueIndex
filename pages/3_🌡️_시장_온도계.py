"""시장 온도계: 밸류에이션이 아닌 맥락(참고) 지표들."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from valueindex import registry, webui

st.set_page_config(page_title="시장 온도계", page_icon="🌡️", layout="wide")
panel, statuses, extras = webui.get_data()
webui.sidebar(statuses)

st.title("🌡️ 시장 온도계")
st.info(
    "**왜 이 지표들은 고평가/저평가 등급이 없나요?**\n\n"
    "금·유가는 이익도 배당도 만들지 않아 '적정 가격'의 기준점이 없고, "
    "VIX·금리차·신용스프레드는 밸류에이션이 아니라 **심리·경기의 신호**입니다. "
    "등급을 매기면 오히려 잘못된 해석을 유도하므로, 여기서는 수치와 맥락만 보여줍니다."
)

GUIDE_LINES = {
    "t10y2y": (0,),          # inversion line
    "aaii_spread": (0,),     # bulls == bears
    "fear_greed": (20, 80),  # extreme fear / extreme greed
}


def render_indicator(key: str) -> None:
    meta = registry.INDICATORS[key]
    s = extras["context"][key].dropna()
    if s.empty:
        return
    st.subheader(meta.label_ko)
    col_metric, col_chart = st.columns([1, 3])
    with col_metric:
        delta = None
        year_ago = s.loc[: s.index[-1] - pd.DateOffset(years=1)]
        if len(year_ago):
            delta = f"{s.iloc[-1] - year_ago.iloc[-1]:+,.1f} (1년 전 대비)"
        st.metric(f"현재 ({meta.unit})", f"{s.iloc[-1]:,.1f}", delta=delta, delta_color="off",
                  help=meta.what_ko)
        st.caption(f"{s.index[0].year}년~ · {meta.source}")
    with col_chart:
        fig = go.Figure(webui.line_trace(s, key, name=meta.label_ko))
        for level in GUIDE_LINES.get(key, ()):
            fig.add_hline(y=level, line_color="#c22f2f", line_width=1, line_dash="dot")
        fig.update_layout(showlegend=False, yaxis_title=meta.unit)
        webui.base_layout(fig, height=260)
        webui.add_recession_shading(fig, extras["usrec"], start=s.index[0])
        st.plotly_chart(fig, width="stretch")
    st.markdown(meta.interpret_ko)
    st.divider()


sentiment_keys = [k for k in registry.CONTEXT_KEYS if registry.INDICATORS[k].group == "sentiment"]
macro_keys = [k for k in registry.CONTEXT_KEYS if registry.INDICATORS[k].group != "sentiment"]

st.header("🧠 심리 온도계 — 시장의 감정을 재는 숫자들")
st.caption(
    "심리 지표는 두 부류입니다: 사람들이 **말하는** 것(설문 — AAII, 미시간대)과 "
    "**돈으로 실제 하는** 것(포지셔닝 — 신용융자, 공포·탐욕의 구성요소). 극단일 때만 "
    "의미가 있고, 관례적으로 **역발상**으로 읽습니다. 매매 신호가 아니라 '내 감정이 "
    "시장 전체와 같은 방향인지 확인하는 거울'로 쓰세요."
)
for key in sentiment_keys:
    render_indicator(key)

st.header("🌍 거시·시장 온도계")
for key in macro_keys:
    render_indicator(key)

st.caption(webui.DISCLAIMER)
