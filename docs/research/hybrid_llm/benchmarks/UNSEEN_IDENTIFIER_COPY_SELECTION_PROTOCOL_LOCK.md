# Unseen-identifier copy & selection diagnostic — protocol lock (documentation-only)

**Documentation-only. Nothing here is implemented, generated, trained, executed, or seeded.**
Protocol completion is **not** implementation or execution authorization.

Always preserved, and untouched by this lock or any future outcome:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

## Protocol-lock status
States: `DRAFT_PREREGISTRATION` → `PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED` →
`IMPLEMENTATION_AUTHORIZED` → `EXECUTION_AUTHORIZED`. **Maximum permitted state for this PR:
`PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED`.** `IMPLEMENTATION_AUTHORIZED` and
`EXECUTION_AUTHORIZED` are **not** emitted.

**Verdict: `UNSEEN_IDENTIFIER_COPY_SELECTION_PROTOCOL_LOCKED`** — the unseen-identifier
copy/selection diagnostic is fully specified across Decisions 1–12; **implementation and execution
remain unauthorized.** The exact prior model recipe was reconstructed from merged source without any
code or architecture change (Decision 6), so `UNSEEN_IDENTIFIER_PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`
does **not** apply. No scientific result verdict is emitted.

## PR #1368 audit and merge record (prerequisite for this lock)
The draft preregistration was independently audited from live Git/GitHub ground truth and merged
before this lock:
- **Decision:** `MERGE_READY_AFTER_SCOPED_CORRECTIONS` → merged.
- **Mechanical state at audit:** open, draft, `mergeable_state: clean`; base = default `bdc6a8cc`;
  **documentation-only** (3 files, +250/−2); **all 7 CI checks green**; **0 unresolved review
  threads**; `experiments/phase_lc/results/abc.json` and all prior evidence unchanged.
- **Content verified live:** the exact scientific question; one representation-neutral format (no
  prose-vs-JSON); the frozen recipe preserved with every forbidden intervention excluded
  (no candidate-index, constrained decoding, pointer/copy/ranking head, BindingSlots, E1 memory,
  relational attention, external-table correction, new architecture, capacity increase, tokenizer
  change); task splits C1–C8; exact-ID output retained; numeric gates `APPROVAL_REQUIRED_BEFORE_EXECUTION`;
  seeds proposed but not consumed; standing invariants preserved; no forbidden claim.
- **Scoped documentation correction applied before merge:** added the explicit two-orthogonal-axes
  framing (copy-vs-selection; seen-vs-unseen), the copy-masks-selection rule, and the
  iterative-diagnosis loop; reaffirmed exact-ID output with no candidate-index in the probe.
- **Merge commit:** `872c034cd44179c59858c1f87ff08832cb4aa32c` (reachable from the authoritative
  default; default synchronized; clean working tree).

This lock freezes numeric gates and the remaining unspecified contracts on top of that merged
preregistration.

## Decision 1 — Frozen scientific diagnostic structure (two orthogonal axes)
The diagnostic preserves **two orthogonal axes**; a full diagnosis reads both.

### Axis A — copy vs selection
- **C1 — direct unseen-ID copy:** the input contains one opaque target identifier explicitly; the
  model must reproduce it exactly. C1 isolates direct contextual copying **without** relation
  selection.
- **C2 — single-relation lookup:** the input contains multiple `source → target` pairs; the model
  must select the pair matching the query source and reproduce its target. C2 requires selection
  **plus** copying.

Interpretation (thresholds in Decision 7):
- high C1 and high C2 → copying and basic relation selection are demonstrated;
- high C1 and low C2 → **selection** is the bottleneck;
- **low C1 → C2 cannot independently diagnose selection**, because every correct selection must
  still pass through the broken copying stage. **Do not classify a selection failure unless C1
  competence clears its frozen gate.**

### Axis B — seen vs unseen generalization
- **C6 — seen-ID control:** identifiers from the training pool.
- **C7 — unseen-ID cohort:** identifiers from a completely disjoint pool (primary cohort).

Interpretation:
- C6 high, C7 low → the operation exists on seen IDs but **does not generalize**;
- C6 low and C7 low → **no demonstrated copy operation**, or a protocol/implementation issue;
- C6 and C7 high → seen→unseen generalization is supported under the tested protocol.

**Do not collapse "copy mechanism absent" and "copy does not generalize" into one verdict.**

## Decision 4 — Frozen task construction
All splits single-hop and bounded. Exactly one matching source per lookup; correct-pair position
uniformly distributed.
- **C1 — direct unseen-ID copy:** one target ID explicitly present; no distractor-selection burden;
  output is the exact ID.
- **C2 — relation lookup:** one query source; multiple `source → target` pairs; exactly one matching
  source; correct-pair position uniform.
- **C3 — evidence-like lookup:** one selected relation; multiple opaque evidence IDs; output is the
  exact evidence ID associated with the correct relation.
- **C4 — position robustness:** correct pair appears uniformly in first / middle / last position.
- **C5 — lexical-similarity decoys:** distractor IDs differ from the target by one or two characters;
  no positional or prefix shortcut.
- **C6 — seen-ID control:** IDs drawn from training pools; same mechanics as the unseen cohorts.
- **C7 — unseen-ID cohort:** fully disjoint identifier pools; same mechanics as C6; primary
  generalization cohort.
- **C8 — missing-key abstention:** queried source absent from context; the model must emit the exact
  frozen abstention token.

Frozen at protocol-lock: examples per split · candidate count · answerable/unanswerable balance ·
position balance · lexical-decoy frequency · seen/unseen allocation · evidence-lookup frequency.
**No constant-gold component enters the primary competence score**; C8 (abstention) is reported
**separately** as a safety/abstention metric (this is the lesson carried from the typed-vs-prose
constant-output finding).

## Decision 5 — Frozen output contracts
- Exact-ID tasks (C1–C7) output **only** the bare `<IDENTIFIER>`.
- Missing-key tasks (C8) output **only** the frozen abstention token `INSUFFICIENT_EVIDENCE`.

No JSON wrapper · no explanation · no reason code · no candidate index · no constrained decoding ·
no arm-specific parser. One exact grader for all splits.

The evaluator must distinguish: exact-sequence match · token-level match · malformed output ·
in-context wrong ID · out-of-context fabricated ID · correct abstention · false abstention.

**Candidate-index output is explicitly forbidden in this probe** — it would remove the copying
requirement being diagnosed. (Candidate-index and constrained decoding are output-format
interventions that route *around* copying; a candidate-ranking objective is what changes selection.
Both belong only to later, separately-authorized programs.)

## Decision 2 — Frozen representation-neutral input format
One deterministic plain-text representation only. **No prose-vs-JSON comparison, no serializer /
paraphrase / representation search, no task-specific output formatting beyond the locked target
type.** Canonical formats:

```text
TASK = <task_name>
QUERY_SOURCE = <source_id>
FACTS:
<source_id_1> -> <target_id_1>
<source_id_2> -> <target_id_2>
...
ANSWER =
```
Direct copy:
```text
TASK = DIRECT_COPY
TARGET = <target_id>
ANSWER =
```
Evidence-like lookup:
```text
TASK = EVIDENCE_LOOKUP
QUERY_RELATION = <source_id> -> <target_id>
FACTS:
<source_id_1> -> <target_id_1> | EVIDENCE = <evidence_id_1>
<source_id_2> -> <target_id_2> | EVIDENCE = <evidence_id_2>
ANSWER =
```
Missing-key abstention:
```text
TASK = MISSING_KEY
QUERY_SOURCE = <absent_source_id>
FACTS:
...
ANSWER =
```
Frozen exactly: field names · capitalization · separators · whitespace · newline layout · fact
ordering · query placement · answer prefix · distractor syntax · evidence syntax · abstention token.

## Decision 3 — Frozen identifier design
**Verified from merged source:** identifiers are **character-visible** under the frozen 200-id
lexical tokenizer — e.g. `Q7X2` encodes to `[81, 55, 88, 50]` (4 tokens = 4 characters, exact
round-trip), and uppercase letters / digits are plain ASCII. A four-character opaque ID therefore
occupies four tokenizer tokens; the copy operation is **not** obscured by subword fragmentation.

Frozen: identifier alphabet · identifier length · allowed prefixes · case · digit/letter balance ·
collision rules · train/dev/final pool sizes · pool-generation algorithm · tokenizer-length strata ·
position distribution · source–target independence.

Recommended identifier form (to be fixed at implementation authorization):
- fixed **four-character** opaque identifiers;
- uppercase ASCII letters and digits;
- **no** semantically meaningful prefix, **no** task-specific prefix, **no** label-correlated shape;
- example: `Q7X2`.

Requirements:
- train, development, and final identifier pools are **disjoint**;
- source and target pools must not leak task labels;
- evidence IDs use the same complexity class but a **distinct domain-separated pool**;
- **no** identifier may encode task type, correct position, answerability, seen/unseen status, or
  relation identity;
- tokenizer decomposition is measured and reported; metrics are reported **by tokenizer length** if
  identifier token lengths vary;
- collision freedom is mechanically verified at generation.

## Decision 7 — Frozen numeric gates
Frozen before any implementation, data generation, or run; **never adjusted after inspecting
reserved results.** Any future departure must be justified from the frozen task design alone, never
from probe results.

**Direct-copy competence (C1, unseen):** mean exact-match ≥ **0.85**; ≥ **4/5** final seeds ≥ **0.80**;
token-level accuracy ≥ **0.95**; fabricated out-of-context ID rate ≤ **0.02**.

**Relation-selection + copy competence (C2):** mean exact-match ≥ **0.80**; ≥ **4/5** final seeds ≥
**0.75**; position-group minimum ≥ **0.70**; in-context wrong-ID rate ≤ **0.15**; fabricated
out-of-context ID rate ≤ **0.02**. *Selection failure may be declared only when C1 passes but C2
fails.*

**Evidence-like lookup (C3):** mean exact-match ≥ **0.80**; ≥ **4/5** final seeds ≥ **0.75**;
fabricated evidence-ID rate = **0**.

**Position robustness (C4):** first ≥ **0.75**; middle ≥ **0.75**; last ≥ **0.75**; max spread across
positions ≤ **0.10**.

**Lexical-decoy robustness (C5):** accuracy degradation vs matched non-decoy cases ≤ **0.05**;
lexical-similarity heuristic must remain below the competence floor.

**Seen-vs-unseen generalization (C6/C7):**
- *Confirmed:* C6 ≥ **0.90**; C7 ≥ **0.80**; C6 − C7 gap ≤ **0.10**; ≥ **4/5** final seeds meet the
  unseen floor.
- *Generalization failure:* C6 ≥ **0.85** and C7 < **0.70**, **or** gap > **0.15**.
- *No demonstrated copy operation:* C6 < **0.70** and C7 < **0.70**. **Do not emit "copy mechanism
  absent" when C6 (seen) is competent.**

**Missing-key abstention (C8):** abstention accuracy ≥ **0.90**; false-answer rate ≤ **0.05**;
fabricated-ID rate ≤ **0.02**.

**Determinism & integrity:** byte-identical dataset regeneration; byte-identical serialization;
stable source/config/tokenizer/dataset/init/data-order/checkpoint/prediction digests; no seed
overlap; no final-cohort inspection before authorization; no protocol deviation; compute limits
respected.

## Decision 8 — Frozen verdict vocabulary (future execution only; none emitted now)
Exactly one primary verdict at a future authorized execution:
- **`UNSEEN_IDENTIFIER_COPY_SELECTION_CONFIRMED`** — C1, C2, C3, C4, C5, C7-generalization, C8, and
  determinism/protocol gates all pass. Supports **only**: *the frozen small-model recipe can copy
  and select unseen opaque identifiers from a bounded controlled context under the preregistered
  protocol.*
- **`UNSEEN_IDENTIFIER_COPY_ONLY_PARTIAL`** — C1 passes, C2 fails, protocol/integrity pass. *Direct
  copying exists; relation selection not established.*
- **`UNSEEN_IDENTIFIER_GENERALIZATION_FAILED`** — C6 passes, C7 fails under the frozen gates. *Works
  on seen IDs; does not generalize adequately to unseen.*
- **`UNSEEN_IDENTIFIER_COPY_CAPABILITY_NOT_FOUND`** — C6 fails and C7 fails and direct-copy below
  gate, protocol/integrity pass. *No copy operation under seen or unseen conditions.* **Not** used
  when seen performance is competent.
- **`UNSEEN_IDENTIFIER_SELECTION_FAILED`** — C1 passes, C2 fails (selection isolated).
- **`UNSEEN_IDENTIFIER_EVIDENCE_LOOKUP_FAILED`** — C1/C2 sufficient, C3 fails.
- **`UNSEEN_IDENTIFIER_ABSTENTION_GATE_FAILED`** — C8 fails.
- **`UNSEEN_IDENTIFIER_PROTOCOL_VIOLATED`** · **`UNSEEN_IDENTIFIER_RESOURCE_BLOCKED`**.

**No verdict automatically authorizes an intervention.**

## Decision 9 — Frozen shortcut checks
Baselines required, each on its relevant split: first-target · last-target · middle-target ·
most-frequent-target · lexical-similarity · prefix-matching · character-overlap · source–target
co-occurrence memorization · seen-ID frequency · constant-abstention · output-template leakage ·
task-label leakage. For every heuristic:
- compute **task-specific chance** mechanically;
- require heuristic ≤ **chance + 0.05**;
- require it **below** the relevant learned competence floor;
- require it **incapable** of satisfying a positive verdict.

A shortcut anomaly must be **resolved before reserved execution**. **Do not repeat the prior process
deviation** (typed-vs-prose) where the shortcut baseline was only investigated after final runs —
the shortcut precheck is a hard pre-reserved-execution gate here.
