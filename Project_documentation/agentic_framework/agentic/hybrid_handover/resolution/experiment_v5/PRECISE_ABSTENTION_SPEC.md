# PRECISE_ABSTENTION_SPEC — Competing Operative Resolution Experiment v0.1

This layer replaces G4's coarse permission/prohibition co-occurrence abstention. It may
abstain at the governance stage ONLY for one of the following preregistered reasons, each
with a full detail record. There is no catch-all or generic low-confidence abstention.

| reason code | fires when |
|---|---|
| `GENUINE_UNRESOLVED_CONFLICT` | a competition is classified GENUINE_UNRESOLVED_CONFLICT |
| `INSUFFICIENT_SCOPE_EVIDENCE` | (reserved) scope needed to decide a conflict cannot be derived |
| `OPERATIVE_TERM_NOT_LOCATED` | no operative term is present among the governing candidates |
| `MULTIPLE_INCOMPATIBLE_OPERATIVE_TERMS` | (reserved) ≥2 incompatible operatives survive resolution |
| `FROZEN_PACKET_CARDINALITY_LIMIT` | (reserved) required multi-operative answer cannot be rendered by the single-primary packet |
| `MISSING_DECISIVE_PROVENANCE` | (reserved) the decisive edge lacks provenance |

Reasons marked "reserved" are defined and wired but did not activate on the hidden pilot;
they are reported with zero counts, not omitted.

## Abstention detail (every abstention records)
- candidate operative set;
- exact unresolved predicate results;
- missing evidence;
- rejected resolution paths;
- reason code.

## What must NOT trigger abstention
- permission and prohibition language merely co-occurring;
- candidates in different authority domains (parallel);
- candidates already resolved by supersession / override / exception / temporal split;
- compatible or cumulative operatives.

The synthetic co-occurrence-safety fixture (different-domain permission/prohibition)
verifies the layer does NOT abstain; the genuine-conflict fixture verifies it DOES. Both
are calibration gates (C8, C9).

## Distinct failure axes (never collapsed into one reason)
The layer distinguishes governance conflict, operative-set multiplicity, and frozen packet
cardinality limitation. See PACKET_CARDINALITY_BOUNDARY.md.
