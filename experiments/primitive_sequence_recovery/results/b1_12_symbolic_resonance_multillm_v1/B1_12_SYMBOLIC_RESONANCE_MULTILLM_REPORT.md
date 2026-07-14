# B1.12 Bare-Word Symbolic Resonance — Multi-LLM Crossover · SETUP (BLOCKED)

**Setup-only run.** The two-LLM cross-over evaluation was **not executed**: both hard gates in the controlling
run specification block it. Per the specification, no model was substituted and no word list was created.
`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE` (not inferred confirmatory — no evidence-freeze
declaration was validated).

Controlling preregistration: `VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md`. Scope artifact:
`B1_12_SCOPE_UPDATE_AND_CONTROLLING_PREREG.md`.

## Run status: **BLOCKED** (two independent reasons)

### 1. `BLOCKED_REQUIRED_MODEL_UNAVAILABLE`

The run requires two independent model families — **Qwen 3 (~30–32B)** and **Mistral Small 3.x (~24B)** — run
with pinned deterministic settings. This environment has **no capability to run either**:

| Check | Result |
|---|---|
| GPU | none (`nvidia-smi` absent) |
| Local runners (ollama / vllm / llama-server / TGI / lmdeploy) | all absent |
| Python inference libs (torch / transformers / vllm / llama_cpp) | all absent |
| Local Qwen / Mistral weights on disk | none found |
| External Qwen / Mistral API keys | none set |

Per the specification, **no other model was silently substituted** (including this assistant). Model config
(revision, quantization, temperature, top-p/k, repetition penalty, max tokens, seed, chat template, Qwen
reasoning mode) is recorded **only** when the models are actually loaded; it is therefore not pinned here.

### 2. `BLOCKED_WORDLIST_NOT_PRECOMMITTED`

The run requires a **separately precommitted B1.12 Bare-Word Symbolic Resonance word list** (frozen before
scoring; attested Sanskrit; under the BSR prereg; **not** the old 60-word calibration set). No such artifact
exists:

| Candidate examined | Rejected because |
|---|---|
| `varna_affliction_pilot_run_v1/wordlist_precommit.json` | belongs to the **Resolution / PMM-PR-CR** methodology, not BSR; and it is the old **60-word calibration** / developmental set |
| `b1_eval_wordlist.json` | H2 **Track-B** English/McRae eval list (dev words + fixtures) — not a Sanskrit BSR precommitment |

The controlling BSR prereg is itself at **`READY_FOR_WORDLIST_PRECOMMITMENT`** — the precommitment is the
not-yet-done next gate. **No words were selected here** (selecting words inside the scoring task is prohibited;
precommitment is a separate step).

## Pinned inputs recorded (available and frozen)

| Input | SHA-256 |
|---|---|
| Parser `sanskrit_stage1_parser.py` | `d885391ffc269803…` |
| Lexicon `frozen/varna_native_stage1_merged_v3.json` | `65116f371aca9f24…` |
| Controlling prereg `VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md` | (in `input_hashes.json`) |
| Scope artifact `B1_12_SCOPE_UPDATE_AND_CONTROLLING_PREREG.md` | (in `input_hashes.json`) |

## What was NOT produced (correctly)

No `run_a_*` / `run_b_*` profiles, evidence, or scores; no `component_agreement`, `word_verdict_agreement`, or
`role_dependence_summary`; no raw model outputs — because no model ran and no word list exists. Fabricating any of
these would violate the specification.

## To unblock (separate future gates, in order)

1. **Model availability** — provide an inference path for Qwen 3 (~30–32B) and Mistral Small 3.x (~24B) (local
   GPU runner or authorized API endpoints), then pin the full deterministic config.
2. **Word-list precommitment** — run the separate B1.12 BSR word-list precommitment task (freeze an attested
   Sanskrit bare-word list under `VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md`), producing a `wordlist_manifest` frozen
   before any scoring.

Only after **both** gates pass may the two-LLM crossover (Run A / Run B) execute.

## Repository discipline

No frozen input, controlling preregistration, prior B1.12 artifact, calibration score, feature-lift artifact, or
resolution-study output was modified. Only this setup/gate record was added.

## Guardrails
Setup-only gate verification. No model run, no model substituted, no word selected, no confirmatory status
inferred. Structure, not validated meaning.
