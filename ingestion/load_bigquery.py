"""Load prepared places and the H3 grid from Parquet into BigQuery.

Uses Application Default Credentials.

Usage:
    uv run --with google-cloud-bigquery python ingestion/load_bigquery.py
"""

from __future__ import annotations

import os
from pathlib import Path

from google.cloud import bigquery

PROJECT = os.environ.get("GCP_PROJECT", "jakarta-geomarketing")
DATASET = os.environ.get("BQ_DATASET", "geomarketing")

PLACES_TABLE = f"{PROJECT}.{DATASET}.raw_places"
CELLS_TABLE = f"{PROJECT}.{DATASET}.raw_h3_cells"

PLACES_SCHEMA = [
    bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("name", "STRING"),
    bigquery.SchemaField("category", "STRING"),
    bigquery.SchemaField("category_alternates", "STRING", mode="REPEATED"),
    bigquery.SchemaField("basic_category", "STRING"),
    bigquery.SchemaField("confidence", "FLOAT"),
    bigquery.SchemaField("longitude", "FLOAT"),
    bigquery.SchemaField("latitude", "FLOAT"),
    bigquery.SchemaField("locality", "STRING"),
    bigquery.SchemaField("region", "STRING"),
    bigquery.SchemaField("country", "STRING"),
    bigquery.SchemaField("version", "INTEGER"),
    bigquery.SchemaField("h3_cell", "STRING"),
]

CELLS_SCHEMA = [
    bigquery.SchemaField("h3_cell", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("resolution", "INTEGER"),
    bigquery.SchemaField("center_lat", "FLOAT"),
    bigquery.SchemaField("center_lng", "FLOAT"),
    bigquery.SchemaField("boundary_wkt", "STRING"),
]

LOADS = [
    (Path("data/places_prepared.parquet"), PLACES_TABLE, PLACES_SCHEMA),
    (Path("data/h3_cells.parquet"), CELLS_TABLE, CELLS_SCHEMA),
]


def load(client: bigquery.Client, source: Path, table: str, schema: list) -> int:
    if not source.exists():
        raise SystemExit(f"missing {source}; run ingestion/prepare_places.py first")

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with source.open("rb") as handle:
        job = client.load_table_from_file(handle, table, job_config=job_config)
    job.result()

    loaded = client.get_table(table).num_rows
    print(f"loaded {loaded:,} rows into {table}")
    return loaded


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    for source, table, schema in LOADS:
        load(client, source, table, schema)

    checks = client.query(
        f"""
        SELECT
          (SELECT count(*) FROM `{PLACES_TABLE}`)                    AS places,
          (SELECT count(DISTINCT h3_cell) FROM `{PLACES_TABLE}`)     AS places_cells,
          (SELECT count(*) FROM `{CELLS_TABLE}`)                     AS grid_cells,
          (SELECT count(DISTINCT category) FROM `{PLACES_TABLE}`)    AS categories
        """
    ).result()
    for row in checks:
        print(
            f"places={row.places:,} | distinct place cells={row.places_cells:,} | "
            f"grid cells={row.grid_cells:,} | categories={row.categories:,}"
        )


if __name__ == "__main__":
    main()
