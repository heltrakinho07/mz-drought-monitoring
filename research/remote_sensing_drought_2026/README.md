# Research protocol — drought propagation in Mozambique

**Status: research scaffold, not a completed or submitted paper.** This folder is isolated from the Streamlit dashboard; its synthetic/demo fallback is NOT valid scientific input.

## Proposed article

**Working title:** *Evaluating Rainfall-to-Vegetation Drought Propagation Across Mozambique Using CHIRPS and MODIS: A Temporally Held-Out, Reproducible Analysis*

**Research question:** How does the association between precipitation deficits and vegetation condition vary by province and precipitation-to-vegetation lag, and how stable are those associations outside the historical calibration period?

**Hypotheses (to test, not results):**
1. The maximum precipitation–vegetation association occurs at different lags across provinces.
2. The strongest lag determined on historical data is not necessarily stable in an unseen period.
3. Province-aggregated signals may conceal substantial within-province heterogeneity.

## Journal fit and prior research

Target: *Remote Sensing* (MDPI), especially the **Applications of Remote Sensing in Hydrology and Ecology: Observations, Methods, and Innovations** special issue (advertised deadline 31 December 2026; verify again before submission).
- Journal scope: https://www.mdpi.com/journal/remotesensing/about
- CHIRPS/MODIS rainfall and vegetation response precedent (2026): https://doi.org/10.3390/rs18050768
- Integrated drought metrics precedent (2025): https://doi.org/10.3390/rs17213560
- Special issue: https://www.mdpi.com/journal/remotesensing/special_issues/ZE7FYV4TCI

**Novelty must be demonstrated**, not assumed. The prior work already uses CHIRPS, SPI, MODIS and VCI. Regional evidence, genuinely independent validation and uncertainty analysis will be needed for a competitive submission. In particular, **the current implementation is only a first-stage baseline, not enough on its own to justify publication**.

## Data contract (real observations only)

Create a CSV with one record per region and calendar month, with these columns:

| column | content |
|---|---|
| region | Stable province/district ID (same boundaries throughout analysis) |
| date | ISO calendar date YYYY-MM-DD; analysis uses calendar month |
| precip_mm | Monthly precipitation total (mm), derived from CHIRPS daily sums |
| ndvi | Monthly mean quality-masked MODIS NDVI, already multiplied by 0.0001 |
| source | Exactly 'earth_engine' for verified Earth Engine exports |

**Do not** export simulated fallback values from streamlit_app.py. Do not relabel synthetic data. Do not commit API credentials, private account keys, raw restricted data, or customer datasets.

Suggested processing: CHIRPS DAILY (UCSB-CHG/CHIRPS/DAILY); MODIS MOD13Q1 Collection 6.1 (MODIS/061/MOD13Q1), apply SummaryQA <= 1, NDVI scale factor 0.0001; harmonise temporal support and resolution, state province aggregation and spatial weights explicitly. GEE monthly export and source-file provenance tooling is now implemented in `export_gee.py` and `combine_exports.py` but has **not yet been executed against live Earth Engine data**. See `GEE_SETUP.md`. Authentication, real exports, validation and provenance verification remain outstanding.

## Initial reproducible baseline

The baseline script `analyze.py` in this folder:
- checks required columns, origin label, physical ranges, uniqueness and monthly continuity;
- computes SPI-3 using a fitted zero-adjusted gamma distribution **by region and calendar month**, on 2003–2020 only (requires sufficient calibration observations);
- computes season-specific VCI from MODIS NDVI minima/maxima on 2003–2020 only;
- evaluates Pearson associations between SPI-3 at t − lag and VCI at t, at lags 0–6 months;
- reports 2021–2025 holdout correlations with year-block-bootstrap intervals;
- outputs timeseries and lag metrics as CSVs.

**Limitations:** Bootstrap intervals based on five test years are unstable. Neither a lag correlation nor SPI/VCI co-variation establishes causality, true forecasting skill, or an independently validated drought classifier. The baseline does not yet handle spatial autocorrelation or change in land cover. Holdout years must not be used to select a lag or adjust the method.

## Earth Engine extraction (not yet run live)

Read [`GEE_SETUP.md`](GEE_SETUP.md) for project setup, safe authentication, one-year pilot exports and merging observed CSV files. Unit tests only use synthetic fixtures.

## Run locally with verified monthly CSV

    pip install -r research/remote_sensing_drought_2026/requirements.txt
    python research/remote_sensing_drought_2026/analyze.py --input /path/to/verified_monthly.csv --output-dir /path/to/results
    python -m pytest research/remote_sensing_drought_2026/tests -q

Outputs should be stored outside Git or assessed for size/license before committing. No real results are provided yet.

## Work still required before manuscript submission

1. Record reproducible Earth Engine ingestion/export scripts, collection versions, CRS, masks, scale, region provenance and availability.
2. Verify data completeness and NDVI QA percentages; compare area-aggregated vs district/pixel-based results.
3. Establish independent reference data (e.g., documented crop anomalies, external soil moisture or field records) with clearly defined independence and uncertainty.
4. Add cross-region generalization, spatial/temporal blocking, sensitivity to climatology window, NDVI compositing, indices and lag choice.
5. Include event-based drought performance metrics against independent references, confidence intervals, robust multiple-testing methodology, and a negative-results section.
6. Audit the literature for originality; document data/software versions; draft manuscript after real results exist.

## Scientific integrity

This scaffold is not a manuscript submission, peer-reviewed result, nor proof of publication suitability. Authors must confirm the eligibility and attribution of each data source. Figures/tables should not be fabricated. The demo dashboard and this research pipeline must remain distinguishable.
