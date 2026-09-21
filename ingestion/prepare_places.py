"""Flatten Overture places and attach an H3 grid.

Overture ships geometry as WKB in CRS84. BigQuery and the dashboard want plain
latitude and longitude, so this step extracts coordinates, flattens the nested
structs, and assigns each place to an H3 cell.

Note on H3: BigQuery's native grid is S2, not H3. Overture itself publishes places
indexed to H3, so the cell assignment happens here with the reference h3 library,
and all aggregation and scoring happens downstream in dbt on BigQuery.

Outputs:
    data/places_prepared.parquet  one row per place, with h3_cell
    data/h3_cells.parquet         one row per cell, with boundary WKT and centre

Usage:
    uv run --with duckdb --with h3 --with pandas --with pyarrow \
        python ingestion/prepare_places.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import h3
import pandas as pd

MIN_LNG, MIN_LAT, MAX_LNG, MAX_LAT = 106.65, -6.40, 107.00, -6.05
H3_RESOLUTION = 8

FLATTEN_SQL = """
COPY (
    SELECT
        id,
        names.primary                            AS name,
        categories.primary                       AS category,
        categories.alternate                     AS category_alternates,
        basic_category,
        confidence,
        ST_X(geometry)                           AS longitude,
        ST_Y(geometry)                           AS latitude,
        addresses[1].locality                    AS locality,
        addresses[1].region                      AS region,
        addresses[1].country                     AS country,
        version
    FROM read_parquet('{input_path}')
    WHERE geometry IS NOT NULL
      AND confidence IS NOT NULL
      AND ST_X(geometry) BETWEEN {min_lng} AND {max_lng}
      AND ST_Y(geometry) BETWEEN {min_lat} AND {max_lat}
) TO '{flat_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
"""


def cell_boundary_wkt(cell: str) -> str:
    """Closed WKT polygon ring for an H3 cell (longitude latitude order)."""

    vertexes = h3.cell_to_vertexes(cell)
    ring = [h3.vertex_to_latlng(v) for v in vertexes]
    coords = [(lng, lat) for lat, lng in ring]
    coords.append(coords[0])
    body = ", ".join(f"{lng:.6f} {lat:.6f}" for lng, lat in coords)
    return f"POLYGON(({body}))"


def main() -> None:
    parser = argparse.ArgumentParser(description="Flatten Overture places and add an H3 grid.")
    parser.add_argument("--input", default="data/places_jakarta.parquet")
    parser.add_argument("--places-output", default="data/places_prepared.parquet")
    parser.add_argument("--cells-output", default="data/h3_cells.parquet")
    parser.add_argument("--resolution", type=int, default=H3_RESOLUTION)
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    flat_path = data_dir / "places_flat.parquet"

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(
        FLATTEN_SQL.format(
            input_path=input_path,
            flat_path=flat_path,
            min_lng=MIN_LNG,
            max_lng=MAX_LNG,
            min_lat=MIN_LAT,
            max_lat=MAX_LAT,
        )
    )

    places = pd.read_parquet(flat_path)
    places["h3_cell"] = [
        h3.latlng_to_cell(lat, lng, args.resolution)
        for lat, lng in zip(places["latitude"], places["longitude"], strict=True)
    ]
    places.to_parquet(args.places_output, index=False)

    cells = sorted(places["h3_cell"].unique())
    grid = pd.DataFrame(
        {
            "h3_cell": cells,
            "resolution": args.resolution,
            "center_lat": [h3.cell_to_latlng(c)[0] for c in cells],
            "center_lng": [h3.cell_to_latlng(c)[1] for c in cells],
            "boundary_wkt": [cell_boundary_wkt(c) for c in cells],
        }
    )
    grid.to_parquet(args.cells_output, index=False)

    print(f"places: {len(places):,} rows -> {args.places_output}")
    print(f"grid:   {len(grid):,} H3 cells at resolution {args.resolution} -> {args.cells_output}")
    print(f"avg places per cell: {len(places) / max(len(grid), 1):.1f}")
    flat_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
