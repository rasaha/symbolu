# CONFLICT_PREDICATE_SPEC — Competing Operative Resolution Experiment v0.1

Two operative candidates are in genuine conflict only if the full predicate battery
passes. Every predicate result is exposed in the `OperativeSet.competitions` record; a
conflict is never a single opaque Boolean.

## The ten predicates
| # | predicate | passes when |
|---|---|---|
| 1 | `both_applicable` | both candidates are in the frozen governing set |
| 2 | `compatible_subjects` | same governed actor (the parties) |
| 3 | `overlapping_action` | same governed action (terminate-for-convenience) |
| 4 | `overlapping_object` | same governed object (the agreement) |
| 5 | `temporal_overlap` | NOT positively separated (dated supersession/amendment splits them) |
| 6 | `authority_overlap` | both authority domains derived AND equal |
| 7 | `conditions_simultaneous` | neither candidate is an exception-scoped condition |
| 8 | `incompatible_outcomes` | polarities are exactly {PROHIBITED, PERMITTED} |
| 9 | `no_resolving_relationship` | no supersedes/overrides/governs_over/exception_to/same_as/amends edge between them |
| 10 | `neither_supporting` | both carry an operative polarity (not NON_OPERATIVE) |

Genuine unresolved conflict = predicates 1–4, 5, 7, 8, 9, 10 pass **and** predicate 6
passes (authority domains positively overlap). If predicate 6 cannot be established
(a domain is UNKNOWN), the competition is `INSUFFICIENT_SCOPE_EVIDENCE`, not a conflict.

## Why predicate 6 is decisive on this corpus
The v0.3 `parallel_overrides` break came from treating a Regulatory Directive and a
Corporate Policy as conflicting when they occupy different authority domains. Predicate 6
(and the DIFFERENT_AUTHORITY_DOMAIN category) prevents exactly that: cross-domain
permission/prohibition is parallel, not conflict, so the layer does not abstain and G3's
operative choice stands.

## Non-collapse
The classification (CONFLICT_CLASSIFICATION_RULEBOOK.md) reads these predicates in a fixed
deterministic order and returns exactly one primary category. No predicate is hidden inside
a scalar score; the full vector is recorded per competition for audit.
