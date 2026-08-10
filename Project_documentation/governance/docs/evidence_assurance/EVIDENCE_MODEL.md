# Evidence Model

*Phase 2. The canonical evidence unit and the separately-defined evidence dimensions. Dimensions are
kept distinct — never collapsed into one score at this layer. Source of truth:
`evidence_assurance/evidence.py` (`ea_evidence_v1`).*

## Canonical evidence unit (`EvidenceUnit`)

| Field | Meaning |
|---|---|
| `evidence_id`, `source_id` | identity of the item and its source |
| `source_type`, `publisher`, `authority_class` | what kind of source, who owns it, how authoritative |
| `retrieval_path` | which retriever/index produced it (for retrieval-path independence) |
| `upstream_source_id` | the source this one **derives from** (None ⇒ primary) |
| `content_ref`, `passage_ref`, `claim_ref` | reference to content / cited passage / target claim (never raw content) |
| `publication_time`, `retrieval_time` | for freshness / supersession |
| `jurisdiction`, `domain` | for jurisdiction/authority matching |
| `primary`, `derivative` | primary vs secondary; derivative (summary/syndication) or not |
| `citation_parent`, `citation_chain` | citation lineage (for circularity / laundering) |
| `content_hash`, `semantic_dupe_group` | exact and near/semantic duplicate detection |
| `provenance_confidence` | confidence in the **metadata itself** (may be low/fabricated) |
| `freshness_state`, `independence_state`, `support_state`, `contradiction_state`, `scope_match_state` | per-dimension states, each may be `unknown` |
| `evidence_quality`, `missing_metadata`, `uncertainty` | quality, what metadata is absent, residual uncertainty |

`ClaimUnit` carries the claim's domain, risk class, jurisdiction, timeframe, population, and scope;
`EvidenceBundle` groups all evidence (and counterevidence) offered for one claim.

## The eight dimensions, defined separately (do not collapse)

| Dimension | Question |
|---|---|
| **Support** | Does the evidence support the claim (content-relevant)? |
| **Entailment** | Does the claim logically follow from the evidence? |
| **Alignment** | Is the evaluated passage the one actually cited for this claim? |
| **Authority** | Is the source appropriate for this domain and decision? |
| **Independence** | Does the source *not* merely derive from the same upstream source as another item? |
| **Freshness** | Is the evidence current enough for the claim? |
| **Coverage** | Does the evidence support the *full* claim scope (not just a narrower part)? |
| **Counterevidence** | Does credible evidence exist against or limiting the claim? |

These are orthogonal. A claim can be **entailed** by evidence that is **stale**, **misaligned** (the
cited passage supports a *different* claim), from a **low-authority** source, and **not independent**
(ten copies of one wrong article). Collapsing them into a single "grounding score" is precisely the
move that made correlated failure invisible in the prior studies — so this layer keeps them apart and
only the disposition logic (Phase 11) combines them, transparently.

## Provenance-confidence is first-class

`provenance_confidence` (and per-item `missing_metadata`) exist because **real provenance is
incomplete or even fabricated**. The model must be able to represent "this claims to be an
independent official source, but we cannot verify the metadata" — and never treat missing provenance
as independence (a hard rule enforced in Phase 9/13).
