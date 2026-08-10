# TAP-E5 — Evidence Assembly — Experiment Report

## 1. Objective

Implement and evaluate a **deterministic Evidence Assembly layer**. Given the four frozen
upstream records — `IntentRecord` (E1), `RetrievalRecord` (E2), `RelationshipRecord` (E3),
`GovernanceRecord` (E4) — assemble exactly one `EvidencePacket`: the **smallest complete,
dependency-preserving, provenance-preserving** object required by downstream claim
validation.

E5 is the pipeline's **linker**. The previous stages discover information; E5 packages it
into one deterministic object. Its purpose is *not* to determine truth, reason, validate
claims, or generate responses — only to assemble the minimal complete evidence package.

## 2. Boundary (what E5 is not)

E5 performs **no retrieval, no LLM calls, no external APIs, no new evidence**. It **never**
determines truth, validates claims, generates responses, performs governance reasoning,
resolves a conflict, or fills a gap. It never invents, summarizes, rewrites, or merges
evidence, and never merges semantically distinct evidence. It consumes only the four frozen
upstream records through their public interfaces and adds no field to them.

## 3. Inputs and output

**Inputs:** `IntentRecord`, `RetrievalRecord`, `RelationshipRecord`, `GovernanceRecord`
(all frozen public interfaces).

**Output:** one immutable, deterministic `EvidencePacket` (see [SCHEMA](SCHEMA.md)) carrying:
intent reference; the required evidence units (with provenance, confidence, retrieval
metadata); the relationships supported by that evidence (type, direction, polarity,
modality, temporal qualifiers, provenance); the governance decisions (governing authority,
rejected authorities, precedence, exception/temporal/jurisdiction/scope basis, governance
confidence); an explicit **dependency graph**; every **conflict** unchanged; every **gap**
unchanged; carried **confidence** (not recomputed); and a per-object **provenance index**.

## 4. Method

### 4.1 EvidencePacket principles

Immutable · deterministic · provenance-preserving · dependency-preserving · minimal ·
complete · lossless with respect to downstream validation. Minimization removes **only**
duplicate references, duplicate dependency paths, transitively-unnecessary objects, and
downstream-unused metadata. It **never** removes supporting evidence, alternative/rejected
governing authorities, minority evidence, conflicts, gaps, confidence, provenance, or
dependency edges.

### 4.2 Fourteen-stage deterministic pipeline

`validate upstream schemas → import records → build dependency graph → collect reachable
evidence → collect reachable relationships → collect reachable governance → collect
conflicts → collect gaps → deduplicate references → dependency-integrity verification →
provenance verification → packet minimization → packet validation → packet freeze`. Every
stage emits trace metadata; every sort carries a stable id tiebreak; no output depends on
set/dict iteration order. See [ARCHITECTURE](ARCHITECTURE.md).

### 4.3 Ablation ladder (A–F)

| Config | Adds | Intended weakness |
|---|---|---|
| **A** | naive union | duplicate ids, orphan (unused) evidence, no provenance |
| **B** | deduplicate | still ships unused evidence; no provenance |
| **C** | dependency-aware (winner closure only) | drops rejected/minority evidence → *smaller but incomplete* |
| **D** | + full closure | complete, but no provenance index |
| **E** | + provenance | complete + provenanced, but not minimized / unvalidated |
| **F** | + minimization + validation + freeze | — (full) |

Configuration is selected on the **DEV split only**: the simplest baseline (A..F) satisfying
every preregistered gate. The locked eval split is scored once, for the verdict.

## 5. Corpus

New, independently authored: **32 packet cases across 13 families** (dev 16 / eval 16).
Families: single / multiple / shared / unused evidence, rejected authorities (minority
evidence), multiple governing authorities, E3 conflicts, E4 conflicts, multiple gaps,
nested dependencies, independent dependency trees, deep provenance, minimal-packet edge
cases. Each case is compiled into the four upstream records via their public schemas; the
minimal-complete **gold is computed independently of the assembler**. See [CORPUS](CORPUS.md).

## 6. Results

Selection chose **baseline F** — the simplest configuration passing every preregistered gate
on DEV; every earlier baseline fails ≥1 gate:

| Baseline | DEV gates passed | First blocking failures |
|---|---|---|
| A | no | duplicate/minimality/provenance/orphan/validation/size + severe criticals |
| B | no | minimality/provenance/orphan/validation + severe criticals |
| C | no | completeness/reference-integrity (over-pruned minority) + severe criticals |
| D | no | provenance/minimality/validation + severe criticals |
| E | no | minimality/validation + severe criticals |
| **F** | **yes** | — |

**Locked eval, selected baseline F — all 14 gates pass** (completeness, minimality,
dependency-preservation, provenance-preservation, reference-integrity, conflict-preservation,
gap-preservation, duplicate-elimination = 1.00; unsupported-reference-rate, orphan-rate = 0;
validation-success, determinism = 1.00; packet-size-reduction = 0.32 ≥ 0.05;
severe-critical-failure-count = 0). All twelve critical-failure classes are **0** for F on
both splits. See [METRICS](METRICS.md) and [FAILURE_ANALYSIS](FAILURE_ANALYSIS.md).

## 7. Verdict

**`PASS_WITH_LIMITED_CLAIM`.**

**Supported claim (narrow):** TAP-E5 deterministically assembles a minimal,
provenance-preserving, dependency-preserving `EvidencePacket` from frozen upstream TAP
records. It preserves all information required for downstream claim validation while
introducing no new reasoning, evidence, governance decisions, or factual assertions.

**Explicitly NOT claimed / does not do:** E5 does not validate claims, determine truth,
resolve conflicts, fill gaps, retrieve evidence, or perform governance reasoning. Results are
mechanism/construction validation on this study's synthetic corpus with authored upstream
fixtures — not production performance or external generalization.

## 8. Integrity

- TAP-E1, TAP-E1.1, TAP-E2, TAP-E3, TAP-E4 are **unchanged** (byte-identical frozen hashes
  and stored artifacts; consumed through frozen public interfaces only).
- Deterministic across `PYTHONHASHSEED ∈ {0,1,7,42,123}` — identical result hash and
  `frozen_components_hash`.
- Full repository regression: **153 tests pass**.
- `frozen_components_hash = 7a91bcf9…`; `eval_inputs_hash = 04b87570…` (n_eval = 16).

## 9. Freeze & next layer

The `EvidencePacket` public interface is **frozen** as the downstream contract. The **next
layer is TAP-E6 — Claim Validation**: the first layer that evaluates whether a proposed claim
is actually supported by the assembled packet. E5's sole responsibility is ensuring that
packet is complete, minimal, deterministic, and fully traceable. See
[CHANGELOG](CHANGELOG.md) and [LEAKAGE_AUDIT](LEAKAGE_AUDIT.md).
