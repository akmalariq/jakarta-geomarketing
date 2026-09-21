"""Export the H3 cell scores from BigQuery into a JSON payload for the dashboard.

Writes a single compact JSON file so the dashboard is fully static: no API keys, no
runtime BigQuery access, nothing to break.

Usage:
    uv run --with google-cloud-bigquery python export/export_dashboard.py \
        --output ../cloudflare/portfolio/projects/jakarta-geomarketing/cells.json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import bigquery

PROJECT = "jakarta-geomarketing"
MARTS = f"{PROJECT}.geomarketing_marts"

CELLS_SQL = f"""
SELECT
    h3_cell,
    opportunity_rank,
    opportunity_tier,
    opportunity_score,
    demand_score,
    diversity_score,
    competition_score,
    total_places,
    demand_count,
    competitor_count,
    demand_group_diversity,
    demand_office,
    demand_education,
    demand_retail,
    demand_lifestyle,
    demand_lodging,
    demand_health,
    demand_leisure,
    ROUND(center_lat, 6) AS center_lat,
    ROUND(center_lng, 6) AS center_lng,
    boundary_wkt
FROM `{MARTS}.fct_h3_cells`
ORDER BY opportunity_rank
"""

MIX_SQL = f"""
WITH ranked AS (
    SELECT
        h3_cell,
        category,
        category_group,
        place_role,
        place_count,
        ROW_NUMBER() OVER (PARTITION BY h3_cell, place_role ORDER BY place_count DESC) AS rn
    FROM `{MARTS}.fct_cell_category_mix`
)
SELECT h3_cell, category, category_group, place_role, place_count
FROM ranked
WHERE rn <= 5
ORDER BY h3_cell, place_role, place_count DESC
"""

SUMMARY_SQL = f"""
SELECT
    COUNT(*)                                    AS cells,
    SUM(total_places)                           AS places,
    SUM(demand_count)                           AS demand,
    SUM(competitor_count)                       AS competitors,
    COUNTIF(opportunity_tier = 'prime')         AS prime_cells,
    ROUND(AVG(opportunity_score), 1)            AS avg_score,
    MAX(opportunity_score)                      AS max_score
FROM `{MARTS}.fct_h3_cells`
"""

GROUPS = ["office", "education", "retail", "lifestyle", "lodging", "health", "leisure"]


def wkt_to_coords(wkt: str) -> list[list[float]]:
    """Parse our own POLYGON((lng lat, ...)) WKT into a coordinate ring.

    Coordinates are rounded to five decimals (about one metre), which halves the
    payload size with no visible difference on the map.
    """

    inner = wkt[wkt.index("((") + 2 : wkt.rindex("))")]
    ring: list[list[float]] = []
    for pair in inner.split(","):
        lng, lat = pair.strip().split()
        ring.append([round(float(lng), 5), round(float(lat), 5)])
    return ring


def main() -> None:
    parser = argparse.ArgumentParser(description="Export H3 cell scores for the dashboard.")
    parser.add_argument(
        "--output",
        default="../cloudflare/portfolio/projects/jakarta-geomarketing/cells.json",
    )
    args = parser.parse_args()

    client = bigquery.Client(project=PROJECT)

    mix: dict[str, dict[str, list[dict]]] = {}
    for row in client.query(MIX_SQL).result():
        bucket = mix.setdefault(row.h3_cell, {"competitor": [], "demand": []})
        bucket[row.place_role].append(
            {"category": row.category, "group": row.category_group, "count": row.place_count}
        )

    cells = []
    detail: dict[str, dict] = {}
    for row in client.query(CELLS_SQL).result():
        entry = {
            "id": row.h3_cell,
            "rank": row.opportunity_rank,
            "tier": row.opportunity_tier,
            "score": round(row.opportunity_score, 1),
            "demand_score": round(row.demand_score, 1),
            "diversity_score": round(row.diversity_score, 1),
            "competition_score": round(row.competition_score, 1),
            "places": row.total_places,
            "demand": row.demand_count,
            "competitors": row.competitor_count,
            "groups": [getattr(row, f"demand_{g}") for g in GROUPS],
            "center": [round(row.center_lng, 5), round(row.center_lat, 5)],
            "ring": wkt_to_coords(row.boundary_wkt),
        }
        cells.append(entry)
        detail[row.h3_cell] = mix.get(row.h3_cell, {"competitor": [], "demand": []})

    summary = next(iter(client.query(SUMMARY_SQL).result()))
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Overture Maps places (ODbL), DKI Jakarta bounding box",
        "weights": {"demand": 0.55, "diversity": 0.25, "low_competition": 0.20},
        "group_order": GROUPS,
        "summary": {
            "cells": summary.cells,
            "places": summary.places,
            "demand": summary.demand,
            "competitors": summary.competitors,
            "prime_cells": summary.prime_cells,
            "avg_score": summary.avg_score,
            "max_score": summary.max_score,
        },
        "cells": cells,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    detail_path = output.with_name("cells-detail.json")
    detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    print(f"wrote {output} ({output.stat().st_size / 1024:.0f} KB) with {len(cells):,} cells")
    print(f"wrote {detail_path} ({detail_path.stat().st_size / 1024:.0f} KB) loaded on demand")
    print(f"summary: {payload['summary']}")


if __name__ == "__main__":
    main()
