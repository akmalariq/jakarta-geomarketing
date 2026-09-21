-- Intermediate: places rolled up to their H3 cell.
--
-- Candidate cells are filtered to those with enough places to be meaningful. A cell
-- with one or two POIs is usually an edge cell at the bounding box boundary, and
-- including them would distort the normalised scores.

{{ config(materialized='view') }}

WITH cell_metrics AS (
    SELECT
        h3_cell,

        COUNT(*)                                                    AS total_places,
        COUNTIF(place_role = 'competitor')                          AS competitor_count,
        COUNTIF(place_role = 'demand')                              AS demand_count,
        COUNTIF(place_role = 'other')                               AS other_count,

        COUNTIF(category_group = 'office')                          AS demand_office,
        COUNTIF(category_group = 'education')                       AS demand_education,
        COUNTIF(category_group = 'retail_anchor')                   AS demand_retail,
        COUNTIF(category_group = 'lifestyle')                       AS demand_lifestyle,
        COUNTIF(category_group = 'lodging')                         AS demand_lodging,
        COUNTIF(category_group = 'health')                          AS demand_health,
        COUNTIF(category_group = 'leisure')                         AS demand_leisure,

        COUNT(DISTINCT IF(place_role = 'demand', category_group, NULL)) AS demand_group_diversity,
        COUNT(DISTINCT category)                                    AS category_diversity,
        ROUND(AVG(confidence), 4)                                   AS avg_confidence

    FROM {{ ref('int_places_classified') }}
    GROUP BY h3_cell
    HAVING COUNT(*) >= {{ var('min_places_per_cell', 25) }}
)

SELECT * FROM cell_metrics
