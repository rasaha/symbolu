# Results — archetype-alignment test

- role words N = 20  ·  blind judges = 3  ·  metric = mean rank 1(best)–3(worst)  ·  real-first chance = 0.333
- **mean rank(real) = 2.133**  ·  mean rank(scrambled) = 2.567  ·  mean rank(random) = 1.300
- real ranked #1 rate = 0.150  (chance 0.333)
- **real vs scrambled advantage = +0.433**  (95% CI +0.000 … +0.850)  ← LOAD-BEARING
- real vs random advantage = -0.833  (95% CI -1.267 … -0.350)  (floor)

## VERDICT: **INCONCLUSIVE**

| word | rank(real) | rank(scrambled) | rank(random) |
|---|---|---|---|
| doctor | 3.00 | 2.00 | 1.00 |
| teacher | 2.67 | 2.33 | 1.00 |
| judge | 2.00 | 3.00 | 1.00 |
| warrior | 2.00 | 3.00 | 1.00 |
| mother | 2.00 | 3.00 | 1.00 |
| monk | 3.00 | 1.67 | 1.33 |
| king | 1.00 | 3.00 | 2.00 |
| artist | 3.00 | 2.00 | 1.00 |
| farmer | 2.33 | 2.67 | 1.00 |
| priest | 2.33 | 2.67 | 1.00 |
| healer | 2.00 | 3.00 | 1.00 |
| guardian | 2.00 | 3.00 | 1.00 |
| leader | 2.00 | 3.00 | 1.00 |
| thief | 1.00 | 2.67 | 2.33 |
| tyrant | 2.00 | 1.00 | 3.00 |
| nurse | 2.00 | 3.00 | 1.00 |
| builder | 2.00 | 3.00 | 1.00 |
| hunter | 2.67 | 2.33 | 1.00 |
| sage | 1.00 | 2.67 | 2.33 |
| servant | 2.67 | 2.33 | 1.00 |

_Pre-registered (PREREG_ARCHETYPE_SIGNAL.md). Verdict computed by rule, not by hand. Load-bearing comparison is real vs scrambled; random is a floor. Interpretive lens — not part of C×R×S._

## Interpretation

**Headline: the pre-registered `ARCHETYPE_SIGNAL_DETECTED` condition is clearly NOT met.** It required
`real` to beat **both** controls with CI lower bound > 0. Instead:

### 1. The "random floor" inverted into a ceiling — the most important finding.
The content-free nonsense chains were ranked **best** (mean rank **1.30**), while the real chain came in
the **middle** (2.13) and scrambled **worst** (2.57). Real ranked #1 on only **15%** of words — *below*
the 33% chance rate. This is not noise; it is a mechanism:

> When you ask "does this propensity sequence embody *suffering → healing*?", a **meaningful** chain
> (real *or* scrambled) can be seen to **actively clash** with the transformation, and gets penalised.
> A **nonsense** chain (`miti, polo, cumo`) has no semantic content to contradict the archetype, so
> judges find no disconfirming evidence and score it as the *cleanest fit*. Opacity beats content.

So the archetype-fit judgment is dominated by *absence of contradiction*, not presence of aptness — a
direct, quantified demonstration of **reader-supplied aptness** (the same failure mode as the two prior
tests), now visible as "the blank screen wins."

### 2. The flagship example goes the wrong way.
On **doctor** (*suffering → healing*, ChatGPT's motivating case) the **real** chain was judged the
**worst** of the three (rank 3.00), behind both scrambled (2.00) and nonsense (1.00). The intuition that
the real varṇa chain especially embodies *suffering → healing* is not borne out — it is the least apt.

### 3. Real vs scrambled (the load-bearing comparison) is a borderline wash.
Real edged scrambled by **+0.43** rank (real better on 11 words, worse on 9), but the 95% CI is
**+0.000 … +0.850** — the lower bound sits **on zero**, so it does **not** clear the pre-registered bar
and is within noise. This is the same result as the prior tests, restated at the archetypal level:
**the real sound→propensity assignment is not distinguishable from a permuted one** for fitting
transformation archetypes. (The tiny edge, if anything real, is far too small and too fragile to build on
— and it is dwarfed by the fact that *nonsense beat both*.)

## Verdict (settled reading)
**No archetypal Sattvic signal.** The frozen rule returns **INCONCLUSIVE** only because the real-vs-
scrambled CI lower bound grazes zero rather than dipping below it; every other axis is decisive against
the hypothesis — real is **worse than opaque nonsense**, real is picked best **below chance**, and the
flagship case inverts. ChatGPT's proposed gap does **not** rescue the model: the archetype reframing
inherits the same reader-supplied-aptness confound and, if anything, exposes it more starkly (opacity
outscores the real lexicon). The archetype-fit metric itself is confounded by the nonsense-ceiling effect,
so it cannot be used to *support* the model even in principle without redesign.

**Limitation / honest caveat:** the random control did not function as intended (it became a ceiling, not
a floor), which is itself the finding. A cleaner follow-up would replace nonsense with *semantically real
but archetype-mismatched* propensities — but that is essentially what the **scrambled** control already
is, and real does not beat it. So the redesign would not change the conclusion.
