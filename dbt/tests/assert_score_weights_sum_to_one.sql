-- The three score weights must sum to exactly 1.0, otherwise the opportunity score
-- silently changes scale whenever someone edits dbt_project.yml.

WITH weights AS (
    SELECT
        {{ var('weight_demand') }}
      + {{ var('weight_diversity') }}
      + {{ var('weight_low_competition') }} AS total
)

SELECT total
FROM weights
WHERE ABS(total - 1.0) > 0.0001
