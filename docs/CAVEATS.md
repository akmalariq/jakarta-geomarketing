# Caveats

This document exists because a scoring model that hides its limits is not trustworthy.
Everything below is a real limitation of this analysis, not a formality.

## 1. POI coverage is uneven, so the score partly measures mapping activity

Overture Maps places derive from OpenStreetMap contributions. Mapping density varies
enormously between neighbourhoods. A cell can score low for two very different reasons:
it is genuinely quiet, or it is under-mapped.

**What this means in practice:** treat the map as a prioritisation tool. Before acting on
any cell, verify it on the ground or against commercial POI data.

**How to detect it:** cells with very few total places relative to their neighbours are
suspicious. The `total_places` column is exposed in the dashboard for exactly this reason.

## 2. This is a heuristic, not a validated model

There is no sales, footfall, rent, lease, or demographic data here. The score has never
been calibrated against revenue, so it is a structured opinion rather than a prediction.

The weights (0.55 demand, 0.25 diversity, 0.20 low competition) are deliberate judgement
calls. They are dbt variables precisely so they can be challenged.

## 3. Scores are relative to DKI Jakarta

Normalisation is min-max within this dataset. A cell scoring 90 is high *for Jakarta*.
Comparing a Jakarta cell to a Singapore cell using these numbers would be meaningless.

## 4. What the model ignores

- Opening hours, brands, price positioning, and store size
- Competitor quality: a warung and a specialty coffee chain count the same
- Rent, lease terms, and landlord constraints
- Physical barriers: rivers, toll roads, and one-way systems
- Travel time: all proximity is straight-line distance, not isochrones
- Zoning, licensing, and permitted use
- Population and daytime footfall

## 5. F&B is treated as a single category

The competitor list covers coffee shops, cafes, restaurants, bakeries, and bars together.
A specialty coffee brand competing with restaurants is a different problem from competing
with other coffee shops. A category-specific analysis would need a narrower list.

## 6. Category mapping is a judgement call too

1,062 distinct Overture categories were reduced to 15 competitor categories and 24 demand
categories by inspection. Categories that are ambiguous or rare were deliberately left as
`other` rather than forced into a bucket. `int_places_classified.sql` holds the mapping,
and a unit test asserts the competitor and demand lists never overlap.

## 7. Transit is missing

The Overture places theme contains almost no transit stations for Jakarta (three metro
stations in the extract), so transit accessibility is **not** part of the score. Doing it
properly would need the Overture `transportation` theme or a GTFS feed.

## 8. Attribution

Places data from Overture Maps Foundation, derived from OpenStreetMap contributors,
licensed under ODbL.
