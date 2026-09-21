"""Dataflow (Apache Beam) batch job: assign H3 cells and land the result in BigQuery.

This is the managed-service variant of the local DuckDB step. The local path is used
for development speed; this path is what you would schedule in production, so the
pipeline runs without a laptop involved.

The job also gives us a useful control: `geomarketing.dataflow_places` must agree with
`geomarketing.raw_places` on every H3 cell assignment, which is checked by a dbt test.

Run:
    uv run --with "apache-beam[gcp]" python dataflow/places_ingest.py \
        --project jakarta-geomarketing \
        --region us-central1 \
        --runner DataflowRunner \
        --temp_location gs://jakarta-geomarketing-raw/temp \
        --staging_location gs://jakarta-geomarketing-raw/staging \
        --num_workers 1 --max_num_workers 1 --machine_type n1-standard-1
"""

from __future__ import annotations

import argparse
import logging

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions

H3_RESOLUTION = 8

BIGQUERY_SCHEMA = {
    "fields": [
        {"name": "id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "name", "type": "STRING"},
        {"name": "category", "type": "STRING"},
        {"name": "latitude", "type": "FLOAT"},
        {"name": "longitude", "type": "FLOAT"},
        {"name": "confidence", "type": "FLOAT"},
        {"name": "h3_cell", "type": "STRING"},
    ]
}

REQUIRED_FIELDS = ("id", "category", "latitude", "longitude")


class AssignH3Cell(beam.DoFn):
    """Attach the H3 cell for each place, dropping rows without a usable location."""

    def __init__(self, resolution: int = H3_RESOLUTION) -> None:
        self.resolution = resolution

    def setup(self) -> None:
        import h3

        self._h3 = h3

    def process(self, element: dict):
        for field in REQUIRED_FIELDS:
            if element.get(field) is None:
                return
        try:
            lat = float(element["latitude"])
            lng = float(element["longitude"])
        except (TypeError, ValueError):
            return

        yield {
            "id": element["id"],
            "name": element.get("name"),
            "category": element["category"],
            "latitude": lat,
            "longitude": lng,
            "confidence": element.get("confidence"),
            "h3_cell": self._h3.latlng_to_cell(lat, lng, self.resolution),
        }


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Dataflow ingestion for Jakarta geomarketing.")
    parser.add_argument("--input", required=True, help="GCS path to the prepared Parquet file")
    parser.add_argument("--table", required=True, help="BigQuery output table")
    parser.add_argument("--resolution", type=int, default=H3_RESOLUTION)
    known_args, pipeline_args = parser.parse_known_args(argv)

    options = PipelineOptions(pipeline_args)
    options.view_as(SetupOptions).save_main_session = True

    with beam.Pipeline(options=options) as pipeline:
        (
            pipeline
            | "ReadPreparedPlaces" >> beam.io.ReadFromParquet(known_args.input)
            | "AssignH3Cell" >> beam.ParDo(AssignH3Cell(known_args.resolution))
            | "WriteToBigQuery"
            >> beam.io.WriteToBigQuery(
                known_args.table,
                schema=BIGQUERY_SCHEMA,
                write_disposition=beam.io.BigQueryDisposition.WRITE_TRUNCATE,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                method=beam.io.WriteToBigQuery.Method.FILE_LOADS,
            )
        )


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    run()
