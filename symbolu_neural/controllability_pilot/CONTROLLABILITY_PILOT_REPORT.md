# Controllability Pilot — Report

**Final question:** *Does Symbol-U behave as a controllable conditioning code
better than matched controls?*

**Short answer (honest):** **No.** Symbol-U *can* act as a conditioning code — it
steers the intended axis above chance (proxy steer-acc **0.74** for `pse_meaning`
vs 0.33 chance). But it is **beaten by matched controls**: a meaningless **random**
per-axis code steers **better (0.94)**, and a **sentiment** code steers **better
(0.93)**. The specific Symbol-U **ontology is irrelevant** (a dimension-relabeling
scores identically, 0.74). With the more compact `vritti_mapper` code, Symbol-U
barely steers at all (**0.35 ≈ chance**). This is **vacuous controllability**: the
*act* of conditioning on any separable code does the steering; Symbol-U's content
is not what's driving it, and its low axis-separability makes it a *worse* switch
than a random one.

**All results are SMOKE-ONLY** (tiny from-scratch GRU LM; proxy evaluators; HF
blocked). They establish the pipeline and the relative ordering of arms, not
production quality. See §6 for the RunPod plan that would harden this.

---

## 1. Setup

- **Axes (semantic):** calm / active / heavy (sattva / rajas / tamas-like).
- **Generator:** 1-layer conditional GRU LM, trained from scratch on a 180-sentence
  smoke corpus, control code injected at every timestep. (HF download blocked, so
  no pretrained LM is available — fluency is smoke-level by construction.)
- **Arms:** base, symbolu, random, shuffled, sentiment, relabel, prompt (see README).
- **Evaluation (PROXY-ONLY):** held-out bag-of-words classifier (`clf`) + keyword
  lexicon scorer (`lex`); fluency = perplexity under the base model; `JSvsB` =
  unigram Jensen-Shannon divergence vs base (did output change?).
- **Reproduce:** `python -m symbolu_neural.controllability_pilot.cli run --u-backend pse_meaning`

## 2. The mechanism, measured first: axis-code separability

How distinct are the three per-axis codes each scheme provides? (mean normalized
pairwise L2; higher = easier for any model to use as a switch)

| code scheme | axis-code separation |
|---|---|
| `vritti_mapper` (Symbol-U) | **0.085** |
| `pse_resonance` (Symbol-U) | 0.150 |
| `pse_meaning` (Symbol-U) | **0.331** |
| `random` | **1.483** |

The Symbol-U codes for *semantically*-defined axes are nearly collinear, because
Symbol-U is **phonological** and the phonological profiles of calm-, active-, and
heavy-words are similar. A random code is ~4–17× more separable. **This single
table predicts every steering result below.**

## 3. Results — `pse_meaning` (richest Symbol-U code; 4 seeds × 8 prompts × 3 axes)

| arm | clf_acc | clf_sel | lex_acc | lex_sel | ppl | JSvsB |
|---|---|---|---|---|---|---|
| base | 0.333 | 0.000 | 0.333 | 0.000 | 7.0 | 0.000 |
| **symbolu** | **0.740** | 0.258 | 0.812 | 0.708 | 14.0 | 0.250 |
| relabel | 0.740 | 0.252 | 0.812 | 0.714 | 15.5 | 0.244 |
| random | **0.938** | 0.360 | 1.000 | 1.000 | 16.1 | 0.328 |
| shuffled | 0.708 | 0.232 | 0.760 | 0.641 | 12.4 | 0.217 |
| sentiment | **0.927** | 0.347 | 1.000 | 1.000 | 16.4 | 0.327 |
| prompt | 0.656 | 0.188 | 0.615 | 0.445 | 78.0 | 0.385 |

*(steer_acc: fraction of generations the proxy assigns to the target axis; chance
= 0.333. selectivity: on-target minus mean off-target probability.)*

## 4. Results — `vritti_mapper` (compact Symbol-U code)

| arm | clf_acc | clf_sel | lex_acc | ppl |
|---|---|---|---|---|
| base | 0.333 | 0.000 | 0.333 | 7.0 |
| **symbolu** | **0.354** | 0.011 | 0.354 | 8.7 |
| relabel | 0.375 | 0.029 | 0.385 | 11.3 |
| random | 0.938 | 0.360 | 1.000 | 16.1 |
| shuffled | 0.333 | −0.001 | 0.333 | 8.8 |
| sentiment | 0.927 | 0.347 | 1.000 | 16.4 |
| prompt | 0.656 | 0.188 | 0.615 | 78.0 |

With the low-separability vritti code, Symbol-U steering collapses to **chance**.

## 5. Direct answers to the evaluation questions

- **Does output change?** Yes — every conditioned arm diverges from base
  (`JSvsB` 0.22–0.39). Conditioning *does something*.
- **Does it move toward the intended direction?** *Partially, weakly, for
  `pse_meaning` (0.74); not for `vritti_mapper` (0.35).* Qualitatively the
  steering is **leaky and inconsistent** — e.g. with `pse_meaning` conditioned on
  *calm*: `"the smooth shore soothes"` (on-axis) but also `"they and weary the
  grave sinks"` (heavy leakage), and some prompts collapse to the same output
  across axes.
- **Does fluency degrade?** Mildly for conditional arms (ppl 14–16 vs base 7);
  badly for the `prompt` arm (ppl 78 — but that arm is unreliable here, see below).
  No repetition pathology (rep = 0.00).
- **Is steering consistent across prompts?** Moderate for the separable codes,
  poor for Symbol-U (low selectivity 0.26 vs random 0.36).
- **Is steering selective across axes?** Symbol-U selectivity (0.26) <
  random (0.36) and sentiment (0.35) — it leaks more across axes.
- **Does Symbol-U beat random / shuffled / sentiment / prompt controls?**
  - vs **random**: **NO** (0.74 < 0.94). The decisive negative — a meaningless
    code steers *better*.
  - vs **shuffled**: ~tie (0.74 vs 0.71). *Caveat:* the generator trains
    end-to-end on whatever (even shuffled) code↔axis pairing it is given, so a
    consistently-shuffled code is still a usable switch; this arm mainly confirms
    "any distinct code works," it does not isolate meaning. A stricter
    train-clean / test-shuffled mismatch is future work.
  - vs **sentiment** (known taxonomy): **NO** (0.74 < 0.93).
  - vs **prompt**: nominally yes (0.74 > 0.66), but **this comparison is not
    trustworthy here** — a tiny from-scratch LM cannot follow "calm" as an
    instruction, so prompting is unfairly handicapped (and its ppl is 78). On a
    real pretrained model, prompting is expected to dominate.
  - **Does the specific ontology matter?** **NO.** `relabel` (dimensions permuted)
    = `symbolu` to three decimals. The Vritti/Guna/Kosha labels are a basis choice
    the adapter is invariant to.

## 6. What this does and does not establish — and the RunPod plan

**Establishes (even at smoke scale):** the pilot pipeline works end-to-end; and
the *content* of the Symbol-U code is not what drives steering — separability is,
and Symbol-U's separability over *semantic* axes is low (phonological–semantic
misalignment), so it is dominated by a random code and a sentiment code, with its
ontology irrelevant. This matches the prior first-principles predictions
(vacuous controllability; ontology-arbitrary; phonological alignment).

**Does NOT establish (environment-limited):** anything about a *real* model's
fluency, or a *fair* natural-language-prompting comparison. Both need a pretrained
LM, which `huggingface.co`'s 403 block prevents here.

**RunPod hardening (exact):**

```bash
pip install torch transformers numpy
export PYTHONPATH=$(pwd)

# 1) Replace the from-scratch GRU with a FROZEN pretrained LM + small trained
#    adapter, keeping the 7 arms identical. Use real instruction prompts for the
#    `prompt` arm (e.g. "Write a calm sentence:"). Sketch:
python - <<'PY'
from transformers import AutoModelForCausalLM, AutoTokenizer  # e.g. gpt2 / Qwen2.5-0.5B
# freeze backbone; train a tiny FiLM/prefix adapter on (E, code); generate per arm;
# score with an LLM judge instead of the proxy classifier.
PY

# 2) Replace proxy evaluators with an LLM judge (axis rating 1-5 per output),
#    and add a human spot-check on 30 samples.
```

Pass condition unchanged: Symbol-U must beat **random**, **sentiment**, and
**real prompting** on a judge-confirmed axis, with the **specific ontology**
beating **relabel**. The smoke result already fails the first two and the
ontology test; the pretrained run is needed only to confirm it also loses to
prompting (expected) — i.e., to remove the one excuse this environment leaves open.

## 7. Verdict

Within the limits above, **Symbol-U does not behave as a controllable conditioning
code better than matched controls.** It is *a* code (steers above chance with the
richer `pse_meaning` variant), but a *worse* one than a random vector or a
sentiment vector, its ontology is a basis choice, and its weakness is explained by
phonological–semantic misalignment (low axis-code separability). The honest
recommendation is the one the framing reviews already implied: this is a
deflationary result reached by the controllability route, consistent with the
information route. A pretrained-model RunPod run can close the remaining
prompting caveat, but is unlikely to reverse the random/sentiment/ontology
findings, which are properties of the Symbol-U code itself, not of the generator.
