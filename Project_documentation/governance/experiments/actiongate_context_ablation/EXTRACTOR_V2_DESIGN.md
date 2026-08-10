# EXTRACTOR_V2_DESIGN

Design of the next-generation extraction + protected-span pipeline. Scope: improve
extractor instability and protected-span precision only. No compressor, no SCC, no
USE, no new theoretical formulas. ActionGate and the corpus are untouched; the new
components plug into the frozen ablation harness via optional parameters
(`ablation.run_ablations(realistic_spec_fn=…)`, `metrics.aggregate(protect_fn=…)`).

## Why v1 failed

- **Instability:** the v1 realistic extractor was a single narrow keyword matcher.
  Paraphrase (held-out) evaded the keywords, so facts were dropped and the extractor
  disagreed with the oracle ~41% of the time on held-out.
- **Precision:** the v1 protected detector was a recall-favoring regex that marked
  any span with a number/URI/policy-word as protected → ~30% precision, ~69%
  protected fraction, ~31% deployable ceiling.

## Multi-stage extractor

    text ─▶ Stage 1: structured (deterministic)        ─┐
           JSON / YAML / k8s / terraform / md-tables /  │  pinned facts (HIGH)
           key:value / shell / numeric-with-unit        │
                                                         ▼
           Stage 2: semantic frames (token-set)   ──▶  concepts (precise + paraphrase
           synonym frames, light-stem prefix match)      recall via synonyms)
                                                         │
           Stage 3: independent validator (fuzzy)  ──▶  char-trigram cosine vs concept
           — DIFFERENT method from Stage 2 —             exemplars
                                                         ▼
           orchestration:  accepted = Stage2 ∪ Stage3_recover(≥0.60)
                           mutex slots resolved (single⊻dual, high⊻medium sim)
                           confirm (≥0.50) ⇒ HIGH ; else UNCERTAIN ⇒ fail-closed keep

- **Stage 1 is the biggest instability win**: structured facts (JSON `{"sink_approved":
  true}`, table `| affected | 8000 records |`) are paraphrase-invariant.
- **Stage 2** carries paraphrase recall through multiple synonym frames matched by
  light-stemmed *prefix* containment, not exact substrings (the v1 failure).
- **Stage 3** is structurally independent (surface n-gram similarity, not tokens), so
  it does not share Stage 2's blind spots. It *confirms* (≥0.50 ⇒ HIGH confidence) and
  can *recover* a missed concept only at a high, unambiguous similarity (≥0.60).
- **Fail-closed**: a Stage-2 fact that Stage 3 does not confirm is still kept
  (`UNCERTAIN`) — a real fact is never dropped on disagreement. Because Stage 3
  *recovery* requires ≥0.60 (well above the ~0.45 cross-concept bleed) and mutex slots
  resolve single/dual and sim-fidelity conflicts, disagreement does not inject
  spurious facts. Fail-closed runs on the unit's own text, so a removed unit's fact
  correctly disappears (which is what makes ablation agree with the oracle).

## Trainable protected-span detector

- **Labels (reused, not invented):** the deterministic gate-derived criticality from
  the existing ablation study — `annotation.derive_primary` mapped to
  {ENVELOPE, DECISION, ASSURANCE, STRUCTURAL, NON_CRITICAL} (redundant→DECISION).
- **Features (paraphrase-robust):** source-type one-hot (metadata, invariant),
  structural flags (has-number / json-brace / pipe / uri / kv-colon), extractor-v2
  concept flags, filler markers, token-count, redundancy flag.
- **Model:** from-scratch multinomial logistic regression (pure Python, deterministic:
  zero init, fixed epochs/lr/L2). No external ML dependency. Trained on DEV+VALIDATION
  units; evaluated on HELDOUT.
- **Fail-closed hybrid** = trained classifier ∪ a minimal safety net (fact-bearing
  source types, structural-reference spans, any extractor-found fact). The classifier
  drives precision; the safety net guarantees recall = 100% (including interaction-only
  spans the single-ablation labels miss).

## What this deliberately does NOT do

- No token compression, no SCC, no USE, no new formulas.
- No modification of ActionGate semantics or the corpus.
- No use of held-out data for training or threshold calibration.
