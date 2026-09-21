-- The opportunity score is a weighted average of three 0-100 components, so it must
-- land inside 0-100 for every cell. Fail loudly if the weighting or the normalisation
-- ever produces something outside that range.

SELECT
    h3_cell,
    opportunity_score,
    demand_score,
    diversity_score,
    competition_score
FROM {{ ref('fct_h3_cells') }}
WHERE opportunity_score < 0
   OR opportunity_score > 100
   OR demand_score < 0
   OR demand_score > 100
   OR diversity_score < 0
   OR diversity_score > 100
   OR competition_score < 0
   OR competition_score > 100
