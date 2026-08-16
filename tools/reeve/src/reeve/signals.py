"""The one I/O seam — build a snapshot from the repo's committed files.

Unlike the backlog groomer (which GETs live issues), Reeve's pulse is read
entirely from committed files: the telemetry log, the live preview sizes, and
the telemetry report. There is no network read at all — the tool holds no
token, and the scheduled workflow's only write is the sticky report issue it
renders. Kept a separate module (imported lazily by the CLI) so the pure
detector/report core needs no filesystem walk to run over a fixed snapshot.
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

# The preview size caps, from scripts/preview-budget.sh (the single source of
# truth). Kept in sync with that file by convention; the telemetry writer
# sources the same two values, so a committed record can never disagree.
MAX_GIF_BYTES = 6 * 1024 * 1024
MAX_SHOT_BYTES = 3 * 1024 * 1024

# The first-line marker of telemetry/REPORT.md's empty-state placeholder.
_PLACEHOLDER = "_No gate runs recorded yet"


def parse_log(text: str) -> list[dict]:
    """Parse telemetry/log.ndjson text into its gate-run records.

    NDJSON, oldest-first. Blank lines are skipped; a malformed line or one
    missing ``schema``/``kind`` raises with its 1-indexed line number, the
    same fail-loud discipline ``tools/telemetry`` uses — a corrupt committed
    line is corruption to fix, not history to silently drop. Only
    ``kind == "gate-run"`` records are returned (future kinds may interleave).
    """
    records: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"telemetry/log.ndjson:{lineno}: not valid JSON ({exc})") from None
        if not isinstance(rec, dict) or "schema" not in rec or "kind" not in rec:
            raise ValueError(
                f"telemetry/log.ndjson:{lineno}: record must be an object with 'schema' and 'kind'"
            )
        if rec.get("kind") == "gate-run":
            records.append(rec)
    return records


def _headroom(size: int, budget: int) -> float:
    """Percent of the budget still free — the same formula tools/telemetry uses."""
    return round((budget - size) * 100.0 / budget, 1)


def scan_previews(root: str) -> list[dict]:
    """Every committed preview GIF/PNG with its size headroom, worst-first."""
    out: list[dict] = []
    for ext, budget in ((".gif", MAX_GIF_BYTES), (".png", MAX_SHOT_BYTES)):
        pattern = os.path.join(root, "designs", "*", "previews", "*" + ext)
        for path in glob.glob(pattern):
            size = os.stat(path).st_size
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            out.append(
                {"file": rel, "bytes": size, "budget": budget, "headroom_pct": _headroom(size, budget)}
            )
    out.sort(key=lambda p: (p["headroom_pct"], p["file"]))
    return out


def _now_iso(now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def gather_snapshot(root: str = ".", now: Optional[datetime] = None) -> dict[str, Any]:
    """Read the committed pulse for ``root`` into a snapshot dict."""
    log_path = os.path.join(root, "telemetry", "log.ndjson")
    text = ""
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as fh:
            text = fh.read()
    records = parse_log(text)

    report_path = os.path.join(root, "telemetry", "REPORT.md")
    report_placeholder = True
    if os.path.exists(report_path):
        with open(report_path, encoding="utf-8") as fh:
            report_placeholder = _PLACEHOLDER in fh.read()

    return {
        "generatedAt": _now_iso(now),
        "records": records,
        "previews": scan_previews(root),
        "reportPlaceholder": report_placeholder,
    }
