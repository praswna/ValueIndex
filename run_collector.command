#!/bin/bash
# ValueIndex 로컬 데이터 수집기 — 더블클릭으로 실행 (macOS)
# 저장소 폴더 안에 두고 더블클릭하면 브라우저에 수집기가 열립니다.
# (최초 1회: Finder에서 우클릭 → 열기 로 Gatekeeper 허용)

cd "$(dirname "$0")" || exit 1

if ! python3 -c "import valueindex" 2>/dev/null; then
  echo "[ValueIndex] 첫 실행 - 필요한 패키지를 설치합니다..."
  python3 -m pip install -e .
fi

echo "[ValueIndex] 수집기를 시작합니다. 브라우저가 열립니다..."
python3 -m streamlit run collector.py
