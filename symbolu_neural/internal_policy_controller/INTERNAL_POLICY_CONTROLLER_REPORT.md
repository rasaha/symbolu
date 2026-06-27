# Internal Draft→Policy→Final-Answer Symbol-U Controller — Report

**Final question:** *Does an internal draft→policy→final-answer Symbol-U controller
work better than (1) direct token-level injection, (2) hidden-state modulation,
(3) external API control packet, and (4) generic self-refinement?*

**Short answer (honest):**
- It is the **best architectural fit** Symbol-U has had (sentence-level critic of a
  completed draft — the right granularity). Better *shape* than (1) and (2).
- But it **does not work better** on the bottom line. It **loses to generic
  self-refinement (4)** and is **crushed by a trivial sentiment critic**, because
  the bottleneck is **critic diagnostic accuracy** and Symbol-U — being
  phonological — can barely diagnose *semantic/pragmatic* draft flaws (0.333 vs
  0.200 chance; content critic 0.533; sentiment critic 1.000). The **ontology is
  irrelevant** (relabeled critic = Symbol-U critic exactly).

All generation/revision is **SMOKE-ONLY** (no pretrained LLM / API available
offline). The **critic diagnostic-accuracy** result, however, is assumption-light
(supervised, ground-truth flaw labels, held-out) — and it is the decisive finding.

---

## 1. Architecture reviewed

Draft→policy→final is a **critique-and-revise / self-refinement** loop (Self-Refine,
Reflexion, Constitutional AI's critique→revise) — **not** RLHF (no training, no
reward model). Its one structural advantage for Symbol-U: it evaluates a
**completed draft as a whole**, which is Symbol-U's native granularity (a property
of finished utterances, not token transitions or mid-stream hidden states). That
resolves the granularity mismatch that sank the internal-neural attempts.

**The catch (decisive):** standard self-refinement uses *the LLM itself* as critic
— which can read the draft's *meaning*. Replacing it with a Symbol-U critic that
reads *phonology* is a **downgrade in critic quality**. Right granularity, wrong
feature: the flaws a critic must catch (speculation, escalation, vagueness) are
semantic; Symbol-U measures sound.

## 2. What was built

Isolated prototype in `symbolu_neural/internal_policy_controller/` (no older file
touched; reuses only `complementarity_probe.backends` to compute a draft's
Symbol-U state). Pipeline: **draft → critic diagnoses flaw → emits policy →
SHARED rule-based reviser applies it → proxy evaluation.** The reviser is identical
across arms, so arm differences trace to **critic quality**.

- `drafts.py` — 15 clean base answers × {speculative, escalated, verbose, vague,
  none} = 75 labeled drafts (flaw = ground truth).
- `critics.py` — each arm = a featurizer + a small logistic-regression flaw
  classifier (fit on a train split). Featurizers: content BoW (generic),
  affect-lexicon (sentiment), Symbol-U/PSE state vector, shuffled, relabeled,
  random.
- `reviser.py` — shared deterministic text surgery (+ wired real-LLM reviser for
  the hardened run).
- `evaluator.py` — proxy metrics: residual flaw, improvement-over-draft, meaning
  preservation, directness.
- `pilot.py`, `cli.py`, tests (6 pass).

## 3. Arms

| # | arm | critic |
|---|---|---|
| 1 | `base` | none (final = draft) |
| 2 | `generic_refine` | content-reading critic (proxy for **LLM self-critique**) |
| 3 | `sentiment` | affect/style-lexicon critic |
| 4 | `random` | random-feature critic |
| 5 | `shuffled_symbolu` | Symbol-U state, draft↔state link broken |
| 6 | `relabeled_symbolu` | Symbol-U state, dimensions permuted (ontology relabel) |
| 7 | `symbolu` | real Symbol-U/PSE critic |

## 4. Metrics & Results (75 drafts, 30 held-out, seed 0)

| arm | diag_acc | residual_flaw ↓ | improvement ↑ | meaning_pres ↑ | directness |
|---|---|---|---|---|---|
| base | n/a | 0.101 | 0.000 | 0.626 | 0.968 |
| generic_refine | **0.533** | 0.030 | 0.071 | 0.680 | 1.000 |
| **sentiment** | **1.000** | **0.000** | **0.101** | **0.779** | 1.000 |
| random | 0.200 | 0.077 | 0.023 | 0.647 | 0.974 |
| shuffled_symbolu | 0.233 | 0.064 | 0.037 | 0.645 | 0.987 |
| relabeled_symbolu | 0.333 | 0.046 | 0.054 | 0.652 | 1.000 |
| **symbolu** | **0.333** | 0.046 | 0.054 | 0.652 | 1.000 |

*(diag_acc chance = 0.200; improvement = flaw_score(draft) − flaw_score(final).)*

## 5. Direct answers to the required questions

- **Does Symbol-U improve the final answer beyond generic refinement?** **No.**
  Symbol-U improvement 0.054 < generic 0.071 < sentiment 0.101. Its critic
  misdiagnoses (0.333), so the shared reviser applies the wrong fix and the flaw
  largely survives.
- **Does Symbol-U beat the required controls?**
  - vs **generic self-refinement**: **NO** (diag 0.333 < 0.533; improve 0.054 < 0.071).
  - vs **sentiment/style critic**: **NO**, decisively (0.333 < 1.000; 0.054 < 0.101).
    The flaws are affect/style markers a sentiment critic reads perfectly.
  - vs **random** (0.200) / **shuffled** (0.233): **slightly above** — Symbol-U
    carries a faint sliver of signal, but it is marginal and near chance.
  - vs **relabeled**: **tie to 3 decimals** — the specific ontology is a basis
    choice the linear critic is invariant to. **Ontology does not matter.**
- **Does the ontology matter?** **No** (relabeled = symbolu exactly).
- **Is this more promising than direct token-level control?** As an *architecture*,
  yes (right granularity, interpretable policy, no training). As a *result*, no —
  it lands in the same place (ontology irrelevant; beaten by simpler baselines),
  and it adds a critic-diagnosis step whose low accuracy is the new bottleneck.

## 6. The four-way final comparison

| compared to | architecture fit | bottom-line result |
|---|---|---|
| (1) token-level injection | **better** (sentence-level, no per-token surgery) | same: ontology irrelevant, beaten by controls |
| (2) hidden-state modulation | **better** (black-box, interpretable, no training) | same |
| (3) external API packet | ~equivalent (both critique/control via text) | same; adds a 2× generation cost (draft+final) |
| (4) generic self-refinement | this *is* self-refinement, with a weaker critic | **worse** — loses to LLM-self-critique and to a sentiment critic |

**So:** the draft→policy→final framing is the **most defensible architectural home**
for Symbol-U, but it **does not work better than generic self-refinement** — it
works worse, because a phonological critic cannot diagnose semantic flaws, and the
ontology contributes nothing.

## 7. Honest limitations

- **Smoke-only generation/revision:** no pretrained LLM or API offline, so the
  reviser is rule-based and the evaluators are proxies (lexicon-based). Small N
  (75 drafts, single seed).
- **The diagnostic-accuracy result is the trustworthy part** (supervised,
  ground-truth labels, held-out) — and it is decisive and unlikely to reverse.
- **A real LLM would make Symbol-U look *worse*, not better:** real
  LLM-self-critique (the true "generic self-refinement" baseline) is far stronger
  than the content-BoW proxy used here, widening the gap Symbol-U already loses.
- Flaws here are injected with lexical markers (favorable to the lexicon critics);
  but Symbol-U's failure is *diagnostic* (it can't read the flaw at all), which a
  subtler flaw set would not fix.

## 8. Hardened run (needs a real LLM; not available in this sandbox)

```bash
export PYTHONPATH=$(pwd)
export ANTHROPIC_API_KEY=...        # or MISTRAL_API_KEY
# swap the rule-based reviser for reviser.LLMReviser(backend=...) and replace the
# proxy evaluator with an LLM judge (clarity/caution/escalation/preference 1-5);
# keep all 7 arms. Real generic_refine = the LLM critiquing its own draft.
python -m symbolu_neural.internal_policy_controller.cli run
```
Pass condition (pre-registered): Symbol-U critic must beat generic self-refinement
AND sentiment AND random/shuffled, with the **specific ontology** beating
relabeled, on a judge-confirmed metric. The smoke run already fails the first two
and the ontology test.

## 9. Final verdict

The internal draft→policy→final controller is the **right architecture** for a
sentence-level signal and the cleanest place Symbol-U could live — but it is **not**
more effective than generic self-refinement, and the ontology is inert. The
bottleneck it exposes is fundamental and consistent with every prior pilot: a
deterministic **phonological** signal cannot judge **semantic** properties, so as a
critic it is dominated by any content-reading or affect-reading baseline. Use
ordinary self-refinement (the LLM as its own critic); Symbol-U adds latency and an
ontology that does no work.
