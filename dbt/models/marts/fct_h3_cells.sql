-- Mart: one row per H3 cell, with the opportunity score and its components.
--
-- Score definition (weights are dbt variables, see dbt_project.yml):
--   opportunity_score = w_demand    * demand_score
--                     + w_diversity * diversity_score
--                     + w_low_comp  * (100 - competition_score)
--
-- demand_score and competition_score are min-max normalised across all candidate
-- cells, so the score is relative to Greater Jakarta rather than absolute. Scores
-- are therefore comparable between cells in this dataset, not across cities.

{{ config(materialized='table', cluster_by=['h3_cell']) }}

WITH metrics AS (
    SELECT * FROM {{ ref('int_cell_metrics') }}
),

bounded AS (
    SELECT
        *,
        MIN(demand_count)           OVER () AS min_demand,
        MAX(demand_count)           OVER () AS max_demand,
        MIN(competitor_count)       OVER () AS min_competition,
        MAX(competitor_count)       OVER () AS max_competition,
        MIN(demand_group_diversity) OVER () AS min_diversity,
        MAX(demand_group_diversity) OVER () AS max_diversity
    FROM metrics
),

scored AS (
    SELECT
        *,
        SAFE_DIVIDE(100 * (demand_count - min_demand), NULLIF(max_demand - min_demand, 0))                       AS demand_score,
        SAFE_DIVIDE(100 * (competitor_count - min_competition), NULLIF(max_competition - min_competition, 0))   AS competition_score,
        SAFE_DIVIDE(100 * (demand_group_diversity - min_diversity), NULLIF(max_diversity - min_diversity, 0))   AS diversity_score
    FROM bounded
),

combined AS (
    SELECT
        s.h3_cell,
        g.center_lat,
        g.center_lng,
        g.boundary_wkt,

        s.total_places,
        s.competitor_count,
        s.demand_count,
        s.other_count,

        s.demand_office,
        s.demand_education,
        s.demand_retail,
        s.demand_lifestyle,
        s.demand_lodging,
        s.demand_health,
        s.demand_leisure,

        s.demand_group_diversity,
        s.category_diversity,
        s.avg_confidence,

        ROUND(COALESCE(s.demand_score, 0), 2)       AS demand_score,
        ROUND(COALESCE(s.diversity_score, 0), 2)    AS diversity_score,
        ROUND(COALESCE(s.competition_score, 0), 2)  AS competition_score,

        ROUND(
              {{ var('weight_demand') }}            * COALESCE(s.demand_score, 0)
            + {{ var('weight_diversity') }}         * COALESCE(s.diversity_score, 0)
            + {{ var('weight_low_competition') }}   * (100 - COALESCE(s.competition_score, 0))
        , 2) AS opportunity_score,

        ROUND(SAFE_DIVIDE(s.competitor_count, NULLIF(s.demand_count, 0)), 3) AS competitor_to_demand_ratio

    FROM scored s
    JOIN {{ source('geomarketing', 'raw_h3_cells') }} g USING (h3_cell)
)

SELECT
    *,
    CASE NTILE(4) OVER (ORDER BY opportunity_score DESC)
        WHEN 1 THEN 'prime'
        WHEN 2 THEN 'strong'
        WHEN 3 THEN 'moderate'
        ELSE 'low'
    END AS opportunity_tier,
    RANK() OVER (ORDER BY opportunity_score DESC) AS opportunity_rank
FROM combined
