# E1 frozen-representation readout diagnostic — preregistration (DRAFT)

**DRAFT — documentation only. Nothing here is implemented, trained, or executed. No models, no readout
training, no seed allocation or reserved runs.** This is a **diagnostic**, not a successor architecture and
not a C1 variant. Always preserves, in any later work:
`E1_TEMPORAL_TRANSFER_PARTIAL` · `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.
**T5 predecessor/successor stays outside every gate, selection, and conclusion.**

## 0. Grounding
The frozen C1 temporal-patching track is closed (`C1_TEMPORAL_PATCHING_TRACK_CLOSURE.md`): minimal,
capacity-fixed interventions did not clear the latest-state (T4) gate. The factorial (#1358) localized the
wall to the **pooled read** — even null-excluded, the mean-pooled dual encoder addresses the correct latest
record only ~0.80 of the time. Before spending architecture budget on a successor, this diagnostic asks the
cheapest sufficient question: **is the information already present in the frozen token representations but
lost/blended by mean pooling?**

## 1. Scientific question (answer only this)
> Does the frozen temporal E1 encoder already contain enough **token-level** information for latest-state
> retrieval, with that information being **lost or blended by mean pooling**?

The diagnostic must distinguish three outcomes:
- **information present but pooling inadequate** — a learned readout over the *same frozen* token
  embeddings recovers T4 substantially;
- **information absent or insufficient** — no tested frozen readout recovers T4 (a larger or newly trained
  encoder would be required — out of scope here);
- **improvement dependent on structural token-role priors** — only the arm that is handed fixed
  schema-level token roles improves, so the gain reflects a structural prior, not learned separation.

## 2. Frozen components (hard requirement)
The future diagnostic **freezes** and never applies a base optimizer step to:
- the token **embeddings**;
- the **semantic-key encoder** (`key_head`);
- the **query encoder** (`query_head`);
- the **value encoder** / read path;
- **all validated C1 base weights** (the learned null key included);
- the **episode generator** and the temporal task family (same vocabulary/generator semantics, ~32
  keys/episode, splits T1–T9);
- the **existing training checkpoints** (the frozen temporal E1 from PR #1354/#1358; reuse the exact
  trained weights so this is a true *same-encoder, different-read* comparison).

**Only the new readout parameters may be trained.** This adds readout capacity and is therefore
**diagnostic-only** — the exact status of the PR #1356 oracle counterfactual arms (informative for
attribution, never deployable). It is not a C1 variant and must never be reported as one.

## 3. Proposed arms
All arms consume the **same frozen token embeddings** of the same episodes; they differ only in how those
token vectors are reduced into a per-candidate score. Every arm reports its added parameter count and
trains only its own readout parameters (frozen base param hashes recorded and verified unchanged).

### R0 — Frozen mean pooling (reference)
The existing frozen C1 read (masked-mean → head → cosine/τ, learned null). **No new parameters.** This is
the baseline every other arm is measured against.

### R1 — Learned token-attention readout (primary arm)
A small learned attention readout over the frozen **query** and **key** token embeddings: query-derived
attention weights select/reweight key tokens before scoring, so entity and predicate information can be
read without being averaged together. Requirements:
- **no** ground-truth entity; **no** correct event position; **no** answer value; **no** evaluator slot;
- **no** hard-coded maximum-position rule;
- added parameter count **reported**; base encoder **completely frozen**;
- attention weights are a learned function of the (frozen) token vectors only.
This is the **primary diagnostic arm**: a substantial R1 gain over R0 is the signal that the information is
present but pooling destroys it.

### R2 — Learned dual-head readout
Two learned heads over the **same** frozen token representations: one intended to capture **entity
relevance**, one intended to capture **temporal-predicate / order relevance**; their outputs combine into
the per-candidate score. The heads must **discover** any useful separation through training —
**no per-example oracle token roles are provided.** If fixed token-layout information is used at all, it
must be declared explicitly as a **structural prior** (see R3) and that arm re-labelled accordingly.

### R3 — Structural token-role readout (optional, upper-bound only)
Included only as a **diagnostic upper bound**. It may use **fixed schema-level** token-role positions
(e.g., "key slot 3 is the position token") but **no episode-specific oracle** (never the correct entity,
correct latest index, or answer). It is **weaker evidence** because it relies on a structural prior.
**R3 alone must not justify a successor architecture** — only R1/R2 (learned separation) can.

## 4. Capacity and interpretation (per arm, preregistered)
For **every** arm, preregister and later report:
- **added parameter count** (readout only);
- **training budget** (readout steps/optimizer/lr — the base is frozen);
- **frozen base parameter hashes** (recorded before and verified unchanged after);
- **whether structural token-role information is used** (R0/R1/R2: no; R3: yes, schema-level only);
- **why the arm is diagnostic** rather than a deployable C1 variant (it adds readout capacity over a frozen
  encoder; its purpose is attribution, not deployment).

**Interpretation bounds:**
- A **positive** result supports only: *"Frozen token-level representations contain useful latest-state
  information that the original mean-pooled read does not exploit."*
- A **negative** result supports only: *"The tested frozen readouts did not recover sufficient latest-state
  information from the frozen representations."*
- **Neither** result validates temporal transfer, establishes capacity independence, or unblocks KDA. A
  positive result **motivates** (does not justify or authorize) a successor; a successor remains a separate,
  explicitly-authorized, capacity-scoped preregistration.

## 5. Shortcut / oracle-hardcoding protections (prohibited)
The preregistration prohibits, and the future run must mechanically check against:
- ground-truth **entity filtering**; correct **latest-position** input; **answer values inside keys**;
  evaluator-provided **memory positions**; **external-table** lookup;
- **hard-coded global-latest** selection (pick the max-step record);
- **train/final identity overlap**;
- **post-hoc threshold tuning**; **use of reserved outcomes to redesign the readout**.

Retain and require **near chance** for both the **global-latest heuristic baseline** and the **lexical
overlap baseline** (inherited temporal leakage suite). If an attention arm "works," these guards prove it is
not a recency or surface-overlap shortcut. The no-oracle proof (AST + signature, as in the factorial) must
extend to every readout's forward: it may read only the frozen token embeddings and the query, never
ground-truth/evaluator/metadata.

## 6. Proposed measurements (per arm, per seed, per split — later reporting)
- **null-inclusive T4 accuracy** (primary) and **null-excluded T4 addressing**;
- **correct-entity rate**, **correct-latest-record rate**, **null-selection rate**, **wrong-entity rate**,
  **right-entity/wrong-older rate**;
- inherited **T1, T2, T3, T6, T7, T9** regression (null-excluded addressing);
- **no-match false accepts and false rejects**;
- **added parameter count**; **deterministic replay** (byte-identical readout hash); **leakage + shortcut**
  results.
- **T5** reported for completeness only, **outside** the verdict.

## 7. Proposed go/no-go logic (numbers frozen on dev fixtures BEFORE execution)
Propose, and freeze on non-reserved dev fixtures before any reserved seed:
- a **minimum absolute improvement over R0** on null-inclusive T4 — `APPROVAL_REQUIRED_BEFORE_EXECUTION`;
- a **minimum absolute T4 floor** — `APPROVAL_REQUIRED_BEFORE_EXECUTION`;
- **no material regression** on inherited semantic-retrieval splits (T1/T2/T3, and T6/T7/T9) — tolerance
  `APPROVAL_REQUIRED_BEFORE_EXECUTION`;
- **no-match limits** (false-accept ≤, false-reject ≤) — inherited ceilings, confirmed before execution;
- **≥ 4 of 5 fresh seeds** passing; **determinism** and **leakage** gates required.

Numeric thresholds are **not** finalized from reserved evidence and are marked
`APPROVAL_REQUIRED_BEFORE_EXECUTION`. R3 (structural-prior arm) is reported but **cannot alone** trigger a
"signal present" conclusion.

## 8. Proposed conclusions (diagnostic only)
Exactly one of:
`FROZEN_REPRESENTATION_READOUT_SIGNAL_PRESENT` · `FROZEN_REPRESENTATION_READOUT_SIGNAL_PARTIAL` ·
`FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND` · `FROZEN_REPRESENTATION_READOUT_PROTOCOL_VIOLATED` ·
`FROZEN_REPRESENTATION_READOUT_RESOURCE_BLOCKED`.
Always co-emit `E1_TEMPORAL_TRANSFER_PARTIAL`, `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`KDA_VALIDATION_BLOCKED`. **Never** emit `E1_TEMPORAL_TRANSFER_VALIDATED`, `E1_STRUCTURAL_TRANSFER_CONFIRMED`,
or `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`. `SIGNAL_PRESENT` supports only §4's positive statement; it does not
authorize a successor.

## 9. Proposed seeds and compute budget (proposal; approval required)
- **Fresh seeds** disjoint from every prior program seed (verified: 7/28–32/71/73/74/500–502/700–702/
  720–722/740–742/2028–2032/3140–3144/5140–5144/6140–6144/7140–7144). Proposed:
  **train-readout seed 75; dev 750–752; final 7150–7154** (mechanically confirmed disjoint).
- **Budget:** readout-only training on the frozen encoder (no base steps); bounded — ~3–4 arms × 5 final
  seeds × the frozen C1 train/eval density; CPU fp32, `threads=4`; determinism prerequisite (byte-identical
  readout replay) before any reserved seed; protocol lock committed before the first reserved seed. Exact
  step/optimizer budget `APPROVAL_REQUIRED_BEFORE_EXECUTION`.

## 10. Capacity and parameter-accounting plan (summary)
| arm | readout | frozen base | added params | structural prior | status |
|---|---|---|---|---|---|
| R0 | frozen mean-pool | all C1 weights | 0 | no | reference |
| R1 | learned token attention | all C1 weights | report | no | primary |
| R2 | learned dual-head | all C1 weights | report | no (declare if any) | learned-separation |
| R3 | structural token-role | all C1 weights | report | **yes (schema-level)** | upper-bound, weaker |

Base parameter hashes recorded and verified unchanged for every arm; only readout params train; exact
counts `APPROVAL_REQUIRED_BEFORE_EXECUTION` (set when the readout forms are finalized).

## 11. Shortcut / oracle-hardcoding analysis (summary)
The risk is that a readout learns a **recency shortcut** (attend to max-step token) or a **surface-overlap
shortcut**, or that R2/R3 quietly consume oracle token roles. Mitigations: global-latest and lexical
baselines required near chance; AST + signature no-oracle proof over every readout forward; R3's structural
prior is schema-level only (never episode-specific) and cannot alone conclude `SIGNAL_PRESENT`; no reserved
outcome may feed back into readout design.

## 12. Unresolved decisions requiring approval before execution
1. **Exact readout forms** for R1 (attention parameterization) and R2 (dual-head parameterization), each
   confirmed learned + non-oracle — `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
2. **Whether to include R3** (structural upper bound) in the first pass — `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
3. **All numeric go/no-go thresholds** (min improvement over R0, T4 floor, regression tolerances, no-match
   limits, seed proportion), frozen on dev fixtures — `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
4. **Final seed set and readout compute budget** (proposed in §9) — `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
5. **Added parameter counts per arm** once the readout forms are fixed — `APPROVAL_REQUIRED_BEFORE_EXECUTION`.

Until these are approved and frozen on non-reserved fixtures, **no implementation and no execution begin.**
This draft proposes the question, frozen-component contract, arms, capacity/parameter-accounting plan,
shortcut/oracle analysis, measurements, go/no-go scaffold, conclusion vocabulary, seeds, and open decisions
only. **No successor architecture is begun.**
