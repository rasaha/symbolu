# Ground-Truth Protocol

*Phase 6. Ground truth is annotated **independently of the EvidenceAssurance rules** and independently
of the observed (possibly misleading) metadata — from the TRUE latent state, via two rubrics with
adjudication. Source: `evidence_assurance/dataset.py`.*

## Separation of concerns

| Layer | Sees | Role |
|---|---|---|
| **TRUE latent state** | claim correctness, true independence, upstream correctness, alignment, freshness, authority, counterevidence | reality |
| **Ground truth** | the TRUE latent state (via annotators A + B) | the correct evidence state |
| **Observed metadata** | possibly incomplete / adversarially misleading provenance | what a method sees |
| **Method under test** | observed metadata only | its disposition |

The pivotal design: **CLEAN_DEPENDENT** (true claim, all evidence derived from one *correct* upstream)
and **CORRELATED_FAILURE / ADVERSARIAL_PROVENANCE** (false claim, evidence from one *wrong* upstream)
are **indistinguishable by source count or diversity** — they present as N correlated sources either
way. They differ only in whether the single upstream source is actually correct and aligned. A method
can separate them only by verifying provenance + alignment, not by counting. That is the study's core
discriminating test.

## Two independent annotators

Both apply a **shared hard precedence** on the safety-critical dimensions (so they agree on what
matters), then diverge on the soft tail:

- **Shared hard precedence:** misaligned → MISALIGNED; false claim or correlated-on-wrong-source →
  REJECT_EVIDENCE_STATE; counterevidence → CONFLICTED; non-authoritative in high-risk →
  AUTHORITY_MISMATCH.
- **Annotator A (provenance-first soft tail):** stale > dependent > insufficient > limitations.
- **Annotator B (claim-first soft tail):** limitations(overstated) > dependent > stale > insufficient.

They diverge only when multiple *soft* flags coexist (e.g. a case that is both stale and
single-upstream: A → STALE, B → DEPENDENT).

## Adjudication (disagreement recorded, not hidden)

- A == B → gold.
- A ≠ B → gold = the **more conservative** (more restrictive) state; `annotator_disagreement = True`.
- **Disagreement rate: 8.3%** (52 / 624), **entirely on the CLEAN_DEPENDENT soft tail** (stale ×
  dependent), all adjudicated to STALE. No disagreement on any safety-critical (reject/misaligned/
  conflicted) case — the annotators agree perfectly on what must not be delivered. Disagreement is
  never converted into an optimistic label.

## Corpus (ea_corpus_v1_1)

- **624 cases**, 13 domains × 4 size variants × 12 latent templates. dev/eval = 156/468.
- **Partitions:** CLEAN_INDEPENDENT 312, CLEAN_DEPENDENT 156, CORRELATED_FAILURE 104,
  ADVERSARIAL_PROVENANCE 52.
- **Gold states (8):** VERIFIED 80, VERIFIED_WITH_LIMITATIONS 52, STALE 104, CONFLICTED 104,
  MISALIGNED 104, AUTHORITY_MISMATCH 24, DEPENDENT 52, REJECT_EVIDENCE_STATE 104. High-risk: 288.
  *(v1_1 corrected a high-risk-gate bug that had suppressed AUTHORITY_MISMATCH — see
  `CORPUS_CHANGELOG.md`. 24 high/critical-risk low-authority cases moved VERIFIED → AUTHORITY_MISMATCH;
  MISALIGNED and all partition counts unchanged.)*
- Each case records: claim, true latent state (correctness/independence/upstream/alignment/freshness/
  authority/counter), observed metadata (publishers/domains/paths/upstream-ids/hashes/authority/years/
  alignment/provenance-confidence/completeness), correlated-failure type, annotator A/B, gold state,
  expected AssertionGate delivery effect, disagreement flag, rationale.
- **Cases constructed so EvidenceAssurance loses:** ADVERSARIAL_PROVENANCE (dependent sources
  disguised as independent with fabricated metadata + low provenance confidence) — a naive
  independence check keyed on observed distinct publishers/paths/hashes is *fooled*; only reasoning
  about provenance confidence catches it. This partition, and the missing-metadata study (Phase 16),
  are where the method is punished.

## Independence from EvidenceAssurance

Gold uses the TRUE latent state via A/B rubrics; the EvidenceAssurance component (Phase 13) sees only
the OBSERVED metadata and computes its own disposition. No EA rule is reused to define gold, so a
method that matches gold under adversarial/missing metadata is genuinely recovering the truth, not
re-deriving its own inputs.
