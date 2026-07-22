"""Google Earth Engine extraction helpers for the Mozambique (Gaza) drought monitoring project.

Requires an authenticated Earth Engine session, set up once from the notebook/shell — not here,
since a helper module shouldn't authenticate as a side effect of being imported:
    earthengine authenticate
    ee.Initialize(project="geoprocessamento-426809")
"""

import ee
import pandas as pd

# Gaza province, southern Mozambique — real admin boundary (GADM level 3, dissolved to the
# province via NAME_1), not a bounding box. Asset must be accessible to the authenticated user.
GAZA_AOI = (
    ee.FeatureCollection("projects/eengine-project/assets/distritos/gadm41_MOZ_3")
    .filter(ee.Filter.eq("NAME_1", "Gaza"))
    .geometry()
)

COLLECTIONS = {
    "smap_soil_moisture": "NASA_USDA/HSL/SMAP10KM_soil_moisture",
    "sentinel1": "COPERNICUS/S1_GRD",
    "sentinel2_sr": "COPERNICUS/S2_SR_HARMONIZED",
    "modis_lst": "MODIS/061/MOD11A2",
    "chirps_precip": "UCSB-CHG/CHIRPS/DAILY",
    "era5_land": "ECMWF/ERA5_LAND/DAILY_AGGR",
}

# SCL (Scene Classification Layer) codes to drop: 3 cloud shadow, 8/9 cloud medium/high
# probability, 10 cirrus. See Sentinel-2 L2A product spec.
_S2_CLOUD_SCL_CODES = [3, 8, 9, 10]


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
    ic = ee.ImageCollection(collection_id).filterDate(start, end).filterBounds(aoi).select(band)

    def _reduce(img):
        stats = img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e9)
        return ee.Feature(None, {
            "date": img.date().format("YYYY-MM-dd"),
            band: stats.get(band),
        })

    fc = ic.map(_reduce).filter(ee.Filter.notNull([band]))
    features = fc.getInfo()["features"]
    rows = [f["properties"] for f in features]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


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
    ic = (
        ee.ImageCollection(COLLECTIONS["sentinel2_sr"])
        .filterDate(start, end)
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

    fc = ic.map(_reduce).filter(ee.Filter.notNull(["NDVI"]))
    features = fc.getInfo()["features"]
    rows = [f["properties"] for f in features]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


def sentinel1_vv_time_series(aoi: ee.Geometry, start: str, end: str, scale: int = 100) -> pd.DataFrame:
    """VV backscatter mean over `aoi`, filtered to IW mode / descending pass for consistency."""
    ic = (
        ee.ImageCollection(COLLECTIONS["sentinel1"])
        .filterDate(start, end)
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

    fc = ic.map(_reduce).filter(ee.Filter.notNull(["VV"]))
    features = fc.getInfo()["features"]
    rows = [f["properties"] for f in features]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df
