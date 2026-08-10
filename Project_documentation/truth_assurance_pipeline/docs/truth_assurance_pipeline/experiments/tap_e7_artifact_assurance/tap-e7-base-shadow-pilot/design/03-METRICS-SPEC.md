# 3. Metrics Specification

All metrics stay **within TAP-E7's scope**; none invents capability TAP-E7 does not have.

## Case-level signals (from the AssuranceRecord)
- outcome ∈ {ASSURED, NOT_ASSURED, INDETERMINATE}
- findings by category (fabrication, status upgrade, certainty overstatement*, scope expansion*,
  citation/provenance mismatch, omitted qualifier*, unsupported assertion, integrity/processing/modality limitations)
  (*categories marked engine-level/informational — BASE abstains; recorded for the gap analysis)

## Effectiveness (positive = ground-truth ISSUE; TAP-positive = outcome ≠ ASSURED)
- **True positive / false positive / true negative / false negative** confusion counts.
- **Precision** = TP/(TP+FP) — how trustworthy a non-ASSURED verdict is (target: high; demo = 1.00).
- **Recall** = TP/(TP+FN) overall, and **recall restricted to BASE-detectable classes** (demo = 1.00).
- **Indeterminate rate** = INDETERMINATE / N — the fraction routed to humans by design.
- **False-negative rate** and **engine-gap misses** (issues TAP ASSURED), broken out by category.
- **Outcome distribution** and **per-domain** breakdown.

## Category-specific counts (observational, per the prompt)
unsupported assertions, missing evidence, certainty inflation, scope expansion, incorrect citations,
omitted qualifiers, fabricated relationships — each counted as (ground-truth occurrences) vs
(TAP-flagged occurrences), so the coverage gap per category is explicit.

## Human-factor metrics (design-level; require reviewers)
- **reviewer agreement** (inter-rater κ between two blind reviewers).
- **average review time** per case, with/without TAP-E7 assistance (efficiency signal).
These are **N/A in the synthetic demonstration** and are collected only in a live human pilot.

## Reporting rules
Report point estimates with counts; for the medium+ tiers add 95% Wilson intervals. Never report a
derived metric TAP-E7 cannot support (e.g., "semantic accuracy" beyond the finding taxonomy).
