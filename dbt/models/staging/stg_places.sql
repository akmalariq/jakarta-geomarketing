-- Staging: typed, de-duplicated places with a valid location and H3 cell.

{{ config(materialized='view') }}

SELECT
    id,
    name,
    category,
    basic_category,
    confidence,
    latitude,
    longitude,
    locality,
    region,
    country,
    h3_cell
FROM {{ source('geomarketing', 'raw_places') }}
WHERE h3_cell IS NOT NULL
  AND latitude IS NOT NULL
  AND longitude IS NOT NULL
