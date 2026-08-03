# Policy Workflow Compiler P2 — Version-Decoupling Correction

Follow-up to the merged PR #1314 (merge commit `40d19b83`). PR #1314 was **already
merged** when this correction began, so per merged-PR discipline the fix is delivered
on a fresh branch (`claude/policy-workflow-compiler-p2-version-fix`) and a new
follow-up PR — the merged PR cannot be reused.

## Defect
PR #1314 held `DISTRIBUTION_VERSION = "0.1.0"` (while `PRODUCT_VERSION = "0.2.0"`)
because the distribution version fed the frozen `workflow_ir.v1` logical digest.
That preserved v1 fingerprints but created a **packaging defect**: a build with
`workflow_ir.v2`, ~30 new public names, new CLI commands, release validation, and
materially different wheel/sdist contents would be published under the same
distribution version `0.1.0` as the P1-only build.

## Fix — decouple package version from digest semantic identity
- `DISTRIBUTION_VERSION = "0.2.0"`, `PRODUCT_VERSION = "0.2.0"`.
- New explicit, frozen per-contract digest identities:
  `WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION = "0.1.0"` (frozen legacy),
  `WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION = "0.2.0"`.
- New `digest_compiler_version_for(contract_version)` — pure constant lookup, no
  ambient package/metadata/clock/env read, fail-closed on unknown versions.
- `release._logical_payload` now commits to `digest_compiler_version_for("workflow_ir.v1")`
  (frozen `0.1.0`) under the **unchanged** key name, so the v1 digest bytes are
  identical. The v2 enrichment `compiler_version` now sources the explicit v2 identity.
- The on-disk release manifest metadata `compiler_distribution_version` honestly
  reports the building distribution (`0.2.0`); it is **not** part of the logical digest.

## Invariants verified
| Item | Before | After |
|---|---|---|
| v1 release digest | `sha256:fb9fd4b9…` | `sha256:fb9fd4b9…` (byte-identical) |
| v1 IR logical digest | `sha256:169ad24c…` | `sha256:169ad24c…` (byte-identical) |
| Distribution / product version | 0.1.0 / 0.2.0 | **0.2.0 / 0.2.0** |
| v1 digest semantic identity | (ambient 0.1.0) | **frozen constant 0.1.0** |
| v2 digest semantic identity | (ambient 0.1.0) | **explicit 0.2.0** |
| Wheel / sdist filename | 0.1.0 | **0.2.0** |
| Compiler suite | 139 | **153** (+14 decoupling tests) |
| AWC P1/P2 (v1 consumer) | 158 | 158 |
| Governance Studio P3A | 94 | 94 |
| Distribution verifier | PASS | PASS (0.2.0 filenames, frozen v1 digest, bit-for-bit) |
| Platform-freeze digest | `d993093570…` | `d993093570…` (unchanged) |

## Upgrade terminology
"lossless upgrade" wording replaced with **deterministic, non-destructive v1→v2
enrichment that preserves all v1 information and explicitly labels derived /
defaulted / deferred / unresolved semantics** — it does not recover source-policy
facts absent from v1.
