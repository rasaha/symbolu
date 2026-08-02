# Decision Authority migration — exact baseline

Recorded directly from the repository before any code move.

| Item | Value |
|---|---|
| Branch | `claude/decision-authority-canonical-package-migration` |
| Starting commit | `8946df9c` |
| Working tree | clean at start |
| Kernel version | `1.0.0` (frozen) |
| Legacy namespace | `decision_governance` |
| Legacy distribution | `decision-governance` (symlink to root kernel) |
| Kernel `.py` files (incl. 6 tests) | **101** |
| Kernel LOC | **8130** |
| Deduplicated kernel tests | **29** (verified via `pytest --collect-only`; see `test_manifest.txt`) |
| Public API module | `decision_governance.api` |
| Public API manifest hash (freeze) | `1b89386992bb9572b82eca40fb36760ab9451c85db76e6ce43d3339c13ad5543` |
| API-snapshot file sha256 | `974936bc79bbe14f46be4ab77f47d2e92d881f71202d64ec7da84834456c7ed5` |
| Freeze `core_tree_hashes.decision_governance` | `f38a615970c332c46e6bf3e908ed823729dbdcfc26137871436e853f3120f81c` |
| Freeze `manifest_digest` | `f318dfd21e693093253efc15785a41beddc575d5a14384502ebd14808e79b148` |
| External runtime deps | pydantic + Python stdlib (verified: no `governance_providers` / `ugence_governance_contracts` / `cer_v0_*` imports) |

## Equivalence fingerprint (before)

Captured by `scripts/da_migration_capture.py` → `baseline_equivalence.json`:

| Fingerprint | Value |
|---|---|
| version | `1.0.0` |
| public API sha256 | `82685c11664413ae…` |
| pydantic models | **29**, digest `ecf2af545153760b…` |
| enums | **30**, digest `f7034fa92c76dde7…` |

## Baseline green

- `pytest decision_governance/tests` → **29 passed**
- `python -m platform_freeze.verify` → **PASS** (substantive digest `6f605add…`)

## Known pre-existing platform_freeze pytest failures (unrelated, recorded separately)

`platform_freeze/tests`: **19 passed / 2 failed** — `test_classify_change_reports_evidence`,
`test_hiring_baseline_discovery`. Documented as pre-existing in the Governance Contracts
migration report; **not** touched by this migration.
