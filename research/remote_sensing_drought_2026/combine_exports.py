"""Verify and merge yearly GEE Drive exports into a scientifically audited CSV.

The 'source' field is only a consistency gate, not cryptographic proof of origin.
Review Drive/EE task logs and remote dataset provenance independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

REQUIRED = {
    "region", "region_code", "date", "precip_mm", "ndvi", "source",
    "n_chirps_days", "n_modis_scenes", "ndvi_valid_fraction",
}


def merge_exports(
    folder: Path, start_year: int, end_year: int,
    expected_regions: int = 11, minimum_valid_fraction: float = 0.05
) -> tuple[pd.DataFrame, list[dict]]:
    if not 2003 <= start_year <= end_year <= 2025:
        raise ValueError("Expected analysis years between 2003 and 2025")
    if not (0 < minimum_valid_fraction <= 1):
        raise ValueError("minimum_valid_fraction must be in (0, 1]")
    if expected_regions < 1:
        raise ValueError("expected_regions must be positive")
    data = []
    sources = []
    for year in range(start_year, end_year + 1):
        p = folder / f"mz_drought_{year}.csv"
        if not p.is_file():
            raise ValueError(f"Missing yearly Earth Engine Drive export: {p}")
        blob = p.read_bytes()
        sources.append({"file": p.name, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)})
        df = pd.read_csv(p, dtype={"region": str, "source": str, "region_code": str})
        missing = REQUIRED.difference(df.columns)
        if missing:
            raise ValueError(f"{p.name}: missing columns {sorted(missing)}")
        if df.empty or not df["source"].eq("earth_engine").all():
            raise ValueError(f"{p.name}: empty data or unverified origin tag")
        df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="raise")
        if (df["date"].dt.year != year).any() or (df["date"].dt.day != 1).any():
            raise ValueError(f"{p.name}: invalid month dates or wrong year")
        for key in ("precip_mm", "ndvi", "n_chirps_days", "n_modis_scenes", "ndvi_valid_fraction"):
            df[key] = pd.to_numeric(df[key], errors="raise")
        if df[["precip_mm", "ndvi", "n_chirps_days", "n_modis_scenes", "ndvi_valid_fraction"]].isna().any().any():
            raise ValueError(f"{p.name}: missing measurements or QA indicators")
        if (df["precip_mm"] < 0).any() or not df["ndvi"].between(-1, 1).all():
            raise ValueError(f"{p.name}: physically invalid NDVI/precipitation")
        if not df["region"].notna().all() or df["region"].str.strip().eq("").any():
            raise ValueError(f"{p.name}: invalid province name")
        if not df["region_code"].notna().all() or df["region_code"].str.strip().eq("").any():
            raise ValueError(f"{p.name}: missing GAUL province code")
        if not (df["n_chirps_days"] == df["date"].dt.days_in_month).all():
            raise ValueError(f"{p.name}: incomplete CHIRPS daily coverage")
        if not (df["n_modis_scenes"] >= 1).all():
            raise ValueError(f"{p.name}: absent MODIS composites")
        if not df["ndvi_valid_fraction"].between(minimum_valid_fraction, 1).all():
            raise ValueError(f"{p.name}: NDVI coverage below threshold or >100%; inspect QA")
        if df.duplicated(["region_code", "date"]).any():
            raise ValueError(f"{p.name}: duplicate province/month observations")
        if df["region_code"].nunique() != expected_regions:
            raise ValueError(f"{p.name}: expected {expected_regions} province codes, "
                             f"got {df['region_code'].nunique()}")
        months_per_region = df.groupby("region_code")["date"].nunique()
        if not months_per_region.eq(12).all() or len(df) != expected_regions * 12:
            raise ValueError(f"{p.name}: incomplete month coverage")
        data.append(df)
    merged = pd.concat(data, ignore_index=True).sort_values(["region_code", "date"])
    codes_per_name = merged.groupby("region")["region_code"].nunique()
    names_per_code = merged.groupby("region_code")["region"].nunique()
    if (codes_per_name > 1).any() or (names_per_code > 1).any():
        raise ValueError("GAUL province identifiers are inconsistent across years")
    if merged.duplicated(["region_code", "date"]).any():
        raise ValueError("Duplicate province/month across yearly exports")
    return merged, sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path, help="Folder of downloaded yearly mz_drought_YYYY.csv files")
    parser.add_argument("--output", required=True, type=Path, help="Output verified_monthly.csv")
    parser.add_argument("--start-year", type=int, default=2003)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--expected-regions", type=int, default=11)
    parser.add_argument("--minimum-valid-fraction", type=float, default=0.05)
    args = parser.parse_args()
    merged, source_files = merge_exports(
        args.input_dir, args.start_year, args.end_year,
        args.expected_regions, args.minimum_valid_fraction
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)
    manifest = {
        "status": "source-tagged GEE export, validated structurally (not independently authenticated)",
        "period": [args.start_year, args.end_year],
        "rows": len(merged),
        "regions": sorted(merged["region"].unique().tolist()),
        "collections": {
            "precipitation": "UCSB-CHG/CHIRPS/DAILY",
            "vegetation": "MODIS/061/MOD13Q1",
            "boundaries": "FAO/GAUL/2015/level1",
        },
        "source_files": source_files,
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "note": "Verify actual EE task provenance, collection versions, spatial method and original records separately",
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Validated {len(merged)} region-month observations. CSV: {args.output}")
    print(f"Input checksums and provenance checklist: {manifest_path}")


if __name__ == "__main__":
    main()
