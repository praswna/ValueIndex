"""Build docs/data/*.json for the static site.

Run: python scripts/build_site_data.py [--force]
Used daily by .github/workflows/refresh-data.yml after the data refresh.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valueindex import sitebuild  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "data"


def main() -> None:
    force = "--force" in sys.argv
    statuses = sitebuild.build_site(OUT, force=force)
    by = {}
    for name, status in statuses.items():
        by.setdefault(status, []).append(name)
    for status, names in sorted(by.items()):
        print(f"{status}: {len(names)} sources")
    print(f"wrote {len(list(OUT.glob('*')))} files to {OUT}")


if __name__ == "__main__":
    main()
