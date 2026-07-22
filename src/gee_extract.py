"""Google Earth Engine extraction helpers for the Mozambique (Gaza) drought monitoring project.

Requires an authenticated Earth Engine session, set up once from the notebook/shell — not here,
since a helper module shouldn't authenticate as a side effect of being imported:
    earthengine authenticate
    ee.Initialize(project="geoprocessamento-426809")
"""

from datetime import date

import ee
import pandas as pd


def gaza_aoi() -> ee.Geometry:
    """Gaza province, southern Mozambique — real admin boundary (GADM level 3, dissolved to
    the province via NAME_1), not a bounding box. Asset must be accessible to the authenticated
    user. Built lazily (call after ee.Initialize()) rather than at module import time, since a
    module-level ee.FeatureCollection(...) call would run before the caller gets a chance to
    initialize the client.
    """
    return (
        ee.FeatureCollection("projects/eengine-project/assets/distritos/gadm41_MOZ_3")
        .filter(ee.Filter.eq("NAME_1", "Gaza"))
        .geometry()
    )


COLLECTIONS = {
    # L4 SPL4SMGP replaces the deprecated NASA_USDA/HSL/SMAP10KM_soil_moisture asset.
    # 3-hourly cadence, ~9km. Bands include sm_surface and sm_rootzone (root-zone moisture,
    # useful directly for drought monitoring instead of relying only on ERA5-Land for that).
    "smap_soil_moisture": "NASA/SMAP/SPL4SMGP/008",
    "sentinel1": "COPERNICUS/S1_GRD",
    "sentinel2_sr": "COPERNICUS/S2_SR_HARMONIZED",
    "modis_lst": "MODIS/061/MOD11A2",
    "chirps_precip": "UCSB-CHG/CHIRPS/DAILY",
    "era5_land": "ECMWF/ERA5_LAND/DAILY_AGGR",
}

# SCL (Scene Classification Layer) codes to drop: 3 cloud shadow, 8/9 cloud medium/high
# probability, 10 cirrus. See Sentinel-2 L2A product spec.
_S2_CLOUD_SCL_CODES = [3, 8, 9, 10]


def _month_chunks(start: str, end: str):
    """Yield (chunk_start, chunk_end) ISO date pairs covering [start, end) one month at a time."""
    cur = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    while cur < end_date:
        nxt = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
        chunk_end = min(nxt, end_date)
        yield cur.isoformat(), chunk_end.isoformat()
        cur = nxt


def _fetch_chunked(build_fc, value_key: str, start: str, end: str) -> pd.DataFrame:
    """Run `build_fc(chunk_start, chunk_end)` month by month and concatenate the results.

    A single getInfo() over a multi-year, sub-daily collection (e.g. 3-hourly SMAP over two
    years) can exceed Earth Engine's per-request memory limit ("User memory limit exceeded"),
    so long ranges are split into monthly chunks and stitched together client-side.
    """
    frames = []
    for chunk_start, chunk_end in _month_chunks(start, end):
        features = build_fc(chunk_start, chunk_end).getInfo()["features"]
        rows = [f["properties"] for f in features]
        if rows:
            frames.append(pd.DataFrame(rows))
    if not frames:
        return pd.DataFrame(columns=["date", value_key])
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def region_time_series(collection_id: str, band: str, aoi: ee.Geometry,
                        start: str, end: str, scale: int = 10000) -> pd.DataFrame:
    """Return a daily/native-cadence mean time series of `band` over `aoi`.

    Args:
        collection_id: Earth Engine ImageCollection id (see COLLECTIONS).
        band: band name to reduce.
        aoi: region to average over.
        start, end: ISO date strings, e.g. "2023-01-01".
        scale: reduction scale in meters (match the native resolution of the source).
    """
    def build_fc(chunk_start, chunk_end):
        ic = (
            ee.ImageCollection(collection_id)
            .filterDate(chunk_start, chunk_end)
            .filterBounds(aoi)
            .select(band)
        )

        def _reduce(img):
            stats = img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e9)
            return ee.Feature(None, {
                "date": img.date().format("YYYY-MM-dd"),
                band: stats.get(band),
            })

        return ic.map(_reduce).filter(ee.Filter.notNull([band]))

    return _fetch_chunked(build_fc, band, start, end)


def _mask_s2_clouds(image: ee.Image) -> ee.Image:
    scl = image.select("SCL")
    mask = ee.Image(1)
    for code in _S2_CLOUD_SCL_CODES:
        mask = mask.And(scl.neq(code))
    return image.updateMask(mask)


def sentinel2_ndvi_time_series(aoi: ee.Geometry, start: str, end: str,
                                scale: int = 100, max_cloud_pct: float = 40) -> pd.DataFrame:
    """NDVI mean over `aoi` from Sentinel-2 L2A (B8 NIR, B4 Red), cloud-masked via SCL.

    `scale` defaults to 100 m rather than the native 10 m: reduceRegion over a
    province-sized AOI at 10 m for every image in the collection is expensive and slow.
    Drop `scale` to 10-20 m once you shrink the AOI to a district/parcel-level test area
    (e.g. for the SAR downscaling follow-up project).
    """
    def build_fc(chunk_start, chunk_end):
        ic = (
            ee.ImageCollection(COLLECTIONS["sentinel2_sr"])
            .filterDate(chunk_start, chunk_end)
            .filterBounds(aoi)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
            .map(_mask_s2_clouds)
        )

        def _reduce(img):
            ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
            stats = ndvi.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e9)
            return ee.Feature(None, {
                "date": img.date().format("YYYY-MM-dd"),
                "NDVI": stats.get("NDVI"),
            })

        return ic.map(_reduce).filter(ee.Filter.notNull(["NDVI"]))

    return _fetch_chunked(build_fc, "NDVI", start, end)


def sentinel1_vv_time_series(aoi: ee.Geometry, start: str, end: str, scale: int = 100) -> pd.DataFrame:
    """VV backscatter mean over `aoi`, filtered to IW mode / descending pass for consistency."""
    def build_fc(chunk_start, chunk_end):
        ic = (
            ee.ImageCollection(COLLECTIONS["sentinel1"])
            .filterDate(chunk_start, chunk_end)
            .filterBounds(aoi)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .select("VV")
        )

        def _reduce(img):
            stats = img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e9)
            return ee.Feature(None, {
                "date": img.date().format("YYYY-MM-dd"),
                "VV": stats.get("VV"),
            })

        return ic.map(_reduce).filter(ee.Filter.notNull(["VV"]))

    return _fetch_chunked(build_fc, "VV", start, end)
