# TAP — Layer Specifications v0.1

Each layer: single responsibility · explicit inputs · outputs · provenance · failure
modes · abstention · confidence · evaluation metrics. Architecture-only; no code.

> Boundary: `12_RESEARCH_BOUNDARIES.md`. Build status: `01_…§4` (only Layer 4 has a
> synthetic prototype).

---

## Ownership matrix (no shared cells)

| Responsibility | Owning layer |
|---|---|
| scope / user intent | Intent Understanding |
| candidate evidence retrieval | Trusted Retrieval |
| relationship supported-by-evidence? | Layer 1 |
| relationship applicability / who governs? | Layer 2 |
| assemble minimum complete evidence | Layer 3 |
| per-claim factual support | Layer 4 |
| whole-answer faithfulness | Layer 5 |
| final policy admissibility | Safety / Policy |

No responsibility appears twice.

---

## Pre-truth stage — Intent Understanding

- **Responsibility:** turn the user request into a scoped, typed query (entities,
  intent type, constraints). Not a truth layer.
- **Inputs:** raw user request.
- **Outputs:** `ScopedQuery` (intent, entities, constraints, scope hints).
- **Failure modes:** misscoped intent, dropped constraint.
- **Abstention:** ambiguous intent → request clarification.
- **Metrics:** intent classification accuracy; constraint-capture recall.

## Pre-truth stage — Trusted Retrieval

- **Responsibility:** produce candidate evidence (documents + spans) for the scoped
  query. Not a truth layer; it does not decide truth.
- **Inputs:** `ScopedQuery`.
- **Outputs:** `CandidateEvidence` (documents, spans, retrieval scores, provenance).
- **Failure modes:** missing relevant evidence; retrieval of misleading evidence.
- **Abstention:** insufficient candidate evidence → downstream abstention signal.
- **Metrics:** retrieval recall/precision against a labeled evidence set.

---

## Layer 1 — Relationship Truth Layer

- **Single responsibility:** determine whether proposed semantic relationships are
  actually supported by evidence. **Never makes governance decisions.**
- **Relationship vocabulary (examples):** `same_as`, `supersedes`, `overrides`,
  `references`, `depends_on`, `supports`, `contradicts`.
- **Inputs:** `CandidateEvidence` + proposed relationships.
- **Outputs:** validated / rejected / uncertain relationships, each with provenance
  and a **relationship-confidence** dimension.
- **Failure modes:** false relationship acceptance; false rejection; direction
  error; entity error.
- **Abstention:** relationship abstention (`09_…`) when evidence is insufficient.
- **Metrics:** relationship precision/recall; direction accuracy; abstention
  correctness.
- **Prototype note:** the existing synthetic `relationship_claim_validation/`
  validates relationship *claims* and is the closest reference; a dedicated Layer-1
  experiment is future work (`11_…`).

## Layer 2 — Governance Truth Layer

- **Single responsibility:** determine **applicability** — which supported
  relationships actually govern. **Never invents relationships** (consumes Layer 1's
  validated set only).
- **Concerns:** operative source, authority, supersession, exceptions, scope,
  domain, temporal validity, conflict resolution.
- **Inputs:** validated relationships (Layer 1) + governance metadata.
- **Outputs:** validated governing relationships, operative source, applicable
  evidence, or **governance abstention**.
- **Failure modes:** wrong operative source; missed exception; unresolved conflict
  treated as resolved (or vice versa); scope/temporal/authority misapplication.
- **Abstention:** governance abstention on genuine unresolved conflict.
- **Metrics:** operative-source accuracy; conflict-resolution correctness;
  abstention correctness on genuine-conflict cases.

## Layer 3 — Evidence Packet

- **Single responsibility:** produce the **minimum complete** evidence downstream
  reasoning needs. **No natural-language generation.**
- **Packet contents:** documents, supporting spans, governance path, relationship
  path, provenance, confidence.
- **Inputs:** Layer 1 + Layer 2 outputs.
- **Outputs:** an `EvidencePacket`.
- **Failure modes:** incompleteness (omits a material obligation/exception);
  over-inclusion (packet not minimal); provenance gaps.
- **Abstention:** cannot assemble a complete packet → abstain / escalate.
- **Metrics:** completeness (all material evidence present); minimality; provenance
  coverage.

## Layer 4 — Claim Truth Layer

- **Single responsibility:** validate every factual claim produced from the packet;
  each claim is an atomic hypothesis.
- **Statuses:** `SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONTRADICTED`, `UNSUPPORTED`,
  `INSUFFICIENT_EVIDENCE`, `UNKNOWN`.
- **Must distinguish:** missing evidence · contradictory evidence · unsupported
  inference · scope leakage · temporal leakage · authority leakage.
- **Inputs:** `EvidencePacket` + candidate claims.
- **Outputs:** per-claim `EvidenceRecord` (status, action, spans, missing
  predicates, claim-confidence).
- **Failure modes:** accepting an unsupported claim; rejecting a supported one;
  missing a leakage class.
- **Abstention:** claim abstention (`INSUFFICIENT_EVIDENCE`).
- **Metrics:** claim precision/recall; per-status accuracy; leakage-detection rate.
- **Prototype note:** a **synthetic** reference implementation exists —
  `relationship_claim_validation/` v0.1 — with deterministic judges and the six
  statuses. It is construction-validated only (see its `FINAL_VERDICT.md`).

## Layer 5 — Response Truth Layer

- **Single responsibility:** validate the **complete answer** for faithfulness to the
  validated claims. Owns only response correctness.
- **Checks:** unsupported additions · missing citations · hallucinated facts ·
  contradictions · missing qualifications · over-generalization.
- **Inputs:** draft response + validated claims + packet.
- **Outputs:** validated response, required edits/qualifications, or **response
  abstention**.
- **Failure modes:** passing a hallucinated addition; demanding a spurious edit;
  missing an over-generalization.
- **Abstention:** response abstention (refuse / hedge) when the answer cannot be made
  faithful.
- **Metrics:** faithfulness (claim-coverage), citation completeness,
  over-generalization detection.

---

## Safety / Policy Layer (post-truth)

- **Responsibility:** final admissibility (policy, safety, compliance). Distinct from
  truth. In this monorepo a separate ActionGate/enforcement line addresses
  action-admissibility; it is **out of TAP scope** and unmodified.
