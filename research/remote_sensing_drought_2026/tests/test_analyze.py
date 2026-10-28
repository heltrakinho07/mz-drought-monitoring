"""Synthetic unit-test fixtures are NOT research observations."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze import add_indices, lag_metrics, load_monthly


def fixture_data():
    rng = np.random.default_rng(7)
    dates = pd.date_range("2003-01-01", "2025-12-01", freq="MS")
    data = pd.DataFrame({
        "region": "Synthetic province A",
        "date": dates,
        "precip_mm": 80 + 15 * np.sin(np.arange(len(dates)) * np.pi / 6) + rng.uniform(1, 25, len(dates)),
        "ndvi": 0.45 + 0.10 * np.sin(np.arange(len(dates)) * np.pi / 6) + rng.normal(0, 0.025, len(dates)),
        "source": "earth_engine",  # unit-test plumbing only; synthetic, never export as research CSV
    })
    return data


def test_reject_demo_data(tmp_path):
    f = tmp_path / "demo.csv"
    df = fixture_data()
    df["source"] = "demo"
    df.to_csv(f, index=False)
    with pytest.raises(ValueError, match="demo data rejected"):
        load_monthly(f)


def test_reject_duplicate_months(tmp_path):
    f = tmp_path / "duplicate.csv"
    df = fixture_data()
    pd.concat([df, df.iloc[[0]]], ignore_index=True).to_csv(f, index=False)
    with pytest.raises(ValueError, match="Duplicate"):
        load_monthly(f)


def test_calibration_does_not_use_holdout_values():
    df = fixture_data()
    a = add_indices(df)
    changed = df.copy()
    changed.loc[changed["date"] > "2020-12-01", "ndvi"] = 0.9
    changed.loc[changed["date"] > "2020-12-01", "precip_mm"] = 200.0
    b = add_indices(changed)
    mask = a["date"] <= "2020-12-01"
    np.testing.assert_allclose(a.loc[mask, "spi3"], b.loc[mask, "spi3"], equal_nan=True)
    np.testing.assert_allclose(a.loc[mask, "vci"], b.loc[mask, "vci"], equal_nan=True)


def test_lag_metrics_have_holdout_and_bounded_correlations():
    indexed = add_indices(fixture_data())
    report = lag_metrics(indexed, max_lag=2)
    assert list(report["lag_months"]) == [0, 1, 2]
    assert report["n_test"].eq(60).all()
    assert report["pearson_holdout"].between(-1, 1).all()
    assert (report["holdout_ci_low"] <= report["holdout_ci_high"]).all()
