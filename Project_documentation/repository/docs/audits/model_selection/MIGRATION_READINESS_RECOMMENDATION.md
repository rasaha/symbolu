# Model Selection — Migration-Readiness Recommendation

## Verdict (Section 19 — exactly one)

> ## READY — separate Model Selection product logic from research evaluation

## Why this verdict (and not the others)

The Section-19 STOP conditions are tested and **none applies**:

| STOP condition | Applies? | Evidence |
|---|---|---|
| Boundary architecturally unclear (selection/routing/orchestration/Hybrid LLM/execution inseparable) | **No** | Boundary is clear and documented: eligibility↔selection cleanly split; Hybrid LLM, control plane, and provider execution are separate and only *consume* MSP (`HYBRID_LLM_AND_CONTROL_PLANE_BOUNDARY.md`, `IMPORT_GRAPH.md`) |
| Evidence & scoring semantics not reproducible | **No** | Fully deterministic, version-stamped, frozen replay verified byte-identical (`EVIDENCE_AND_SCORING_ASSESSMENT.md`). Evidence is *synthetic/optimistic*, but that is quality, not reproducibility |
| Dependency direction prevents safe migration | **No** | `execution_gate` is a dependency-free leaf; consumers depend on it; no inversion to unwind (`IMPORT_GRAPH.md`) |

Among the READY options:

- *migrate one canonical capability* — **not yet**, because the two-stage core is duplicated 4–5× and
  interleaved with research code; there is no single directory to lift.
- *separate policy core from routing and execution* — partially true (the pilot co-locates execution),
  but routing does not exist in production and execution is only a blocked pilot; this is not the
  dominant blocker.
- *split policy eligibility from optimization ranking* — **already done**; eligibility (ExecutionGate)
  and ranking (ModelPolicy) are architecturally separated and test-covered. The soft-vs-hard *quality*
  floor is a documented policy-semantics gap, not an eligibility/ranking entanglement.
- **separate product logic from research evaluation** — **the accurate blocker.** Genuine reusable
  product logic (deterministic eligibility gate + weighted-utility selection + contracts) is real and
  coherent, but in every directory it is interleaved with — and duplicated across — research/benchmark
  evaluation (simulator, oracle, baselines, metrics, harness) and, in the pilot, provider execution.
  Extracting and unifying the product core out of the research evaluation is the required first step
  before any canonical package can exist.

This verdict **subsumes** the duplication finding: designating a canonical core (recommended:
`execution_gate`'s `gate/policy/registry/states/model/reason_codes`, augmented with the experiment's
`fuse_quality`/`route` and the reconciliation opt-in modes) and folding the other copies into it is part
of "separating product logic from research evaluation," because 3 of the 5 copies *are* research
harnesses.

## Exact next phase (proposed — not executed here)

1. **Define the canonical product core** = `execution_gate` eligibility + selection + contracts, plus
   the experiment's multi-source quality fusion and the reconciliation opt-in sufficiency mode (Policy B).
2. **Build a behavior-equivalence harness** (byte-identical before/after capture, as in the GPF
   migration) spanning all current implementations, to prove the consolidated core reproduces each.
3. **Separate research evaluation** (simulator, oracle, baselines, metrics, harnesses, synthetic corpora)
   and **provider execution** (`model_selection_pilot/provider.py`, `execute.py`) into non-migrated
   research/eval locations.
4. **Resolve the soft-vs-hard quality floor** as an explicit opt-in mode with *predicted* (not
   guaranteed) semantics; do not silently change the default.
5. **Then** perform the canonical-package migration to `packages/capabilities/model-selection/`
   (`ugence_model_selection`), carrying `execution_gate/frozen/replay_v1` along and keeping it green.

## Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| I/O-shape divergence (dataclass vs dict) across copies | Medium | behavior-equivalence harness before consolidation |
| Cost/latency numeric drift between copies (`price_per_ktok` vs `pricing_per_mtok`) | Medium | reconcile units explicitly; assert in equivalence harness |
| Synthetic/optimistic evidence mistaken for validated | High (commercial) | keep the reconciliation wording discipline; no "guaranteed"/"validated" claims; pilot is credential-blocked |
| Soft quality floor shipped as if it were a hard guarantee | High | ship as opt-in *predicted* mode only; require calibrated LCB before any guarantee claim |
| Migrating pilot provider execution into the package | Medium | explicitly leave `provider.py`/`execute.py` behind |
| Consumers (control_plane, shadows, governed_inference_pilot) break on repath | Low–Medium | canonical import + legacy shim, as in prior migrations |
| Platform-freeze / API-snapshot disturbance | **None** | Model Selection is not in the platform freeze |

## Bottom line

A coherent, well-bounded, dependency-clean Model Selection capability **exists**, with correct authority
(advisory/policy-bounded), correct dependency direction, reproducible semantics, and **zero platform-freeze
impact**. It is **not yet one thing**: it is duplicated across four-to-five locations and interleaved with
research evaluation and (in the pilot) provider execution. Separating the product core from the research
evaluation — and consolidating the duplicates into it — is the safe, necessary step before a canonical
migration.
