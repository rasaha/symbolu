# Model Selection — Product-Core Separation & Canonical-Package Migration Report

*Behavior-preserving structural consolidation. Follows the completed Model Selection audit
(`docs/audits/model_selection/`), verdict **READY — separate Model Selection product logic from
research evaluation**. No scoring formula, policy weight, quality floor, eligibility constraint,
routing, retry, provider call, Governance Contract, or frozen governance component was changed. The
discipline: **canonicalize the existing policy core first; validate and improve later.***

Companion deliverables in this directory: `FILE_MAP_BEFORE.md`, `FILE_MAP_AFTER.md`,
`PUBLIC_API_INVENTORY.md`, `CONSUMER_MAP.md`, `DUPLICATION_DISPOSITION.md`, `IMPORT_GRAPH_BEFORE.md`,
`IMPORT_GRAPH_AFTER.md`, `DEPENDENCY_DIRECTION.md`, `RESEARCH_SEPARATION.md`,
`PACKAGING_AND_DISTRIBUTION.md`, `EQUIVALENCE_REPORT.md`, `ROLLBACK.md`, plus
`api_before.json` / `api_after.json`, `equivalence_before.json` / `equivalence_after.json`,
`migration_manifest.json`.

## 1. What was done

The production-shaped Model Selection product core — the audit-selected canonical source
`execution_gate` — was extracted verbatim into a canonical package and the legacy namespace turned
into a logic-free compatibility surface:

| | Value |
|---|---|
| Canonical package | `packages/capabilities/model-selection` |
| Canonical namespace | `ugence_model_selection` |
| Distribution | `ugence-model-selection` |
| Version | `0.1.0` |
| Dependencies | Python standard library only (leaf capability; **no** Governance Contracts dependency) |
| Core modules moved verbatim | `gate`, `policy`, `states`, `model`, `registry`, `reason_codes` |
| Added | `api.py` (curated surface), `version.py`, `fingerprint.py`, tests, verifier |
| Legacy compatibility | `execution_gate.*` re-exports the *same objects* (identity preserved) via an eager `sys.modules` alias — **not** a meta-path hook |

## 2. Canonical-source selection (evidence)

`execution_gate` was verified directly as the canonical source because it alone has: production-shaped
dataclass contracts with evidence/TTL/criticality; **all** real consumers (`control_plane`,
`control_plane_shadow`, `execution_gate_shadow`, `governed_inference_pilot`); and a self-contained
replay freeze (`execution_gate/frozen/replay_v1`). The other implementations
(`model_selection_experiment`, `model_selection_pilot`, `model_selection_reconciliation`) are
dict-based **research** engines with a distinct I/O contract and research-only quality fusion; they were
classified as genuinely-different research algorithms, not copies, and were **not** merged (merging
would change behavior). See `DUPLICATION_DISPOSITION.md` and `RESEARCH_SEPARATION.md`.

## 3. Two-stage invariant preserved

```
Approved candidate set → ExecutionGate (fail-closed eligibility) → Eligible set
   → ModelPolicy (policy-weighted deterministic scoring/ranking) → Selected | NO_ELIGIBLE_MODEL
```

Hard eligibility runs before soft scoring; an ineligible candidate can never be selected by a higher
aggregate score; there is no silent fallback; an empty eligible pool abstains. All preserved verbatim
(the modules were moved unchanged; only their import prefixes became relative). The soft-by-default
quality-floor gap the audit identified is **unchanged** — it is a documented product gap, not a
migration defect.

## 4. Behavioral equivalence (byte-identical)

A deterministic harness (`scripts/model_selection_equivalence_capture.py`) was run through the
`execution_gate` surface in a pre-migration worktree (real modules) and in the post-migration tree
(compatibility surface → canonical), over 11 frozen scenarios covering eligibility decisions (state +
reasons + full condition serialization), selection results (selected/ranked/abstain/reason/components),
the `harness.run()` pipeline, exception edges, and per-decision fingerprints:

| Capture | sha256 |
|---|---|
| before | `e8e86b425628a894…` |
| after | `e8e86b425628a894…` |

**Byte-identical.** See `EQUIVALENCE_REPORT.md`.

## 5. Public API — PATCH

The consumer surface (`execution_gate.{reason_codes,states,model,gate,policy,registry}`, 51 public
symbols) is **byte-identical** before/after (`api_before.json` == `api_after.json`, sha256
`3780087f866a7967`). Compatibility classification: **PATCH**. See `PUBLIC_API_INVENTORY.md`.

## 6. Consumers

Primary product/control-plane consumers repointed to import the canonical package directly
(identity-preserving 1:1 swap): `control_plane/adapters.py`, `governed_inference_pilot/adapters/execution_gate.py`.
Shadow harnesses (`execution_gate_shadow/*`, `control_plane_shadow` eligibility adapter) stay on the
`execution_gate` surface, exercising the compatibility path. Neither posture transfers authority into
Model Selection; the governed-inference pilot still performs provider execution *after* selection,
outside the canonical package. See `CONSUMER_MAP.md`.

## 7. Dependency direction

`ugence_model_selection` imports only the Python standard library — a leaf. All consumers depend on it;
it depends on nothing above it. No dependency inversion. See `DEPENDENCY_DIRECTION.md` and
`IMPORT_GRAPH_AFTER.md`.

## 8. One physical implementation

The product-core eligibility and scoring/ranking logic now exists in exactly one place
(`ugence_model_selection`); the legacy namespace holds no product logic; the research engines are
classified separate (not duplicates of the canonical core). Guarded by
`scripts/check_model_selection_single_impl.py` (PASS) and the legacy-identity test
`execution_gate/tests/test_legacy_compat.py`. See `DUPLICATION_DISPOSITION.md`.

## 9. Packaging

Wheel built and verified canonical-only (no research/pilot/provider/benchmark members); clean-venv
install imports `ugence_model_selection[.api]` from site-packages and runs eligibility + selection +
`NO_ELIGIBLE_MODEL` + deterministic fingerprint with no monorepo path
(`verify_model_selection_distribution.py`). See `PACKAGING_AND_DISTRIBUTION.md`.

## 10. Freeze & terminology

Model Selection was **not** in the platform freeze; nothing frozen was touched. Platform-freeze
verifier PASS (digest `d4ad77e16516e0db6bf2faf3275c8ac8351644e7561d33f157bb55b5a174a1a6`, unchanged);
replay aggregate `8b05b2da798a6222` unchanged; Governance Contracts untouched; terminology validator
PASS.

## 11. Honest status

- **No runtime behavior changed** (byte-identical equivalence + PATCH API).
- **No other capability modified** (only the `execution_gate` namespace, its two repointed consumers,
  and additive package/docs/tests).
- Evidence remains primarily **synthetic**; this migration validates **no** commercial model-quality
  claim and establishes **no** real provider-reliability claim.
- The **soft-by-default quality-floor gap is unchanged** (documented, not silently corrected).
- **No routing or execution capability was added.**

## 12. Verdict

**MODEL SELECTION MIGRATION PR READY — awaiting merge authorization.**
