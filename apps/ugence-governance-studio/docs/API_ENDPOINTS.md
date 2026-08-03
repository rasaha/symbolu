# Governance Studio API — Endpoints (P3B)

All domain endpoints are under `/api/v1`. Operational endpoints are unprefixed.
Every domain response uses the standard `ApiResponse` envelope. 23 operations.

## Operational
| Method | Path | Operation |
|--------|------|-----------|
| GET | `/health` | liveness (no domain execution) |
| GET | `/ready` | readiness (manifests, fixture hashes, AWC import, contracts) |
| GET | `/version` | version + maturity + AWC/compiler contract facts |

## Scenarios
| Method | Path | Operation |
|--------|------|-----------|
| GET | `/api/v1/scenarios` | list scenario metadata |
| GET | `/api/v1/scenarios/{id}` | scenario detail (manifest, narrative, notices) |
| GET | `/api/v1/scenarios/{id}/workflow` | canonical workflow + dispositions + digests |
| GET | `/api/v1/scenarios/{id}/registry` | frozen registry snapshot |
| GET | `/api/v1/scenarios/{id}/eligibility?verify_expected=true` | real eligibility + verification |
| GET | `/api/v1/scenarios/{id}/ranking?verify_expected=true` | real ranking + verification |
| GET | `/api/v1/scenarios/{id}/plan?verify_expected=true` | real plan + verification |
| GET | `/api/v1/scenarios/{id}/export` | deterministic export bundle |
| POST | `/api/v1/scenarios/{id}/what-if` | controlled perturbation |

## Workflows
| Method | Path | Operation |
|--------|------|-----------|
| POST | `/api/v1/workflows/validate` | validate a compiled workflow |
| POST | `/api/v1/workflows/adapt` | adapt (explicit v1/v2 dispatch, fail-closed) |
| POST | `/api/v1/workflows/compare-adaptations` | v1/v2 equivalence classification |

## Eligibility / Ranking / Composition
| Method | Path | Operation |
|--------|------|-----------|
| POST | `/api/v1/eligibility/evaluate` | role eligibility reports |
| POST | `/api/v1/ranking/evaluate` | role candidate rankings |
| POST | `/api/v1/composition/compose` | composition + proposals + fallbacks + plan |

## Explanations
| Method | Path | Operation |
|--------|------|-----------|
| POST | `/api/v1/explanations/eligibility` | passed/failed/unknown conditions, reasons, evidence |
| POST | `/api/v1/explanations/ranking` | raw/normalized/weighted criterion contributions |
| POST | `/api/v1/explanations/plan` | selection states, constraints, concentration, fallbacks |

## Plans
| Method | Path | Operation |
|--------|------|-----------|
| POST | `/api/v1/plans/replay` | replay a plan; compare fingerprint to expected |
| POST | `/api/v1/plans/compare` | diff two deterministically-produced plans |

Domain / scenario inputs accept either a `scenario_id` (frozen inputs, optional
injected `logical_time`) or fully inline pinned artifacts. No endpoint accepts a
filesystem path, code, or policy script.
