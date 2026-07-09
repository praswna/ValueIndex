#!/bin/bash
# ValueIndex 로컬 데이터 수집기 — 더블클릭으로 실행 (macOS)
# 저장소 폴더 안에 두고 더블클릭하면 수집기 창이 열립니다.
# (최초 1회: Finder에서 우클릭 → 열기 로 Gatekeeper 허용)

cd "$(dirname "$0")" || exit 1

if ! python3 -c "import valueindex, markdown" 2>/dev/null; then
  echo "[ValueIndex] 첫 실행 - 필요한 패키지를 설치합니다..."
  python3 -m pip install -e ".[site]"
fi

echo "[ValueIndex] 수집기 창을 엽니다..."
python3 collector_gui.py
