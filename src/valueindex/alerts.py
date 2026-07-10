"""Rating-change detection between two builds of overview.json.

The daily Actions run compares yesterday's overview.json (git HEAD before
the refresh) with the freshly built one; any band change becomes a GitHub
issue, which GitHub then emails to the repo owner. This is the app's "stay
quiet until something actually changes" alert channel — no server, no keys.
"""
from __future__ import annotations

from . import registry, stats

_RATING_LABEL = {r.key: f"{r.label_ko}" for _, r in stats.RATINGS}


def _fmt(key_label: str, old_key: str, new_key: str) -> str:
    return (f"- **{key_label}**: {_RATING_LABEL.get(old_key, old_key)} → "
            f"**{_RATING_LABEL.get(new_key, new_key)}**")


def diff_overview(old: dict, new: dict) -> list[str]:
    """Human-readable (Korean) lines for every rating-band change."""
    lines = []
    old_s = old.get("summaries", {})
    for key, summ in new.get("summaries", {}).items():
        prev = old_s.get(key)
        if prev and prev.get("rating") != summ.get("rating"):
            label = registry.INDICATORS[key].label_ko if key in registry.INDICATORS else key
            lines.append(_fmt(label, prev["rating"], summ["rating"]))
    old_pca = old.get("pca", {}).get("rating")
    new_pca = new.get("pca", {}).get("rating")
    if old_pca and new_pca and old_pca != new_pca:
        lines.insert(0, _fmt("종합 밸류에이션 지수", old_pca, new_pca))
    return lines


def issue_body(lines: list[str]) -> str:
    return (
        "매일 데이터 갱신 중 σ 등급 밴드가 바뀐 지표가 있어 알립니다.\n\n"
        + "\n".join(lines)
        + "\n\n등급 변화는 '행동하라'는 신호가 아니라 '점검하라'는 신호입니다 — "
        "[월간 점검](https://praswna.github.io/ValueIndex/report.html)과 "
        "[규율 페이지](https://praswna.github.io/ValueIndex/discipline.html)의 "
        "시나리오 규칙을 먼저 확인하세요.\n\n"
        "_확인했으면 이 이슈는 닫으면 됩니다._"
    )
