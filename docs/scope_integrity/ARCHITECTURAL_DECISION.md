# Architectural Decision & Integration Contract (M6)

*Decided against the frozen protocol and the falsification assessment. One option is chosen; the
integration contract with ClaimIntegrity and the unresolved residual are stated exactly.*

## The six options

| # | Option | Verdict |
|---|---|---|
| 1 | Adopt full scope-carrying split (E) | **No** — undeployable generally (0.218) |
| 2 | Adopt only subject propagation (C) | **No** — subject-carry is not load-bearing; C is 0.472 on general |
| 3 | Adopt subject + qualifier (D) | **No** — 0.358 on general |
| 4 | Preserve-and-flag all scope-spanning conjunctions (F) | **No** — safe but leaves the residual; and F ungated is 0.218 general |
| 5 | **Hybrid — split only when attachment is provable, else preserve-and-flag** | **Chosen (tightly gated)** |
| 6 | Reject targeted decomposition, retain 0.068 | **No** — the gated hybrid demonstrably removes the residual |

## Decision: Option 5 — gated hybrid (split-when-provable, else preserve-and-flag)

Adopt a **tightly-gated hybrid** as a small extension to the ClaimIntegrity preservation-first
splitter:

1. Run the existing splitter unchanged (it handles all text and resolves references).
2. For **only** the claims it keeps whole that match the scope-spanning-conjunction pattern (a
   coordinating conjunction spanned by an `unless/except/…` modifier):
   - if the attachment is **provable** (single clear subject, no comma-splice/second-subject
     ambiguity) → split and **carry the postposed exception** across the conjuncts, then resolve
     references;
   - else → **preserve the whole span** and emit `INDETERMINATE_SCOPE` (whole-span evaluation / human
     review).
3. Leave everything else untouched — behavior on non-conjunction text is **identical** to the current
   splitter.

The load-bearing rule is postposed-exception distribution; subject-carry and the other propagations are
optional refinements (not load-bearing for the residual). This is the smallest mechanism supported by
the evidence, as the protocol requires.

### Why Option 5

- It is the **only** configuration that reduces the residual on the un-rigged general corpus
  (0.068 → 0.000) without raising false-rejection or evidence-query, **and** survives held-out data.
- It is not an abstention artifact — it actively splits provable cases; it flags only the genuinely
  ambiguous ones.
- It stays within the architecture constraint: a small regex extension over the frozen splitter, no
  parser, no LLM, no new downstream engine.

## Integration contract with ClaimIntegrity

The extension plugs into the ClaimIntegrity decision (adopted there: *reduce to semantic validation
after simple splitting*) as follows, **without modifying any frozen ClaimIntegrity code**:

```
model output
   │
   ▼
ClaimIntegrity preservation-first splitter   (frozen: sentence-split, never-strip, reference-resolve)
   │  produces claim units; some are scope-spanning conjunctions kept whole (the residual)
   ▼
ScopeIntegrity extension  (this study)
   │  for each kept-whole scope-conjunction:
   │    provable  → scope-carrying split (carry postposed exception) + reference resolution
   │    ambiguous → preserve whole + emit INDETERMINATE_SCOPE (route to whole-span eval / human review)
   ▼
per-dimension validator  (ClaimIntegrity checkers, as audit / high-risk gate)
   ▼
EvidenceAssurance → AssertionGate → ActionGate   (all unchanged)
```

**Contract terms:**
- **Input:** a claim unit the splitter kept whole. **Output:** either ≥2 scope-faithful atomic claims,
  or the original span tagged `INDETERMINATE_SCOPE` with a reason code.
- **Invariant:** the extension never fires on non-scope-conjunction claims (identical behavior to the
  splitter there); it never drops a governing modifier; it never emits a dangling pronoun (reference
  resolution is composed in).
- **Failure mode:** on ambiguity it preserves-and-flags — it does not guess. The flag is the downstream
  signal for whole-span evaluation or human review.
- **No new state:** the extension emits ClaimIntegrity claim units; it introduces no new
  evidence/delivery/action vocabulary.

## What remains unresolved (exact)

1. **The ambiguous scope residual** (scope corpus 0.148): nested exceptions, multiple subjects,
   adversarial punctuation. The extension flags these `INDETERMINATE_SCOPE`; it does not resolve them.
   Resolving them safely requires attachment parsing the mechanism deliberately avoids.
2. **The general 0.000 is corpus-bounded.** On real (non-synthetic) text, pattern detection and
   exception distribution will be imperfect; the transferable claim is directional, not the exact rate.
3. **Spurious over-propagation (~7.7%)** converts to conservative false-rejection, not unsafe delivery —
   an accepted, surfaced cost, subject to a policy decision on whether the safety gain is worth it.
4. **Live validation.** As with the prior tracks, this is a deterministic study with a modelled
   downstream adapter; a live end-to-end integration on real model outputs is the necessary follow-up.

## One-line statement

> Adopt a tightly-gated hybrid: over the frozen ClaimIntegrity splitter's output, split a scope-spanning
> conjunction only when attachment is provable — carrying the postposed exception across the conjuncts
> and resolving references — otherwise preserve the whole span and flag `INDETERMINATE_SCOPE`. It
> removes the exception-under-split residual (0.068 → 0.000 on the un-rigged general corpus) as a small
> regex extension, and flags the genuinely ambiguous remainder for review.
