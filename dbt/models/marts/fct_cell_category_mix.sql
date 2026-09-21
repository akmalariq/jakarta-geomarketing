-- Mart: category mix per cell, used by the dashboard detail panel to explain why a
-- cell ranks where it does.

{{ config(materialized='table', cluster_by=['h3_cell']) }}

SELECT
    h3_cell,
    category,
    category_group,
    place_role,
    COUNT(*) AS place_count
FROM {{ ref('int_places_classified') }}
WHERE place_role IN ('competitor', 'demand')
GROUP BY h3_cell, category, category_group, place_role
