# Results — archetype RECOVERY re-run on the CORRECTED (retroflex) English mapping

> Same pre-registration and harness as `RESULTS_ARCHETYPE_RECOVERY.md`. The only change: the frozen
> English g2p → varṇa table was corrected so alveolar **stops/flap t d n → retroflex Ṭa/Ḍa/Ṇa** (Indian-
> English realization) and **dental fricatives** voiced *th* → dental **Da**, voiceless *th* → dental
> **ta** (the prior table had this inverted). This was set as a uniform rule before re-judging. Verdict
> computed by rule. Not a meaning claim; not part of C×R×S.

## Why this re-run exists
A reviewer (correctly) flagged that English stop /d/ was mapped to **dental Da** (Peevishness) while the
soft /ð/ in "the" was mapped to **retroflex Ḍa** — inverted vs how a Sanskrit-trained ear hears English.
After the fix, the readings are more faithful — e.g.:

| word | before | after |
|---|---|---|
| guide | … Da⁻ **Peevishness** ⤳ Patience | … **Ḍa⁻ Shyness ⤳ Fearlessness** |
| doctor | Da⁻ Peevishness … Ta … | **Ḍa⁻ Shyness ⤳ Fearlessness** … Ṭa … |
| the | Ḍa⁻ Shyness ⤳ Fearlessness | Da⁻ Peevishness ⤳ Patience |

The question: does a more faithful, frozen mapping let the real chain recover its archetype?

## Confirmatory arm — 9 blind LLM judges (3 per lexicon), forced choice, K = 6, chance = 0.167

| arm | recovery accuracy |
|---|---|
| chance | 0.167 |
| **real** | **0.211**  (95% CI 0.078 … 0.367) |
| scrambled | 0.233 |
| random-symbolic | 0.222 |

- accuracy(real) CI **includes chance** → not above guessing.
- **Δ_scr = real − scrambled = −0.022**  (95% CI −0.178 … +0.133) — real still trails the wrong-mapping control.
- **Δ_rnd = real − random = −0.011**  (95% CI −0.144 … +0.122) — CI includes 0.

### VERDICT: **NO_ARCHETYPE_RECOVERY_SIGNAL**

## Supporting arms

| judge | acc(real) | acc(scrambled) | acc(random) | verdict |
|---|---|---|---|---|
| **LLM** (9 blind judges) | 0.211 (CI 0.08–0.37) | 0.233 | 0.222 | **NO_ARCHETYPE_RECOVERY_SIGNAL** |
| random (null) | 0.167 (CI 0.03–0.30) | 0.197 | 0.170 | **NO_ARCHETYPE_RECOVERY_SIGNAL** |
| wordnet (deterministic) | _not re-run (CPU-prohibitive at S-controls in sandbox)_ | — | — | — |

The deterministic wordnet arm was not re-run on the corrected mapping: the Wu-Palmer similarity sweep over
30 words × ~41 control chains × 6 options exceeds the sandbox CPU budget (timed out at both S=20 and S=8).
It is non-gating. For reference, the **prior-mapping** wordnet arm (`RESULTS_ARCHETYPE_RECOVERY.md`) returned
accuracy(real) = 0.133 — **below** chance and below both controls — and the corrected-mapping confirmatory
(LLM) and null arms above both return NO_ARCHETYPE_RECOVERY_SIGNAL, so the verdict is not in doubt.

## Interpretation
The fix is the **right thing to do** for dialect faithfulness and is kept. But it did **not** change the
verdict — and this is expected, not disappointing: the scrambled control uses the *same corrected
segmentation*, so a better mapping only helps if **which sound carries which propensity** is what matters.
Four prior nulls already showed it isn't, and this fifth run confirms it on the improved mapping. Better
phonetics ≠ recoverable signal. The lens stays a consistent reflective mirror; the `phoneme_overreach`
firewall to C×R×S stands.

## Reproducibility
Corrected table is frozen in `varna_lens.py` (`_ARPA_C`). Re-run: `archetype_recovery_test.py --judge
random|wordnet`, or `--emit` for the blind LLM items. Picks + key archived in
`RESULTS_ARCHETYPE_RECOVERY_FIXED_LLM_PICKS.json`; `score_items(picks, key)` recomputes the verdict.
