# Code Governance Claim Manifest & Non-Compensatory Gates

> Machine-readable form: `docs/claim_statuses.json`. Companion to the merged
> `CHANGE_INTELLIGENCE_EVIDENCE_LAYER.md` and its
> `change_intelligence_evidence_profiles.json`.

## Claim state semantics

A Claim Manifest is a **structured set of per-claim verdicts**, never one blended
quality score. Each `ClaimEntry` carries its own status:

| Status | Meaning | Satisfies a mandatory claim? |
|---|---|---|
| `SATISFIED` | met by admissible current-head evidence | ✅ |
| `NOT_APPLICABLE` | claim does not apply to this change | ✅ |
| `FAILED` | validator reported a blocking failure | ❌ |
| `INCOMPLETE` | required evidence not yet present/finished | ❌ |
| `UNSUPPORTED` | claim family not supported by supplied evidence | ❌ |
| `STALE` | evidence bound to a superseded head SHA | ❌ |
| `CONFLICTING` | contradictory evidence | ❌ |

## Risk tiers → required claims (orchestration only; no analyzers)

From the merged evidence profiles (`LOW`/`MEDIUM`/`HIGH`). Higher tiers include
lower-tier mandatory families:

| Tier | Mandatory claim families |
|---|---|
| `LOW` | BUILD, UNIT_TEST, STATIC_ANALYSIS |
| `MEDIUM` | LOW + DIFFERENTIAL_TEST, DEPENDENCY_DELTA, PUBLIC_API_DELTA, PERFORMANCE_BUDGET |
| `HIGH` | MEDIUM + SECURITY, MUTATION_ADEQUACY, INDEPENDENT_REVIEW |

Advisory (optional, descriptive) families: ARTIFACT_SIZE_DELTA, COMPLEXITY_DELTA,
ARCHITECTURE_DELTA, PROPERTY_TEST. Advisory evidence is **never** converted into
a hard denial unless a policy explicitly marks a claim mandatory.

Only claim families named in the merged documentation are supported. Change
Intelligence **analyzers are not implemented** in this phase — the product
governs evidence produced by external validators (it does not detect).

## Non-compensatory mandatory evaluation

`evaluate_claim_requirements(manifest, requirements)` produces a `ClaimEvaluation`:

```
mandatory_claims_complete      # every mandatory claim present & not incomplete
mandatory_claims_satisfied     # no mandatory claim missing/failed/stale/
                               #   conflicting/unsupported/inadmissible/incomplete
missing_required_claims
failed_required_claims
stale_required_claims
conflicting_required_claims
unsupported_required_claims
inadmissible_required_claims   # mandatory claim from an UNTRUSTED validator
incomplete_required_claims
optional_claim_summary         # DESCRIPTIVE ONLY — counts by status
proceed                        # complete AND satisfied
```

**Non-compensatory guarantee (structural):** the mandatory verdict is computed
only from mandatory claims. A required claim that is missing, stale, failed,
conflicting, unsupported, or inadmissible **cannot** be compensated for by:

- high aggregate evidence coverage,
- many successful optional claims,
- a high model-confidence score,
- passing tests in another category.

TAP's per-claim `evidence_coverage` (a float in `[0,1]`) stays **descriptive** —
it is never used as an aggregate authorization or quality score. Completeness
checks are owned by the Workflow Service; assertion governance by TAP; binding
decisions by Decision Authority; exact-action authorization by ActionGate. These
responsibilities are never collapsed.

## Manifest fingerprint

The manifest fingerprint is **order-independent** (entries sorted by their own
fingerprints before hashing): re-ordering claims does not change it, while any
change to a governed claim field does. The same normalized manifest always yields
the same fingerprint.
