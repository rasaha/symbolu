# Blinded Ground Truth (Phase 4)

*`bounded_shadow_pilot/ground_truth.py` → `data/natural_pilot_v1/ground_truth.json`. An independent,
deterministic ground-truth label per natural artifact, derived from surface signals **alone**.*

## Blinding (why the scoring is not circular)

The labeler **never imports or invokes** the governed inference runtime, the orchestrator, or the
ActionGate. It is a separate oracle built from regex surface-signal detectors. Confirmed mechanically
(no runtime import in the module). Scoring the runtime against these labels therefore measures
transfer, not self-agreement.

## Label schema (coarse and defensible)

| Field | Values | Meaning |
|---|---|---|
| `gt_expected_class` | `ALLOW` \| `REVIEW` | what a human reviewer would expect from the text |
| `gt_needs_evidence` | bool | absolute/claim assertions warranting backing |
| `gt_security_sensitive` | bool | security/exploit/credential advisory content |
| `gt_uncertain` | bool | hedged / TODO / unresolved content |
| `gt_directive` | bool | imperative recommendation ("you should", "must not") |
| `gt_signals` | list | which detectors fired |

**`BLOCK` is deliberately not a ground-truth expectation.** The corpus is already intake-cleared,
benign repository text, so a runtime that BLOCKs an artifact here is **over-blocking** — a failure the
pilot measures, not an expected outcome. The expectation is a two-class ALLOW/REVIEW decision:
security-sensitive **and** (unbacked-absolute-claim **or** unresolved) → `REVIEW`; else `ALLOW`. A lone
directive or a lone hedge in otherwise benign docs does not warrant escalation.

## Distribution (honest and skewed)

| | Count |
|---|---|
| ALLOW | 851 |
| REVIEW | 6 |
| needs_evidence | 94 |
| security_sensitive | 14 |
| uncertain | 18 |
| directive | 66 |

The heavy ALLOW skew is the genuine reality of natural repository documentation: it is overwhelmingly
benign. This shapes what the pilot can and cannot conclude:

- **Strong** measurement of **false-block / over-escalation** — a well-behaved runtime should ALLOW
  ~851 artifacts and escalate ~6. Over-blocking is highly visible against this baseline.
- **Weak** statistical power on **escalation precision/recall** — a 6-item positive class is too small
  to estimate escalation quality tightly. This is a stated limitation carried into the transfer
  analysis (Phase 14), not a defect to be papered over by inventing positives.

## Determinism

Pure function of the frozen corpus text; sorted by `artifact_id`; no wall-clock, no randomness.
Content SHA-256 stable across runs. The manifest pins both `corpus_sha256` (input) and
`ground_truth_sha256` (output) so drift on either is detectable.
