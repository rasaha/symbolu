# B1.12 — Development Log (pre-evidence-freeze; auditable)

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. B1.12 remains open to separately-versioned
experimentation before any future confirmatory evidence freeze. This log records the G0 audit v1 iteration.
**No threshold change is proposed or implemented in this commit.**

---

## Iteration: G0 structural audit v1 (auditor role)

- **Date context:** follows curator pool-freeze `d50fbb9`.
- **Frozen configuration used (unchanged):** prereg `2c613f4` + V1.1 `6f197fd` + V1.2 `7935f48`; pool sha256
  `8cf857…d296d0b4`; parser `PARSER_SPEC_v1` sha256 `d885391f…721947`. Contract: `k=6`, band `[2,6]`,
  `τ_edit=0.34`, `s(x)≥0.34`, endpoint `≤3`, bigram `≤0.50`, trigram `≤0.34`, span `≤2`, objective max-min
  `d_edit`, tie-breaks a→d. Opaque-ID identity = `(type,unit)`; map sha256 `7f6e6f8f…29b300b` (32 identities).
- **Metrics inspected:** per-word `s(x)`, length; pairwise `d_edit`, `d_ord|inv`, LCS ratio, positional overlap,
  multiset Jaccard, repetition-profile distance, abs length diff, first/last-unit match, bigram/trigram Jaccard,
  unique bigram/trigram counts; subset-level endpoint multiplicity, length span, constraint survival counts.
- **G0 outcome:** **`G0_PASS`** — 178,234 of 1,623,160 size-6 subsets satisfy all frozen hard constraints;
  selected subset `{asthi, grīvā, jñāna, keśa, nadī, sūrya}` with min pairwise `d_edit = 0.80`.
- **Failed / binding constraints (observed, not acted on):**
  - **Endpoint no-majority is the dominant bottleneck** — independently satisfied by only 186,718/1.62M subsets;
    first-eliminator for 1,243,569. Cause: most pool words are consonant-initial and inherent-`a`-final, so
    first/last opaque identities cluster.
  - Edit-floor second (199,960 first-eliminations); length-span minor (1,397); bigram/trigram never binding.
- **Observations that MAY motivate later versioned exploratory work (NOT changes now):**
  1. **Between-word order-specific signal is sparse in this pool** — 444/595 pairs have `d_ord|inv = 0` (75%),
     mean 0.069. Short attested words differ mostly by *inventory*, not *order*. A future H2 instrument should
     not assume abundant pairwise order separability; the per-word A-vs-D / A-vs-B contrast carries the design.
     A later pool emphasizing longer forms and shared-inventory near-anagrams could raise pairwise order signal —
     this would be a **new versioned pool**, never a retrofit of pool v1.
  2. **Endpoint clustering** (consonant-initial / `a`-final) is a structural property of short Sanskrit nouns;
     if a future study wants a less endpoint-bound selection space, that is a candidate-pool design question for a
     new version, not a G0 threshold change.
  3. All 35 words passed `s(x) ≥ 0.34` comfortably (min 0.40) — the self-order floor was not a limiting factor
     here; no evidence it needs revisiting.
- **Preservation rule:** this `G0_PASS` result stands. Any later exploratory revision (alternate thresholds,
  broader pool, longer words) must be a **new version**, reported alongside — never overwriting — this outcome,
  and never called confirmatory evidence.
