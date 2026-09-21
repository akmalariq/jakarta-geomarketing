"""Guards on the competitor and demand category mapping.

The mapping lives in dbt SQL, which is not importable, so this test parses the model
and asserts the properties that matter: both lists are non-empty, they do not overlap,
and every category mentioned is a real Overture category observed in the extract.

If someone adds a category to the wrong list, or misspells one, this test fails.
"""

from __future__ import annotations

import re
from pathlib import Path

MODEL = Path("dbt/models/intermediate/int_places_classified.sql")

# A sample of categories confirmed to exist in the DKI Jakarta extract.
KNOWN_OVERTURE_CATEGORIES = {
    "restaurant",
    "indonesian_restaurant",
    "coffee_shop",
    "cafe",
    "bakery",
    "bar",
    "central_government_office",
    "professional_services",
    "college_university",
    "school",
    "shopping_center",
    "grocery_store",
    "hotel",
    "hospital",
    "park",
    "gym",
    "pharmacy",
}


def _category_lists() -> tuple[list[str], list[str]]:
    """Extract the competitor and demand category lists from the model.

    The model defines the lists with `category IN (...)`, first for the place_role
    CASE and then again for the category_group CASE. Taking the first two blocks
    avoids matching unrelated quoted strings such as the materialization config.
    """

    sql = MODEL.read_text(encoding="utf-8")
    blocks = re.findall(r"category IN\s*\((.*?)\)", sql, flags=re.S)
    if len(blocks) < 2:
        raise AssertionError("expected at least two `category IN (...)` lists in the model")

    quoted = re.compile(r"'([a-z_]+)'")
    return quoted.findall(blocks[0]), quoted.findall(blocks[1])


def test_mapping_lists_are_not_empty():
    competitor, demand = _category_lists()

    assert len(competitor) >= 10
    assert len(demand) >= 20


def test_competitor_and_demand_categories_do_not_overlap():
    competitor, demand = _category_lists()

    assert set(competitor).isdisjoint(set(demand))


def test_mapping_only_uses_categories_seen_in_the_extract():
    competitor, demand = _category_lists()

    unknown = (set(competitor) | set(demand)) - KNOWN_OVERTURE_CATEGORIES - {
        # Categories used elsewhere in the CASE that are also verified present.
        "asian_restaurant", "chicken_restaurant", "fast_food_restaurant",
        "noodles_restaurant", "chinese_restaurant", "eat_and_drink",
        "ice_cream_shop", "pizza_restaurant", "japanese_restaurant",
        "coworking_space", "financial_service", "bank_credit_union",
        "real_estate_service", "elementary_school", "preschool",
        "shopping", "convenience_store", "furniture_store", "mobile_phone_store",
        "beauty_salon", "spas", "accommodation",
    }

    assert not unknown, f"unverified categories in mapping: {sorted(unknown)}"
