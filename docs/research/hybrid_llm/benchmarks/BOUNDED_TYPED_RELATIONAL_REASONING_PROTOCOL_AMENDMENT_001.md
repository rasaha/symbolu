# BTRR Protocol Amendment 001 — Representation-Capacity Only

**Status: `BTRR_PROTOCOL_AMENDMENT_001_READY_FOR_OWNER_REVIEW`.**
Documentation-only amendment. No experiment code, no model, no training, no seed consumption. Execution
remains unauthorized and fail-closed. Machine-readable companion:
`BOUNDED_TYPED_RELATIONAL_REASONING_PROTOCOL_AMENDMENT_001.json`.

Preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL`,
`KDA_VALIDATION_BLOCKED`.

## 0. What this amendment does and does not do
This amendment makes the **smallest representation-capacity change** needed to make the already-frozen
BTRR experiment *representable* by the harness. It changes only lexical vocabulary and sequence capacity.
It does **not** change the scientific question, task semantics, entity/event density, the PATH_GIVEN /
PATH_DISCOVERY distinction, the reasoning architecture, the metrics, the numeric gates, the shortcut
gates, the verdict precedence, the final-seed requirement, or the reserved seeds. The
`..._IMPLEMENTATION_BLOCKER.md` finding is preserved and remains authoritative until this amendment is
approved.

## 1. Citations
- Original preregistration: `BOUNDED_TYPED_RELATIONAL_REASONING_PREREGISTRATION.md` (+ `.json`).
- Original protocol lock: `BOUNDED_TYPED_RELATIONAL_REASONING_PROTOCOL_LOCK.md`.
- Implementation blocker: `BOUNDED_TYPED_RELATIONAL_REASONING_IMPLEMENTATION_BLOCKER.md`, commit
  **`f8dd65c5e734bc1f31eaf100e4069c050d014e8c`**.

## 2. Exact conflicting clauses (from the blocker)
1. Reuse of the single-hop frozen tokenizer (vocab 200; 69/69 lexeme slots consumed) vs. the BTRR schema
   and output vocabulary (events/policies/conditions/path_mode/reasoning_path + statuses `SUPPORTED`,
   `POLICY_NOT_APPLICABLE`, `INVALID_RELATION_PATH`).
2. Frozen `input_token_limit = 512` / `max_seq = 1024` vs. upper-range R9/R12 serialization (measured
   **1348** tokens even in the most compact form).
3. Frozen `config.py` `STATUS_VALUES` / `OUTPUT_FIELDS` vs. the BTRR 4-status output contract carrying
   `reasoning_path` (required by the exact-ordered path metric).

## 3. Exact changed clauses (representation capacity only)
| Clause | Old (frozen) | New (Amendment 001) |
|---|---|---|
| Tokenizer | reuse `single_hop_typed_vs_prose/tokenizer.py` | **new BTRR-specific frozen tokenizer** (same algorithm; separate file/version) |
| Lexeme count | 69 | 80 |
| `vocab_size` | 200 | **211** |
| `input_token_limit` | 512 | **1664** |
| `max_seq_len` | 1024 | **2048** |
| `output_token_limit` | 384 | 384 (**unchanged**) |
| Output-schema lexical support | single-hop statuses only | + 4 BTRR statuses and JSON output scaffold (fields **unchanged**) |

The single-hop tokenizer `experiments/single_hop_typed_vs_prose/tokenizer.py` is **NOT modified**; it and
the typed-vs-prose experiment remain byte-stable. The BTRR tokenizer is a separate, independently frozen,
versioned artifact derived from the same deterministic longest-match algorithm.

## 4. Exact unchanged clauses
Scientific question (Q0/Q2a/Q2b); model depth (2 layers), `d_model` 64, 4 heads, `d_ff` 256, causal SDPA
attention; AdamW, lr 3e-4, batch 8, ≤2000 updates, dropout 0; output-only next-token CE loss; greedy
argmax decoding; P0 (B1–B7) definition; R1–R12 task semantics; entity density 6–12; event density
2–4/entity; PATH_GIVEN vs PATH_DISCOVERY; all metrics; all numeric gates; structure-blind/shortcut gates;
verdict precedence; final-seed requirement (≥4/5); reserved seeds; single-checkpoint paired-evidence
invariant; R10 authorized-absence non-claim; forbidden verdicts; bounded positive claim.

## 5. Rationale
The single-hop tokenizer and 512/1024 model were sized for atomic single-hop episodes. BTRR intrinsically
requires multi-record temporal + policy working sets and a richer output contract. The minimal fix is to
raise lexical and sequence capacity so the preregistered state can be *presented* without truncation,
while leaving the reasoning computation untouched.

## 6. BTRR tokenizer specification (frozen)
Algorithm: identical to the single-hop `LexicalTokenizer` — IDs 0–127 literal ASCII, 128 PAD, 129 BOS,
130 EOS, lexemes from 131, deterministic longest-match recognition, one-ASCII-character fallback, lossless
and reversible. IDs are assigned by list order (`131 + index`); encoding uses longest-match ordering.
`vocab_size = 211` (IDs 0–210).

Frozen lexeme inventory (ID → lexeme):

```
131 "\n<OUTPUT>\n"   132 "CTX "   133 "QRY "   134 "ENT "   135 "REL "   136 "EVT "   137 "POL "
138 "EVD "   139 " COND "   140 " OUT "
141 resolve_attribute  142 resolve_path_target  143 latest_event_value  144 path_then_latest
145 apply_policy   146 PATH_GIVEN   147 PATH_DISCOVERY   148 NOT_APPLICABLE
149 invoice  150 contract  151 vendor  152 employee  153 department
154 governed_by  155 approved_vendor  156 assigned_to  157 member_of  158 belongs_to_contract  159 supplies
160 risk  161 status  162 tier   163 amount  164 region  165 value
166 EQ  167 GT  168 GE  169 LT  170 LE  171 NE
172 LOW  173 MEDIUM  174 HIGH  175 CRITICAL  176 ACTIVE  177 EXPIRED  178 PENDING
179 supports  180 contradicts
181 approval_requirement  182 target_attribute  183 latest_state
184 vendor_risk  185 contract_state  186 assignment
187 VP_APPROVAL_REQUIRED  188 DIRECTOR_APPROVAL_REQUIRED  189 AUTO_APPROVED  190 MANUAL_REVIEW
191 REJECTED  192 ESCALATE_RISK  193 HOLD_PENDING_EVIDENCE  194 NO_ACTION
195 "Entity:"  196 "Event:"  197 "Policy:"  198 "Relation:"
199 {"answer":"    200 {"answer":null    201 ","reasoning_path":[    202 ],"evidence_ids":[
203 ],"status":"   204 "}   205 ","
206 "SUPPORTED"   207 "INSUFFICIENT_EVIDENCE"   208 "POLICY_NOT_APPLICABLE"   209 "INVALID_RELATION_PATH"
210 null
```

Label-leakage controls: opaque entity/event/evidence/tenant IDs remain ASCII char-level (mechanically
copyable, never lexemes, never answer-encoded); all 8 outcome tokens are symmetric lexemes so tokenization
privileges none; `requested_property` / `policy_scope` labels are uniform across outcomes.

### Frozen serialization format (model-visible; used for sizing)
Input, line-oriented, `\n`-separated:
```
CTX <tenant>
QRY <op> <path_mode> <root_id> <requested_property> <policy_scope?> <event_type?>   ; PATH_DISCOVERY: no relation_chain
ENT <entity_type> <entity_id> [<attr_key> <attr_val> ...]
REL <src_id> <relation_type> <tgt_id>
EVT <event_id> <entity_id> <event_type> <sequence> <value>
POL <policy_id> COND <field> <op> <literal> [COND ...] OUT <outcome>
EVD <evidence_ref> <stance> <supports_ref>
```
Output (fields identical to the frozen ReasoningOutput contract):
`{"answer":"<outcome>"|null,"reasoning_path":[<"Type:id">...],"evidence_ids":[<id>...],"status":"<STATUS>"}`.
ASCII fallback guarantees losslessness for any residual substring (e.g. the abstain scaffold), so
correctness never depends on lexeme coverage — only token efficiency does.

## 7. Context-size amendment (evidence-based; tokenizer-only measurements)
Handcrafted schema fixtures encoded with the BTRR tokenizer (no model, no training, no seeds):

| Fixture | Tokens |
|---|---|
| Minimum-size R9 (6 entities, path 2 hops, 2 events, 1 policy/2 conditions, 3 evidence) | 169 |
| **Maximum-size R9 / R12 (12 entities, 12 relations, 48 events, 2 policies × 3 conditions, 10 evidence)** | **1348** |
| Maximum ReasoningOutput (SUPPORTED, 5-node path, 8 evidence ids) | 62 |
| P0 maximum output (abstain) | 45 |
| Input + output worst case | 1410 |

The maximum fixture saturates the frozen density (entities = 12, events = 4/entity = 48), so it is the
worst preregistered instance. Chosen limits with a fixed 20% input margin rounded up to a multiple of 64:
- `input_token_limit = 1664` (margin **316 tokens ≈ 23%** over the measured 1348; absorbs ID/attribute
  length variance and R12 confusable-distractor worst case within the frozen density).
- `output_token_limit = 384` (**unchanged**; max measured output 62 ≪ 384).
- `max_seq_len = 2048` (≥ `input_token_limit + output_token_limit` = 2048). **No truncation is permitted.**

## 8. Parameter-count consequence (honest accounting)
`d_model = 64`; the output head is **weight-tied** to the token embedding, so vocabulary growth adds
parameters **once** (in the shared embedding), not twice.

| Model | vocab | max_seq | token emb | positional emb | reasoning blocks | total |
|---|---|---|---|---|---|---|
| Old (single-hop recipe) | 200 | 1024 | 12,800 | 65,536 | 131,392 | **209,728** |
| New (BTRR Amendment 001) | 211 | 2048 | 13,504 | 131,072 | 131,392 | **275,968** |

- Absolute delta: **+66,240**. Percentage delta: **+31.6%**.
- From vocabulary (weight-tied token embedding, counted once): **+704** (= (211−200) × 64).
- From context (positional embedding table): **+65,536** (= (2048−1024) × 64) — the dominant term.
- Reasoning-block parameters (attention + FFN, where relational/temporal/policy computation must occur):
  **131,392 → 131,392, delta 0**.

The model is **not** parameter-identical to the prior single-hop recipe. The amended claim is stated
exactly as: *Transformer reasoning depth/width/heads/FFN and training recipe are held fixed; only lexical
representation capacity and sequence capacity are increased to encode the preregistered BTRR state without
truncation.*

## 9. Causal-interpretation preservation
The amendment changes **representation capacity** (enough vocabulary and context to *present* the working
set) — it does not change **reasoning capability** (whether the model can *discover and execute*
relation/temporal/policy chains). The +31.6% is almost entirely a larger positional-embedding lookup
table (position → vector) plus 11 extra embedding rows — representational plumbing, not reasoning depth or
width. No structure-aware neural component, relational operator, pointer/copy head, retrieval layer,
constrained decoder, or external memory is introduced. The model still receives serialized tokens and must
learn the reasoning behavior itself. Therefore the amendment does not answer the scientific question by
construction: it lets the model *see* the state, not *reason* over it.

## 10. Gate re-check (every frozen gate classified)
| Gate class | Classification |
|---|---|
| All §8 numeric gates (answer/entity/path/latest-event/policy/evidence/abstention/hallucination/R4/R7/R9/R12) | **Unchanged and still valid** — derived from chance/competence/structure-blind baselines, which depend on entity/event/outcome counts (unchanged), not on vocab or context length |
| Structured-output-validity gate (≥0.98) | **Affected mechanically only** — same output contract, now with lexical support; threshold unchanged |
| Structure-blind / shortcut gates | **Unchanged** |
| Verdict precedence (0 PROTOCOL_VIOLATED → 1 base capability → …) | **Unchanged** |
| Final-seed requirement (≥4/5), reserved seeds, single-checkpoint invariant | **Unchanged** |
| **Invalidated gates** | **None** |

Because no scientific gate is invalidated, the outcome is
`BTRR_PROTOCOL_AMENDMENT_001_READY_FOR_OWNER_REVIEW` (not `BTRR_AMENDMENT_REQUIRES_SCIENTIFIC_REDESIGN`).

## 11. Amendment review matrix
| Original frozen requirement | Blocker | Amendment 001 | Scientific effect | Status |
|---|---|---|---|---|
| Reuse single-hop tokenizer (vocab 200, 69 slots) | No room for BTRR schema/output tokens | Separate BTRR tokenizer, 80 lexemes, vocab 211 (single-hop tokenizer untouched) | None (representation only) | Resolved |
| input 512 / ctx 1024, no capacity change | Max R9/R12 = 1348 tokens > 512 and > 1024 | input 1664 / ctx 2048 (measured + 20% margin) | None (no truncation; density unchanged) | Resolved |
| Reuse config STATUS_VALUES/OUTPUT_FIELDS | Lacks BTRR statuses + reasoning_path | BTRR output lexemes; contract fields unchanged | None (same fields/metric) | Resolved |
| Reasoning architecture (2×64, 4 heads, 256 FFN) | — | Unchanged | None | Preserved |
| P0 + R1–R12 semantics, densities, PATH distinction | — | Unchanged | None | Preserved |
| All numeric/shortcut gates, precedence, seeds | — | Unchanged | None | Preserved |

Proven: no old tokenizer modified; no reasoning architecture changed; no scientific task changed; no gate
changed; no reserved seed consumed; no experiment implementation added; execution remains fail-closed.

## 12. Authorization
`experiments/relational_reasoning_bounded_context/EXECUTION_AUTHORIZATION.md` remains **unsigned /
fail-closed**. Reserved seeds smoke `8100`, development `8101–8103`, final `81600–81604` are unchanged and
untouched; no new reserved seed was created. Only tokenizer/schema sizing on handcrafted strings was
performed.
