# ANNOTATION_SCHEMA

The blind-annotator artifact (`AnnotatorRecord`) — produced from the documents
alone. Field list is fixed; author-only fields are structurally absent.

| Field | Meaning |
|---|---|
| cand_id | opaque content-hash id |
| graph.nodes | citation → node type (Clause/Definition/Exception/Policy/Table/Version/Document) |
| graph.edges | list of typed, directed `(src, type, dst)` |
| governing | citations that govern |
| defeated | citations discarded by a precedence edge (with reason = the edge) |
| abstain | whether the correct outcome is abstention |
| packet_expectation | {tfc, notice_days, penalty} or {abstain: true} |
| ambiguity_status | free-text ambiguity note ("none" if unambiguous) |
| confidence | annotator confidence in [0,1] |
| evidence_provenance | `"src|type|dst"` → verbatim needle located in a document |

## Provenance
Every accepted edge carries a provenance needle that appears in a document
(GOLD sufficiency: 0 issues). Provenance is stored ONLY in evaluation-facing
annotations and is never exposed to resolver-facing code.

## Banned (author-only) fields
`author_rationale, intended_graph, proposed_difficulty, intended_capability,
expected_answer, template_id, target_weakness, dev_case_ref` — never present on an
annotator record (enforced).
