# StoryGraph Evaluation Evidence Ledger

Append-only record of frozen StoryGraph evaluation runs. **Historical evidence is
never overwritten or relabeled.** A defect discovered after a run is recorded as a
*superseding* entry; the original run keeps its own hashes, metrics, and verdict.

---

## Run 1 — account-takeover slice, partial-match defect (SUPERSEDED)

- **Commit:** `78911a9f`
- **Freeze version:** `ctd.freeze/2.0.0`
- **StoryGraph schema:** `ctd.storygraph/1.0.0`
- **Freeze digest:** `sha-256:318e321bc825c8ed954c29a78787a9875f381a978c5b6ddb18ee3879f2dcfaf0`
- **Story-graph digests:**
  - `ACCOUNT_TAKEOVER_TRANSFER@1.0.0` = `sha-256:4b716710ed71b77ba67aefe9f5a8927348b92a41de8f18cd15481020937b852d`
  - `DIGITAL_EXFILTRATION_STORY@1.0.0` = `sha-256:b4fe287d88fa28b81cd625641b35dd83f9f6a29051d7ab43c4b7319051185a46`
- **Corpus split hashes:**
  - dev = `sha-256:78adbccc7edde449df5dd9579babaaf3aa97c68b81aab4bc898702c2edaeb95e`
  - calibration = `sha-256:ef5bfa4e3c3439c5b537808c59a1411b64be8e6c81fbbba405fabdc6246e66f8`
  - final = `sha-256:c37482f3e4a6106e1bc10fd3ca2d2d290df2ab80bd121b25b18ac6c08c4ee436`
  - corpus = `sha-256:94ffbfdfe798fcd21c325e232c604ada450df9eb902e467bb7cd30630c24c727`
- **Metrics (9-case hand-built corpus):**
  - `true_completion_detection_rate` = 1.0
  - `benign_false_completion_rate` = 0.0
  - `evasion_false_completion_rate` = 0.0
  - **`benign_escalate_advisory_rate` = 0.75** ← the defect signal
  - benign ESCALATE cases = `B1_fully_covered_by_verified_context`,
    `B3_partial_no_completion`, `B4_wrong_order_no_completion`
- **Original verdict (as written in `STORY_GRAPH_ADVERSARIAL_VALIDATION.md`):**
  `CONTINUE — StoryGraph adversarial validation passed`

### Corrected verdict for Run 1 (evidence-based)

> **`CONTINUE — StoryGraph adversarial validation incomplete`**

Run 1 is **not** a passing result. The completion-gating axis was sound (0.0
benign/evasion false-completion), but the advisory axis was defective: three of
four benign look-alikes emitted `ESCALATE`.

### Semantic defect (root cause)

In `storygraph.py::_build_match`, the per-dimension consistency fraction defaulted
to **`1.0` when no edges of that kind were evaluable**:

```python
def frac(kind):
    s, t = per_kind[kind]
    return (s / t) if t else 1.0        # <-- defect: 0 evaluable edges => 1.0
```

When a completion node was absent, the discriminating `SAME_ENTITY` / `ORDER` /
`WITHIN` edges (which reference the completion node) became non-evaluable. Their
dimensions therefore defaulted to `1.0`, no structural gate tripped, and the frozen
weighted `harmful_score` cleared `threat_threshold` — so an *incomplete* benign
workflow was classified `THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT` (an ESCALATE
category) purely from **untested** relationships. Absence of a benign explanation
was, in effect, being treated as positive harmful evidence.

The original `STORY_GRAPH_ADVERSARIAL_VALIDATION.md` remains unmodified as the
historical Run-1 record (it already discloses `benign_escalate_advisory_rate = 0.75`
as a "known limitation"). This ledger reclassifies its verdict; it does not edit it.

### Reconstructability

Run 1 is reconstructable from commit `78911a9f`. The hashes above were captured
directly from `evaluation/freeze.build_freeze('78911a9f', profile='final')` and
`evaluation/story_corpus.evaluate_corpus()` at that commit prior to any Run-2 change.
A test (`test_prior_run_preserved`) asserts these constants remain on record.

---

## Run 2 — corrected partial-match semantics (SUPERSEDED)

See `STORY_GRAPH_PARTIAL_MATCH_VALIDATION.md` for the Run-2 specification, the new
semantic version, the re-frozen configuration, and the final-split verdict.

- **Commit:** `019e1f0d`
- **Freeze digest:** `sha-256:ed63bc9ba3f7636548360ecfb7d3cec6426fc02c884734a861a1f8347055c3da`
- **Corpus hash:** `sha-256:53e171feb364969f6a19bc286565e32d3666b6b5fb1c0878763b0be3cfd6fb42`
- **Correctness metrics:** encoded completion 1.0, benign/evasion false completion
  0.0, benign ESCALATE 0.0 — these stand.
- **Original verdict:** `CONTINUE — StoryGraph adversarial validation passed`.

### Run-3 verification finding on Run 2

Run 2's correctness results are sound, but its **final split was EXPOSED**: full
corpus aggregates including final-split cases were inspected before freeze and the
corpus/coverage model was tuned afterward (see `STORY_GRAPH_FINAL_SPLIT_AUDIT.md`).
Run 2 therefore does **not** establish evaluation *independence*. Disposition: the
Run-2 final split is retained as development evidence; a replacement held-out final
split is introduced in Run 3.

## Run 3 — verification & proof semantics (CURRENT)

See `STORY_GRAPH_VERIFICATION_VALIDATION.md`. Run 3 does not add detection features;
it (a) audits and replaces the exposed final split with a held-out generation, (b)
canonicalizes duplicate/retry events so witnesses are strictly minimal
(`ctd.witness.tiebreak/2.0.0`), (c) proves mandatory-edge fail-closed completion,
and (d) adds the imperfect-benign context taxonomy (missing context is never harmful
evidence).

- **Commit:** `pending-run3`
- **Freeze digest:** `sha-256:2e696f6a9579f82946a6bf77cbdaab6efe2d8a10df6cf9907b1ccf5330781767`
- **Holdout final id-hash:** `sha-256:c25b15049035c813a49aed056ec734106546c5b31d2f921c1ac48d36b3a121c7`
  (generator `ctd.storycorpus.gen/2.0.0`, seed `[911,912,913]`, 147 cases)
- **Verdict:** `CONTINUE — evaluation integrity and proof semantics passed`.

Run 3 supersedes Run 2's *integrity claim* only; all Run-1 and Run-2 hashes,
metrics, commits, and verdicts above remain on the record.
