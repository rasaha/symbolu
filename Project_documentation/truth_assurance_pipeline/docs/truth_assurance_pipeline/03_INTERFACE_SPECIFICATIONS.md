# TAP — Interface Specifications v0.1

Typed interface **definitions** (responsibilities and signatures), not
implementations. These are specification sketches; they are **not** production code
and nothing here is wired into any existing system.

> Boundary: `12_RESEARCH_BOUNDARIES.md`.

---

## 1. Conventions

- Interfaces are shown as abstract type signatures. A conforming implementation is a
  separate, future, single-layer experiment (`11_…`).
- Every layer method takes the shared `Provenance` (append-only, `04_…`) and returns
  an updated one alongside its typed output.
- Every layer output carries a `ConfidenceVector` (`05_…`) and may carry an
  `Abstention` (`09_…`).

## 2. Shared types (sketch)

```
ScopedQuery        = { intent, entities[], constraints[], scope_hints[] }
Document           = { doc_id, spans[] }
Span               = { span_id, doc_id, text, offsets, meta }
CandidateEvidence  = { documents[], spans[], retrieval_scores{}, provenance }
Relationship       = { rel_id, type, source, target, scope?, temporal?, authority? }
EvidencePacket     = { documents[], supporting_spans[], relationship_path[],
                       governance_path[], provenance, confidence }
Claim              = { claim_id, text, cited_span_ids[], derived_from_packet_ref }
EvidenceRecord     = { claim_id, status, action, supporting_spans[],
                       contradicting_spans[], missing_predicates[], confidence }
ResponseDraft      = { text, claim_refs[], citations[] }
ValidatedResponse  = { text, edits[], qualifications[], abstained?, provenance }
Provenance         = append-only object (see 04_)
ConfidenceVector   = multidimensional (see 05_)
Abstention         = { layer, reason, evidence_refs[] } | null
```

## 3. Layer interfaces (sketch)

```
interface IntentUnderstanding:
    understand(request: str, prov: Provenance)
        -> (ScopedQuery, Provenance)

interface TrustedRetrieval:
    retrieve(q: ScopedQuery, prov: Provenance)
        -> (CandidateEvidence, Provenance)

interface RelationshipTruthLayer:                      # Layer 1
    validate(evidence: CandidateEvidence,
             proposed: Relationship[], prov: Provenance)
        -> (RelationshipVerdicts, Provenance)
    # RelationshipVerdicts = { validated[], rejected[], uncertain[], confidence }
    # MUST NOT make governance decisions.

interface GovernanceTruthLayer:                        # Layer 2
    govern(validated: Relationship[], meta: GovernanceMeta, prov: Provenance)
        -> (GovernanceResult, Provenance)
    # GovernanceResult = { governing[], operative_source, applicable_evidence[],
    #                      abstention?, confidence }
    # MUST NOT invent relationships.

interface EvidencePacketBuilder:                       # Layer 3
    build(rel: RelationshipVerdicts, gov: GovernanceResult, prov: Provenance)
        -> (EvidencePacket, Provenance)
    # MUST NOT generate natural language.

interface ClaimTruthLayer:                             # Layer 4
    validate(packet: EvidencePacket, claims: Claim[], prov: Provenance)
        -> (EvidenceRecord[], Provenance)
    # status ∈ {SUPPORTED, PARTIALLY_SUPPORTED, CONTRADICTED,
    #           UNSUPPORTED, INSUFFICIENT_EVIDENCE, UNKNOWN}

interface ResponseTruthLayer:                          # Layer 5
    validate(draft: ResponseDraft, records: EvidenceRecord[],
             packet: EvidencePacket, prov: Provenance)
        -> (ValidatedResponse, Provenance)
    # owns response correctness only.

interface SafetyPolicyLayer:                           # post-truth (out of TAP scope)
    admit(resp: ValidatedResponse, prov: Provenance)
        -> (FinalResponse, Provenance)
```

## 4. Contract rules (enforced by review, not by this document's code)

1. **Type isolation.** A layer may read only the upstream types listed in its
   signature; it may not reach around the pipeline.
2. **Provenance append-only.** Every method returns a Provenance that *extends* its
   input (`04_…`); replacing it is a contract violation.
3. **No cross-responsibility mutation.** Layer 2 receives Layer 1's verdicts as
   read-only; it cannot add or edit relationships.
4. **Deterministic-first.** Where a deterministic validator applies (`07_…`), the
   layer must consult it before any judge, and a deterministic result is
   authoritative.
5. **Confidence + abstention mandatory.** Every layer output includes a
   ConfidenceVector and may carry an Abstention; neither is optional.

## 5. Replaceability

Because layers communicate only through these signatures, any layer implementation
can be replaced (e.g. a deterministic Layer 4 vs an LLM-judge Layer 4) without
changing another layer — the independent-replaceability success criterion. The only
existing conforming artifact is the synthetic Layer-4 prototype in
`relationship_claim_validation/`.
