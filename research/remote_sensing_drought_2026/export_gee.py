"""Export observed monthly CHIRPS precipitation and MOD13Q1 NDVI from Earth Engine.

Exports one CSV *per year* to your own Google Drive. No simulated results.
By default this only prints the plan and never starts a paid/quota-consuming task.
"""
from __future__ import annotations

import argparse
import calendar

START_YEAR = 2003
END_YEAR = 2025
COLLECTIONS = {
    "precip": "UCSB-CHG/CHIRPS/DAILY",
    "vegetation": "MODIS/061/MOD13Q1",
    "regions": "FAO/GAUL/2015/level1",
}
SELECTORS = [
    "region", "region_code", "date", "precip_mm", "ndvi", "source",
    "n_chirps_days", "n_modis_scenes", "ndvi_valid_fraction",
]


def validate_year_range(start_year: int, end_year: int) -> list[int]:
    if not (START_YEAR <= start_year <= end_year <= END_YEAR):
        raise ValueError(f"Require {START_YEAR} <= start-year <= end-year <= {END_YEAR}")
    return list(range(start_year, end_year + 1))


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def ndvi_with_qa(ee, image):
    """MOD13Q1 VI good or marginal (SummaryQA 0 or 1); scale NDVI to [-1,1]."""
    valid = image.select("SummaryQA").lte(1)
    return image.select("NDVI").updateMask(valid).multiply(0.0001).rename("ndvi")


def year_collection(ee, year: int, regions, ndvi_scale: int = 1000):
    """Create a server-side FeatureCollection of region/month measurements.

    CHIRPS is summed in time then spatially averaged over each province.
    MODIS composite is averaged in time then spatially averaged, after QA.
    The spatial NDVI sample scale is configurable and approximate; it is
    NOT equivalent to a native 250 m per-pixel full-resolution assessment.
    """
    chirps = ee.ImageCollection(COLLECTIONS["precip"])
    modis = ee.ImageCollection(COLLECTIONS["vegetation"])

    def per_month(month: int):
        beginning = ee.Date.fromYMD(year, month, 1)
        end = beginning.advance(1, "month")
        ch = chirps.filterDate(beginning, end).select("precipitation")
        md = modis.filterDate(beginning, end)
        month_precip = ch.sum().rename("precip_mm")
        good_ndvi = md.map(lambda image: ndvi_with_qa(ee, image))
        month_ndvi = good_ndvi.mean().rename("ndvi")
        # Fraction of sampled pixels with >=1 QA-accepted observation this month.
        valid_pixels = good_ndvi.count().gt(0).unmask(0).rename("ndvi_valid_fraction")

        def per_region(region):
            geom = region.geometry()
            rain = month_precip.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geom,
                scale=5566, maxPixels=1_000_000_000, tileScale=4
            ).get("precip_mm")
            ndvi = month_ndvi.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geom,
                scale=ndvi_scale, maxPixels=1_000_000_000, tileScale=4
            ).get("ndvi")
            fraction = valid_pixels.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geom,
                scale=ndvi_scale, maxPixels=1_000_000_000, tileScale=4
            ).get("ndvi_valid_fraction")
            return ee.Feature(None, {
                "region": region.get("ADM1_NAME"),
                "region_code": region.get("ADM1_CODE"),
                "date": beginning.format("YYYY-MM-dd"),
                "precip_mm": rain,
                "ndvi": ndvi,
                "source": "earth_engine",
                "n_chirps_days": ch.size(),
                "n_modis_scenes": md.size(),
                "ndvi_valid_fraction": fraction,
            })

        return regions.map(per_region)

    return ee.FeatureCollection([per_month(m) for m in range(1, 13)]).flatten()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="GCP project registered and enabled for Earth Engine")
    parser.add_argument("--start-year", type=int, default=2003)
    parser.add_argument("--end-year", type=int, default=2003)
    parser.add_argument("--drive-folder", default="mz_drought_research_2026")
    parser.add_argument("--ndvi-scale", type=int, default=1000,
                        help="Sampling scale in metres; 1000m is an initial computational compromise")
    parser.add_argument("--authenticate", action="store_true", help="Open interactive GEE login if needed")
    parser.add_argument("--check-access", action="store_true", help="Test GEE access and province count; do not export")
    parser.add_argument("--start-tasks", action="store_true", help="Explicitly start Drive export jobs")
    parser.add_argument("--max-tasks", type=int, default=2,
                        help="Safety limit for number of yearly jobs started per invocation")
    args = parser.parse_args()

    years = validate_year_range(args.start_year, args.end_year)
    if not (250 <= args.ndvi_scale <= 10000):
        parser.error("ndvi-scale must be between 250 and 10000 metres")
    if args.max_tasks < 1:
        parser.error("max-tasks must be >=1")
    print("Project:", args.project)
    print("Years:", years)
    print("Collections:", COLLECTIONS)
    print("Drive folder:", args.drive_folder)
    print("NDVI sampling scale:", args.ndvi_scale, "metres")
    if not (args.check_access or args.start_tasks):
        print("PLAN ONLY. Add --check-access for connection test or --start-tasks to export.")
        return

    import ee  # imported only when GEE is actually requested
    if args.authenticate:
        ee.Authenticate()
    ee.Initialize(project=args.project)
    regions = ee.FeatureCollection(COLLECTIONS["regions"]).filter(
        ee.Filter.eq("ADM0_NAME", "Mozambique")
    )
    number = regions.size().getInfo()
    if not number:
        raise RuntimeError("No Mozambique provinces found in GAUL 2015; confirm dataset")
    print("Selected GAUL level-1 features:", number)
    if args.check_access:
        print("Connection and region query successful. No export started.")
        return
    if len(years) > args.max_tasks:
        raise ValueError(
            f"Refusing to start {len(years)} tasks; max-tasks={args.max_tasks}. "
            "Select fewer years or deliberately raise --max-tasks."
        )
    for year in years:
        collection = year_collection(ee, year, regions, args.ndvi_scale)
        name = f"mz_drought_{year}"
        task = ee.batch.Export.table.toDrive(
            collection=collection, description=name,
            folder=args.drive_folder, fileNamePrefix=name,
            fileFormat="CSV", selectors=SELECTORS,
        )
        task.start()
        print(f"Started {year}: task_id={task.id}; file={name}.csv")
    print("Tasks are asynchronous. Check Earth Engine Tasks, download completed Drive CSVs,")
    print("and combine with combine_exports.py. This script does not claim completed exports.")


if __name__ == "__main__":
    main()
