# Google Earth Engine (GEE) — scientific data collection

## Status and responsibilities

The extraction code is implemented and has **offline unit tests**. This does NOT prove live access, successful remote tasks, or scientific validity. A person with access to the appropriate Google account must enable/check the Cloud project, authenticate, launch exports, and obtain the outputs. Never share passwords, OAuth tokens, or service account JSON in GitHub or this chat.

### 1. Project prerequisites (browser)

1. Open https://console.cloud.google.com/ and select a Cloud Project you are permitted to use.
2. Verify the **Earth Engine API is enabled**.
3. Confirm the project is **registered** and approved for your appropriate noncommercial research eligibility, or configured for commercial billing where required. Noncommercial usage is governed by monthly Earth Engine compute-unit quotas; check tier before large exports.
4. Verify that your Google identity has access to the project and Earth Engine. The project ID is a CLI parameter; it is not a credential.
5. For interactive research, use your own user OAuth credentials. **No service account JSON is needed.**

Official instructions:
- https://developers.google.com/earth-engine/guides/access
- https://developers.google.com/earth-engine/guides/auth
- https://developers.google.com/earth-engine/guides/noncommercial_tiers

### 2. Install and confirm API access

With Python 3.11+ and a local terminal or GitHub Codespace (adjust remote OAuth auth_mode as documented by Google):

    pip install -r research/remote_sensing_drought_2026/requirements-gee.txt

Print planned exports **without login or starting tasks**:

    python research/remote_sensing_drought_2026/export_gee.py \
      --project YOUR_GCP_PROJECT_ID --start-year 2003 --end-year 2003

Log in once on your machine:

    earthengine authenticate

Test *live* access (no export started):

    python research/remote_sensing_drought_2026/export_gee.py \
      --project YOUR_GCP_PROJECT_ID --check-access

If browser login is needed, pass \`--authenticate\` in a supported environment. On a remote Codespace, use an authentication method supported by Google for remote environments. Do not put secret keys in Git or Actions.

### 3. One-year pilot — create actual CSV

    python research/remote_sensing_drought_2026/export_gee.py \
      --project YOUR_GCP_PROJECT_ID --start-year 2003 --end-year 2003 \
      --start-tasks

The script queues a Drive table-export task named \`mz_drought_2003\` to the folder \`mz_drought_research_2026\`; the task can be monitored in Earth Engine's Tasks tab or with the API. **Task initiation is not completion.** When completed, download \`mz_drought_2003.csv\` to a private local \`exports/\` directory. Inspect for missing values and consistency.

The full period is 2003–2025 inclusive: 23 yearly exports, one at a time (or a controlled batch with \`--max-tasks\`). Earth Engine jobs may be slow or exceed quotas. Run a small pilot first. Default NDVI sampling is 1000 m for reduced computation, despite the native 250 m MODIS product; assess the sensitivity to this approximation before publication.

**Data workflow:**
- GAUL 2015 level 1 regions of Mozambique;
- CHIRPS DAILY monthly **sum** per grid cell, then region **spatial mean** = region-average monthly precipitation (mm);
- MOD13Q1 SummaryQA 0/1 (good/marginal) mask, NDVI times \`0.0001\`, monthly **mean**, then region **spatial mean**;
- Report number of CHIRPS days, number of MODIS scenes and fraction of region sample pixels with >=1 accepted NDVI observation. All numbers are computed by Earth Engine after queuing a task.

### 4. Assemble a 2003–2025 CSV and run the first analysis

Save files as \`exports/mz_drought_2003.csv\` through \`exports/mz_drought_2025.csv\` (not tracked). Then:

    python research/remote_sensing_drought_2026/combine_exports.py \
      --input-dir exports \
      --output research/remote_sensing_drought_2026/data/verified_monthly.csv \
      --start-year 2003 --end-year 2025

    python research/remote_sensing_drought_2026/analyze.py \
      --input research/remote_sensing_drought_2026/data/verified_monthly.csv \
      --output-dir research/remote_sensing_drought_2026/results

Structural validation checks 11 regions, continuous monthly coverage, valid bounds, CHIRPS daily counts, MODIS image counts, QA fraction, and source tags. SHA256 manifests help establish local file integrity; they do **not** cryptographically prove the data came from GEE.

### 5. Scientific limitations and next steps

The analysis is **not yet publication ready**. Important:
- GAUL spatial geometry is a versioned boundary reference, not necessarily Mozambique's most recent official administrative boundaries. Validate geometry, naming and usage terms. GAUL terms restrict reuse of source boundary data to noncommercial purposes.
- The NDVI valid-pixel fraction uses sample pixels including non-vegetated areas and is an approximate data-availability diagnostic, **not** an agricultural valid-area percentage.
- Using all land cover types together causes heterogeneous vegetation responses; introduce agricultural/land-cover stratification, spatial weighting and pixel-scale sensitivity analyses.
- MODIS 16-day observations are assigned to months by image start dates. Examine temporal support and composites spanning months.
- Historical SPI gamma estimation is sensitive to zero rainfall and sample size. Compare against standard implementations and test fit assumptions.
- Seasonal VCI based on calibration minima and maxima can exceed 0–100 in unseen periods; this may be valid extrapolation and must not be clipped without justification.
- No ground truth is built into this pipeline. Need independent soil moisture / crop impacts / local station checks (not CHIRPS-derived precipitation reused as ground truth).
- Time-lag Pearson r is **association**, not causality or forecast skill. Avoid training/test leakage.
- The exact collection data version, QA choices, geometry, account registration tier, task IDs, exports, missingness and analysis scripts must be recorded in the methods section.

Do not cite unobserved results. The application's simulated/offline fallback is explicitly outside the scientific workflow.
