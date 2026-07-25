# AI-Assisted Hiring Framework — Module (Phase 1: Foundation)

An **isolated** module implementing the *foundation* of the AI-Assisted Hiring
Framework described in
[`docs/design/AI_ASSISTED_HIRING_FRAMEWORK_DESIGN.md`](../docs/design/AI_ASSISTED_HIRING_FRAMEWORK_DESIGN.md).

This phase delivers the canonical data contracts, an audited workflow state
machine, and the hard, enforced separation between **AI recommendations
(advisory)** and **human employment decisions (binding)**. It does *not*
implement AI scoring, ranking, résumé evaluation, fairness models, assessment
generation, or production integrations.

## Core architectural invariant

> **AI evaluates evidence and produces advisory recommendations.
> Only an authenticated human actor may create a binding employment decision.**

This is enforced in **types, service logic, persistence boundaries, tests, and
API permissions** — not merely documented:

* `Recommendation` pins `actor_type = AI`; `Decision` pins `actor_type = HUMAN`.
  A `Decision` **cannot be constructed** with an AI actor.
* Creating a decision requires an **authenticated human** identity — an AI or
  service principal is rejected (and the attempt is audited as a security
  violation).
* **AI actors can never drive a workflow transition.** Binding transitions
  (`ADVANCED`/`HOLD`/`REJECTED`) require a valid human `Decision`.
* The API layer applies an **authorization hook** on every endpoint, in
  addition to the service/policy enforcement beneath it.

## Scope of Phase 1

**Implemented:** domain enums; immutable/versioned contracts
(`NormalizedEvidence`, `LayerScore`, `CandidateEvaluation`, `Recommendation`,
`Decision`, `CandidateWorkflow`, `AuditEvent`); the workflow state machine;
separate recommendation and decision services; append-only audit; in-memory
repositories; the decision-boundary and transition policies; a callable API
facade with authorization hooks; and a full test suite.

**Deliberately excluded (later phases):** LLM calls, résumé parsing, candidate
ranking, assessment delivery, capability scoring, confidence prediction,
fairness/bias analysis, protected-attribute inference, ATS/HRIS integrations,
production database adapters, and frontend components. Interfaces/placeholders
mark where these attach.

## Directory map

```
ai_hiring/
├── README.md
├── __init__.py          # HiringPlatform + build_in_memory_platform() wiring
├── common.py            # stdlib-only helpers: ids, clock, deterministic hash
├── errors.py            # typed domain error hierarchy
├── domain/              # immutable, validated contracts (pydantic, frozen)
│   ├── enums.py         #   ActorType, WorkflowState, Disposition, CapabilityLayer, ...
│   ├── evidence.py      #   NormalizedEvidence, EvidenceRef
│   ├── evaluation.py    #   LayerScore, CandidateEvaluation, ReasonCode, Gap, ...
│   ├── recommendation.py#   Recommendation (advisory, actor=AI)
│   ├── decision.py      #   Decision (binding, actor=HUMAN), Override, Approval
│   ├── workflow.py      #   CandidateWorkflow
│   └── audit.py         #   AuditEvent
├── services/            # orchestration (the only place state mutates)
│   ├── audit_service.py
│   ├── evaluation_service.py
│   ├── recommendation_service.py
│   ├── decision_service.py
│   └── workflow_service.py
├── repositories/        # ports + in-memory adapters
│   ├── interfaces.py
│   └── in_memory.py
├── policies/            # boundary + transition rules (not inline in services)
│   ├── decision_boundary.py
│   └── transition_policy.py
├── api/                 # callable facade + optional FastAPI adapter
│   ├── schemas.py
│   └── routes.py
├── tests/
└── docs/
    ├── ARCHITECTURE.md
    └── IMPLEMENTATION_STATUS.md
```

## How to run the tests

```bash
# from the repository root
python -m pip install pytest pydantic      # pydantic is a declared project dep
python -m pytest ai_hiring/tests -q
```

The module is isolated: it is not in the repository's default `testpaths`, is
not imported by any existing code.

## Packaging / installation verification

`ai_hiring` is registered for package discovery in `pyproject.toml`
(`[tool.setuptools.packages.find]` → `include = [..., "ai_hiring*"]`), so it and
all its subpackages are included in editable installs and built distributions.
To verify install, out-of-root import, tests, and wheel contents:

```bash
# from the repository root
pip install -e .                                    # editable install succeeds
(cd /tmp && python -c "import ai_hiring; print(ai_hiring.__version__)")
python -m pytest ai_hiring/tests -q                 # 51 tests pass

# built wheel contains ai_hiring/ and every subpackage
python -m build --wheel --outdir dist
python - <<'PY'
import glob, zipfile
whl = sorted(glob.glob("dist/*.whl"))[-1]
pkgs = sorted({
    n.split("/", 2)[1] if n.count("/") >= 2 else "ai_hiring"
    for n in zipfile.ZipFile(whl).namelist()
    if n.startswith("ai_hiring/") and n.endswith("__init__.py")
})
print("wheel:", whl)
print("ai_hiring subpackages in wheel:", pkgs)
PY
```

Expected subpackages: `api`, `domain`, `policies`, `repositories`, `services`
(plus the top-level `ai_hiring` package). As with the existing `symbolu*` /
`agentic*` packages, the build also bundles the module's `tests/` files — this
matches the repository's established packaging behavior.

## Example service flow

```python
from ai_hiring import build_in_memory_platform
from ai_hiring.domain.enums import ActorType, Disposition, WorkflowState
from ai_hiring.policies.decision_boundary import StaticIdentityProvider

# 1. Wire a platform with an identity provider (placeholder auth hook).
idp = StaticIdentityProvider()
idp.register_human("hm-alex")
idp.register_ai("ai-eval-engine")
platform = build_in_memory_platform(idp)

ws = platform.workflow_service
ws.initialize("cand-1", "role-backend", correlation_id="corr-1")
for state in (WorkflowState.SOURCED, WorkflowState.ASSESSING, WorkflowState.EVALUATED):
    ws.transition("cand-1", state, actor_type=ActorType.SYSTEM, correlation_id="corr-1")

# 2. Store an evaluation (built elsewhere; scoring is a later phase).
#    evaluation = ... a CandidateEvaluation with all ten capability layers ...
# platform.evaluation_service.store(evaluation, actor_id="ai-eval-engine", correlation_id="corr-1")

# 3. AI recommends — advisory only, no workflow change.
# rec = platform.recommendation_service.create(
#     evaluation_id=evaluation.evaluation_id,
#     suggested_disposition=Disposition.ADVANCE,
#     actor_id="ai-eval-engine", correlation_id="corr-1")

# 4. Move to review, then a human decides (binding). An AI/service principal
#    passed as human_actor_id here is rejected and audited.
# ws.request_review("cand-1", evaluation, correlation_id="corr-1")
# decision = platform.decision_service.create(
#     recommendation_id=rec.recommendation_id, human_actor_id="hm-alex",
#     disposition=Disposition.REJECT, panel=("hm-alex",),
#     rationale_job_related="concurrency gap disqualifying for this role",
#     override=Override(reason="AI over-weighted a happy-path sample"))
```

See `tests/test_end_to_end_foundation.py` for the complete runnable scenario.

## Known exclusions & limitations

* No real identity provider — `StaticIdentityProvider` is a test/dev stand-in.
* No persistent storage — in-memory repositories only.
* No cryptographic audit hash-chain yet (the `previous_event_hash` field is
  reserved so it can be added without a contract change).
* Scoring, fairness, and inference guardrails are **not** implemented; the
  contracts reserve their shape only.
* No legal-compliance claims are made anywhere in code or docs — only
  enforceable controls are described.

## Phase 2 — Evidence Ingestion & Normalization (implemented)

Phase 2 builds the immutable evidence substrate that later AI modules consume:
multi-format ingestion, deterministic normalization, raw/normalized hashing,
job-relevance + prohibited-field quarantine, immutable versioning with full
provenance, contiguous chunking, a deterministic search index, an evidence
lineage DAG, and one append-only audit event per pipeline stage. It adds **no**
scoring, ranking, embeddings, fairness, or LLM inference.

New packages: `normalization/` (pipeline, parsers, cleaners, quarantine,
hashing, provenance, chunking, lineage), `index/` (deterministic search),
plus `services/{evidence_ingestion,search,provenance}_service.py` and
`repositories/{evidence_artifacts,evidence_index_repository}.py`. See
[`docs/EVIDENCE_PIPELINE.md`](docs/EVIDENCE_PIPELINE.md).

Quick example:

```python
from ai_hiring import build_in_memory_platform
from ai_hiring.normalization import RawSubmission, EvidenceFormat

platform = build_in_memory_platform()
sub = RawSubmission.from_text(
    "def solution(): return 42",
    candidate_id="cand-1", role_id="role-backend", assessment_item_id="a1",
    declared_format=EvidenceFormat.SOURCE_CODE, uploader="svc-ats",
    filename="solution.py", assessment_type="WORK_SAMPLE",
)
ingested = platform.evidence_ingestion_service.ingest(sub, correlation_id="corr-1")
print(ingested.evidence_id, ingested.version, len(ingested.chunks))

# deterministic retrieval + lineage + version history
platform.search_service.keyword("solution")
platform.provenance_service.lineage(ingested.evidence_id)
platform.provenance_service.versions(ingested.evidence_id)
```

## Phase 2.5 — Evidence Boundary Hardening (implemented)

Hardens the evidence boundary before any scoring exists: explicit extraction
outcomes, a fail-closed evaluation-eligibility policy, resource limits, DOCX/ZIP
archive-safety, JSON/CSV complexity limits, context-aware duplicate semantics,
lineage-DAG integrity, tenant/candidate/application isolation, authorization-aware
tenant-scoped search, quarantine non-leakage, reconstruction + hash integrity,
atomic (fail-closed) ingestion, and complete success/failure audit sequences.
See [`docs/EVIDENCE_BOUNDARY_HARDENING.md`](docs/EVIDENCE_BOUNDARY_HARDENING.md)
and the machine-readable capability matrix in
`normalization/capability_matrix.py`.

**Format support is not uniform.** In particular, **PDF support is LIMITED** —
bounded native-text extraction from *uncompressed* streams only: **no OCR, no
scanned/image-only pages, no encrypted PDFs, no compressed streams**. An empty
PDF extraction is never accepted as evidence (it fails closed); ambiguous
compressed/image-only PDFs are routed for manual review. DOCX is LIMITED
(archive-safe text extraction; images/encrypted unsupported). See the capability
matrix for every format.

> Scope note: **No hiring evaluation or scoring logic was introduced in Phase
> 2.5** (this phase hardens the evidence substrate only). This is not a claim
> that no scoring logic exists anywhere in the wider repository.

## Phase 3A — Capability Ontology & Rubric Contracts (implemented)

The **constitution of evaluation** — immutable contracts that define what
evaluation *means*, frozen before any evaluator exists. New packages `ontology/`
(capabilities, hierarchy, evidence-type + reason-code vocabularies, versioning)
and `rubrics/` (rubric contracts, capability mappings, scoring scales, evidence
admissibility rules, uncertainty contracts, conflict representation, approval
lifecycle), plus `services/{ontology,rubric,rubric_validation}_service.py` and
`repositories/{ontology,rubric}_repository.py`. Capabilities are immutable and
versioned; rubrics move through Author → Reviewer → Approver → Publisher and are
immutable after publication; only PUBLISHED rubrics may later be used for
evaluation. See [`docs/CAPABILITY_ONTOLOGY.md`](docs/CAPABILITY_ONTOLOGY.md).

> **This phase defines the constitution of evaluation, not the evaluator.** It
> does not evaluate candidates, score, rank, or run any model. No candidate
> evaluation, scoring algorithm, recommendation generation, or LLM inference was
> introduced in Phase 3A.

## Phase 3B — Deterministic Assessment Runtime (implemented)

The runtime that **executes** the Phase-3A constitution deterministically, with
**no AI inference of any kind**. New package `assessments/` (workspaces, evidence
bindings, excluded-evidence and missing-evidence records, observations,
structural completeness, advisory `Assessment`), plus
`services/{evidence_binding,assessment_validation,assessment_completeness,assessment}_service.py`
and `repositories/{assessment_workspace,assessment}_repository.py`, and the
`api/assessment_routes.py` facade. It resolves published rubric/capability
versions, binds *authorized-declared* evidence under the published admissibility
policy, accepts externally supplied **non-AI** observations and validates them by
pure scale membership, records missing evidence, uncertainty, and conflicts,
computes *structural* completeness, and produces immutable, append-only advisory
assessment records. See
[`docs/DETERMINISTIC_ASSESSMENT_RUNTIME.md`](docs/DETERMINISTIC_ASSESSMENT_RUNTIME.md).

> **No LLM inference in Phase 3B.** The runtime binds, validates, records, and
> assembles. It contains no model call, no text interpretation, no embedding, no
> similarity scoring. It never scores from free-form evidence, ranks or compares
> candidates, generates recommendations, makes or authorizes decisions,
> constructs CERs, invokes the ActionGate, or mutates any published contract.
> Every stored value is supplied by an authorized non-AI source and checked for
> conformance — never computed or inferred. `Assessment.advisory_only` is a
> `Literal[True]`, and the runtime carries no score, rank, or decision field.

## Next milestone

**Phase 3C — Interpretation under governance** (future): the first phase in which
an AI system may interpret evidence, strictly under the constitution this runtime
proved executable, and still behind the Phase-1 human-decision boundary and the
governance middleware. It must not invent any contract. Do not begin until all
Phase 1, 2, 2.5, 3A, and 3B tests pass. See
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).
