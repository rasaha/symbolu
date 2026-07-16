# Varṇa Symbolic Resonance — B1.12 · PREREGISTRATION **V2.1** (minimal amendment)

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Status: FROZEN (SHA-256 recorded in `B1_12_V2_1_PREREG_FREEZE.md`). Controlling for execution. NOTHING run yet
under v2.1.**

V2.1 is the **minimal** amendment resolving CONTRADICTION-1
(`results/b1_12_symbolic_resonance_v2/B1_12_V2_METHODOLOGY_CONTRADICTION_LOG.md`), authorised by the maintainer.
It **incorporates `VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md` (SHA `831e48ec…`) in full by reference** and changes
**exactly one thing**. Everything else in v2 — Design A (single tightened DBR axis), fully independent
(non-crossover) two-model judgments, the tightened 25-vs-50 scale, the no-supplementation firewall, the
polarity-neutral full-range opposition/resolution convention (§1.4), aggregation, verdict bands, and the frozen
fresh 20-word list (`b1_12_symbolic_resonance_wordlist_v2/`, SHA `7a558008…`) — is **unchanged**.

## The single amendment

**Problem (CONTRADICTION-1).** The DBR scale defines `0 = no defensible relationship without importing outside
meaning`, but the relationship taxonomy has only ten strictly-positive accounting relationships and no way to
express "no relationship." A component that legitimately scores 0 therefore has no valid relationship value.

**Amendment.** Add exactly one relationship value:

> **`no_relationship`** — meaning "the ordinary bare word does not account for this mapping by any relationship."
> It is **valid only when `dbr_score == 0`, and forbidden at any non-zero score.**

Rules:
- The ten positive relationships (embodiment, constitutive_property, characteristic_expression, implication,
  natural_consequence, generation, opposition, resolution, regulation, containment) are **unchanged**; they remain
  valid at any score, including 0.
- `no_relationship` is the honest label for a genuine score-0 non-relationship. A model that scores 0 SHOULD use
  `no_relationship`; a model that scores > 0 MUST NOT use it.
- `no_relationship` is a **distinct** relationship for agreement purposes: it agrees (exact) only with
  `no_relationship`, and is incompatible with every positive relationship. It belongs to no compatibility group.
- Common honest synonyms a model may emit for this case (`none`, `no`, `n/a`, `no relation`, `no_relation`) are
  canonicalized to `no_relationship` (logged as coercions, exactly like orthographic typos); this canonicalization
  is likewise accepted only at `dbr_score == 0`.

**Nothing else changes.** No threshold is loosened, no axis added, no mapping/parser/gloss/word-list altered, and
the v2 result — the halt — stands as recorded in the contradiction log.

## What this fixes and does not fix
- Fixes: an honest "this word does not account for this mapping" (score 0) is now expressible, so the independent
  judge no longer has to choose between inventing a false positive relationship and emitting an invalid token.
- Does not change: how *positive* resonance is scored, the opposition/resolution full-range convention, or any word.

## Gate sequence
`FROZEN`. Re-run the **same** fresh 20-word list under v2.1 (verify_inputs now pins the v2.1 prereg hash). The
runner's validator and judge prompt implement only this amendment.

## Provenance
Amends `VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md`; motivated by the Phase-3 contradiction log. No frozen mapping,
parser, gloss, word list, verdict band, or the independent two-model design was modified.
