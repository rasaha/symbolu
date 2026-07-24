# Natural-Artifact Corpus `natural_pilot_v1` (Phase 3)

*`bounded_shadow_pilot/harvest.py` → `bounded_shadow_pilot/data/natural_pilot_v1/corpus.json`.
Naturally occurring repository artifacts — docstrings, markdown documentation, and block comments —
from real product/library code that was **never authored for a governance test corpus**. Every
candidate is routed through the Phase-2 intake protocol; only accepted, de-identified,
use-case-classified artifacts enter the frozen corpus.*

## Evidence verdict

| | |
|---|---|
| **Count** | **857** |
| **Target** | 200 |
| **Evidence status** | **SUFFICIENT** (857 ≥ 200) |
| Unique source files | 223 |
| Corpus SHA-256 (content) | `25a257976191de87…` |

The count is the **actual** number of eligible natural artifacts after intake filtering, dedup, and
bounding. Had it fallen below 200, the manifest would record `NOT_ENOUGH_EVIDENCE` and the pilot would
return that verdict rather than fabricate data. It did not.

## What was harvested (honest provenance)

Real product/library roots, chosen for domain diversity and because their text documents code — not
governance behaviour:

`cyber_security` · `cloud_controller` · `control_plane` · `simulator` · `sdk` ·
`truth_assurance_pipeline` · `ndol` · `varna_lens` · `robotics_reliability_bench` · `resonant_model` ·
`execution_gate` · `execution_proposal_engine` · `trading` · `trading2` · `agent_runtime_v2` · `acp` ·
`token_compression` · `restoration`.

Extraction is deterministic: Python docstrings via `ast` (module/class/function), markdown prose
blocks (headings/tables/code-fences dropped), and contiguous full-line comment runs.

## What was excluded (guarantees "not designed for its test corpora")

Never harvested: `assertion_governance`, `assertion_gate_robustness`, `evidence_assurance`,
`claim_integrity`, `scope_integrity`, `governed_inference_pilot`, `customer_shadow_readiness`,
`bounded_shadow_pilot`, all `model_selection_*` tracks, `tests`, and cache/result directories. No
artifact authored for the runtime's own corpora can leak in.

## Composition

| Source kind | Count |
|---|---|
| docstring | 431 |
| doc (markdown) | 353 |
| comment | 73 |

| Use case (derived) | Count |
|---|---|
| software_engineering_recommendation_review | 499 |
| compliance_summary_review | 149 |
| cybersecurity_advisory_review | 98 |
| it_operations_guidance | 49 |
| enterprise_policy_interpretation | 42 |
| contract_summary_review | 11 |
| technical_support_review | 7 |
| procurement_policy_review | 2 |

Length: char_len 80 / 266 / 2601 (min/median/max); word_len 12 / 36 / 405.

## Filtering (fail-closed, non-permissive)

| Rejected | Count | Meaning |
|---|---|---|
| quality | 711 | below the 80-char / 12-word / 50%-letters floor |
| prohibited | 30 | intake flagged PII/restricted markers under de-identified clearance |
| duplicate | 11 | same `artifact_id` or normalized text already present |
| excluded | 6 | matched a hard-excluded use case (clinical/trading/permission/deletion/…) |
| provenance / unclassifiable / other | 0 | — |

## Bounding (scope compliance)

The pilot's scope is **volume-bounded**. Each source file contributes at most 6 artifacts and each
source root at most 60, so no single file or module dominates. Many roots hit the 60 cap, so the true
repository supply of eligible natural artifacts exceeds 857 — the corpus is a **deliberately bounded**
subset, not the exhaustive count. This is disclosed, not hidden: `total_eligible_seen_before_bounding`
and `per_root_count` are recorded in the manifest.

## Known honest limitation

These are natural artifacts, so they carry **no gold evidence bundles, registries, or telemetry** — the
structured corpora's authored governance inputs. Phase 4 derives ground truth and Phase 6 derives
governance inputs deterministically from the natural text; every transfer result in this pilot is
explicitly conditioned on that derivation (see `PILOT_ASSUMPTIONS_AND_EXCLUSIONS.md`).

## Determinism

`harvest.harvest()` is a pure function of repository content: sorted by `artifact_id`, no wall-clock,
no randomness. Two runs produce byte-identical output (verified: content SHA-256 stable across runs).
