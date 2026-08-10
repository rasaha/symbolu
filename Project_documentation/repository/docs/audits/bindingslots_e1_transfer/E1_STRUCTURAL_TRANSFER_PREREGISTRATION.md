# E1 structural-transfer preregistration (Temporal Event Memory)

**DRAFT PREREGISTRATION — for approval. Nothing here is executed.** No implementation code, no training,
no evaluation, no seed allocation, no ablations, no capacity scaling, no versioning, no Phase/MLA/KDA.
Always preserves, in any later experiment: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`KDA_VALIDATION_BLOCKED`. A pass would at most emit `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`; it would **not**
unblock KDA.

## 1. Scientific question (answer only this)
> Does the **exact frozen E1 C1 mechanism** transfer to a **structurally different but comparable-scale**
> memory task **without retuning**?

This first transfer test must **isolate mechanism transfer from model-capacity limitations**. It does
**not** use realistic unrestricted natural language, and a failure here would **not** show that a larger
E1 could not work on real NL — only that the frozen recipe did or did not transfer under a controlled
structural change.

## 2. Frozen recipe (exact; no change permitted)
Reuse the validated C1 recipe verbatim: `steps=1200`, `temperature=0.07`, `train_no_match_frac=0.30`,
learned null key, contrastive episode-local matching, **separate semantic key and value
representations**, hard top-1 value retrieval, ~32 candidate memories/episode. **No** architecture,
dimension (`D=64`), loss (InfoNCE / cosine), optimizer (Adam, `lr=1e-3`, `batch=48`), or capacity change.
The frozen `models.E1` / `models.B0` and the 17 frozen PR #1351 gates are reused; only the **task
family, evaluator, and seeds** are new (same discipline as the merged confirmation PR #1352).

## 3. New task family — **Temporal Event Memory** (structurally different)
Each episode holds ≈**32 event records** (the memories/keys). A record describes an entity, an event
type, an **ordered position/timestamp**, and a resulting status; relationships (predecessor/successor,
current-vs-earlier state) arise from the *ordering across records*, not from new linguistic complexity.

- **Record (key) example:** `Orion Systems | event=status_change | step=8 | -> suspended`
  (rendered as bounded surface tokens; the **value** is the resulting status, stored separately and
  never inside the key surface).
- **Query examples (each a distinct temporal/relational predicate):**
  - latest-state: "current status of Orion Systems"
  - temporal-order: "was Lumen restricted before or after the audit event"
  - predecessor/successor: "which project became active after Nova was closed"
  - immediately-before: "status immediately before suspension"

The task differs from the original compositional-lookup family through **temporal ordering, updates, and
relational event structure** — not merely new vocabulary or paraphrases. Proposed encoding (a genuinely
open design point, see §11): position/step is a **small bounded integer token** carried in each record;
"latest"/"current"/"before"/"after" are learned query predicates; the dual encoder must combine
entity-match with a learned position/relation preference to rank the correct record top-1. Whether a
mean-pooled cosine matcher can do this is exactly what the transfer tests.

## 4. Why C1 capacity is adequate (so a failure is not mere under-capacity)
- **Density unchanged:** ≈32 memories/episode (validated regime).
- **Dimensions unchanged:** `D=64`, same model; embedding/sequence dims within the validated range.
- **Bounded key/query lengths:** records and queries render to a small, bounded number of tokens
  (comparable to the original KLEN≈4 / QLEN≈9); positions are bounded integer tokens, not free text.
- **No larger tokenizer or language model:** a small synthetic vocabulary only; no pretrained embeddings.
- **Structural, not linguistic, variation:** difficulty comes from *ordering/relations among records*,
  which the model must learn to use — not from longer inputs, larger vocab, or open-ended NL.
This keeps input scale within C1's demonstrated capacity, so a failed transfer cannot be dismissed as
"the model was simply too small for the domain."

## 5. Proposed transfer splits (each a separate gate; no averaging)
- **T1 — unseen entities** (entities absent from training)
- **T2 — unseen event combinations** (novel entity×event-type×status)
- **T3 — temporal-order queries** (before/after relations)
- **T4 — latest-state queries** (must select the highest-position record for the entity)
- **T5 — predecessor/successor queries** (relational across two events)
- **T6 — paraphrased queries** (same predicate, different wording)
- **T7 — confusable entities and event types** (similar names / similar event types)
- **T8 — no-match queries** (queried entity/event/predicate has no matching record) — **independent
  hard gate**
- **T9 — stable direct retrieval** (single unambiguous record; the easy case)

## 6. Comparison (execution phase only; not now)
- **B0** — frozen anonymous BindingSlots baseline.
- **E1** — exact frozen C1 recipe.
Identical episodes for B0 and E1. **No** C1 retuning. **No** capacity-increased E1 arm (that belongs to a
separate, later capacity track, out of scope here).

## 7. Leakage and shortcut protections (must all hold; mechanically checked before the cohort)
Prohibited: answer values inside semantic keys; exact opaque identifiers shared verbatim between query
and key; evaluator-provided memory positions/indices; **timestamp/position tokens that directly reveal
the answer** (position must help *rank* records, never encode the status itself); future-query-aware
event construction; external-table lookup during E1 inference; train/evaluation identity overlap; fixed
event templates that make the answer location trivial. **Include a lexical / heuristic baseline** (e.g.
token-overlap or most-recent-record heuristic) that is expected to remain **near chance / clearly below
E1** on the relational and no-match splits — proving the task is not solvable by a surface shortcut.

## 8. Gates (reuse the confirmed E1 gate structure where applicable; frozen before execution)
The later execution must require, **without weakening after seeing results**:
- E1 **materially outperforms B0** (min improvement over B0 ≥ the frozen PR #1351 margin, 0.50, on the
  primary retrieval split);
- **≥ 4 of 5 fresh seeds** pass all primary gates; worst-seed floor on the primary split;
- **strong unseen-entity** performance (T1/T2 addressing above the frozen generalization bar);
- **strong temporal and relational retrieval** (T3/T4/T5 above frozen bars) — these are the transfer's
  crux and are gated explicitly;
- **stable direct-case** performance (T9, no regression);
- **no-match** false-accept and false-reject within the frozen limits (T8, independent hard gate);
- **deterministic reproduction** (byte-identical replay on a non-reserved fixture);
- **no leakage or shortcut violation** (§7).
Per-split scores are always reported separately; a strong retrieval number may never mask weak no-match
or weak relational behavior. Exact per-split numeric bars are frozen on **non-reserved development
fixtures** before the final cohort (some are `APPROVAL_REQUIRED_BEFORE_EXECUTION`, §11), following the
PR #1351 gate-rationale method (absolute competence bars vs. the B0 baseline + minimum effect size, not
thresholds set at observed dev performance).

## 9. Proposed seeds & compute (frozen before execution)
- **Fresh seeds only**, disjoint from every prior seed in the program (V100 28–32; E1 dev 500–502;
  burned 2028–2032; E1 final 3140–3144; confirmation train 71 / dev 700–702 / final 5140–5144). Proposed
  final set (subject to approval): `[6140, 6141, 6142, 6143, 6144]`; dev `[720, 721, 722]`; train-episode
  seed `73`. Disjointness asserted mechanically before lock.
- **Bounded compute:** ≈1500 train episodes, `STEPS=1200` per seed, 5 final seeds, CPU fp32,
  `threads=4`; mechanical futility (stop when max possible remaining passes < required); no selective
  seed restarts; no post-evaluation tuning.
- **Determinism prerequisite + protocol lock** before any reserved run, exactly as in PR #1351/#1352.

## 10. Interpretation boundaries
A **pass** supports **only**: "the frozen E1 recipe transferred from the original compositional task
family to the preregistered Temporal Event Memory task at comparable scale." A **failure** means: "the
frozen E1 recipe did not transfer under the tested structural change." Neither outcome determines
whether a **larger** E1 architecture could work on realistic natural language (that is a separate,
later, capacity track). Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`KDA_VALIDATION_BLOCKED`. A pass emits at most `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`; KDA stays blocked.

## 11. Unresolved decisions requiring approval before execution
1. **Position/temporal encoding** — the exact scheme (bounded integer step tokens vs. relative-order
   tokens) and how "current/latest/before/after" query predicates are rendered so they *rank* records
   without leaking the answer. `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
2. **Relational (T5 predecessor/successor) formulation & scoring** — whether a single-key retrieval
   model can express "the record whose entity became active *after* another entity's event," and how the
   correct target key is defined. This is the **highest-risk split**; if it proves ill-posed for a
   single-top-1 matcher, whether to keep it as a hard gate or record it as a diagnostic must be decided
   **before** execution. `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
3. **Exact per-split numeric gates** — frozen on dev fixtures with the B0/effect-size rationale; values
   `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
4. **Final seed set & compute budget** — the proposed seeds/budget in §9 pending approval.
5. **Which split is the "primary" retrieval split** for the improvement-over-B0 and worst-seed gates
   (proposed: latest-state T4 or unseen-entity T1). `APPROVAL_REQUIRED_BEFORE_EXECUTION`.

Until these are approved and frozen on non-reserved fixtures, **no execution begins**. This draft
proposes the task family, capacity justification, splits, gate structure, leakage protections, and open
decisions only.
