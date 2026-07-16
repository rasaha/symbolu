# B1.12 V2 — Methodology Contradiction Log (run-time)

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`

Documented **separately** during Phase-3 execution, per the standing instruction: *"If genuine methodological
contradictions emerge during the run, document them separately, but do not modify the methodology during
execution."* **No frozen artifact (prereg, prompt, rubric, validator, mappings, word list) was modified. The run was
halted, not patched.**

## CONTRADICTION-1 — the relationship taxonomy cannot express "score 0 / no relationship"

### Where it surfaced
Run: V2 independent judge, model **Qwen/Qwen3-32B**, word **`jaṅghā`** (शङ्घा → "shank", the lower leg).
Aborted with `RUN_INVALID:judge_invalid:jaṅghā` after 3 identical retries (raw in `raw_all.jsonl`).

Qwen's 3 mapped consonants (j, ṅ, gh) carry **ego/affliction** mapping glosses:
- j → the inflated "I did / I control this" (ahaṃkāra as sole doership)
- ṅ → dambha / vanity (self displayed and performed for others)
- gh → mamatā / possessive "mine-ness"

Qwen judged, correctly and honestly, that the ordinary bare word "shank" (a leg bone) has **no defensible
relationship** to any of these; it scored all three components **`dbr_score: 0`** with adjudication *"No defensible
relationship without importing outside meaning."* — and set **`"relationship": "none"`**.

### Why this is a contradiction, not a model error or a bug
- The frozen DBR scale (VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md §1.2, embedded verbatim in the prompt) defines
  **`0 = no defensible relationship without importing outside meaning.`** So score 0 is not only permitted, it is the
  *prescribed* score for exactly this situation.
- The frozen relationship taxonomy is **ten strictly-positive accounting relationships** (embodiment,
  constitutive_property, characteristic_expression, implication, natural_consequence, generation, opposition,
  resolution, regulation, containment). Every component **must** carry one of these ("use ONLY these; do not
  invent"). **There is no member that means "no relationship."**
- Therefore a component that legitimately scores 0 has **no valid relationship value**. The model's only options are
  (a) invent a false positive relationship for something it just rated 0 (dishonest, and the whole point of the
  no-supplementation firewall is to prevent that), or (b) emit an out-of-taxonomy token such as `"none"` (honest,
  but fails validation as `invented_relationship`). Qwen chose the honest option; the validator — faithfully
  enforcing the frozen protocol — rejected it.

The harness is behaving exactly as frozen. The gap is in the **protocol**: `dbr_score = 0` and the mandatory
10-type relationship field are mutually unsatisfiable when a word genuinely does not account for its mapping.

### Scope / blast radius
This is **systemic, not a one-off.** The v2 word list deliberately contains concrete-object, animal, and body-part
words (per the frozen category quotas), whose consonants map to affliction/ego glosses. Any such word for which a
rigorous judge finds *no* relationship will hit the same wall. Expect it to recur across most of the
concrete/animal/body words (e.g. jaṅghā, kapāla, lalāṭa, cāpa, darpaṇa, kuṇḍala, mukura, kūrma, chāyā, …). The v1
author→scorer design masked this because authors tended to assert *some* loose positive relationship (which the
scorer then rated low); the v2 independent-judge design surfaces the honest "no relationship" directly.

### What was NOT done (discipline)
- The frozen prompt, rubric, validator, taxonomy, scale, mappings, and word list were **not** modified.
- No relationship label was added; `"none"` was **not** whitelisted; validation was **not** relaxed.
- The run was **halted** at the first occurrence rather than worked around. Qwen's first 11 words
  (akrodha, asūyā, audārya, bhrama, chāyā, cintā, cāpa, dama, darpaṇa, dhvani, dhṛti) validated and are in
  `raw_all.jsonl`; the judge output JSON was not written because the phase aborted.

### Resolution requires a maintainer decision (a methodology change → new freeze) — not taken here
Completing V2 requires resolving CONTRADICTION-1, which is a scoring-protocol change and therefore **out of scope
for "execute V2 exactly as written."** Options (documented, none implemented):
1. **Minimal amendment (v2.1 freeze):** add a single null relationship value (e.g. `no_relationship`) that is valid
   **only** when `dbr_score == 0`, and forbidden otherwise. Preserves the 10 positive types unchanged; simply lets
   score-0 be expressible. Re-freeze prereg + validator, re-run the same fresh 20-word list.
2. **Prompt-level instruction (v2.1 freeze):** instruct judges that when they would score 0, they must still name the
   *closest* relationship and set score 0 (relationship becomes descriptive-only at score 0). Risk: reintroduces a
   forced-positive-label the judge just rated 0, muddying relationship-agreement stats.
3. **Treat the block itself as the V2 finding** and do not run further: the independent-judge protocol, applied to a
   category-balanced list, is structurally unable to score honest non-relationships — a reportable limitation.

**Recommended:** Option 1 (minimal, honest, least-invasive) — but it is the maintainer's call, and it is a v2.1
methodology decision, not something to be done silently mid-run. Awaiting instruction. No further V2 execution until
the resolution is chosen and re-frozen.
