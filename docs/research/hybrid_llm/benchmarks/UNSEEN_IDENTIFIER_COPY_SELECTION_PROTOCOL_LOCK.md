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
