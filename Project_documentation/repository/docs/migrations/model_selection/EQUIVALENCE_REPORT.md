# Model Selection — Behavioral Equivalence Report

## Method

`scripts/model_selection_equivalence_capture.py` produces a deterministic, canonical-JSON capture of the
Model Selection core's behavior, imported through the `execution_gate` surface. That surface exists as
**real modules** in the pre-migration tree and as the **logic-free compatibility surface** over
`ugence_model_selection` in the post-migration tree, so the identical script runs in both and any drift
appears as a byte difference.

Captured over the frozen scenario battery (`execution_gate.scenarios.SCENARIOS`, 11 scenarios, fixed
instant `T0`):

- per-candidate **eligibility decisions**: state, reasons, full `EligibilityDecision.to_dict()`
  (conditions, verdicts, criticality, evidence, detail), and a SHA-256 fingerprint of each;
- **selection results**: selected id, ranked utilities, abstained, reason, eligible/excluded ids, with a
  fixed deterministic quality prior and default `PolicyWeights`;
- the full **`harness.run()` pipeline** result (eligibility + selection + simulated outcomes across all
  scenarios);
- **exception/abstain edges** (empty eligible pool → abstain).

## Procedure

1. `git worktree add --detach <tmp> 2a5a8efc` (pre-migration tip; real `execution_gate`).
2. Run the capture there → `equivalence_before.json`.
3. Run the capture in the migrated tree (compatibility surface → canonical) → `equivalence_after.json`.
4. Byte-compare.

## Result

| Capture | Scenarios | sha256 |
|---|---|---|
| `equivalence_before.json` | 11 | `e8e86b425628a894ec863e304c0bad929928b38d3ba3d2fae4afa9d3add26884` |
| `equivalence_after.json` | 11 | `e8e86b425628a894ec863e304c0bad929928b38d3ba3d2fae4afa9d3add26884` |

**BYTE-IDENTICAL.** Eligibility decisions, disqualification reasons, eligible-candidate ordering, score
components, weighted totals, tie-breaking, selected candidate, no-eligible result, exception behavior,
serialization, and fingerprints are all unchanged.

## Corroborating evidence

- **Public API**: `api_before.json` == `api_after.json` (51 symbols, sha256 `3780087f866a7967`) → PATCH.
- **Replay freeze**: `execution_gate/frozen/replay_v1/verify_frozen.py` → aggregate `8b05b2da798a6222`,
  unchanged (frozen artifacts untouched).
- **Legacy identity test**: `execution_gate/tests/test_legacy_compat.py` asserts each
  `execution_gate.<mod>` **is** the canonical module object and public types share identity.

No unexplained difference exists.
