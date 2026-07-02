"""Archive-file data availability.

Reusable across complex data types (hydrophone, seismometer, ADCP). Ports the
file-counting logic from the hydrophone dashboard (``Hydrophone.py`` /
``monitor.py``) and the availability plotting used in
``notebooks/read_fft_files.ipynb``:

  1. List archived files per expected extension over the last N days.
  2. Bucket files by day and extension (date parsed from filename YYYYMMDD).
  3. Compare per-day counts against an expected files-per-day rate.
  4. Derive a status + a per-day availability strip for the widget.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from core.parallel import thread_map
from core.status import EntityStatus, StatusLabel

_DATE_RE = re.compile(r"(\d{8})")


def _filename(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("filename") or entry.get("file") or ""
    return ""


def _file_date(entry: Any):
    if isinstance(entry, dict) and entry.get("dateFrom"):
        try:
            return datetime.fromisoformat(entry["dateFrom"].replace("Z", "+00:00")).date()
        except ValueError:
            pass
    match = _DATE_RE.search(_filename(entry))
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            return None
    return None


def get_files_info(client, device_code: str, extensions: list[str], days: int = 7) -> list[tuple[str, Any]]:
    """Return (extension, file_entry) tuples for the lookback window.

    Extension listings are fetched concurrently (they are independent ONC calls).
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    date_from = start.strftime("%Y-%m-%dT00:00:00.000Z")
    date_to = end.strftime("%Y-%m-%dT23:59:59.000Z")

    def fetch(ext: str) -> list[tuple[str, Any]]:
        return [(ext, entry) for entry in client.get_archive_files(device_code, ext, date_from, date_to)]

    files: list[tuple[str, Any]] = []
    for chunk in thread_map(fetch, extensions):
        files.extend(chunk)
    return files


def compute_availability(
    client,
    device_code: str,
    extensions: list[str],
    *,
    days: int = 7,
    expected_files_per_day: int = 288,
) -> dict[str, Any]:
    """Build a per-day availability summary + status for one device."""
    extensions = extensions or []
    files = get_files_info(client, device_code, extensions, days=days)

    by_date: dict[Any, dict[str, int]] = {}
    last_data = None
    recent: list[dict[str, Any]] = []
    for ext, entry in files:
        day = _file_date(entry)
        name = _filename(entry)
        if name:
            recent.append({"filename": name, "extension": ext, "date": day.isoformat() if day else None})
        if not day:
            continue
        bucket = by_date.setdefault(day, {})
        bucket[ext] = bucket.get(ext, 0) + 1
        if last_data is None or day > last_data:
            last_data = day

    recent.sort(key=lambda item: item["filename"], reverse=True)
    recent_files = recent[:15]

    today = datetime.now(timezone.utc).date()

    # A day is scored by its BEST-covered product (a device may only archive one
    # extension, so summing across expected extensions would understate it).
    day_cells: list[dict[str, Any]] = []
    good_days = 0
    partial_days = 0
    for offset in range(days):
        day = today - timedelta(days=offset)
        counts = by_date.get(day, {})
        total = sum(counts.values())
        best = max(counts.values()) if counts else 0
        frac = min(1.0, best / expected_files_per_day) if expected_files_per_day else 0.0
        if frac >= 0.8:
            level = "good"
            good_days += 1
        elif total > 0:
            level = "partial"
            partial_days += 1
        else:
            level = "none"
        day_cells.append(
            {
                "date": day.isoformat(),
                "counts": counts,
                "total": total,
                "frac": round(frac, 3),
                "level": level,
            }
        )
    day_cells.reverse()

    # Coverage = share of days with a full day of data (partial counts as half).
    coverage_pct = 100.0 * (good_days + 0.5 * partial_days) / days if days else 0.0
    status = _availability_status(last_data, coverage_pct, today)

    return {
        "days": day_cells,
        "last_data_date": last_data.isoformat() if last_data else None,
        "days_since_last_data": (today - last_data).days if last_data else None,
        "coverage_pct": round(coverage_pct, 1),
        "extensions": extensions,
        "expected_files_per_day": expected_files_per_day,
        "recent_files": recent_files,
        "status": status.to_dict(),
    }


def _availability_status(last_data, coverage_pct: float, today) -> EntityStatus:
    if last_data is None:
        return EntityStatus(StatusLabel.NO_DATA, "No archived files in window")
    days_since = (today - last_data).days
    if days_since >= 3:
        return EntityStatus(StatusLabel.NO_DATA, f"No data for {days_since} days")
    if coverage_pct >= 85:
        return EntityStatus(StatusLabel.GOOD, f"{coverage_pct:.0f}% day coverage")
    if coverage_pct >= 40:
        return EntityStatus(StatusLabel.INTERMITTENT, f"{coverage_pct:.0f}% day coverage")
    return EntityStatus(StatusLabel.BAD, f"{coverage_pct:.0f}% day coverage")
