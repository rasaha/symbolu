# Workflow-IR Contract-Version Decision — P2

## Decision: Option B — introduce `workflow_ir.v2` (coexisting, additive)

P2 introduces a new `workflow_ir.v2` contract that **coexists** with the frozen
`workflow_ir.v1`. It is **not** a silent mutation of v1.

### Why Option B (not Option A)

P2 adds materially richer role semantics — node semantic purpose, role-relevant
capability requirements, typed contract references, dependency semantics, authority
/ human-review classification, and per-value policy provenance. This changes what a
downstream consumer can interpret and adds fields that participate in a new
fingerprint. Under the prompt's rules, that requires a new contract version, not an
additive relabel of v1.

### Coexistence guarantees (all verified by tests)

- `workflow_ir.v1` remains readable and is emitted unchanged by the existing
  pipeline (`compile_policy_pack`). Its `ir_version` string is untouched.
- **v1 fingerprints are byte-stable.** The v1 release digest
  (`sha256:fb9fd4b9…`) and the v1 IR-only digest (`sha256:169ad24c…`) are pinned in
  `tests/test_v2_contract_and_regression.py` and unchanged.
- The compiler explicitly emits v1 (`compile`, `compile --contract workflow_ir.v1`)
  or v2 (`compile --contract workflow_ir.v2`). v2 **embeds** the exact v1 graph
  (`base_ir`) and pins its digest (`base_ir_digest`), so v2 is a strict superset.
- v2 validation is separate and explicit (`CompiledReleaseValidator` /
  `validate_compiled_release`).
- A v2 artifact is never mislabeled as v1: its `ir_version` and `contract_version`
  are `workflow_ir.v2`; the embedded base keeps `workflow_ir.v1`.
- Unknown versions **fail closed**: the validator returns `UNSUPPORTED_VERSION`.
- A **lossless upgrade** utility exists (`upgrade_workflow_ir`, CLI `upgrade-v1`):
  enrichment is a pure function of the v1 graph, so upgrading a v1 IR reproduces the
  exact fingerprint of `compile --contract workflow_ir.v2`. Semantics absent from v1
  are marked unresolved / not-applicable — **never invented**.

### The distribution-version subtlety (important)

The v1 **release** logical digest commits to `compiler_distribution_version`
(= `DISTRIBUTION_VERSION`) via `release._logical_payload`. Bumping
`DISTRIBUTION_VERSION` would therefore change **every** existing `workflow_ir.v1`
release digest — a real break of P1 fingerprint stability.

**Resolution:** `DISTRIBUTION_VERSION` is deliberately **held at `0.1.0`**. The P2
capability bump is carried by `PRODUCT_VERSION` → `0.2.0` (which is *not* an input to
any v1 digest) and by the `workflow_ir.v2` contract itself. This preserves v1
byte-stability while still marking the product's P2 maturity honestly in
`version_info()`.

### v2 fingerprint definition

The v2 `workflow_fingerprint` **is** the v2 `logical_digest()` — a content digest
over the base graph digest plus every enriched field (node semantics, dependency
semantics, feature declarations, and reference manifests), excluding the stored
fingerprint slot itself. It is re-verifiable by recomputation, and the release
validator flags any mismatch as `INTEGRITY_FAILURE`.
