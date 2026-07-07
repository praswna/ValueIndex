"""Replace bundled sample CSVs with live data (run on a networked machine
or by the refresh-data GitHub Actions workflow).

Successful sources also get their refresh time recorded in
``sample_data/_meta.json`` so the app loader can treat fresh files as a
real-data snapshot and skip network fetches on cold start.

Run: python scripts/refresh_sample_data.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valueindex import config, loader  # noqa: E402

META_PATH = config.SAMPLE_DATA_DIR / "_meta.json"


def main() -> None:
    config.SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    meta: dict[str, str] = {}
    if META_PATH.exists():
        try:
            meta = json.loads(META_PATH.read_text())
        except json.JSONDecodeError:
            meta = {}

    now = datetime.now(timezone.utc).isoformat()
    failures = []
    for name, (fetch_fn, _) in loader.SOURCES.items():
        try:
            df = fetch_fn()
            if df is None or df.empty:
                raise ValueError("fetch returned no rows")
            df.to_csv(config.SAMPLE_DATA_DIR / f"{name}.csv", index=False)
            meta[name] = now
            print(f"refreshed {name}: {len(df)} rows")
        except Exception as exc:  # noqa: BLE001
            failures.append(name)
            print(f"FAILED {name}: {exc}")

    META_PATH.write_text(json.dumps(meta, indent=1, sort_keys=True))

    ok = len(loader.SOURCES) - len(failures)
    print(f"\n{ok}/{len(loader.SOURCES)} sources refreshed.")
    if failures:
        print(f"failed (previous files kept): {failures}")


if __name__ == "__main__":
    main()
