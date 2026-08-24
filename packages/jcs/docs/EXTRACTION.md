# ugence-jcs extraction record

## What moved

`cer_v0_3/cleanroom/canon.py` moved to `packages/jcs/src/ugence_jcs/canon.py`
(`git mv`, so the history follows). Only the module docstring changed; every line
of executable code is byte-identical to the pre-extraction file.

The five canonicalization error types the canonicalizer raises —
`BareNumberError`, `NonFiniteNumberError`, `NonNFCError`, `UnsupportedTypeError`,
`DuplicateSetElementError` — moved with it into `ugence_jcs/errors.py`, keeping
their names, their `category` keys and the `path` keyword. The base class moved
too, renamed `JcsError` for authority neutrality; `cer_v0_3.cleanroom.errors`
binds `CleanRoomError = JcsError`, so `except CleanRoomError` still catches every
clean-room fault and no `category` string changed.

`DuplicateKeyError` and the CER structural/profile error types stayed in the
clean-room: they describe CER envelope validation, not JSON canonicalization.

## What did not move

`digest.py` (domain-separated, length-prefixed action identity), `cer.py` (CER
validation and the v2 identity projection) and `profiles.py` stayed in
`cer_v0_3/cleanroom`. They encode a specific authority domain — an ActionGate
domain tag, a CER envelope schema version, a profile registry. A canonicalization
substrate must not carry those, so the extraction stopped at the byte stream.

## Package placement

`packages/jcs`, alongside the existing top-level leaves `packages/governance-contracts`,
`packages/governed-value`, `packages/policy-authority`, `packages/risk_authority`,
`packages/trusted-evidence-authority` and `packages/uvi-policy-contracts`.

The `packages/` tiers — `capabilities/`, `providers/`, `runtime/`, `tooling/`,
`integration/`, `products/` — each name a role in the platform. A JCS
canonicalizer fills none of them: it is not a capability (it decides nothing), not
a provider (it fronts no authority), not a runtime and not a product. The existing
convention for a dependency-free substrate that several tiers may consume is a
top-level leaf, and those leaves are directory-named by stripping the `ugence-`
prefix from the distribution name (`ugence-governance-contracts` →
`packages/governance-contracts`). `ugence-jcs` → `packages/jcs` follows both rules.

## Consumption without an editable install

Three path bootstraps put `packages/jcs/src` on `sys.path` for a bare source
checkout, mirroring how the other migrated packages are resolved: the repository
`conftest.py`, `cer_v0_3/tests/conftest.py`, and `cer_v0_3/_paths.py`.

## Independence

The clean-room exists to prove the CER identity semantics are reproducible by an
implementation that shares no code with the reference path. Extraction could have
weakened that proof in two ways, and both are closed:

* the clean-room may now import exactly one non-stdlib module, `ugence_jcs`, and
  `test_only_stdlib_absolute_imports` still rejects every other;
* `test_extracted_jcs_leaf_is_independent` and
  `test_extracted_jcs_leaf_is_stdlib_only` apply the same forbidden set
  (`action_gate_ref`, `cer_v0_1`, `cer_v0_2`, `symbolu_robotics`, `cer_v0_3`) and
  the same stdlib-only rule to the extracted source tree, so reference code cannot
  re-enter through the leaf.

## Evidence

| Claim | Evidence |
| --- | --- |
| Byte stream preserved | `packages/jcs/tests/test_canonical_vectors.py` — vectors captured from the pre-extraction implementation |
| Frozen CER V0.2 identity preserved | `cer_v0_3/tests/test_cleanroom.py::test_cleanroom_matches_frozen_scale_digest` and `::test_cleanroom_matches_frozen_rollout_digest`, now running through `ugence_jcs` |
| Clean-room independence intact | `cer_v0_3/tests/test_forbidden_imports.py` (6 tests) |
| Installs and behaves outside the monorepo | `packages/jcs/verify_jcs_distribution.py` (`--no-index` clean venv) |
| Platform freeze unaffected | `python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json` |
