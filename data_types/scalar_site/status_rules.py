"""Scalar data status evaluation."""

from __future__ import annotations

import pandas as pd

from core.status import EntityStatus, StatusLabel


def evaluate_scalar_status(df: pd.DataFrame, rules: dict) -> EntityStatus:
    if df is None or df.empty:
        return EntityStatus(StatusLabel.NO_DATA, "No scalar data in lookback window")

    thresholds = rules.get("thresholds", {})
    good_min = float(thresholds.get("good_min_coverage_pct", 85))
    intermittent_min = float(thresholds.get("intermittent_min_coverage_pct", 30))

    lookback_hours = int(rules.get("lookback_hours", 24))
    expected_interval = int(rules.get("expected_interval_minutes", 60))
    expected_points = max(1, (lookback_hours * 60) // expected_interval)

    valid = df["value"].notna().sum()
    coverage_pct = 100.0 * valid / expected_points

    if coverage_pct >= good_min:
        if _looks_bad(df, rules):
            return EntityStatus(StatusLabel.BAD, "Data present but quality concerns")
        return EntityStatus(StatusLabel.GOOD, f"{coverage_pct:.0f}% coverage")

    if coverage_pct >= intermittent_min:
        return EntityStatus(StatusLabel.INTERMITTENT, f"{coverage_pct:.0f}% coverage")

    return EntityStatus(StatusLabel.NO_DATA, f"{coverage_pct:.0f}% coverage")


def _looks_bad(df: pd.DataFrame, rules: dict) -> bool:
    """Simple placeholder for per-instrument bad-data scripts."""
    bad_cfg = rules.get("bad_data", {})
    flatline_hours = float(bad_cfg.get("flatline_hours", 6))
    if len(df) < 3:
        return False

    values = df["value"].dropna()
    if values.empty:
        return True

    # Flat line detection: std dev near zero over substantial span
    if values.std(ddof=0) == 0 and len(values) > flatline_hours:
        return True
    return False
