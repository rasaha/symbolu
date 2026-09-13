# Changelog

All notable changes to `ugence-change-effect-policy`.

## [0.1.0] — 2026-09-13

Initial contract-only release. Stage 1 item 3.2 of the Change Effect Classifier (M15),
under the owner's eight-point ruling of 2026-09-13 (ADR §11).

### Added

* `ChangeEffectClassificationPolicy` — the three-member artifact: protected-registry list,
  delegation table and mapping coordinate, projected together so one body digest covers
  all three.
* `ChangeEffectPolicyMetadata` — the family's own identity envelope, with `policy_family`
  fixed as a property rather than a settable field.
* `ProtectedRegistryEntry` and `PROTECTED_REGISTRY_IDS` — the seven protected registries.
  The list states which registries are protected; it states no effect class, route or
  outcome.
* `ChangeEffectPolicyFamilyAdapter` and `change_effect_coordinate` — registration with the
  shared Policy Authority from outside its own distribution. The adapter describes and
  projects; it never resolves, issues, signs or verifies.
* Refusals: `DelegationEntryRefused` (Stage 1 ships an empty table, not inactive entries),
  `MappingCoordinateRefused` (no sentinel, placeholder or fabricated coordinate), and
  `OperativeWithoutMappingRefused` (ruling 6).

### Deliberately not added

`ClosureBundleMapping` content in any form — no obligation-to-effect rules, no
required-primitive table, no executable predicates, no D1, D3, D4 or D5 semantics or
parameters. No delegation entry type. No classifier, closure verifier, routing, effect
projection, admission computation, policy resolution or self-registration.
