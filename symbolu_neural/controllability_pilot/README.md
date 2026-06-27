# Symbol-U Controllability Pilot (experimental / isolated)

**Status: EXPERIMENTAL, SMOKE-LEVEL.** A small pilot, not a full study. It tests
whether Symbol-U can *steer* generation, not whether it adds information.

## Framing (frozen — not re-litigated here)

> **Symbol-U = a deterministic, open-loop feedforward conditioning code.**
> The goal is **controllability** (steer tone / affect / style / energy / delivery
> along intended axes), **not** semantic information addition.

The base Transformer is responsible for language; Symbol-U is (at most) a control
input. The question: **does conditioning on Symbol-U steer outputs toward an
intended axis better than matched controls?**

## The honest test design

- **Axes are defined SEMANTICALLY** — `calm` / `active` / `heavy`
  (sattva / rajas / tamas-like). Deliberate: if the axis were defined by
  Symbol-U itself, steering would be circular. Symbol-U is *phonological*; the
  axis is *semantic*; the pilot asks whether the phonological code can steer the
  semantic axis.
- **Seven arms, identical generator, differ only in the control code** (so we
  separate the *content* of the code from the *act* of conditioning):

  | arm | code per axis |
  |---|---|
  | `base` | none (unconditional reference) |
  | `symbolu` | Symbol-U vector centroid of the axis's training text |
  | `random` | fixed random per-axis vector (distinct, meaningless) |
  | `shuffled` | Symbol-U centroids mapped to the wrong axes |
  | `sentiment` | known axis-keyword centroid (a "known taxonomy" baseline) |
  | `relabel` | Symbol-U centroids with dimensions permuted (ontology relabeling) |
  | `prompt` | base model, axis word prepended to the prompt (NL prompting) |

## Hard environment limitations (read before trusting any number)

1. **No real pretrained LM.** `huggingface.co` is blocked by network policy (403),
   so the generator is a **tiny GRU LM trained from scratch on the smoke corpus.**
   Text fluency is poor by construction. Results are **SMOKE-ONLY**: they test the
   *pipeline* and the *relative ordering of arms*, not production quality.
2. **No LLM judge.** Evaluation uses two transparent **PROXY** scorers: a
   keyword **lexicon scorer** and a held-out **bag-of-words classifier**. A real
   study must replace these with human / strong-LLM judges.
3. **The NL-prompting arm is not a fair test here.** A tiny from-scratch LM cannot
   follow "calm" as an instruction the way a pretrained model does, so the
   `prompt` arm understates prompting. The real prompting baseline needs a
   pretrained model (see RunPod below).

## Commands

```bash
export PYTHONPATH=$(pwd)

# fast pipeline check
python -m symbolu_neural.controllability_pilot.cli smoke

# full pilot (a few minutes, CPU)
python -m symbolu_neural.controllability_pilot.cli run --u-backend pse_meaning
python -m symbolu_neural.controllability_pilot.cli run --u-backend vritti_mapper

# qualitative example generations
python -m symbolu_neural.controllability_pilot.cli samples --u-backend pse_meaning

# tests (machinery only)
python symbolu_neural/controllability_pilot/tests/test_pilot.py
```

### On a machine / RunPod with a real pretrained LM

The decisive prompting and fluency comparison needs a pretrained model. With HF
access, the same arms should be re-run swapping the from-scratch GRU for a frozen
pretrained LM + a small trained adapter, and the `prompt` arm using real
instruction-style prompts. Exact setup in `CONTROLLABILITY_PILOT_REPORT.md` §6.

## Files

| file | role |
|---|---|
| `data.py` | semantic smoke corpus (calm/active/heavy) + neutral prompts |
| `codes.py` | per-axis control codes for every arm |
| `generator.py` | tiny conditional GRU LM (per-timestep code injection) |
| `evaluator.py` | proxy lexicon scorer + BoW classifier + fluency/diversity |
| `pilot.py` | orchestrator + report |
| `cli.py` | entry point (`run` / `smoke` / `samples`) |
| `tests/test_pilot.py` | machinery tests |
| `CONTROLLABILITY_PILOT_REPORT.md` | run results + honest verdict |

## Isolation

Reuses only the sibling `complementarity_probe.backends` to compute the Symbol-U
vector. Does **not** modify or depend on the older detector files or
`clean_softmax`. Nothing deleted.
