# RESOLVER_METRICS — Component Metrics for the Resolution Layer

These are **component** metrics for stages 2–4. They are kept entirely separate
from SEEB's pipeline metrics, which are not redefined.

## Graph-structure metrics (stage 2)
| Metric | Definition |
|---|---|
| Relationship Edge Precision | correct predicted edges / all predicted edges |
| Relationship Edge Recall | correct predicted edges / all gold edges |
| Relationship Type Accuracy | nodes with correct type / gold nodes present |
| Cross-document Link Accuracy | gold cross-document edges predicted / all gold cross-document edges |

Edges match on the exact typed triple `(src_citation, edge_type, dst_citation)`.

## Governance / outcome metrics (stages 3–4)
Each is accuracy over the cases tagged with that capability; "correct" =
abstention matches gold when abstention is expected, else the derived answer
`(tfc, notice, penalty)` equals the expected answer.

| Metric | Cases it scores |
|---|---|
| Precedence Resolution Accuracy | supersession / precedence cases |
| Override Resolution Accuracy | explicit override / governs_over cases |
| Exception Resolution Accuracy | exception cases |
| Definition Resolution Accuracy | conflicting-definition cases |
| Version Selection Accuracy | version cases |
| Conflict Resolution Accuracy | contradiction cases |
| Negation Interpretation Accuracy | negation cases |
| Cycle Detection Accuracy | circular-reference cases |
| Cross-document Link Accuracy | reference-following cases |
| Abstention Accuracy | all cases: abstain decision == gold |
| Coverage Abstention | coverage/OCR cases (upstream extraction) |

## Pipeline metrics (reported unchanged, not redefined)
Reported per resolver via `pipeline_bridge.py` using SEEB's own `evaluate_case`
+ aggregator: **Unsafe Handover Rate, Fail-closed Rate, Packet Sufficiency,
Routing Accuracy, Unsupported Claim Rate, Precedence Recall**. These are SEEB's
definitions verbatim. See the caveat in RESOLVER_BASELINES.md (evidence held at
Mode B, resolver varied → read as relative deltas, not the official baseline).

## Why component + pipeline are both reported
Component metrics localise *where* a resolver succeeds or fails (edge, governance,
packet). Pipeline metrics show the *end-to-end* consequence through the unchanged
handover pipeline. A resolver can have high edge recall yet fail end-to-end (as
here: edge recall 0.94 but Precedence Resolution 0.33, the gap living in packet
construction) — reporting both is what makes the failure legible.

## Determinism
All metrics are deterministic; repeated runs are byte-identical (tested).
