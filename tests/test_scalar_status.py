"""Tests for scalar status rules."""

import pandas as pd

from core.status import StatusLabel
from data_types.scalar_site.status_rules import evaluate_scalar_status


def test_no_data_when_empty():
    status = evaluate_scalar_status(pd.DataFrame(), {"lookback_hours": 24, "expected_interval_minutes": 60})
    assert status.label == StatusLabel.NO_DATA


def test_good_when_full_coverage():
    df = pd.DataFrame({"value": [float(i) for i in range(24)]})
    rules = {
        "lookback_hours": 24,
        "expected_interval_minutes": 60,
        "thresholds": {"good_min_coverage_pct": 85, "intermittent_min_coverage_pct": 30},
    }
    status = evaluate_scalar_status(df, rules)
    assert status.label == StatusLabel.GOOD
