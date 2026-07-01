# Pre-registration — archetype-alignment test

> Registered **before** any chain was judged. Verdict is computed by the rule below, not by hand.
> Interpretive lens — not a universal claim, not part of C×R×S.

## Hypothesis (the gap the two prior tests did not cover)
The acoustic chain does **not** recover a word's *dictionary* meaning (test 1, NO_SIGNAL) and a real
artifact is **not** more *useful* than a scrambled one (test 2, NO_UTILITY_SIGNAL). This test asks the
distinct, lower-resolution question: for **role/function words whose archetypal *transformation* is
clear**, does the **real** varṇa chain embody that transformation (FROM → TO) **better than** a
**scrambled** chain or a **random-symbolic** chain?

- **doctor**: suffering → healing. Not "identify the word *doctor*", but "does this propensity sequence
  fit *suffering → healing* better than controls?"

## Materials (frozen)
- **20 role words**, each with a pre-committed archetype `(FROM, TO)`, listed in `archetype_test.py`
  (`ARCHETYPES`). Committed in this file's commit **before** judging. Mix of positive transformations
  (doctor, teacher, healer) and negative ones (thief: security→loss; tyrant: freedom→oppression) so a
  judge cannot win by always choosing the "nicest" chain.
- **Segmentation:** English g2p (pronunciation), identical routing to the prior tests.
- **Chain rendering:** mechanical worldly-gloss chain (same `essence()` as `signal_test.py`) — a
  comma-separated propensity sequence, **no +/− signs, no ⤳ overlay** (so structure can't leak the
  answer). The same renderer is applied to all three lexicons.

## Three lexicons (per word)
1. **real** — the frozen Sanskrit lexicon (`varna_lens.CONS/VOW`, worldly glosses).
2. **scrambled** — the **same** propensity vocabulary, permuted among keys (consonant glosses among
   consonants, vowel glosses among vowels), one fixed seed. **This is the load-bearing control:** it
   preserves the vocabulary's richness and length; real can only beat it via the *specific*
   sound→propensity assignment.
3. **random** — content-free nonsense tokens (no semantic content). **This is only a floor:** nonsense
   cannot embody a transformation, so `real > random` is near-trivial and proves only that judges are
   doing the task.

## Judging (blind)
- Each word presents its three chains as **A/B/C in randomized order**; the judge is **never told which
  chain is real/scrambled/random**.
- Task: **rank** the three chains **1 (best) – 3 (worst)** by how well the propensity sequence embodies
  the word's **FROM → TO** transformation.
- **≥3 independent blind judges** (blind LLM sub-agents); per-word ranks averaged across judges.

## Metrics
- `mean_rank(lex)` = mean over words of the (judge-averaged) rank, 1 = best.
- `real_first_rate` = fraction of words where real's mean rank is strictly lowest (chance = 1/3).
- **Advantage** `adv = rank(control) − rank(real)` per word (positive ⇒ real is better). Paired
  **bootstrap 95% CI** (10 000 resamples) on `adv` for scrambled and for random.

## Verdict rule (pre-registered — ChatGPT's rule)
- **ARCHETYPE_SIGNAL_DETECTED** iff `mean_rank(real) < mean_rank(scrambled)` **and**
  `mean_rank(real) < mean_rank(random)`, **and** the bootstrap CI lower bound of **both** advantages
  `> 0`.
- **NO_ARCHETYPE_SIGNAL** iff the real-vs-**scrambled** advantage CI **contains 0** (real is
  indistinguishable from the permuted control — this *restates* NO_SIGNAL at the archetypal level:
  any rich propensity vocabulary fits archetypes via reader projection).
- **INCONCLUSIVE** otherwise.

## What each outcome would and would not license
- **SIGNAL_DETECTED** would license the claim: *the specific Sanskrit sound→propensity mapping carries
  archetypal (Sāttvic transformation) information beyond a permuted vocabulary.* It would **not** revive
  the dictionary-meaning claim (already falsified) — only the coarser transformation-fit claim.
- **NO_ARCHETYPE_SIGNAL** would settle that the archetypal reframing does not rescue the model: the
  aptness is reader-supplied at the archetype level too.

## Reproduce
```bash
python archetype_test.py emit  --out archetype_packet.json      # blind packet (+ hidden key)
# 3 blind judges rank A/B/C per word → j1.json j2.json j3.json  ({"<id>": {"A":r,"B":r,"C":r}})
python archetype_test.py score --packet archetype_packet.json --judges j1.json j2.json j3.json --out RESULTS_ARCHETYPE_SIGNAL.md
```
