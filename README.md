# Jakarta Geomarketing

![CI](https://github.com/akmalariq/jakarta-geomarketing/actions/workflows/ci.yml/badge.svg)

A location intelligence platform that scores retail and F&B site opportunities across
**DKI Jakarta** using H3 hexagons, built on 289,015 points of interest from
**Overture Maps**, modelled in **BigQuery** with **dbt**.

**Interactive map:** https://akmalariq.dev/projects/jakarta-geomarketing/

---

## The business question

*Where in Jakarta should a new F&B or retail outlet open?*

The model scores every H3 resolution 8 hexagon (roughly 0.7 km²) on three components:

| Component | Weight | Meaning |
|---|---|---|
| **demand_score** | 0.55 | Density of demand-generating places: offices, education, retail anchors, lodging, lifestyle, health, leisure |
| **diversity_score** | 0.25 | How many different demand categories are present, so mixed-use beats single-purpose |
| **low competition** | 0.20 | Inverse of F&B competitor density (coffee shops, cafes, restaurants, bakeries, bars and similar) |

```
opportunity = 0.55 * demand_score
            + 0.25 * diversity_score
            + 0.20 * (100 - competition_score)
```

The weights are **dbt variables**, not hardcoded values, and two data tests enforce that
they sum to 1.0 and that every score stays within 0 to 100.

## Architecture

```
Overture Maps places (GeoParquet, DKI Jakarta bbox)
        |
        v
Cloud Storage   gs://jakarta-geomarketing-raw/{raw,prepared}/
        |
        v
BigQuery        geomarketing.raw_places        (289,015 rows, with h3_cell)
                geomarketing.raw_h3_cells      (1,844 cells, with boundary WKT)
        |
        v
dbt             staging -> intermediate -> marts
                - staging.stg_places
                - intermediate.int_places_classified   (competitor vs demand)
                - intermediate.int_cell_metrics        (per-cell counts)
                - marts.fct_h3_cells                   (scores, tiers, ranks)
                - marts.fct_cell_category_mix          (drill-down detail)
        |
        v
JSON export     cells.json + cells-detail.json
        |
        v
MapLibre map    deployed as a static page (no runtime BigQuery access)
```

### Why H3 is computed in Python, not BigQuery

BigQuery's native spatial grid is **S2**, not H3; there is no `H3_LATLNG_TO_CELL` built-in.
Overture itself publishes places indexed to H3, so this project assigns cells with the
reference `h3` library during ingestion and keeps every piece of business logic
(classification, aggregation, normalisation, scoring) in dbt on BigQuery where it can be
tested and versioned.

## Repo layout

```
ingestion/prepare_places.py   flatten GeoParquet, extract lat/lng, assign H3 cells
ingestion/load_bigquery.py    load prepared parquet + grid into BigQuery
dbt/                          staging, intermediate, marts, 20 data tests
export/export_dashboard.py    query the marts and emit the dashboard JSON
dataflow/places_ingest.py     Dataflow (Apache Beam) variant of the ingestion step
terraform/                    Cloud Storage, BigQuery dataset, service account, IAM
docs/                         architecture, cost, caveats
tests/                        offline unit tests (no cloud credentials required)
```

## Quickstart

```bash
uv sync --dev

# 1. download and prepare the POI extract (DKI Jakarta bbox)
uv run --with overturemaps overturemaps download \
  --bbox=106.65,-6.40,107.00,-6.05 -f geoparquet -t place -o data/places_jakarta.parquet
uv run python ingestion/prepare_places.py

# 2. upload and load into BigQuery
gcloud storage cp data/places_prepared.parquet gs://<bucket>/prepared/
gcloud storage cp data/h3_cells.parquet gs://<bucket>/prepared/
uv run python ingestion/load_bigquery.py

# 3. transform and score
uv run --with dbt-bigquery dbt run --project-dir dbt --profiles-dir dbt
uv run --with dbt-bigquery dbt test --project-dir dbt --profiles-dir dbt

# 4. export for the dashboard
uv run python export/export_dashboard.py --output ../cloudflare/portfolio/projects/jakarta-geomarketing/cells.json
```

## What the data looks like

| Metric | Value |
|---|---|
| Places downloaded | 289,015 |
| Places in candidate cells | 286,101 |
| Distinct POI categories | 1,062 |
| H3 cells (resolution 8) | 1,844 built, 1,564 scored after the 25-place minimum |
| Demand POIs | 65,239 |
| F&B competitors | 49,630 |
| Prime cells (top quartile) | 391 |

## Cost

Everything runs inside Google Cloud's **always-free tier**, except the optional Dataflow
batch job:

| Service | Usage | Cost |
|---|---|---|
| Cloud Storage | about 40 MB | free tier (5 GB) |
| BigQuery storage | about 30 MB | free tier (10 GiB) |
| BigQuery queries | a few GB scanned | free tier (1 TiB/month) |
| dbt | runs on your machine | free |
| **Dataflow batch** | one job, 1 worker, about 5 minutes (ran to JOB_STATE_DONE) | **under $0.50** |

Services deliberately **not** used, because they are not in the free tier and the project
does not need them: Cloud SQL, Dataproc, Cloud Composer, Datastream. See `docs/ARCHITECTURE.md`.

### Not implemented yet

- **Scheduled refresh.** A Cloud Run Job plus Cloud Scheduler entry would rebuild the
  extract monthly. The Terraform here provisions the bucket, dataset, service account, and
  IAM roles, but the job and schedule are not wired. Region and runtime cost were sized
  for it.
- **Dataproc or Dataplex variant** of the transformation step, to widen the GCP service
  coverage beyond BigQuery, GCS, IAM, and Dataflow.
- **Transit accessibility**, using the Overture `transportation` theme instead of the
  places theme, which barely contains transit stations for Jakarta.
- **H3 resolution 9 drill-down** below the current resolution 8 cells.

## Honest caveats

1. **POI coverage is not uniform.** Overture places derive from OpenStreetMap, and mapping
   activity varies by neighbourhood. A low score can mean "quiet" or "under-mapped".
2. **This is a heuristic, not a validated model.** There is no sales, footfall, rent, or
   lease data, so the score has not been calibrated against revenue.
3. **Scores are relative to DKI Jakarta.** Normalisation is min-max within this dataset, so
   90 means "high for Jakarta", not "high globally".
4. **Not modelled:** opening hours, brands, price positioning, floor area, rent, competitor
   quality, and physical barriers such as rivers or toll roads. Distances are straight-line.

Full detail in `docs/CAVEATS.md`.

## Data attribution

Places data from **Overture Maps Foundation**, derived from **OpenStreetMap** contributors,
licensed **ODbL**. This project redistributes only derived aggregates.

## Stack

Python (DuckDB, h3, pandas, PyArrow) · Google Cloud Storage · BigQuery · dbt · Dataflow
(optional) · Terraform · MapLibre GL JS · GitHub Actions
