# BTRR Protocol Amendment 002 — Corrective (Zero-Truncation Proof + Doc Reconciliation)

**Status: `BTRR_PROTOCOL_AMENDMENT_002_READY_FOR_INDEPENDENT_AUDIT`.**
Documentation-only corrective amendment. No experiment code, no model, no training, no seed consumption.
Execution remains unauthorized and fail-closed. Machine-readable companion:
`BOUNDED_TYPED_RELATIONAL_REASONING_PROTOCOL_AMENDMENT_002.json`.

Preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL`,
`KDA_VALIDATION_BLOCKED`.

## 0. Audit finding accepted
The independent adversarial audit returned **`BTRR_AMENDMENT_001_REQUIRES_CORRECTION`**. Accepted without
dispute. The audit affirmed as valid: Amendment 001's tokenizer design, parameter-accounting method,
scientific-task preservation, gate preservation, causal interpretation, append-only provenance, and
execution lock. The **material defect**: the original preregistration does not numerically bound all
serialization-size-driving dimensions, so Amendment 001 cannot *prove* that `input_token_limit = 1664` and
`max_seq_len = 2048` accommodate every legal preregistered episode. Amendment 002 repairs exactly this
(the zero-truncation proof) plus the two minor documentation inconsistencies, and changes nothing
scientific.

## 1. Citations (append-only; originals not rewritten)
- Original preregistration commit **`626a897a513eb7e415cde6fbaff10e9e922b8abb`**.
- Implementation blocker commit **`f8dd65c5e734bc1f31eaf100e4069c050d014e8c`**.
- Amendment 001 commit **`9e6168f93c850acbf2bc134d5226aad1572c1add`** (preserved unchanged).
- Audit verdict **`BTRR_AMENDMENT_001_REQUIRES_CORRECTION`**.

What A001 got right: the separate frozen BTRR tokenizer (80 lexemes, vocab 211), the weight-tied
parameter method, and holding the reasoning architecture/task/gates fixed. What A002 repairs: it makes the
legal input space **finite and explicit**, then re-derives context capacity from the *proven* maximum
(A001's 1664/2048 were computed from an unproven "worst case" and are superseded).

## 2. Scientific experiment preserved (unchanged)
Q0/Q2 question; P0 B1–B7; R1–R12 semantics; PATH_GIVEN/PATH_DISCOVERY; entity density 6–12; event density
2–4/entity; temporal, policy, and authorized-absence semantics; structured output contract; all scientific
metrics; all numeric gates; shortcut gates; verdict precedence; 4-of-5 final-seed rule; model depth,
hidden dim, heads, FFN, attention architecture; optimizer/training recipe; reserved-seed assignments.
This correction only makes the finite legal input space explicit so zero-truncation is provable.

## 3. Frozen size-dimension caps (bound the experiment honestly first)
Every model-visible variable-length dimension is now explicitly bounded. Caps are chosen for scientific
sufficiency and are **not** reverse-engineered to fit A001's 1664/2048 (which they in fact exceed).

| Dimension | Cap | Why scientifically sufficient | Serialization consequence |
|---|---|---|---|
| Entities/episode | 6–12 (unchanged) | frozen density; entity-selection chance ≤1/6 | ≤12 ENT lines |
| Events/entity | 2–4 (unchanged) | frozen temporal density | ≤48 EVT lines total |
| Relation records | 20 | 3-hop discovery + confusable near-duplicate paths (~1.7/entity) | ≤20 REL lines |
| Max hops / path length | 3 | matches preregistered R3/R4 "2–3 hops" | ≤3 chain rtypes; ≤8 output path nodes |
| Policies/episode | 4 | 1 applicable + ≤3 near-miss distractors | ≤4 POL lines |
| Conditions/policy | 4 | composite typed (temporal+attribute+relational) conditions | ≤4 COND clauses/POL |
| Evidence records | 16 | required support + distractor evidence for precision/recall | ≤16 EVD lines |
| Attributes/entity | 3 | intended fact density for policy-condition reference | ≤3 key/value pairs/ENT |
| Identifier length (ctx/tenant/entity/event/evidence/policy) | 6 chars | unique + copyable within episode; opaque, not answer-encoded | ≤6 ASCII tokens/ID |
| Attribute/event value, condition literal | 9 tokens | enterprise amounts ≤9 digits; uniform conservative cap | ≤9 tokens/value |
| Numeric literal digits | 9 | amount thresholds | ≤9 tokens |
| Sequence integer digits | 2 | ≤48 events fit in 2 digits | ≤2 tokens/sequence |
| Reasoning-path nodes (output) | 8 | ≤3 hops + event + policy nodes | ≤8 path nodes |
| Evidence ids (output) | 16 | ≤ max_evidence | ≤16 output ids |

`context_id` is metadata and is **not** model-visible (not serialized). Attribute keys, entity/relation/
event/policy types, operators, statuses, path modes, requested-property, and policy-scope are all frozen
lexemes (length-bounded by construction). The uniform 9-token value cap is a deliberate conservative
over-approximation: it upper-bounds every value field whether numeric or categorical, so the
zero-truncation guarantee is safe even for value shapes the generator never intends to emit.

## 4. Caps do not make the experiment easier (difficulty vs representation)
- Bounding **opaque ID length** (6) does not reveal any answer — IDs remain opaque and copyable.
- Bounding **policies** (4) does not remove policy reasoning — a distractor-laden policy-selection task
  remains.
- Bounding **relation records** (20) still permits multi-hop discovery and required confusable distractors.
- Bounding **evidence** (16) does not remove evidence-grounding — selective citation among distractors
  remains.
- Bounding **attributes** (3) preserves the intended fact density used by policy conditions.
- Bounding **conditions/policy** (4) preserves composite temporal+attribute policy evaluation.
- Entity density (6–12) and event density (2–4/entity) are **unchanged**.

No cap materially narrows a previously intended scientific capability. Therefore this is a corrective
amendment, **not** `BTRR_AMENDMENT_REQUIRES_SCIENTIFIC_REDESIGN`.

## 5. Proven legal maximum (frozen A001 tokenizer + compact serializer; tokenizer-only)
A single boundary fixture **simultaneously saturates every compatible cap** (12 entities × 3 attrs; 20
relations; 48 events; 4 policies × 4 conditions; 16 evidence; 6-char IDs; 9-token values; 2-digit
sequences; longest PATH_GIVEN 3-chain query line as a strict over-approximation across splits). Measured
token counts (no model, no seeds):

| Fixture | Tokens |
|---|---|
| **Maximal legal input (R9/R12 over-approximation, all caps saturated)** | **2901** |
| Maximal P0 input (bounded entity set + evidence for copy/select) | 643 |
| Maximal ReasoningOutput (outcome + 8-node path + 16 evidence ids + status) | 194 |
| Maximal input + output combined | 3095 |

Maximal input serialized shape (schematic): `CTX <id6>` · `QRY path_then_latest PATH_GIVEN <id6>
approval_requirement vendor_risk risk governed_by approved_vendor supplies` · 12×`ENT vendor <id6> amount
<9> region <9> tier <9>` · 20×`REL <id6> governed_by <id6>` · 48×`EVT <id6> <id6> risk <2> <9>` · 4×`POL
<id6> COND amount GT <9> ×4 OUT VP_APPROVAL_REQUIRED` · 16×`EVD <id6> supports <id6>`. Joint-saturation
note: PATH_GIVEN vs PATH_DISCOVERY query-line difference is ≤3 tokens; using the longest query line
upper-bounds every split, so 2901 bounds all legal episodes of any task type.

## 6. Context capacity from the proven maximum (A001's limits superseded)
Same mechanical rule: worst legal input + 20% fixed margin, round up to a 64-token boundary; output floor
384; **no truncation**.

| Limit | Amendment 001 | **Amendment 002** | Basis |
|---|---|---|---|
| `input_token_limit` | 1664 | **3520** | 2901 worst + 21% margin, round 64 |
| `output_token_limit` | 384 | **384** (unchanged) | worst output 194 ≪ 384 |
| `max_seq_len` | 2048 | **3904** | ≥ input_token_limit + output_token_limit = 3904 |

A001's 1664/2048 are honestly superseded: the proven worst input (2901) exceeds A001's entire 2048
context, which is precisely the audit's point.

## 7. Parameter accounting (recomputed for the new max_seq)
`d_model = 64`; weight-tied output head (vocab growth counted once).

| Model | vocab | max_seq | token emb | positional emb | reasoning blocks | total |
|---|---|---|---|---|---|---|
| Single-hop original | 200 | 1024 | 12,800 | 65,536 | 131,392 | **209,728** |
| Amendment 001 | 211 | 2048 | 13,504 | 131,072 | 131,392 | **275,968** |
| **Amendment 002** | 211 | 3904 | 13,504 | 249,856 | 131,392 | **394,752** |

- Δ vs single-hop: **+185,024 (+88.2%)**. Δ vs Amendment 001: **+118,784**.
- The increase is entirely the positional-embedding table (65,536 → 249,856) plus the 11 extra embedding
  rows from A001's vocabulary (+704, unchanged in A002). **Reasoning-block parameters: 131,392 →
  131,392, delta 0.**
- Stated exactly: *reasoning depth/width/heads/FFN remain unchanged; total trainable parameters increase
  because representation/sequence capacity increases.* The model is **not** parameter-identical.

## 8. Gate-impact analysis (every frozen scientific gate)
| Gate | Classification |
|---|---|
| All §8 numeric gates (answer/entity/path/latest-event/policy/evidence/abstention/hallucination/R4/R7/R9/R12) | **UNCHANGED_AND_VALID** — derived from chance/competence/structure-blind baselines; independent of vocab and context length |
| Structured-output-validity gate (≥0.98) | **MECHANICALLY_AFFECTED_BUT_STILL_VALID** — same contract/threshold, larger context |
| Structure-blind / shortcut gates | **UNCHANGED_AND_VALID** |
| Verdict precedence (0 PROTOCOL_VIOLATED → 1 base capability → …) | **UNCHANGED_AND_VALID** |
| Final-seed rule (≥4/5), reserved seeds, single-checkpoint invariant | **UNCHANGED_AND_VALID** |
| **INVALIDATED** | **None** |

No scientific numeric gate changes → the corrective amendment is valid.

## 9. Documentation reconciliations (the two minor audit findings)
**A — `capacity_increase` override (explicit).** The original `..._PREREGISTRATION.json`
`model.forbidden_components` lists `capacity_increase`. Amendments 001/002 **supersede that item only for**:
lexical representation capacity (tokenizer vocabulary; the token-embedding rows it implies) and sequence
capacity (the positional-embedding rows implied by `max_seq_len`). It **remains forbidden** for reasoning
depth, hidden width, attention heads, FFN width, attention architecture, and any specialized reasoning
module. This override is now explicit, not implicit.

**B — P0 tokenizer naming (reconciled, append-only).** The original
`..._BASE_CAPABILITY_PREREQUISITE.md` references `LexicalTokenizer` (the single-hop class). Clarification:
P0 and R1–R12 use the **same BTRR-specific frozen tokenizer** introduced by Amendment 001. The scientific
invariant is **same tokenizer + same checkpoint for P0 and R1–R12** — not reuse of the single-hop
tokenizer implementation. The original P0 document is not rewritten.

## 10. Audit-response / review matrix
| Audit finding | Amendment-001 state | Amendment-002 correction | Scientific effect | Status |
|---|---|---|---|---|
| Unbounded relation records | assumed 12 | frozen cap 20 (rationale §3) | none | Resolved |
| Unbounded max_hops | implicit | frozen cap 3 (= R3/R4 "2–3") | none | Resolved |
| Unbounded policies | assumed 2 | frozen cap 4 | none | Resolved |
| Unbounded conditions/policy | assumed 3 | frozen cap 4 | none | Resolved |
| Unbounded evidence | assumed 10 | frozen cap 16 | none | Resolved |
| Unbounded R12 distractors | implicit | bounded within entity/relation/event caps | none | Resolved |
| Unbounded identifier length | assumed short | frozen cap 6 chars | none | Resolved |
| Unbounded attribute/value lengths | assumed short | 3 attrs/entity; value ≤9 tokens; numeric ≤9 digits; seq ≤2 digits | none | Resolved |
| Zero-truncation proof | asserted (1348), unproven | **proven 2901** → input 3520 / max_seq 3904 (+20% margin) | none | Resolved |
| `capacity_increase` override | implicit | explicit (lexical + sequence only) | none | Resolved |
| P0 tokenizer naming | "LexicalTokenizer" | same BTRR frozen tokenizer + same checkpoint | none | Resolved |

## 11. Provenance & execution lock
Amendment 001 (`.md`/`.json`) and the original preregistration are **not** altered. The protocol-lock
index is updated append-only to point to Amendment 002.
`experiments/relational_reasoning_bounded_context/EXECUTION_AUTHORIZATION.md` remains **unsigned /
fail-closed**; reserved seeds smoke `8100`, dev `8101–8103`, final `81600–81604` are unchanged and
untouched; no new reserved seed created. Only tokenizer/schema sizing on handcrafted strings was performed.
