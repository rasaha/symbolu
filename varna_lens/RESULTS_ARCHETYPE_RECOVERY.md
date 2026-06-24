# Results — archetype RECOVERY (forced-choice "absolute match") test

> Pre-registration: `PREREG_ARCHETYPE_RECOVERY.md`. Verdict computed by the registered rule, not by
> hand. This is the **strict** re-test requested after the soft-rating archetype test
> (`RESULTS_ARCHETYPE_SIGNAL.md`, NO_ARCHETYPE_SIGNAL): a soft 1–5 fit rating lets a reader project a
> fit onto any chain, so here the judge must **pick the one correct archetype from a lineup** — a
> definite right/wrong answer projection can't rescue. Not a meaning claim; not part of C×R×S.

## Design
30 role words; for each, **K = 6** archetype options (correct + 5 decoys, fixed before judging). A blind
judge sees only a chain and the 6 options and must pick which transformation it traces. **chance =
1/6 ≈ 0.167.** Chains generated under three lexicons — **real**, **scrambled** (same vocabulary, wrong
sound→propensity attachment), **random-symbolic** (neutral nouns). Detection required real to beat
**chance and both controls**, CIs clear of the line.

## Confirmatory arm — blind LLM judges (3 per lexicon, each answering all 30)

| arm | recovery accuracy |
|---|---|
| chance | 0.167 |
| **real** | **0.233**  (95% CI 0.111 … 0.378) |
| scrambled | 0.300 |
| random-symbolic | 0.200 |

- accuracy(real) CI **includes chance** → real is **not** above guessing.
- **Δ_scr = real − scrambled = −0.067**  (95% CI −0.211 … +0.078) — real is, if anything, **worse**
  than the wrong-mapping control.
- **Δ_rnd = real − random = +0.033**  (95% CI −0.067 … +0.144) — CI includes 0.

### VERDICT: **NO_ARCHETYPE_RECOVERY_SIGNAL**

Real fails every clause of the rule: not above chance, does not beat scrambled (it trails it), does not
beat random. The "absolute match" intuition is not borne out — the real chain does not point to its own
archetype any better than a scrambled or neutral one.

## Supporting arms

| judge | acc(real) | acc(scrambled) | acc(random) | verdict |
|---|---|---|---|---|
| **LLM** (9 blind judges) | 0.233 (CI 0.11–0.38) | 0.300 | 0.200 | **NO_ARCHETYPE_RECOVERY_SIGNAL** |
| random (null) | 0.167 (CI 0.03–0.30) | 0.197 | 0.170 | **NO_ARCHETYPE_RECOVERY_SIGNAL** |
| wordnet (deterministic) | _(re-runnable via `--judge wordnet`; CPU-heavy)_ | | | _expected NO_ARCHETYPE_RECOVERY_SIGNAL_ |

The random-null arm lands exactly at chance (0.167), confirming the pipeline is unbiased.

## Why the stricter test makes the result *cleaner*, not weaker

The soft-rating test could be dismissed as "judges are too generous." This forced-choice test removes
that: there is one right answer per item. Result — when the judge *must commit*, the real lexicon
gives **no advantage at all**, and even loses to the scrambled control. Tightening the task did not
surface a hidden signal; it removed the only thing (reader generosity) that had let real look non-zero
before. That is the signature of *no signal*, not of a signal we were measuring badly.

Note the real chains were genuinely informative-looking and judges reasoned carefully about them — they
just weren't pointing at the right archetypes any more often than wrong-mapping chains were. That is
exactly "reader-supplied aptness."

## Interpretation (binding, per prereg)

**NO_ARCHETYPE_RECOVERY_SIGNAL.** This is now the **fourth** independent pre-registered null
(lexical meaning, utility, archetype-fit, archetype-recovery). The specific sound→propensity attachment
carries no recoverable archetypal signal under a strict absolute-match task either. Varṇa Lens stays a
consistent symbolic mirror for reflection; its value is reader-supplied, not veridical. The
`phoneme_overreach` firewall to C×R×S stands.

## Reproducibility
Fixed seeds (`BASE_SEED = 20240624`, K = 6, S = 20). `--judge random` / `--judge wordnet` are CPU
deterministic; `--emit real|scrambled|random` produces the blind items; the 9 judge pick-sheets + the
answer key are archived in `RESULTS_ARCHETYPE_RECOVERY_LLM_PICKS.json`, and
`archetype_recovery_test.score_items(picks, key)` recomputes the verdict.
