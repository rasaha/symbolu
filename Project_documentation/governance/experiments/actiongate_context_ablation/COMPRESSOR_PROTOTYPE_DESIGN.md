# COMPRESSOR_PROTOTYPE_DESIGN

The first ActionGate Context Minimization prototype: an **extractive** compressor
that removes whole spans only. It reuses the frozen protected-span detector and the
frozen oracle extractor + gate; it changes nothing in ActionGate, the corpus, or
the extractor, and introduces no SCC/USE.

## Pipeline

    context
      │  protected-span detector (frozen fail-closed hybrid)
      ▼
    P0 mask  (spans that must be preserved exactly)
      │
      ▼
    lossless structural compression
      • redundancy-set collapse (keep one representative)
      • exact-duplicate-text removal
      (lossless: a retained copy carries the same information)
      │
      ▼
    budgeted extractive selector
      • remove ONLY non-protected spans, lowest structural value first,
        until the target token reduction is reached
      • never rewrite / paraphrase / summarize; original order preserved
      │
      ▼
    compressed context ──▶ ActionGate extraction (oracle) ──▶ evaluation
      │
      ▼
    decision-invariance check vs original
      signature = envelope + outcome + dispositive rules + applied constraints
      │
      ├─ invariant ──▶ emit compressed context
      └─ changed ────▶ FAIL-CLOSED:
                         restore the necessary removed spans (those whose individual
                         removal changes the signature — a detector miss);
                         if still not invariant (joint effects) ──▶ fall back to original

## Why the signature excludes provided-evidence counts

"Evidence/approval requirements" are enforced through the **decision outputs**, not
by counting inputs. Removing a *required* evidence span changes the outcome (e.g.
`ALLOW → SIMULATE_AND_RETRY`) — caught by the signature. Removing a *redundant*
evidence span leaves outcome/dispositive-rules unchanged — correctly treated as
safe. Counting `n_evidence` would flag redundant removals as decision changes, which
is wrong; so the signature is (envelope, outcome, dispositive_rules,
applied_constraints).

## What the prototype does and does not claim

- It **guarantees** decision invariance by construction (fail-closed verification
  against the real gate), and 100% protected recall (protected spans are never
  removed; misses are restored).
- It does **not** guarantee incidental-detail preservation — non-protected content
  is intentionally removable. That is the compression.
- The achievable reduction is bounded by the non-protected fraction (~66% on this
  corpus). Beyond that, removal would touch protected spans and fail-closed prevents
  it — so the operating range is essentially [0, non-protected fraction].

## Determinism & reuse

Structural + extractive selection and the invariance check are pure functions over
the frozen components. The only non-deterministic output is wall-clock latency,
which is reported but never used in an equality/hash check.

## Baselines & task proxy

See COMPRESSOR_PREREGISTRATION.md. The generic protection-unaware baseline is the
control that shows *why* the P0 mask is necessary; the task metric is a deterministic
information-preservation proxy because no open-weights LLM is runnable here.
