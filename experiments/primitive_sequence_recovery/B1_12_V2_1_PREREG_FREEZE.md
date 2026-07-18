# B1.12 V2.1 Preregistration — FREEZE RECORD

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`

**Frozen file:** `VARNA_SYMBOLIC_RESONANCE_PREREG_V2_1.md`
**SHA-256:** `1c89584de2f0b89883a7f8276f5176256fe6eb528df7c60dd09b31781178724f`
**Incorporates by reference:** `VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md` (SHA `831e48ecc409140f64a943c0331242043424045c703d01be1cd4c55dcfb59550`) in full.
**Status:** FROZEN. Controlling for V2.1 execution on the same fresh 20-word list
(`b1_12_symbolic_resonance_wordlist_v2/`, SHA `7a558008a22151a48f7770790bbfb01cdef190b64d3ae6feb8677b0b360457b4`).

## The single amendment (CONTRADICTION-1 resolution)
Adds exactly one relationship value `no_relationship`, VALID ONLY when `dbr_score == 0` and forbidden at any
non-zero score. The ten positive relationships, the DBR scale, the no-supplementation firewall, the polarity-neutral
opposition/resolution convention, aggregation, verdict bands, mappings, parser, and the fresh 20-word list are ALL
unchanged. Honest score-0 synonyms (none/no/n-a/no relation/null/nil) are canonicalized to `no_relationship`
(logged), accepted only at score 0.

## Runner implementation of the amendment (b1_12_bsr_v2_runner/)
- `bsr_rubric.py`: `NULL_RELATIONSHIP="no_relationship"`; `validate_judge` accepts it iff dbr_score==0 (reason
  `no_relationship_requires_zero` otherwise); `canonicalize_relationship` maps null-synonyms to it.
- `prompts.py`: judge prompt states the score-0-only rule.
- `verify_inputs.py`: controlling prereg pinned to this v2.1 file's hash.

## Discipline
No threshold loosened, no axis added, no mapping/parser/gloss/word-list altered. The v2 halt stands as recorded in
`results/b1_12_symbolic_resonance_v2/B1_12_V2_METHODOLOGY_CONTRADICTION_LOG.md`.
