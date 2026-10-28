"""Offline GEE-export checks. All fixture observations are synthetic and not results."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combine_exports import merge_exports
from export_gee import days_in_month, validate_year_range


def write_mock_year(folder: Path, year: int = 2003):
    rows = []
    for region in range(11):
        for month in range(1, 13):
            rows.append({
                "region": f"TEST_REGION_{region:02d}",
                "region_code": str(region),
                "date": f"{year}-{month:02d}-01",
                "precip_mm": 55 + region + month,
                "ndvi": 0.4,
                "source": "earth_engine",  # test fixture only: not real provenance
                "n_chirps_days": days_in_month(year, month),
                "n_modis_scenes": 2,
                "ndvi_valid_fraction": 0.75,
            })
    frame = pd.DataFrame(rows)
    frame.to_csv(folder / f"mz_drought_{year}.csv", index=False)
    return frame


def test_valid_month_length_and_year_range():
    assert days_in_month(2004, 2) == 29
    assert days_in_month(2003, 2) == 28
    assert validate_year_range(2003, 2005) == [2003, 2004, 2005]
    with pytest.raises(ValueError):
        validate_year_range(2025, 2026)


def test_combine_complete_year_and_provenance_hash(tmp_path):
    write_mock_year(tmp_path)
    frame, provenance = merge_exports(tmp_path, 2003, 2003)
    assert len(frame) == 132
    assert len(provenance) == 1
    assert len(provenance[0]["sha256"]) == 64


def test_combine_rejects_missing_day(tmp_path):
    frame = write_mock_year(tmp_path)
    frame.loc[0, "n_chirps_days"] = 12
    frame.to_csv(tmp_path / "mz_drought_2003.csv", index=False)
    with pytest.raises(ValueError, match="incomplete CHIRPS"):
        merge_exports(tmp_path, 2003, 2003)


def test_combine_rejects_low_ndvi_coverage(tmp_path):
    frame = write_mock_year(tmp_path)
    frame.loc[0, "ndvi_valid_fraction"] = 0.01
    frame.to_csv(tmp_path / "mz_drought_2003.csv", index=False)
    with pytest.raises(ValueError, match="NDVI coverage"):
        merge_exports(tmp_path, 2003, 2003)


def test_combine_rejects_demo_source(tmp_path):
    frame = write_mock_year(tmp_path)
    frame["source"] = "demo"
    frame.to_csv(tmp_path / "mz_drought_2003.csv", index=False)
    with pytest.raises(ValueError, match="origin tag"):
        merge_exports(tmp_path, 2003, 2003)


def test_combine_rejects_missing_province(tmp_path):
    frame = write_mock_year(tmp_path)
    frame = frame[frame["region_code"] != "10"]
    frame.to_csv(tmp_path / "mz_drought_2003.csv", index=False)
    with pytest.raises(ValueError, match="expected 11"):
        merge_exports(tmp_path, 2003, 2003)
