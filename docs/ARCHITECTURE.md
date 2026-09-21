# Architecture

## Flow

```
1. Extract      Overture Maps CLI, bbox 106.65,-6.40,107.00,-6.05 (DKI Jakarta)
                -> data/places_jakarta.parquet (289,019 rows, 53.6 MB)

2. Prepare      DuckDB reads GeoParquet, extracts lon/lat from WKB, flattens structs
                -> data/places_prepared.parquet
                h3 library assigns an H3 resolution 8 cell to each place
                -> data/h3_cells.parquet (boundary WKT + centre per cell)

3. Load         Cloud Storage  gs://jakarta-geomarketing-raw/{raw,prepared}/
                BigQuery  geomarketing.raw_places      (289,015 rows)
                          geomarketing.raw_h3_cells    (1,844 rows)

4. Model        dbt on BigQuery
                  staging.stg_places
                  intermediate.int_places_classified   competitor / demand / other
                  intermediate.int_cell_metrics        per-cell counts and diversity
                  marts.fct_h3_cells                   scores, tiers, ranks
                  marts.fct_cell_category_mix          drill-down detail

5. Export       export/export_dashboard.py -> cells.json (587 KB) + cells-detail.json (990 KB)

6. Serve        Static MapLibre page on akmalariq.dev, no runtime BigQuery access
```

## Design decisions

### H3 is assigned in Python, not in BigQuery

BigQuery's native spatial grid is **S2**. There is no `H3_LATLNG_TO_CELL` built-in, which
this project confirmed by probing the function directly. Options were:

1. Deploy the community H3 user-defined functions into the project, or
2. assign cells with the reference `h3` library during preparation, or
3. switch to S2 cells, which BigQuery does support natively.

Option 2 was chosen: Overture itself publishes places indexed to H3, H3 hexagons render
well on a web map, and it keeps the cell assignment in one place instead of adding a
deployment step for UDFs. **All business logic still runs in dbt on BigQuery**, so the
classification, aggregation, normalisation, and scoring remain testable and versioned.

### Candidate cells are filtered to at least 25 places

A hexagon with two POIs at the edge of the bounding box is an artefact of the extract
boundary, not a market. Including those cells would distort min-max normalisation, so
`min_places_per_cell` (a dbt variable, default 25) drops them: 1,844 built cells become
1,564 scored cells.

### Scores are normalised, not absolute

`demand_score` and `competition_score` are min-max normalised across the candidate cells
in this dataset. A score of 90 therefore means "high for DKI Jakarta". Comparing two
cities would require a shared baseline, which this project does not claim to provide.

### Weights are configuration, not code

The opportunity formula reads its three weights from dbt variables. Two data tests guard
it: one asserts the weights sum to 1.0, another asserts every score and component lands
within 0 to 100. Changing the weighting is a one-line change with an automatic check.

### The dashboard is static

The page fetches two JSON files. There is no API, no key, and no BigQuery call at runtime,
so it cannot fail under load and costs nothing to host. Category detail is a separate file
loaded only when a visitor opens a cell, which halves the initial payload.

## Cost

| Service | This project's usage | Free tier | Cost |
|---|---|---|---|
| Cloud Storage | ~40 MB | 5 GB/month | $0 |
| BigQuery storage | ~30 MB | 10 GiB/month | $0 |
| BigQuery queries | a few GB scanned per full rebuild | 1 TiB/month | $0 |
| Dataflow batch (optional) | 1 job, 1 worker, minutes | none | ~$1-3 |
| Cloud Run + Scheduler (if wired) | seconds/month | 2M requests, 3 jobs | $0 |

**Deliberately excluded because they are not in the always-free tier:** Cloud SQL,
Dataproc, Cloud Composer, Datastream. This project does not need them, and saying so is
more useful than quietly running up a bill.

The region is `us-central1` throughout, because the Cloud Storage free tier applies to US
regions and co-locating storage with BigQuery keeps load jobs free of egress.
