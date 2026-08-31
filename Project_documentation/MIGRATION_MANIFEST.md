# MIGRATION_MANIFEST.md - Stage 1 (Inventory & Plan)

> **Stage 1 is inventory and planning only.** No existing documentation file is
> moved, renamed, deleted, or rewritten by this manifest. The only new files in
> this change are under `Project_documentation/`. This manifest is the
> authoritative artifact to be **independently audited before any migration**.

---

## Phase 2 execution record (relocation performed)

Stage 1 was approved and **Phase 2 relocation has now been executed** on branch
`claude/symbolu-docs-migration-phase2` (base `2aea95f0`, the Stage-1 HEAD). The
authoritative per-file outcome is [`manifests/PHASE2_LEDGER.md`](manifests/PHASE2_LEDGER.md).

**Scope correction applied in Phase 2:** `apps/**` and `products/**` are ACTIVE
implementation boundaries, not legacy. Stage-1 `MOVE` entries under `products/**`
(118 files) were overridden to `ACTIVE_PRODUCT_KEEP`; `apps/**` docs remain
colocated (`ACTIVE_APP_KEEP`). Neither tree was migrated.

Outcome totals (all 3437 discovered Markdown files accounted for):

```text
MOVED ................. 1646     EXCLUDED_HYBRID ...... 982
STUBBED_AND_MOVED ....   94      EXCLUDED_PACKAGE ..... 259
JUSTIFIED_DEVIATION ..    5      ACTIVE_PRODUCT_KEEP .. 118
DEFERRED_REVIEW ......  251      ACTIVE_APP_KEEP ......  72
KEPT (infra/tooling) .   10
------------------------------------------------------------
Relocated (MOVED + STUBBED_AND_MOVED) = 1740
Sum = 1646+94+5+251+10+982+259+118+72 = 3437
```

**Justified deviations** — kept at canonical path because a CI/operational
consumer references them by exact path (moving would break enforcement):
`ONTOLOGY_FREEZE_CONTRACT.md`, `docs/governance/PROTECTED_BRANCHES.md`,
`docs/ontology/CHANGELOG.md`,
`docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`,
`docs/audits/bindingslots_persistence_preregistration/ADAPTIVE_EXECUTION_AMENDMENT.md`.

**Reference repair:** relative Markdown links in moved files (and links pointing
to moved files) were recomputed, and exact repo-relative documentation paths in
scripts/CI/config/code-comments were updated. Internal-link validation after
migration found **0 regressions** (all remaining dangling links pre-existed the
migration). Path-only edits inside `packages/**`/`products/**` were limited to
doc-reference pointers in comments/docstrings/package docs; no source behavior
changed.

The Stage-1 plan and verification record below are retained unchanged for audit.

---

## Provenance

```text
Repository:     rasaha/symbolu  (origin https://github.com/rasaha/symbolu)
Default branch: claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF
Default HEAD:    59bb4f2762e624d3b2efe90e3d8c555f502da687
Working branch: claude/symbolu-docs-inventory-plan-658pua (created from default HEAD)
Working tree:   clean at analysis start; only Project_documentation/** added
```

## How this manifest was built (methodology)

1. Enumerated **every** tracked `*.md`/`*.markdown` file (`git ls-files`): **3437** files.
2. Extracted per-file content signals (first heading/title, Hybrid-LLM keyword hits).
3. Built a repository-wide **inbound Markdown link graph** and scanned CI
   workflows, `pyproject.toml`, and `Makefile` for documentation references.
4. Performed deep, evidence-based characterization of the high-risk namespaces
   (agentic/symbolu, acp/ACP/control_plane, cer_v0_*, ai_hiring, cyber_security,
   robotics, trading, the docs/ tree, and the Hybrid-LLM boundary), citing source
   files and READMEs.
5. Encoded the findings as a deterministic classifier that assigns every file a
   logical module, document type, classification, proposed destination, and
   action - using `REVIEW_REQUIRED` wherever evidence was insufficient rather than
   guessing.

The complete per-file tables live in **[`manifests/`](manifests/)** (split by
module). This master file is the summary, the exclusion accounting, the risk
analysis, and the verification record.

## Inventory totals

```text
Total Markdown files discovered .............. 3437
Packages-excluded (packages/**) .............. 259
Hybrid-LLM-excluded (semantic) ............... 982
Infrastructure/tooling-excluded .............. 10
REVIEW_REQUIRED (ambiguous / Hybrid boundary)  197   (+57 candidate docs flagged Hybrid=REVIEW)
Legacy/project migration candidates .......... 1989
--------------------------------------------------------
Accounting check: 259 + 982 + 10 + 197 + 1989 = 3437
```

Candidate action mix: **MOVE=1764**, **STUB_AND_MOVE=99**, **REVIEW=126**.

## Migration exclusions

### A. Active packages - packages/** (259 files) - EXCLUDED (G8)
Every Markdown file under `packages/**` (capabilities, products, providers,
runtime, tooling, risk_authority, governance-provider-framework,
governance-contracts) stays **authoritative and colocated**. Full list:
[`manifests/EXCLUDED_packages.md`](manifests/EXCLUDED_packages.md).

### B. Hybrid LLM / model research (982 files) - EXCLUDED (semantic, G7)
The exclusion is **semantic, not path-based**. It covers the active Hybrid-LLM,
neural-model, KV-cache/CTM, quantization, and symbolic-representation research
lineage wherever it lives.

| Area | Verdict | Evidence |
|---|---|---|
| `CTM_plus/**` (158) | EXCLUDE | CTM/KV-cache/INT4/FP8 kernels, TurboQuant, KVPolicy/KVSimulator - the "CTM/KV integration research" named in the brief |
| `hybrid_llm_vnext_lab/**` (28) | EXCLUDE | "Hybrid LLM vNext Lab - Bounded Binding-Slot Incubation", NOT_A_PRODUCTION_MODEL |
| `symbolu_neural/**` (35) | EXCLUDE | "Trainable Neural Architecture Skeleton" - patent-implementation attempts inside a Transformer |
| `experiments/**` (LLM/phase/KV/binding-slot/primitive-sequence subset) | EXCLUDE | phase-quad, KV, binding-slot, primitive-sequence-recovery symbolic studies |
| `mechinterp/`, `token_compression/`, `resonant_model/`, `ndol/`, `eval/`, `eval_results/` | EXCLUDE | mech-interp, compression, model harness, KV decode, LM eval |
| `varna_lens/**` (64), `restoration/**` (85) | EXCLUDE (research/archive) | Varna symbolic-representation research; archive of old phase engines/acoustic mappers |
| `docs/research/**` (63), `docs/hardware/**` (8) | EXCLUDE | Hybrid-LLM relational-reasoning research; phase-attention silicon (COHERA/UCP/Sovereign-1) |
| `quad_*/` dirs | EXCLUDE | Phase-Quad / BCVF-USE-SCC research machinery |
| Root: `HYBRID_LLM_*`, `INT4_PROTECTED_VC_BRIEF`, `KVPro_VC_brief`, `CONSCIOUS_GENERATION_LLM_*`, `LLM_STEERING_CONTROLLER_*`, `TOKEN_COMPRESSION_*`, `LATENT_SEMANTIC_*`, `LORA_IA3_*`, `TRAINING_DIAGNOSIS_*`, `MILESTONE_A_*`, `S1_S2_*`, `STRUCTURAL_V1_*`, `O1_5_*`, `PHASE_CAPABILITY_VALIDATION_SPEC`, `SYMBOL_U_*` (theory), `THEORY_FORMALIZATION`, `FALSIFICATION_STRATEGY`, `ENGLISH_LEXICAL_FAILURE_ANALYSIS`, `VARNA_STATE_OPERATOR_THEORY` | EXCLUDE | Named Hybrid-LLM / neural-model / Symbol-U theory research |

**Inverse caution honoured:** `agentic/hybrid_handover/**` (~130 docs) is **NOT**
excluded despite the word "hybrid" - it is governance capability-resolution
research (extractor architectures, adjudication corpora), not LLM training. It
stays in the `agentic_framework` candidate set.

Full list: [`manifests/EXCLUDED_hybrid_llm.md`](manifests/EXCLUDED_hybrid_llm.md).
Boundary cases deferred to humans: [`manifests/REVIEW_REQUIRED.md`](manifests/REVIEW_REQUIRED.md).

### C. Infrastructure / tooling (10 files) - EXCLUDED
Packaging `README.md` stubs under `packaging/dgm-*` and `VERSION`-class metadata
that must stay colocated. List: [`manifests/EXCLUDED_infra.md`](manifests/EXCLUDED_infra.md).

## Logical module map (evidence-supported)

```text
physical paths                                            -> logical module
--------------------------------------------------------------------------
agentic/**, agentic_framework_review/**,                  -> agentic_framework
  agent_runtime_migration/**, agent_runtime_v2/**,
  root AGENTIC_FRAMEWORK_*/AGENT_RUNTIME_*/AGENTIC_WIRING_AUDIT/SOVEREIGN_*
symbolu_core/**                                           -> symbolu_core (canonical SUPPLY runtime)
symbolu/**                                                -> symbolu_legacy_monolith (SUPERSEDED shim; twins of the two above)
acp/**, ACP/**, ai_control_plane_v3/**,                   -> control_plane
  docs/control_plane/**, control_plane_shadow/**,
  root AI_CONTROL_PLANE_VC_BRIEF/UGENCE_AI_CONTROL_PLANE_*
cyber_security/**                                         -> action_gate_cyber
cer_v0_1|v0_2|v0_3|public_draft|open_standard/**          -> cer (versioned family)
ai_hiring/**, docs/ai-hiring/**                           -> ai_hiring (legacy; packaged copy stays in packages/)
truth_assurance_pipeline/**, docs/truth_assurance_pipeline/**, tap_provider/**, root TAP_*  -> truth_assurance_pipeline
symbolu_robotics/**, robotics_reliability_bench/**,       -> autonomous_robotics
  root ROBOTICS_*/AUTONOMOUS_ROBOTICS_*/PREDICTOR_TRUST_*/BCVF_BROCHURE
trading/**, trading2/**                                   -> trading
model_selection_experiment|pilot|reconciliation/**,       -> model_selection
  root MODEL_SELECTION_*/ADR_MODEL_SELECTION_*
simulator/**                                              -> simulator (PCAM)
products/dilchat/**, products/code-governance/**          -> products
apps/**                                                   -> apps (active-app; mostly KEEP - see review)
ActionGate/decision-governance/assurance-pilot dirs +     -> governance
  root ACTIONGATE_*/POLICY_PACK_*/ACTION_CLEARANCE_*/AGENT_WORKFORCE_COMPOSER_*/UGENCE_*GOVERNANCE*
docs/audits|design|architecture|migrations|platform-v1 +  -> repository
  root UGENCE_PLATFORM_*/status/roadmap/strategy docs
```

### Per-module manifest index

| Module | Scope | Candidates | Actions |
|---|---|---:|---|
| [`agentic_framework`](manifests/agentic_framework.md) | Agentic Framework (agent runtime + governance library) | 259 | MOVE=236, STUB=23, REVIEW=0 |
| [`symbolu_core`](manifests/symbolu_core.md) | Symbolu Core (SUPPLY runtime slice - canonical) | 13 | MOVE=9, STUB=4, REVIEW=0 |
| [`symbolu_legacy_monolith`](manifests/symbolu_legacy_monolith.md) | Symbolu Legacy Monolith (compat-shim - SUPERSEDED/duplicate) | 42 | MOVE=0, STUB=0, REVIEW=42 |
| [`control_plane`](manifests/control_plane.md) | Control Plane (ACP runtime, unified console, AICP v3, enterprise wiring) | 104 | MOVE=104, STUB=0, REVIEW=0 |
| [`governance`](manifests/governance.md) | Governance (ActionGate, decision governance, assurance pilots, execution/assertion) | 366 | MOVE=343, STUB=22, REVIEW=1 |
| [`action_gate_cyber`](manifests/action_gate_cyber.md) | Action Gate - Cybersecurity line (Agent Action Admissibility Gate) | 79 | MOVE=67, STUB=12, REVIEW=0 |
| [`cer`](manifests/cer.md) | CER - Canonical Execution Request (versioned interop spec family) | 45 | MOVE=44, STUB=1, REVIEW=0 |
| [`ai_hiring`](manifests/ai_hiring.md) | AI-Assisted Hiring (legacy source + program docs) | 54 | MOVE=42, STUB=1, REVIEW=11 |
| [`truth_assurance_pipeline`](manifests/truth_assurance_pipeline.md) | Truth Assurance Pipeline / TAP (assertion governance) | 116 | MOVE=103, STUB=13, REVIEW=0 |
| [`autonomous_robotics`](manifests/autonomous_robotics.md) | Autonomous Robotics (BCVF / predictor-trust runtime) | 34 | MOVE=32, STUB=2, REVIEW=0 |
| [`trading`](manifests/trading.md) | Trading (SymbolU trading framework - experimental) | 2 | MOVE=0, STUB=2, REVIEW=0 |
| [`model_selection`](manifests/model_selection.md) | Model Selection Policy | 17 | MOVE=15, STUB=2, REVIEW=0 |
| [`simulator`](manifests/simulator.md) | Simulator (PCAM chip simulator) | 17 | MOVE=16, STUB=1, REVIEW=0 |
| [`products`](manifests/products.md) | Products (dilchat, code-governance) | 118 | MOVE=113, STUB=5, REVIEW=0 |
| [`apps`](manifests/apps.md) | Apps (ugence-governance-studio, console) | 72 | MOVE=0, STUB=0, REVIEW=72 |
| [`repository`](manifests/repository.md) | Repository-level (platform strategy, architecture, audits, migrations, status) | 651 | MOVE=640, STUB=11, REVIEW=0 |

## Highest-risk ambiguities (namespace / version overlaps)

1. **acp/ vs ACP/ - case collision, two unrelated modules.** `acp/` (lowercase)
   = *Autonomous Control Plane* robotics/cloud runtime (V1->V2.2, frozen baselines).
   `ACP/` (uppercase, 2 files) = *Ugence AI Control Plane - Unified Console*. On a
   case-insensitive filesystem these collide. **Proposed distinct destinations:**
   `control_plane/autonomous_acp/` vs `control_plane/unified_console/`.
2. **"AI Control Plane" architecture spans 3 generations.** `acp/AI_CONTROL_PLANE_ARCHITECTURE.md`
   (V2.2) / `docs/control_plane/SYSTEM_ARCHITECTURE.md` (Phase-3, self-labelled
   *canonical*) / `ai_control_plane_v3/**` (design-only v3 verdict). The ADR
   `ADR_MODEL_SELECTION_POLICY_PLACEMENT.md` (reconciliation 2026-08-01) is the
   terminology authority. Do **not** auto-merge.
3. **CER version ladder.** `cer_v0_1 -> cer_v0_2 -> cer_v0_3` are the same module's
   frozen generations (byte-preserved digests forward); `cer_public_draft/` is the
   **canonical external** artifact; `cer_open_standard/` is a **separate strategy
   study**, not a spec release. v0_1/v0_2 = HISTORICAL.
4. **symbolu/ vs agentic/ vs symbolu_core/.** `symbolu/` is a
   backwards-compatibility shim (its `__init__.py` routes imports to the new
   homes); its docs are **byte-identical twins** or drifted copies. Migrate from
   the canonical homes; treat `symbolu/` copies as DUPLICATE_CANDIDATE.
5. **AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md is OLDER than the non-V2 file** (doc
   version v0.7 May 2026 vs v1.3 July 2026). Filename suffix != newer - human call
   required on which is canonical.
6. **"BCVF" is overloaded** across robotics (predictor-trust), cyber_security
   (behavioural), and an LLM-origin scorer (`symbolu_bcvf_llm/`). A rename to DRDC
   is already recommended in `ROBOTICS_V2_MIGRATION_PLAN.md`. Keep the three senses
   distinct; the LLM-origin one is Hybrid-excluded.
7. **ai_hiring/ & tap_provider/ are legacy facades** whose canonical code was
   extracted into `packages/` (SUPERSEDED). `docs/ai-hiring/product/*` is a
   near-exact twin of `packages/products/ai-hiring/docs/*`.

## Duplicate candidates (do NOT merge in Stage 1)

| Group | Members | Relationship | Confidence |
|---|---|---|---|
| symbolu shim twins | `symbolu/**` <-> `agentic/**`, `symbolu_core/**` | Byte-identical / drifted copies of canonical homes | High |
| CER cross-generation | `cer_v0_*/...SPEC/IDENTITY/SECURITY/EXECUTIVE_SUMMARY` <-> `cer_public_draft/*` <-> `cer_open_standard/0*` | Same conceptual docs re-emitted per generation | High |
| AI Control Plane arch | `acp/AI_CONTROL_PLANE_ARCHITECTURE.md` <-> `docs/control_plane/SYSTEM_ARCHITECTURE.md` <-> `ai_control_plane_v3/03_ADAPTER_ARCHITECTURE.md` | Three architectural generations | Medium-High |
| ai-hiring product docs | `docs/ai-hiring/product/*` <-> `packages/products/ai-hiring/docs/*` (excluded) | Near-exact filename-parallel set; packaged copy canonical | High |
| ACP executive summaries | `acp/ACP_EXECUTIVE_SUMMARY.md`, `ACP_V2_EXECUTIVE_SUMMARY.md`, `ACP_V2_1_INVESTOR_SUMMARY.md`, `AI_CONTROL_PLANE_EXECUTIVE_SUMMARY.md` | Overlapping per-version summaries | Medium |
| cyber action_gateway variants | `cyber_security/action_gateway{,_isolated,_k8s,_mcp}/{README,IMPLEMENTATION_FINDINGS}.md` | 4 deployment variants, same-named docs | Medium |
| Robotics VC briefs | `AUTONOMOUS_ROBOTICS_VC_BRIEF.md` <-> `_V2.md` | Two positioning generations; version conflict | Medium |

90 individual files carry a per-row `Duplicate/Overlap` note in their
module manifest. All remain `DUPLICATE_CANDIDATE` - none is merged or deleted in
Stage 1.

## Reference relationships (Stage-2 repair points - recorded, not repaired)

- **Build config:** `pyproject.toml` sets `readme = "README.md"` -> root `README.md`
  is recommended **KEEP** (relied on by packaging).
- **CI workflows referencing exact doc paths** (must be updated in Stage 2 if the
  target moves):
  - `ONTOLOGY_FREEZE_CONTRACT.md`, `docs/governance/PROTECTED_BRANCHES.md`,
    `docs/ontology/CHANGELOG.md` <- `ontology-freeze-ci.yml`
  - `docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md` <-
    `agent-workforce-composer-spec-ci.yml`
  - `docs/audits/bindingslots_persistence_preregistration/ADAPTIVE_EXECUTION_AMENDMENT.md`
    <- `bindingslots-persistence-amendment-ci.yml`
  - `docs/patent_formula_coverage_matrix.md` <- `formula-drift-ci.yml`
  - (Hybrid, excluded) `docs/audits/hybrid_llm/...`, `docs/research/hybrid_llm/...` <-
    `hybrid-llm-vnext-lab-ci.yml`, `unseen-identifier-integrity.yml`
- **Doc-to-doc links:** an inbound link graph covers **2257** documents
  with >=1 inbound Markdown reference. Per-file inbound counts are in the `Refs In`
  column; heavily-referenced hubs (e.g. `UGENCE_PLATFORM_OVERVIEW.md` 35,
  `ACTIONGATE_VC_BRIEF.md` 31, `acp/ACP_ACTIONGATE_BOUNDARY.md` 16) will need link
  updates when relocated.
- No `mkdocs`/`sphinx`/`docusaurus` site generator is present - docs are loose
  Markdown, so there is no generated index to regenerate.

## README handling policy (Stage 1 records; changes nothing)

- **(A) Implementation-local dev READMEs** (e.g. `agentic/core/*/README.md`) ->
  `STUB_AND_MOVE`: move substantial content, leave a small navigation/dev stub.
- **(B) Substantial project/architecture docs** (e.g. `agentic/agentic_framework/README.md`)
  -> `MOVE` under the module home.
- **(C) Navigation-only** (e.g. `agentic/docs/INDEX.md`) -> `STUB_AND_MOVE` (keep a pointer).
- **(D) Required package/tool docs** (root `README.md` referenced by `pyproject`;
  `packaging/*/README.md`) -> `KEEP`.
All README rows are marked accordingly; **no README is edited in Stage 1.**

## Proposed Project_documentation/ tree

```text
Project_documentation/
|-- README.md                     # scope & index (this change)
|-- MIGRATION_MANIFEST.md         # this file
|-- manifests/                    # full per-file tables (this change)
|   |-- agentic_framework.md          symbolu_core.md
|   |-- symbolu_legacy_monolith.md    control_plane.md
|   |-- governance.md                 action_gate_cyber.md
|   |-- cer.md                        ai_hiring.md
|   |-- truth_assurance_pipeline.md   autonomous_robotics.md
|   |-- trading.md                    model_selection.md
|   |-- simulator.md                  products.md   apps.md
|   |-- repository.md
|   |-- EXCLUDED_packages.md          EXCLUDED_hybrid_llm.md
|   |-- EXCLUDED_infra.md             REVIEW_REQUIRED.md
|
|-- repository/            # platform strategy, architecture, audits, migrations, status
|-- agentic_framework/    symbolu_core/    control_plane/
|-- governance/           action_gate_cyber/   cer/
|-- ai_hiring/            truth_assurance_pipeline/   autonomous_robotics/
|-- model_selection/      simulator/   products/   trading/
    (each module -> README.md + architecture/ specifications/ design/ guides/
     experiments/ validation/ audits/ migration/ historical/ as evidence justifies -
     empty category dirs are NOT created)
```
> The destination *content* directories above are **proposed**; Stage 1 creates
> only `README.md`, `MIGRATION_MANIFEST.md`, and `manifests/`. The module content
> directories are created by Stage 2 when files actually move.

## Verification results (G1-G12)

```text
G1  Zero files under packages/** modified .................... PASS (only Project_documentation/** added)
G2  Zero Hybrid LLM files modified ........................... PASS
G3  Zero existing Markdown files moved ....................... PASS
G4  Zero existing Markdown files deleted ..................... PASS
G5  Zero source-code files modified .......................... PASS
G6  Every migration candidate represented in the manifest .... PASS (1989 candidates enumerated in manifests/)
G7  Every excluded Hybrid LLM document accounted for ......... PASS (982 listed in EXCLUDED_hybrid_llm.md)
G8  Every packages/** Markdown file excluded ................. PASS (259 listed in EXCLUDED_packages.md)
G9  Every proposed destination under Project_documentation/** . PASS (0 exceptions)
G10 No two documents map to the same destination ............. PASS (0 collisions)
G11 All REVIEW_REQUIRED cases explicitly listed .............. PASS (198 in REVIEW_REQUIRED.md)
G12 Working tree contains only Stage-1 documentation additions  PASS (git status = Project_documentation/ only)
```

## Decision

```text
STAGE_1_READY_FOR_AUDIT
```

> This label is **not** authorization for Stage 2. No documentation is migrated
> until this manifest has been independently audited.
