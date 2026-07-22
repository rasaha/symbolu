# Shadow Pilot — Overall Report

- Engine: Implementation B (read-only reference) bound to `tap-e7-base-companion/1.2.0`, fingerprint `sha-256:d01e466e5bb57d6a…` (verified before evaluation).
- Sample: 162 artifacts, 9 domains, 9 issue types, 2 replicates.
- **Read-only:** TAP-E7 output influenced nothing; every result observational.

## Outcome distribution
{"ASSURED": 54, "NOT_ASSURED": 72, "INDETERMINATE": 36}

## Effectiveness vs ground truth (within TAP-E7's scope)
- Confusion (positive = ground-truth issue; TAP-positive = outcome≠ASSURED): {"TP": 108, "FP": 0, "TN": 18, "FN": 36}
- **Precision 1** (zero false positives — never flags a faithful artifact).
- **Recall 0.75** overall; **1** on BASE-detectable classes.
- **Indeterminate rate 0.222**.
- Engine-gap misses (issues TAP ASSURED): **36** — all scope-expansion / omitted-qualifier.

## By issue type
| Issue | detectable by BASE | flag rate | typical outcome |
|---|---|---|---|
| faithful | True | 0 | ASSURED |
| unsupported_assertion | True | 1 | NOT_ASSURED |
| status_upgrade | True | 1 | NOT_ASSURED |
| citation_mismatch | True | 1 | NOT_ASSURED |
| provenance_mismatch | True | 1 | NOT_ASSURED |
| integrity_homoglyph | True | 1 | INDETERMINATE |
| certainty_inflation | False | 1 | INDETERMINATE |
| scope_expansion | False | 0 | ASSURED |
| omitted_qualifier | False | 0 | ASSURED |

## Honest interpretation
- TAP-E7-BASE is a **high-precision, bounded-recall** structural assurance layer. It reliably flags
  fabrication, status upgrades, citation/provenance mismatch, and integrity/spoofing (Unicode), and
  it **never false-alarms** a faithful artifact in this sample.
- It **misses** semantic distortions that leave the content-token set unchanged — **scope expansion**
  and **omitted qualifiers** are ASSURED. `certainty_inflation` was flagged only *incidentally*
  (the extra word "certainly" perturbed correspondence → INDETERMINATE); a token-neutral certainty
  inflation would be missed. These are exactly the four informative/engine-level categories BASE
  documents as out of mandatory scope.
- **Operational implication:** TAP-E7-BASE is valuable as a **first-pass triage / assurance gate for
  structural fidelity**, not as a complete substitute for human semantic review. Its INDETERMINATE
  verdict correctly routes ambiguous/spoofed inputs to humans.
