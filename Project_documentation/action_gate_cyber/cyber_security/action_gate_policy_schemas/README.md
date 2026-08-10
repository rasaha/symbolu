# ActionGate Policy Schema Library

Machine-readable JSON Schemas (draft 2020-12) for the **action-centered ActionGate
business rule** described in `../ACTION_GATE_BUSINESS_RULE_TEMPLATE.md`. These turn a
governed business rule into policy-as-code that a gate implementation can validate,
version, and enforce.

A vague rule — *"prevent risky production changes"* — is not executable. A usable
ActionGate rule must answer: **who** proposes **what** action, on **which** resource,
under **what** authority and evidence, in **what** context, with **what** operational
conditions, and **what happens when any requirement is missing.** The schemas make
those answers mandatory.

## Files

| File | Role |
|---|---|
| `actiongate_policy.schema.json` | **Master** — the flat 17-section business rule; `$defs` for every section. Authoring form. |
| `policy_package.schema.json` | The **seven-artifact** deployable package (below). |
| `artifact_canonical_action.schema.json` | 1. Canonical Action Schema — the exact action being evaluated (§1–§4). |
| `artifact_authority_policy.schema.json` | 2. Authority Policy — who may propose/approve/execute (§5). |
| `artifact_evidence_policy.schema.json` | 3. Evidence Policy — required trusted proof + scope match (§6–§7). |
| `artifact_story_policy.schema.json` | 4. Story Policy — prior events that change meaning (§9). |
| `artifact_consequence_policy.schema.json` | 5. Consequence Policy — conditions, consequences, obligations, overrides (§8, §11, §12, §14). |
| `artifact_operational_clearance_policy.schema.json` | 6. Operational Clearance Policy — safe-to-execute-now + failure behavior (§10, §13). |
| `artifact_audit_reconciliation_policy.schema.json` | 7. Audit & Reconciliation Policy — record, govern, validate (§15–§17). |
| `examples/prod_database_delete.policy.json` | Worked example — flat form. |
| `examples/prod_database_delete.package.json` | Worked example — seven-artifact form. |
| `validate.py` | Dependency-free validator (+ optional `jsonschema` cross-check). |
| `tests/test_schemas.py` | Schema integrity, ref resolution, example validity, rejection of authoring mistakes. |

## Use

```bash
python3 validate.py examples/prod_database_delete.policy.json
python3 validate.py --package examples/prod_database_delete.package.json
python3 -m pytest tests/
```

## Design invariants encoded by the schemas

- **A missing required control is never permission.** `absence_behavior` and
  `failure_behavior` decisions are drawn from `{DENY, HOLD_FOR_REVIEW,
  REQUIRE_ADDITIONAL_EVIDENCE, UNAVAILABLE, OBSERVE, REEVALUATE}` — `ALLOW` is not a
  legal value for a missing control.
- **Non-compensatory conditions.** `decision_conditions` are explicit `required` /
  `prohibited` lists with `non_compensatory: true`, not one blended risk score.
- **StoryGraph is evidence, not an authorizer.** `sequence_context` maps the
  advisory `WOULD_COMPLETE_PROHIBITED_CAPABILITY` finding (from
  `composite_threat_detector`) to a policy `consequence`; it never emits ALLOW/DENY.
- **Exact-action binding.** `canonical_action` requires `payload_digest` + `cer_id`;
  a materially changed action needs a new evaluation.
- **Closed objects.** `additionalProperties: false` on every structured section, so
  an unrecognized field is a policy error, not silently ignored.

## Consequence-vocabulary crosswalk

The business-facing names map onto the deterministic six outcomes of
`../ACTION_GATE_SPECIFICATION.md` §6:

| Business rule (this library) | ACTION_GATE_SPECIFICATION.md outcome |
|---|---|
| `ALLOW` | `ALLOW` |
| `ALLOW_WITH_OBLIGATIONS` | `ALLOW_WITH_CONSTRAINTS` |
| `REQUIRE_ADDITIONAL_EVIDENCE` | `REQUEST_MORE_EVIDENCE` |
| `REQUIRE_HUMAN_REVIEW` / `HOLD_FOR_REVIEW` | `ESCALATE_TO_HUMAN` |
| `SIMULATE_AND_RETRY` | `SIMULATE_AND_RETRY` |
| `DENY` | `DENY` |
| `UNAVAILABLE` | (fail-visible; never silent evidence loss) |

The organization declares which decisions are binding vs shadow-mode projections
(`consequences.binding_decisions` / `consequences.shadow_only_decisions`).
