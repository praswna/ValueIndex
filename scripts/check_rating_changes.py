"""Compare two overview.json files and print rating-band changes.

Used by the refresh-data workflow: it snapshots overview.json before the
refresh, rebuilds, then runs this. Non-empty stdout means "changes" and the
workflow opens a GitHub issue with the output as the body.

Run: python scripts/check_rating_changes.py <old_overview.json> <new_overview.json>
Exit code is always 0 (absence of changes is not an error).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valueindex import alerts  # noqa: E402


def main() -> None:
    old_path, new_path = Path(sys.argv[1]), Path(sys.argv[2])
    if not old_path.exists() or not new_path.exists():
        return  # first run or build failure -> nothing to compare
    try:
        old = json.loads(old_path.read_text(encoding="utf-8"))
        new = json.loads(new_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    lines = alerts.diff_overview(old, new)
    if lines:
        print(alerts.issue_body(lines))


if __name__ == "__main__":
    main()
