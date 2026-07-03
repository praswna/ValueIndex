"""Replace bundled sample CSVs with live data (run on a networked machine).

Run: python scripts/refresh_sample_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valueindex import config, loader  # noqa: E402


def main() -> None:
    config.SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for name, (fetch_fn, _) in loader.SOURCES.items():
        try:
            df = fetch_fn()
            df.to_csv(config.SAMPLE_DATA_DIR / f"{name}.csv", index=False)
            print(f"refreshed {name}: {len(df)} rows")
        except Exception as exc:  # noqa: BLE001
            failures.append(name)
            print(f"FAILED {name}: {exc}")
    if failures:
        print(f"\n{len(failures)} source(s) failed: {failures}")
        print("Existing sample files for those sources were left untouched.")


if __name__ == "__main__":
    main()
