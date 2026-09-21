-- Intermediate: classify every place as a competitor, a demand generator, or other.
--
-- The category lists below were chosen after inspecting the actual category
-- distribution in the DKI Jakarta extract (1,062 distinct categories), so every
-- mapping refers to a category that genuinely exists in the data.

{{ config(materialized='view') }}

WITH classified AS (
    SELECT
        id,
        name,
        category,
        confidence,
        latitude,
        longitude,
        h3_cell,

        CASE
            WHEN category IN (
                'coffee_shop', 'cafe', 'restaurant', 'indonesian_restaurant',
                'asian_restaurant', 'chicken_restaurant', 'fast_food_restaurant',
                'noodles_restaurant', 'bakery', 'chinese_restaurant',
                'eat_and_drink', 'ice_cream_shop', 'pizza_restaurant',
                'japanese_restaurant', 'bar'
            ) THEN 'competitor'

            WHEN category IN (
                'central_government_office', 'professional_services',
                'coworking_space', 'financial_service', 'bank_credit_union',
                'real_estate_service',
                'college_university', 'school', 'elementary_school', 'preschool',
                'shopping_center', 'shopping', 'grocery_store', 'convenience_store',
                'furniture_store', 'mobile_phone_store',
                'beauty_salon', 'spas', 'gym', 'pharmacy',
                'hotel', 'accommodation',
                'hospital', 'park'
            ) THEN 'demand'

            ELSE 'other'
        END AS place_role,

        CASE
            WHEN category IN ('coffee_shop', 'cafe', 'restaurant', 'indonesian_restaurant',
                              'asian_restaurant', 'chicken_restaurant', 'fast_food_restaurant',
                              'noodles_restaurant', 'bakery', 'chinese_restaurant',
                              'eat_and_drink', 'ice_cream_shop', 'pizza_restaurant',
                              'japanese_restaurant', 'bar')
                THEN 'food_and_beverage'
            WHEN category IN ('central_government_office', 'professional_services',
                              'coworking_space', 'financial_service', 'bank_credit_union',
                              'real_estate_service')
                THEN 'office'
            WHEN category IN ('college_university', 'school', 'elementary_school', 'preschool')
                THEN 'education'
            WHEN category IN ('shopping_center', 'shopping', 'grocery_store',
                              'convenience_store', 'furniture_store', 'mobile_phone_store')
                THEN 'retail_anchor'
            WHEN category IN ('beauty_salon', 'spas', 'gym', 'pharmacy')
                THEN 'lifestyle'
            WHEN category IN ('hotel', 'accommodation')
                THEN 'lodging'
            WHEN category = 'hospital'
                THEN 'health'
            WHEN category = 'park'
                THEN 'leisure'
            ELSE 'other'
        END AS category_group

    FROM {{ ref('stg_places') }}
)

SELECT * FROM classified
