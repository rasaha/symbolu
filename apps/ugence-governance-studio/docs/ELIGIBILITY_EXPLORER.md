# Eligibility Explorer

The eligibility matrix (`features/eligibility`) is the primary screen: one role at
a time, agents as rows, API-provided condition names as columns, cells derived
only from API condition results. Overall states are ELIGIBLE / INELIGIBLE /
INDETERMINATE / INVALID_INPUT. Filtering and sorting are presentation-only and
never reorder as a selection decision — no score, rank, recommendation or
preferred agent appears. Selecting a pair opens the explanation drawer.
