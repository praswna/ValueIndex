"""Replace bundled sample CSVs with live data (CLI; also run by the
refresh-data GitHub Actions workflow).

For a GUI version that runs on your home machine — reaching sources that
block datacenter IPs (KRX, FINRA, AAII) — use `streamlit run collector.py`.

Run: python scripts/refresh_sample_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valueindex import collect  # noqa: E402


def main() -> None:
    meta = collect.load_meta()
    failures = []
    for name in collect.source_names():
        df, err = collect.collect_source(name)
        if df is not None:
            meta = collect.save_snapshot(name, df, meta)
            print(f"refreshed {name}: {len(df)} rows")
        else:
            failures.append(name)
            print(f"FAILED {name}: {err}")
    collect.write_meta(meta)

    ok = len(collect.source_names()) - len(failures)
    print(f"\n{ok}/{len(collect.source_names())} sources refreshed.")
    if failures:
        print(f"failed (previous files kept): {failures}")


if __name__ == "__main__":
    main()
