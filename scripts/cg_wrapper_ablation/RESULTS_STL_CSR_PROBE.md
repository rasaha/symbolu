# Static CSR = Context × Semantic × Resonance — RESULT (filled)

> Closeout of the static CSR probe (`docs/STL_CSR_REFACTOR_PLAN.md`). Numbers from
> `runs/bhava_probe/20260621T020740Z_csr/`. Representation/probe track; generation path already parked.

## Setup (confirmed available)
Active-CG checkpoint contained the trained token-scorer Context (`conscious_gen.token_cache._csr_scorer.context_proj`) + `R_tok`. Sanskrit Varna pipeline loaded (46 varṇas, affinity table for 32,768 tokens, 80.6 % Sanskrit-mapped, CMUdict + g2p_en). All CSR components extracted (none faked).

## correctness (n=170; pos=49, neg=121)

| Feature | AUROC | CI | decodable |
|---------|------:|----|:---------:|
| **resonance_combined** | **0.832** | [0.755, 0.903] | yes (single best) |
| state_32d | 0.828 | [0.745, 0.902] | yes |
| state_bhava | 0.818 | [0.736, 0.892] | yes |
| phoneme_bhava / vritti_consonant† | 0.813 | [0.734, 0.886] | yes |
| semantic (input emb.) | 0.783 | [0.701, 0.856] | yes |
| **hidden_only** | 0.777 | [0.690, 0.861] | yes |
| context_r_ctx | 0.738 | [0.641, 0.822] | yes |
| **csr_static (C+S+R)** | 0.778 | [0.697, 0.853] | yes (≤ resonance alone) |
| hidden_plus_csr | 0.736 | [0.650, 0.815] | yes (< hidden) |
| hidden_plus_state_bhava_plus_csr | 0.790 | [0.716, 0.859] | yes (≈ hidden, ns) |

† phoneme_bhava and vritti_consonant came out **identical** — likely a degenerate vowel/consonant
split in extraction. `resonance_combined` (independent varna affinity) is the authoritative Resonance
feature; the split rows are not over-read.

CSR decision answers: state_bhava decodable ✔, resonance ✔, context ✔, semantic ✔;
**CSR beats its parts: �’No’**, CSR adds to state_bhava: No, hidden+state_bhava+CSR beats hidden: No.

## DECISION: `CSR_REDUNDANT` → **PARK_CSR**

Every part decodes correctness, but the **combination adds nothing** over the best part, and **CSR
adds nothing over hidden** (`hidden+csr` 0.736 < hidden 0.777; full 0.790 ≈ hidden, ns). No
complementary signal → park.

### Honest interpretation
- **Resonance decodes correctness (0.832, even best)** — but it is **text-derived**, so this is the
  Sanskrit-phoneme statistics tracking **problem difficulty** (a surface confound), not the phoneme
  structure carrying meaning. The decisive test (adds over hidden) **fails**: the hidden state already
  captures the difficulty signal. This is exactly the redundancy the probe was built to detect.
- The C × S × R decomposition is **redundant**: parts are individually decodable (all correlate with
  difficulty) but carry no joint signal beyond hidden.

## Per-example traces (`inspect_bhava_csr_sample.py`) — three mechanistic findings

Sampling top-correct / top-incorrect / csr-dilutes on the same run sharpens the verdict:

1. **State-Bhava has collapsed to a constant.** All 170 examples — correct, incorrect, clean,
   garbage — have dominant **WIT (idx 8) at 0.988–0.996**, entropy 0.02–0.09. The learned 12D Bhava
   slice is pinned to WITNESS for everything; its only per-example variance is the entropy wiggle
   (0.02 on clean templates vs ~0.08 on the `5-2`/`2*4` templates). Its 0.818 AUROC is therefore an
   **entropy-as-template-ID proxy**, not ontological content — consistent with the inert wrapper
   (`ACTIVE_NO_EFFECT`): the state never moved, so its Bhava never differentiated.

2. **Phoneme-Bhava / Vritti are template fingerprints, not per-example signal.** Every
   `"Sam has X apples and buys Y more"` prompt yields the *identical* phoneme-Bhava (`a`-dominant) and
   *identical* Vritti ("Blind attachment"); the `"box of pens"` family shares a different identical
   vector (`e`-dominant); `"What is 5-2"` a third. They are deterministic functions of template
   wording — their decode-ability is pure template-clustering (= difficulty proxy). This is also why
   the phoneme/vritti split came out degenerate: both are template-constant.

3. **The static `semantic` component is the *worst* predictor and *dominates* `csr_static`.** On the
   garbage-output cases (corr88/84/82 — model emits "Not Rated Yet / Based on 0 answers", gold=incorrect):
   hidden (0.00–0.11), resonance (0.09–0.17) and state_bhava (0.25–0.37) all correctly say *incorrect*,
   but **semantic = 1.00** and **csr_static = 0.85–0.99** (confident-wrong). Every "CSR dilutes" flag
   fires this way, with the viewer's note *"csr_static agrees with semantic but not state_bhava"*.
   Because `csr_static` is an **additive concatenation** through logistic regression, it cannot express
   a multiplicative veto and instead lets its loudest component (semantic) override the others.

### Scope note — this probe did NOT test the C × R × S match-filter

The intended CSR is a **conditional `(word, candidate-meaning)` compatibility gate**:
`MATCH = C × R × S` (multiplicative veto), where **C** = phonemic layer-allowance, **R** = phonemic
realization into a **12D ontological profile**, and **S** = a **non-phonemic** firewall that derives
semantic traits from the realized 12D structure and matches them against an **external domain
template** (dominant gate). The static probe tested none of this:
- features are per-example, with **no candidate-meaning / domain axis** to match against;
- `csr_static` is **additive**, so the multiplicative veto is structurally inexpressible;
- the `semantic` feature was pooled prompt-input embeddings — **no domain templates, no realized-12D
  input, no veto** — and it behaves as an *anti-signal* (systematic false-accepts on garbage outputs),
  the exact opposite of S-as-firewall.

So the `CSR_REDUNDANT` / PARK verdict applies to the **static decomposition**, not to the match-filter
hypothesis, which **remains untested**. A faithful test needs a separate pairwise instrument
(`word × candidate-domain → C·R·S product` with accept/veto labels and external domain templates).
**Deferred** — recorded here, not scheduled.

### One methodological cap on the whole static track
All probe features are extracted from the **prompt**, while the label is the correctness of a
**separately generated continuation**. The static probe is therefore a *difficulty-prediction* task
("will the model fail this prompt?"), not output evaluation — which is why hidden/resonance "work"
(they encode prompt difficulty) and is precisely the text-difficulty confound noted above.

## CG / STL / CSR track — combined verdict: **PARK** (all questions negative)

| Question | Result |
|----------|--------|
| Wrapper improves generation? | `ACTIVE_NO_EFFECT` (B≈C, ΔBhava=0) — parked |
| state-Bhava unique signal? | `BHAVA_WEAK_SIGNAL` — decodable but redundant with hidden |
| CSR = Context×Semantic×Resonance complementary? | `CSR_REDUNDANT` — parts decode, combination redundant with hidden |

## Known limitations / what could still be explored (separate, pre-registered)
- Resonance's apparent signal is a text-difficulty confound; a cleaner test would control for prompt
  length/surface statistics, but the redundancy-with-hidden result already settles "no complementary
  signal."
- The phoneme/vritti split was degenerate — fix only matters if the vowel-vs-consonant breakdown is of
  independent interest; it does not affect the verdict.
- STL (Signal→Transformation→Laya, temporal) remains deferred and untested.
- Probe = correlation; generation path parked, so nothing here revives the wrapper.
