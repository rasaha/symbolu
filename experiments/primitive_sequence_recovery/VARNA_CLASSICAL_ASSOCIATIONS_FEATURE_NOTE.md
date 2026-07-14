# Classical-Association Feature Note (design-only; no model, no lift)

**Design/preregistration-hypothesis note only.** No model run, no feature computed, no lift measured, no
comparison to the frozen V1 lift study. Assesses whether the extracted classical-association layer
(`varna_classical_associations_33.json`) *could* support auxiliary feature families in a **separate, future,
separately-preregistered** study. `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

## Source of the layer

Extracted read-only from the corrected v3.1 polarity table joined to the frozen merged lexicon
(`varna_classical_associations_33.json`, sha256 `354656c2…`). Explicit-only: tattva/guṇa/deity are recorded only
where the source states them; otherwise `MISSING`. No inference.

## Coverage over the 33 confirmatory consonants

| Layer | Count | Consonants | Status |
|---|---|---|---|
| **guṇa** | 3 | `ś`=tamas, `ṣ`=rajas, `s`=sattva | ATTESTED (primary text; ś/ṣ swap RESOLVED) |
| **tattva** | 5 | `y`=vāyu/air, `r`=agni/fire, `l`=kṣiti/earth, `v`=jala/water, `h`=ākāśa/ether | ATTESTED (pañca-mahābhūta bīja set) |
| **deity** | 1 | `v`=Varuṇa | ATTESTED |
| no classical field | 6 | `c, ch, j, ṇ, th, d` | MISSING |

**The critical fact for feature design: guṇa and tattva are extremely sparse** — 3/33 and 5/33 consonants carry
them. They are *not* a per-varṇa layer; they are properties of a small, specific subset (the three sibilants; the
five semivowel/ha bhūta-roots). Any feature built on them is mostly-missing by construction.

## Proposed auxiliary feature families

For a word `w` with consonant multiset (order-free, multiplicity preserved — matching the frozen convention):

| Feature | Dimensional representation | Missingness | Expected relation to A/V/D | Circularity risk | Source-backed? | Tier |
|---|---|---|---|---|---|---|
| **guṇa feature** | 3-dim count/fraction over {sattva, rajas, tamas} from `s`/`ṣ`/`ś` occurrences | **High** — non-zero only for words containing s/ṣ/ś; most words all-zero | **Arousal**: rajas→higher, tamas→lower, sattva→moderate (hypothesis). Weak V/D prior | **Low** — guṇa labels are independent of Warriner English affect norms; no shared source | **Yes** (primary text) | **Primary** (for arousal), *conditioned on coverage* |
| **tattva feature** | 5-dim indicator/count over {air, fire, earth, water, ether} from `y`/`r`/`l`/`v`/`h` | **High** — non-zero only for words with those 5 consonants | Diffuse; fire/air *might* track higher arousal, earth/water lower — weaker, less principled than guṇa | Low | Yes (primary text) | **Exploratory** |
| **guṇa+tattva combined** | 8-dim concatenation | High (union of the two supports) | As above; mild interaction possible | Low | Yes | **Secondary** |
| **binding-gloss feature** (the existing V1 feature) | pooled gloss embedding (768-d) | Low — every consonant has a binding gloss | Already under test in frozen V1 | Low (independent norms) | Yes | **(already primary in V1; do not re-run here)** |
| **all-metadata feature** | binding-gloss embedding ⊕ guṇa ⊕ tattva ⊕ (deity indicator) | Mixed | Superset; hardest to attribute | **Higher** — many correlated dims invite overfitting/attribution ambiguity on a small N | Partly | **Exploratory only** |

## The arousal hypothesis (preregistration hypothesis, NOT a fact)

The guṇa→activation mapping is the single most principled, source-backed, low-circularity bet:

> **H_guṇa (to be preregistered separately).** On held-out data, a 3-dim guṇa feature adds incremental signal to
> **arousal** prediction beyond a base representation and beyond a shuffled-guṇa control, with the directional
> pattern **rajas (`ṣ`) → higher activation**, **tamas (`ś`) → lower activation / inertia**, **sattva (`s`) →
> moderate/balanced**.

This is a hypothesis motivated by the sattva/rajas/tamas = sentient/mutative/static semantics, **not** an
established relation. It must be tested, not assumed — and it is directional, so the sign pattern is part of the
prediction, not a post-hoc reading.

**Coverage caveat that could sink it:** because only `s`/`ṣ`/`ś` carry guṇa, a large share of words will have an
all-zero guṇa vector, so effective N is the sibilant-bearing subset. The separate study must report guṇa-coverage
of its word list up front and power the test on the covered subset, or the null will be uninformative.

## Mandatory separation from the frozen V1 lift study

- The existing `VARNA_FEATURE_LIFT_PREREG_V1.md` and its frozen **88-word** dataset test the **binding-gloss**
  feature. **They are not modified, not re-run, and not reinterpreted here.**
- Any guṇa/tattva experiment must be **separately versioned**, **separately preregistered**, evaluated on
  **held-out** data, and compared against **shuffled** (permuted guṇa/tattva assignment) and **no-feature**
  controls — the same ablation discipline as V1.
- The classical-association layer must **not** be used to reinterpret, rescue, or re-explain any V1 outcome. It is
  a **new feature family**, adjudicated on its own held-out lift or not at all.

## Recommendation

**Most promising source-backed family: the 3-dim guṇa feature, targeted at arousal**, as a *separate* preregistered
study — because it is primary-text-attested, low-circularity, directional, and cheap. Tattva is a reasonable
exploratory add-on; the all-metadata feature is exploratory-only (attribution/overfitting risk on small N). The
first gate for any of these is a **coverage report** on the chosen word list, since guṇa/tattva are sparse by
construction.

## Guardrails
Design-only; no model, no feature, no lift, no V1 modification or reinterpretation. Any classical-association
experiment is a new, separately-frozen study with shuffled + no-feature controls on held-out data. Structure, not
validated meaning.
