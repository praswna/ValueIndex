"""Live data-source health check — run on a machine with internet access.

Fetches every source registered in valueindex.loader.SOURCES and prints a
human-readable table: rows, latest date, elapsed time, or a readable
failure reason. Friendlier than `pytest -m network` for diagnosing which
source broke and why.

Run: python scripts/check_live_sources.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from valueindex import loader  # noqa: E402


def describe_error(exc: Exception) -> str:
    if isinstance(exc, requests.exceptions.HTTPError):
        code = exc.response.status_code if exc.response is not None else "?"
        return f"HTTP {code} — 사이트가 요청을 거부했습니다 (차단/URL 변경 가능성)"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "연결 실패 — 인터넷/프록시/방화벽을 확인하세요"
    if isinstance(exc, requests.exceptions.Timeout):
        return "시간 초과 — 잠시 후 다시 시도하세요"
    if isinstance(exc, (ValueError, KeyError)):
        return f"파싱 오류 — 사이트 형식이 바뀌었을 수 있습니다: {exc}"
    return f"{type(exc).__name__}: {exc}"


def main() -> int:
    print(f"{'소스':<24} {'상태':<6} {'행수':>7} {'최신 날짜':<12} {'소요':>6}")
    print("-" * 62)
    failures: list[tuple[str, str]] = []
    for name, (fetch_fn, _) in loader.SOURCES.items():
        t0 = time.monotonic()
        try:
            df = fetch_fn()
            elapsed = time.monotonic() - t0
            latest = str(df["date"].max().date()) if "date" in df.columns else "-"
            print(f"{name:<24} {'OK':<6} {len(df):>7,} {latest:<12} {elapsed:>5.1f}s")
        except Exception as exc:  # noqa: BLE001 - diagnostic tool, report all
            elapsed = time.monotonic() - t0
            print(f"{name:<24} {'FAIL':<6} {'-':>7} {'-':<12} {elapsed:>5.1f}s")
            failures.append((name, describe_error(exc)))

    print("-" * 62)
    total = len(loader.SOURCES)
    if not failures:
        print(f"✅ 전체 {total}개 소스 정상 — 앱이 실시간 데이터로 동작합니다.")
        return 0
    print(f"⚠️ {total}개 중 {len(failures)}개 실패:")
    for name, reason in failures:
        print(f"  - {name}: {reason}")
    print(
        "\n실패한 소스가 있어도 앱은 캐시/샘플 데이터로 동작합니다.\n"
        "지속적으로 실패하면 위 출력을 GitHub 이슈로 남겨주세요."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
