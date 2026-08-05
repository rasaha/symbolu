# Exact next intervention implied by the evidence

**This document only *names* the next intervention. It is NOT implemented here; no fix, no coefficient
tuning, and no subsequent intervention phase is begun in this PR. KDA remains BLOCKED.** Whatever
follows must be its own preregistered phase with fresh reserved seeds.

The diagnosis localizes two *separate* failures, so it implies two *separate*, narrowly-scoped next
steps — each targeting the exact stage the evidence points to, and each deliberately avoiding stages
the evidence shows are healthy.

## 1. Value path → close the read-address probe→eval generalization gap

**What the evidence licenses.** The stored value is intact and usable and the readout works (A4a/A4b
= 1.0; cosine(post,query) ≈ 0.95–1.0); forcing the address recovers retrieval (A3 ≈ 1.0). Ordinary
retrieval fails only because the eval-time read places ~0.58–0.60 (not ~0.96) on `s*`. So the target
is the **read-address distribution on the real query distribution**, nothing downstream.

**Implied next intervention:** a **read-address generalization objective** — contrastive
correct-slot-vs-competitor read training on a **held-out** query distribution distinct from the
aux/probe distribution (varied query phrasings, hard negative slots with similar content), so the
router learns a general addressing rule rather than fitting the probe distribution.

**Explicitly *not* implied by the evidence:**
- value-path repair, storage changes, or an external key→value table (the memory is already intact and
  usable — these would be bypasses, not repairs);
- naive read *sharpening* alone (lower temperature / entropy penalty / margin): O1 and O2 already
  sharpened the *probe* routing in earlier phases and it did not transfer to eval retrieval and decayed
  — so sharpening is only worth revisiting after a per-example read-rank-on-eval sub-diagnostic shows
  `s*` is already the eval argmax;
- new slots/dimensions, architecture redesign (separate identity/content addressing, multi-head read),
  or enterprise-ID hybrids — the evidence does not implicate slot capacity, key/value entanglement, or
  identifiers (a single forced address already achieves 1.0).

## 2. Quality → decouple the auxiliary gradient in the write-address projection only

**What the evidence licenses.** The quality regression is a gradient conflict concentrated in
`write_addr_proj` (`W_wk`) — negative LM-vs-auxiliary alignment on every quality seed, positive in the
clean controls — while the **backbone and embeddings are not in conflict**.

**Implied next intervention:** a **targeted gradient decoupling** of the persistence/teacher objective
from the language-model objective **confined to the addressing parameters** (write-address projection,
and secondarily the write gate / read-address projection) — e.g. gradient projection (PCGrad-style),
a separate optimizer/adapter, or stop-gradient of the auxiliary through the shared path — rather than a
broad backbone separation, which the evidence shows is unnecessary.

**Explicitly *not* implied:** freezing or separating the whole backbone (no backbone conflict was
measured), or abandoning the auxiliary objective wholesale.

## Sequencing note

These are two independent hypotheses for two independent failures; a future phase could test them
separately or jointly, but each requires its own preregistration, fresh reserved seeds, frozen
classifier, and mechanical advancement gate. Establishing whether either *actually improves*
clean-stable, quality-preserving, causally-clean retrieval is out of scope for this diagnostic PR.
