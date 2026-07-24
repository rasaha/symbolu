# Architectural Decision (Phase 28)

*Decided against the frozen decision rules (`EVALUATION_PROTOCOL.md`) and the falsification outcomes
(`LIMITATIONS_AND_FALSIFICATION.md`). One option is chosen; the rest are recorded with why not.*

## The nine options

| # | Option | Verdict |
|---|---|---|
| 1 | Keep ClaimIntegrity as a distinct (heavyweight) layer | **No** |
| 2 | Keep only for high-risk domains | **No** |
| 3 | Reduce to qualifier + negation + scope checks | partial (folded into 4) |
| 4 | **Reduce to semantic validation after simple splitting** | **Chosen** |
| 5 | Merge into EvidenceAssurance | **No** |
| 6 | Preserve whole sentences, avoid decomposition | **No** |
| 7 | Use human review for complex claims | partial (for the residual only) |
| 8 | Not enough evidence | **No** |
| 9 | Reject ClaimIntegrity | **No** |

## Decision: Option 4 — reduce to semantic validation after simple splitting

Do **not** build a heavyweight decomposition component. Instead:

1. **Decompose with a cheap preservation-first splitter** — sentence segmentation that (a) never
   strips modifiers, (b) resolves cross-sentence references, and (c) does not extract non-assertive
   text. This ~4-probe configuration reproduces the full component's primary-endpoint result (0.068
   unsafe delivery) and its evidence-query benefit (0.000). Clause/triple/aggressive splitting is
   **prohibited** — it is the actual danger (OpenIE 0.864 unsafe).
2. **Run the per-dimension checkers as a *validator*, not a decomposer.** The negation / modality /
   uncertainty / numeric / scope / attribution modules earn their cost as an **audit** of the
   decomposition — especially when the decomposition comes from an untrusted extractor (a third-party
   parser or an LLM). They are what quantified OpenIE at 0.864 and would flag any extractor that strips
   a governing dimension. In high-risk tiers, a validator flag gates delivery (route to `ESCALATE`).
3. **Preserve ambiguity over false precision.** On scope-spanning conjunctions, keep the unit whole and
   flag `INDETERMINATE` rather than force a split that detaches an exception (~8× safer than aggressive
   splitting).

This is a **reduction**: keep the cheap splitter + reference resolution + the checkers-as-audit; drop
the notion of a large dedicated stage. It subsumes Option 3 (the qualifier/negation/scope checks are
the validator) and uses Option 7 only for the residual.

### Why Option 4

- **The evaluation licenses exactly this and no more.** The heavyweight component does not beat
  sentence-splitting on the primary endpoint (H0-1, H0-14, H0-18 survive), so a distinct layer is
  unjustified — but *how* you decompose matters enormously (H0-3, H0-9, H0-17 rejected), so "just use
  any splitter" is wrong. Option 4 keeps the part that pays (preservation-first + reference resolution +
  validation) and drops the part that doesn't (a large bespoke stage).
- **The checkers have a real job — auditing untrusted extractors.** Their value is not in the
  component's own output (preservation is free from not-stripping) but in catching a *different*
  system's drift. That is a validation function, which is what Option 4 names.

### Deliberately scoped conditions

- **Bounded claim.** The recommendation reduces *unsafe delivery from bad decomposition* relative to
  triple extraction; it does **not** beat sentence-splitting, and it does not solve the residual 0.068
  (exception-bearing conjunction). No production-readiness claim — the corpus is deterministic and
  self-built.
- **Placement is upstream of EvidenceAssurance, as a validation gate**, mirroring the EvidenceAssurance
  decision (a cross-cutting stage, not a canonical module). It is not merged into EA (Option 5) because
  EA cannot see the original output and so cannot validate the decomposition.
- **Human review (Option 7) is reserved for the residual** — the exception-bearing conjunctions the
  validator flags `INDETERMINATE` and any high-risk validator flag.

## Why not the others

- **(1) Distinct heavyweight layer** — not justified; ties sentence-splitting on the primary endpoint at
  1/7th the value-per-probe.
- **(2) High-risk only** — there is no high-risk subgroup where the component beat sentence-splitting
  (P = B in every risk tier), so even a scoped heavyweight is unsupported.
- **(5) Merge into EvidenceAssurance** — category error: EA operates on the (already decomposed) claim
  and its evidence, and cannot see the original output; decomposition integrity must be checked
  upstream.
- **(6) Preserve whole sentences** — unsafe (0.454) via ungoverned claims on multi-claim outputs.
- **(8) Not enough evidence** — there is ample, consistent evidence across 832 examples, an adversarial
  set, an error-propagation matrix, an ablation, and a complexity challenge.
- **(9) Reject ClaimIntegrity** — too strong: the concern is real (decomposition drift is a no-tell
  downstream failure) and the validation function has demonstrated value against untrusted extractors.

## One-line statement

> Do not build a heavyweight decomposition stage. Use a cheap preservation-first splitter (never strip,
> resolve references, skip non-assertive text), run the per-dimension checkers as a validator/audit of
> untrusted extractors and a high-risk delivery gate, preserve ambiguity over false precision, and send
> the residual to human review. Decomposition *method* is the lever; a dedicated component is not.
