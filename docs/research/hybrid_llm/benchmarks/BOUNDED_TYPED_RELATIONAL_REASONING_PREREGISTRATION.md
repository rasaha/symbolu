# Bounded Typed Relational Reasoning (BTRR) — Preregistration

**Status: `BTRR_PREREGISTRATION_DRAFT` — awaiting owner review and protocol-lock freeze.**
No implementation code, no training run, and no reserved-seed execution is authorized by this
document. Reserved seeds remain fail-closed (see
`experiments/relational_reasoning_bounded_context/EXECUTION_AUTHORIZATION.md`).

Always preserved / co-emitted by any BTRR verdict:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL`,
`KDA_VALIDATION_BLOCKED`.

This preregistration operationalizes roadmap item #4 ("Structured relational benchmark") of
`HYBRID_LLM_ENTERPRISE_RELATIONAL_REASONING_V1_1.md`. It assumes the settled V1.1 architecture:
deterministic database retrieval + bounded typed working set is the operational foundation;
neural memory (BindingSlots / E1) is optional research and is **not** a prerequisite here.

---

## 1. Scientific question

**Primary (Q2).** Given a bounded, typed relational working set that a deterministic upstream layer
has already retrieved **correctly and completely**, can a plain non-memory transformer

- **Q2a — PATH EXECUTION:** execute a *supplied* relational / temporal / policy plan; and, more
  strongly,
- **Q2b — PATH DISCOVERY:** *discover* the relevant relational path, latest events, and applicable
  policy itself, then emit the grounded structured answer — abstaining when a required fact is absent?

**Prerequisite (Q0).** Does the frozen model possess the mechanical copy / select / emit capability the
benchmark presupposes (§ base-capability prerequisite)? A Q2 null is interpretable only if Q0 passes on
the same checkpoint.

**Explicitly NOT tested.** (a) Neural memory retrieval — Q1, "can memory retrieve the right fact" — is
made true by construction (all authorized facts are already present in the working set). (b) Database /
RLS / **tenant-authorization** correctness — that is the upstream deterministic layer, not the model
(see `..._R10_AUTHORIZED_ABSENCE_SCOPE.md`).

**Isolation guarantee.** The retrieval and authorization layers are realized by the deterministic
generator, which guarantees every fact required for the correct answer — and only tenant-authorized
facts — is already inside the context. Any model error is therefore attributable to reasoning (Q2), not
retrieval (Q1).

---

## 2. Architecture boundary (frozen)

```
authoritative relational DB
   ↓ deterministic authorization + tenant scoping   (generator, NOT model)
   ↓ deterministic retrieval                          (generator, NOT model)
bounded typed ReasoningContext   — all authorized facts present, complete, tenant-pure
   ↓
StructuredOutputModel  (plain SoftmaxTransformerLM; NO memory, NO retrieval, NO BindingSlots/E1)
   ↓
structured answer  { answer, reasoning_path[], evidence_ids[], status }
```

The model MUST NOT: query a database; discover which records to retrieve; use BindingSlots / E1 /
external neural memory / a retrieval table at inference; infer tenant scope; decide authorization;
receive hidden oracle labels; or access evaluator metadata. Enforced by
`FORBIDDEN_MODEL_VISIBLE_KEYS`, tenant-purity-by-construction, and the fact-hash equivalence check.

---

## 3. Split taxonomy

**P0 — Base-capability prerequisite** (non-relational; gates all interpretation; see
`..._BASE_CAPABILITY_PREREQUISITE.md`).

| Split | Capability isolated | Path mode | Gold reasoning |
|---|---|---|---|
| R1 | Direct entity fact | n/a | entity → attribute |
| R2 | Single relation hop | PATH_GIVEN | A→B→attr (plan supplied) |
| R3 | Multi-hop relation | PATH_GIVEN | A→B→C→attr (plan supplied) |
| R4 | Multi-hop relation | **PATH_DISCOVERY** | root+property → *model infers* A→B→C→attr |
| R5 | Temporal latest-state | n/a | events → argmax(sequence) |
| R6 | Relation + temporal | PATH_GIVEN | supplied path → latest event of endpoint |
| R7 | Relation + temporal | **PATH_DISCOVERY** | root+property → *infer path* → latest event |
| R8 | Policy application | facts pre-resolved | resolved facts ⊨ policy → outcome |
| R9 | **Full composite** | **PATH_DISCOVERY** | infer path → latest → policy → outcome |
| R10 | **AUTHORIZED_ABSENCE / CROSS_TENANT_NON_FABRICATION** | discovery | required fact absent → abstain, do not fabricate |
| R11 | Insufficient evidence | discovery | required relation/event/policy removed → abstain w/ structured reason |
| R12 | Confusable records | discovery (composite) | near-duplicate distractors; exactly one correct path |

**Matched execution↔discovery pairs (core non-substitution axis):** R3↔R4, R6↔R7. PATH_GIVEN
(R2/R3/R6/R8) can **never** substitute for PATH_DISCOVERY (R4/R7/R9): discovery splits carry their own
gates and their own precedence branch. **R10** tests only authorized-absence non-fabrication and does
**not** validate database / RLS / tenant authorization.

---

## 4. ReasoningContext / ReasoningQuery schema (frozen contract)

Additive extension of `experiments/single_hop_typed_vs_prose/schema.py`. All records ASCII, frozen,
deterministic; `fact_hash()` = sha256 over `visible_canonical()` (now including events + policies).

```python
ReasoningQuery:
    operation      # {resolve_attribute, resolve_path_target, latest_event_value,
                   #  path_then_latest, apply_policy}
    path_mode      # {PATH_GIVEN, PATH_DISCOVERY, NOT_APPLICABLE}
    root_entity_id
    relation_chain # NON-EMPTY iff PATH_GIVEN;  MUST be () iff PATH_DISCOVERY
    requested_property   # answer-INDEPENDENT label, e.g. "approval_requirement"
    event_type           # field name only, never a value
    policy_scope         # policy FAMILY label, never the policy_id / outcome
  validator (frozen):
    PATH_DISCOVERY -> relation_chain == () AND query names no intermediate entity_id,
                      no target policy_id, and no outcome token anywhere
    PATH_GIVEN     -> relation_chain != ()   (supplies the plan, not the answer)
    requested_property / policy_scope / event_type are drawn from a fixed vocabulary that is
      uniform across outcomes (mutual information with the answer ≈ 0)

Event:       event_id, entity_id, event_type, sequence:int (logical time; NO wall-clock),
             attributes, evidence_ref?, tenant_id
Condition:   (subject_ref, field_or_event_type, operator ∈ {EQ,GT,GE,LT,LE,NE}, literal);
             latest-event semantics for event fields
Policy:      policy_id, conditions:tuple[Condition,...], outcome, tenant_id
Constraints: max_hops:int, temporal:bool, policy:bool   (NEVER answer-revealing; no expect_status)

ReasoningContext:
    context_id, tenant_id, query, entities[], relations[], events[], policies[], evidence[],
    constraints, authoritative_output   # gold; NOT serialized to the model
  visible_canonical(): excludes authoritative_output; for PATH_DISCOVERY excludes relation_chain
  validate(): all FKs resolve; all VISIBLE records share tenant_id (purity by construction);
    unique (entity_id,event_type,sequence);
    COMPLETENESS — answerable episodes' gold answer derivable from visible facts alone;
    R10/R11 — a required fact is provably absent and gold = abstain.

ReasoningOutput: { answer, reasoning_path[], evidence_ids[], status }
    status ∈ {SUPPORTED, INSUFFICIENT_EVIDENCE, POLICY_NOT_APPLICABLE, INVALID_RELATION_PATH}
    reasoning_path scored as EXACT ORDERED match; a correct answer with a wrong path fails the path gate.
```

---

## 5. Model recipe (reuse; no new capability)

- **Model:** `experiments/single_hop_typed_vs_prose/model.py::StructuredOutputModel(FROZEN_MODEL_RECIPE)`
  wrapping `symbolu_neural/clean_softmax/backbone.py::SoftmaxTransformerLM`
  (64 d_model, 2 layers, 4 heads, 256 SwiGLU, ≤1024 ctx, dropout 0, weight-tied head). Plain, non-memory.
- **Objective:** output-only next-token cross-entropy (`ignore_index=-100` over the prompt); input marker
  `\n<OUTPUT>\n`.
- **Train recipe:** `FROZEN_TRAIN_RECIPE` — batch 8, ≤2000 updates, lr 3e-4, AdamW β 0.9/0.95, wd 0.01,
  grad-clip 1.0. Deterministic (CPU fp32, fixed seeds).
- **Inference:** `greedy_generate` (argmax, EOS-terminated), strict structured-output parser.
- **Representation:** single arm, canonical typed serialization (`serialize_b1`-style). No prose-vs-typed
  factorial (owned by `single_hop_typed_vs_prose`, roadmap #11.A). Justification in the gate-rationale doc.
- **Not introduced:** BindingSlots, E1, Phase, KDA, JEPA, GNN, pointer/copy heads, constrained decoder,
  larger capacity, external retrieval. If a split is unlearnable at this recipe, that is a **reported
  negative**, not a license to enlarge; capacity change would be a separate preregistered blocker.

---

## 6. Single-checkpoint paired-evidence invariant (NON-NEGOTIABLE)

**For each experiment seed there is exactly ONE trained BTRR checkpoint. That byte-identical frozen
checkpoint is evaluated on both the P0 base-capability suite and the R1–R12 reasoning suites.**

Required flow, per seed:

```
TRAIN(seed)
  → freeze checkpoint + record parameter_digest (sha256 of state_dict)
  → evaluate P0        on the frozen checkpoint
  → evaluate R1–R12    on the BYTE-IDENTICAL frozen checkpoint (same parameter_digest)
```

Forbidden: a separate P0-trained model; any P0-specific fine-tuning; any optimizer step between P0 and
R1–R12; any checkpoint selection based on P0; any model modification after P0; any separate architecture
or tokenizer for P0. The evaluator MUST assert the `parameter_digest` is identical for the P0 and R1–R12
evaluations of a seed, and MUST assert the model is in `eval()` / `no_grad` for both.

**Each final seed is one paired evidence unit: `checkpoint + P0 + R1–R12`.** P0 does **not** consume a
separate final cohort. If P0 fails on a seed's checkpoint, that seed's R1–R12 outputs may still be
generated for artifact completeness but MUST be mechanically stamped
`NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION` and MUST NOT contribute to
`RELATIONAL_REASONING_NOT_FOUND`, `TEMPORAL_REASONING_FAILED`, `POLICY_REASONING_FAILED`, or any other
reasoning verdict.

---

## 7. Metrics (each reported independently; no blended score)

final-answer accuracy · relation-path accuracy (exact ordered) · entity-selection accuracy ·
latest-event-selection accuracy · policy-condition accuracy · evidence-citation precision / recall ·
abstention accuracy (R10 + R11) · hallucinated-entity rate · hallucinated-relation rate ·
hallucinated-evidence rate · exact structured-output validity · deterministic-replay identity
(`parameter_digest` + output byte-hash stable across two runs).

**R9 composite failure decomposition** (mutually exclusive): wrong entity · wrong relation ·
wrong temporal choice · wrong policy evaluation · wrong final outcome · fabricated fact · invalid output ·
incorrect abstention. Reported as a distribution over failing R9 items, plus separately for R4/R7
discovery failures.

---

## 8. Critical numeric gates (frozen a priori; see `..._GATE_RATIONALE.md`)

Derived from chance level, structure-blind baselines, and minimum competence — **never** from observed
reserved results. Per final seed; overall pass requires ≥ 4 of 5 final seeds.

| Metric | Gate |
|---|---|
| Exact structured-output validity | ≥ 0.98 |
| R1 direct attribute | ≥ 0.95 |
| R2 PATH_GIVEN 1-hop | ≥ 0.90 |
| R3 PATH_GIVEN multi-hop | ≥ 0.85 |
| **R4 PATH_DISCOVERY multi-hop** (non-substitutable) | **≥ 0.75** |
| Entity-selection accuracy | ≥ 0.90 |
| Relation-path accuracy (exact ordered) | ≥ 0.80 |
| Latest-event accuracy (R5/R6/R7) | ≥ 0.85 AND ≥ global-most-recent baseline + 0.20 |
| Policy-condition accuracy (R8/R9) | ≥ 0.85 |
| Evidence precision | ≥ 0.90 |
| Evidence recall | ≥ 0.85 |
| Abstention accuracy (R10 + R11) | ≥ 0.85 AND false-abstention on answerable ≤ 0.10 |
| Hallucinated-entity rate | ≤ 0.02 |
| Hallucinated-relation rate | ≤ 0.02 |
| Hallucinated-evidence rate | ≤ 0.02 |
| **R7 PATH_DISCOVERY + temporal** | **≥ 0.72** |
| **R9 composite final-answer** | **≥ 0.70** |
| **R9 full-chain-correct** (answer ∧ path ∧ temporal ∧ policy) | **≥ 0.60** |
| R12 confusable | ≥ R9 − 0.10 |
| Final seeds required to pass | **≥ 4 of 5** |

**Structure-blind baselines** (computed, not learned): shuffled-context, query-only, majority-class,
most-recent-token, global-most-recent, policy-id→outcome. Every model gate must clear its relevant blind
baseline by ≥ 0.10; any blind baseline within 0.10 of the model → `SHORTCUT_OR_LEAKAGE_DETECTED`.

**Non-compensation (frozen).** `RELATIONAL_REASONING_VALIDATED` requires **every** critical gate —
entity, exact path, R4 and R7 discovery, latest-event, policy, evidence P/R, all three hallucination
caps, abstention, and R9 composite + full-chain — to pass on ≥ 4/5 final seeds. Strong R1/R2/R3
(PATH_GIVEN) cannot offset any temporal, discovery, policy, evidence, or abstention failure.

---

## 9. Shortcut & leakage tests (mechanical, pre-execution; fail-closed)

Enumerated in `..._GATE_RATIONALE.md`. At minimum: policy-outcome lexical leakage; answer in entity IDs;
latest-event-always-serialized-last (randomize event order; latest by `sequence` only); fixed relation
ordering; amount-threshold↔label correlation; entity-type-alone; policy-id→outcome (rotate assignment);
answer copied from a privileged field; train/eval identity overlap (disjoint id pools); evaluator-metadata
exposure; tenant-identifier leakage; global-most-recent; positional; fixed policy-template;
PATH_DISCOVERY path-hint leakage in the query. Structure-blind baselines (shuffled-context, query-only)
must collapse to chance. Any above-band baseline → fail-closed.

---

## 10. Verdict precedence (first match wins) — protocol before base capability

Allowed primaries: `RELATIONAL_REASONING_VALIDATED`, `RELATIONAL_REASONING_PARTIAL`,
`RELATIONAL_REASONING_NOT_FOUND`, `TEMPORAL_REASONING_FAILED`, `POLICY_REASONING_FAILED`,
`EVIDENCE_GROUNDING_FAILED`, `ABSTENTION_FAILED`, `RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY`,
`SHORTCUT_OR_LEAKAGE_DETECTED`, `PROTOCOL_VIOLATED`, `RESOURCE_BLOCKED`.

```
0. protocol-lock / seed-role / schema-integrity / deterministic-replay / provenance failure
      → PROTOCOL_VIOLATED
      (a result obtained under a violated protocol is NEVER a scientific P0 success or failure)
1. P0 base capability not established (on the seed's own frozen checkpoint)
      → RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY
        · co-emit BASE_COPY_SELECTION_CAPABILITY_NOT_ESTABLISHED
        · that seed's R1–R12 stamped NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION
2. shortcut or structure-blind baseline within band → SHORTCUT_OR_LEAKAGE_DETECTED
3. incomplete run / OOM / context-overflow → RESOURCE_BLOCKED
4. abstention gate (R10 + R11) fail → ABSTENTION_FAILED
5. evidence P/R gate fail → EVIDENCE_GROUNDING_FAILED
6. latest-event gate (R5/R6/R7) fail → TEMPORAL_REASONING_FAILED
7. policy gate (R8/R9) fail → POLICY_REASONING_FAILED
8. all critical gates incl. R4/R7 discovery + R9 composite/full-chain pass on ≥4/5
      → RELATIONAL_REASONING_VALIDATED
9. PATH_GIVEN + non-discovery gates pass but any discovery gate (R4/R7/R9) fails
      → RELATIONAL_REASONING_PARTIAL   ("path-execution only; discovery not established")
10. else → RELATIONAL_REASONING_NOT_FOUND
```

Steps 2–10 are reached only for seeds whose checkpoint passed step 0 (protocol valid) and step 1 (P0
established); non-admissible seeds never contribute to any reasoning verdict.

**Forbidden verdicts (never emitted):** `ENTERPRISE_READY`, `PRODUCTION_READY`,
`DATABASE_REPLACEMENT_VALIDATED`, `BINDINGSLOTS_RESOLVED`, `KDA_VALIDATION_ELIGIBLE`, `AGI_VALIDATED`.

**Bounded positive claim (the only one a pass supports):** *A non-memory neural model can, under the
tested synthetic conditions, both execute and discover relational / temporal / policy reasoning over a
correctly retrieved bounded typed working set.*

---

## 11. Seeds (reserved; fail-closed; UNCONSUMED)

- smoke: `8100`
- development: `8101, 8102, 8103`
- final (paired evidence units): `81600, 81601, 81602, 81603, 81604`
- unit-test fixtures (inadmissible as evidence): `883000–883004`

These are disjoint from all prior reserved bands (typed-vs-prose 76/760–762/7160–7164/99001;
unseen-identifier 9070/9071–9073/90760–90764/993000–993004; E1 lineage 23–32/500–502/3140–3144/7140/7150).
Reserved seeds stay fail-closed via `guard_seed` until the owner signs
`experiments/relational_reasoning_bounded_context/EXECUTION_AUTHORIZATION.md`. Development fixtures and
calibration use only smoke/dev seeds; final seeds run once, post-lock.

---

## 12. Interpretation boundaries

A positive BTRR result does not resolve BindingSlots neural routing, does not unblock KDA, does not
establish enterprise or natural-language transfer, does not replace the database, and makes no
production-readiness claim. `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`E1_TEMPORAL_TRANSFER_PARTIAL`, and `KDA_VALIDATION_BLOCKED` are preserved regardless of outcome.
