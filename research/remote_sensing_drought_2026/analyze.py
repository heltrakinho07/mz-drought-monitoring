"""Reproducible preliminary precipitation–vegetation lag analysis.

This script intentionally rejects dashboard/demo data. It does not claim to
validate drought occurrence, forecast skill, or causality.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gamma, norm

TRAIN_END = pd.Timestamp("2020-12-01")
TEST_END = pd.Timestamp("2025-12-01")
START = pd.Timestamp("2003-01-01")
COLUMNS = {"region", "date", "precip_mm", "ndvi", "source"}


def load_monthly(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"region": str, "source": str})
    missing = COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if df.empty:
        raise ValueError("Empty input")
    if not df["source"].eq("earth_engine").all():
        raise ValueError("Only verified Earth Engine exports are allowed; demo data rejected")
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    if (df["date"].dt.day != 1).any():
        raise ValueError("Dates must represent the first day of each calendar month")
    df["precip_mm"] = pd.to_numeric(df["precip_mm"], errors="raise")
    df["ndvi"] = pd.to_numeric(df["ndvi"], errors="raise")
    if df[["precip_mm", "ndvi"]].isna().any().any():
        raise ValueError("Missing precipitation/NDVI values; resolve QA gaps explicitly")
    if (df["precip_mm"] < 0).any() or (~df["ndvi"].between(-1.0, 1.0)).any():
        raise ValueError("Physically invalid precipitation or scaled NDVI")
    if df["region"].isna().any() or (df["region"].str.strip() == "").any():
        raise ValueError("Region identifiers must be nonempty")
    if df.duplicated(["region", "date"]).any():
        raise ValueError("Duplicate region-month records")
    df = df.sort_values(["region", "date"]).reset_index(drop=True)
    if (df["date"] < START).any() or (df["date"] > TEST_END).any():
        raise ValueError("Analysis period must be within 2003–2025")
    for region, g in df.groupby("region"):
        periods = g["date"].dt.to_period("M").astype("int64").to_numpy()
        if len(periods) > 1 and not np.all(np.diff(periods) == 1):
            raise ValueError(f"Nonconsecutive months for {region}; do not interpolate silently")
    return df


def add_indices(df: pd.DataFrame) -> pd.DataFrame:
    """Use 2003–2020 ONLY for calibration; no test-period fitting."""
    out = df.copy().sort_values(["region", "date"]).reset_index(drop=True)
    out["month"] = out["date"].dt.month
    out["year"] = out["date"].dt.year
    out["p3"] = out.groupby("region", sort=False)["precip_mm"].transform(
        lambda s: s.rolling(3, min_periods=3).sum()
    )
    out["spi3"] = np.nan
    out["vci"] = np.nan
    for region, group in out.groupby("region"):
        calibration = group[group["date"] <= TRAIN_END]
        if calibration["year"].nunique() < 15:
            raise ValueError(f"Need at least 15 calibration years for {region}")
        for month in range(1, 13):
            cal_month = calibration[calibration["month"] == month]
            indices = group.index[(group["month"] == month)]
            low, high = cal_month["ndvi"].min(), cal_month["ndvi"].max()
            if not np.isfinite(high - low) or high <= low:
                raise ValueError(f"Unusable NDVI climatology for {region}, month {month}")
            out.loc[indices, "vci"] = (
                (out.loc[indices, "ndvi"] - low) / (high - low) * 100
            )
            vals = cal_month["p3"].dropna().to_numpy(dtype=float)
            positive = vals[vals > 0]
            if len(positive) < 10 or np.std(positive) <= 0:
                raise ValueError(f"Unusable SPI-3 gamma calibration for {region}, month {month}")
            alpha, _, scale = gamma.fit(positive, floc=0)
            p_zero = float(np.mean(vals == 0))
            target = out.loc[indices, "p3"].to_numpy(dtype=float)
            prob = p_zero + (1 - p_zero) * gamma.cdf(target, a=alpha, scale=scale)
            prob = np.clip(prob, 1e-6, 1 - 1e-6)
            transformed = norm.ppf(prob)
            transformed[~np.isfinite(target)] = np.nan
            out.loc[indices, "spi3"] = transformed
    return out


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 12 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _year_block_interval(frame: pd.DataFrame, seed: int, reps: int = 1000) -> tuple[float, float]:
    """Resample entire calendar years, retaining paired months (pilot uncertainty only)."""
    years = np.unique(frame["year"].to_numpy())
    if len(years) < 4:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    blocks = [frame[frame["year"] == year] for year in years]
    values: list[float] = []
    for _ in range(reps):
        picks = rng.integers(0, len(blocks), size=len(blocks))
        sample = pd.concat([blocks[i] for i in picks], ignore_index=True)
        r = _pearson(sample["lagged_spi3"].to_numpy(), sample["vci"].to_numpy())
        if np.isfinite(r):
            values.append(r)
    if len(values) < reps // 2:
        return float("nan"), float("nan")
    return tuple(float(v) for v in np.quantile(values, [0.025, 0.975]))


def lag_metrics(indexed: pd.DataFrame, max_lag: int = 6) -> pd.DataFrame:
    results: list[dict] = []
    for ordinal, (region, data) in enumerate(indexed.groupby("region")):
        data = data.sort_values("date").copy()
        for lag in range(max_lag + 1):
            data["lagged_spi3"] = data["spi3"].shift(lag)
            paired = data.dropna(subset=["lagged_spi3", "vci"])
            training = paired[paired["date"] <= TRAIN_END]
            holdout = paired[paired["date"] > TRAIN_END]
            if len(holdout) < 24:
                raise ValueError(f"Need >=24 holdout months for {region}")
            r_train = _pearson(training["lagged_spi3"].to_numpy(), training["vci"].to_numpy())
            r_test = _pearson(holdout["lagged_spi3"].to_numpy(), holdout["vci"].to_numpy())
            lo, hi = _year_block_interval(holdout, seed=2026 + ordinal * 100 + lag)
            results.append({
                "region": region, "lag_months": lag,
                "n_train": len(training), "n_test": len(holdout),
                "pearson_train": r_train, "pearson_holdout": r_test,
                "holdout_ci_low": lo, "holdout_ci_high": hi,
            })
    return pd.DataFrame(results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    original = load_monthly(args.input)
    indexed = add_indices(original)
    lagged = lag_metrics(indexed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    indexed.to_csv(args.output_dir / "monthly_indices.csv", index=False)
    lagged.to_csv(args.output_dir / "lag_correlations.csv", index=False)
    print("Baseline complete; validation against independent reference data remains pending.")


if __name__ == "__main__":
    main()
