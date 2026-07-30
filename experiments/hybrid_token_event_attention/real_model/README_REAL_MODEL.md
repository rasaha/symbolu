# RM1 — Real-Model Validation of the Dual-Domain Hybrid LLM

RM1 replaces the local **token-model stand-in** used in the frozen controlled study
(`experiments/hybrid_token_event_attention/`) with an **actual open-weight causal language model**
loaded through Hugging Face Transformers, and drives that real model through the *same frozen
external governed architecture*:

```
real token-language model
    → provisional evidence extraction
    → deterministic validation and normalization
    → exact EvidenceRecords
    → P5 smallest-sufficient-set selection
    → contract-aware reasoning router
    → deterministic reasoning by default
    → bounded event attention only for relational contracts
    → typed evidence-linked findings
    → real token-model explanation
    → TAP / RM1 faithfulness evaluation
```

**RM1 does not** fine-tune the base model and does **not** add FSCS, LoRA, adapters, Phase
recurrence, or any other architecture change. It isolates the single effect of swapping the token
stand-in for a real frozen model. It is a **new additive directory**; every frozen component (event
schema, normalization bridge, P5 selector, deterministic reasoner, H2/H3 event modules, causal
controls, datasets, canonical results JSON and report) is **imported, never modified**.

## Honesty boundary (read first)

The sandbox this was authored in has **no `torch`, `transformers`, `accelerate`, `safetensors`, or
GPU**. A genuine open-weight model therefore **cannot be loaded here**, and the harness reports
`RESOURCE_BLOCKED` with exact remediation instead of inventing numbers. **The old stand-in is never
substituted for a real model.** The committed result artifacts under `results/` are the honest
`RESOURCE_BLOCKED` record for this environment plus the model-independent architecture invariants.

To produce a real-model result, run on a suitable machine (see **Run** below); the harness will then
load the model, record proof-of-execution, and emit `COMPLETED` artifacts.

## Real-model authority boundary (§5)

The actual model may perform only two functions:

- **A. interpret** governed source text into *provisional* evidence proposals (semantic fields + an
  exact source span), and
- **B. explain** an already-computed typed result.

The model **never** assigns evidence ids, provenance hashes, authority/version/tenant/access status,
admission decisions, or the outcome. All of that is done by the **deterministic evidence pipeline**
(`evidence_pipeline.py`). Every proposed `source_span` must be an **exact substring** of the cited,
permitted source document; unresolved, malformed, low-confidence, ambiguous, cross-tenant, or corrupt
proposals are **quarantined or rejected**, never silently repaired.

## Layout

```
real_model/
├── run_real_model.py            single user-facing entrypoint (CLI, arms RM0–RM7, artifacts, report)
├── hf_backend.py                real HF AutoModelForCausalLM + resource gate + offline MockBackend
├── prompts.py                   interpret / explain prompts, extraction schema, offline mock responder
├── extraction.py                schema-guided extraction, bounded retries, ClarificationRequest (§7)
├── evidence_pipeline.py         deterministic validation → states → resolution → P5 admission (§5,§6)
├── reasoning_router.py          deterministic contract-aware router (§8)
├── explanation.py               real-model explanation of a computed typed result (§5 role B)
├── evaluation.py                metrics, RM1_FAITHFULNESS_EVALUATOR, integrity/causal controls (§12–14)
├── requirements-real-model.txt  runtime deps (needed ONLY to load a real model)
├── tests/test_real_model_harness.py   mock-backend unit tests (no weights required)
├── results/                     REAL_MODEL_RESULTS.json, REAL_MODEL_TRACES.jsonl,
│                                REAL_MODEL_VALIDATION_REPORT.md, RESOURCE_MANIFEST.json
└── quarantine/                  QUARANTINE.jsonl
```

## Arms (§9)

| arm | pipeline |
|---|---|
| **RM0** | real model over raw source text → final answer directly |
| **RM1** | real model over a retrieved source-span packet → final answer directly |
| **RM2** | real-model extraction → validation → validated events serialized back → model answers directly |
| **RM3** | real-model extraction → validation → **deterministic-only** reasoner → typed outcome |
| **RM4** | RM3 + **router-gated** bounded event attention for relational contracts |
| **RM5** | **oracle** EvidenceRecords → deterministic reasoner (real-model-independent ceiling) |
| **RM6** | oracle EvidenceRecords → router → deterministic + event attention |
| **RM7** | best typed outcome → real-model explanation → faithfulness evaluation |

Decisive comparisons: `RM1−RM0` (retrieval), `RM2−RM1` (structured events), `RM3−RM2` (deterministic
enterprise computation), `RM4−RM3` (router-gated event attention), `RM5−RM3` (construction gap),
`RM6−RM4` (loss from real-model extraction + admission). **`RM4−RM0` is not attributed entirely to
event attention.**

### Event-attention branch

RM4/RM6's relational branch requires the frozen H3 event operator. RM1 loads a canonical checkpoint
if one exists (verifying its hash) or trains **only** the existing event module on the existing
training split under the pre-registered architecture/hyperparameters — never on RM1 held-out data. If
no operator is available in a given run, the routed relational branch executes the deterministic
reasoner and the run **records `event_attention_available = false`** rather than silently claiming an
event-attention result.

## TAP boundary (§13)

The repository's `tap_provider` governs **assertion support relative to evidence** — a related but
different contract from **explanation-over-events faithfulness**. Because no existing public API
scores an event-explanation against admitted `EvidenceRecords`, RM1 ships a clearly labelled
**`RM1_FAITHFULNESS_EVALUATOR`** (`evaluation.py`). It is deterministic and gold-anchored, and does
**not** use the same real model as the sole judge of its own explanation. It checks: cited-id
existence, cited-span existence, unsupported numeric/authority claims, qualifier preservation,
active-vs-stale confusion, authority exceedance, and evidence-attribution exact match.

## Run

Any **open-weight** causal LM works — pass an HF repo id, a pinned revision, or a local directory.
`--model-id` is **optional**: it defaults to the open, ungated **`Qwen/Qwen2.5-0.5B-Instruct`**
(Apache-2.0, small enough to run on CPU). Override it for a larger open model such as
`mistralai/Mistral-7B-Instruct-v0.3`, or via `$UGENCE_REAL_MODEL_ID`.

```bash
# 1. install real-model deps on a suitable machine (GPU or a 32 GB+ CPU host)
pip install -r experiments/hybrid_token_event_attention/real_model/requirements-real-model.txt

# 2. smoke run with the open default model (no placeholder / env var needed)
python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
    --mode smoke --limit 20 --device auto --dtype auto

# 2b. or pick a specific open-weight model (repo id, pinned revision, or local dir)
python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
    --model-id "mistralai/Mistral-7B-Instruct-v0.3" --revision "<commit-sha>" \
    --mode smoke --limit 20 --device auto --dtype auto

# 3. full held-out run
python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
    --model-id "mistralai/Mistral-7B-Instruct-v0.3" --mode full --device auto --dtype auto
```

`$UGENCE_REAL_MODEL_ID` / `$UGENCE_MODEL_REVISION` still work as optional overrides for the model and
its pinned revision.

CLI flags: `--model-id --revision --dataset-jsonl --mode smoke|full --limit --seed
--device auto|cuda|mps|cpu --dtype auto|bf16|fp16|fp32 --load-in-4bit --max-input-tokens
--max-new-tokens --clarification-limit --output-dir --offline --resume --trust-remote-code`.
Decoding is deterministic (`do_sample=false`); seeds are set and recorded (note that some GPU ops are
not bitwise deterministic). `trust_remote_code` defaults to **false**; authentication tokens are read
from the environment but never printed or written to artifacts. **4-bit** loading is offered only on
CUDA with `bitsandbytes` present and only when the caller opts in — the harness never silently
quantizes or switches model families.

### Exercising the harness without weights

```bash
# run the unit tests (no torch/transformers needed)
python -m unittest experiments.hybrid_token_event_attention.real_model.tests.test_real_model_harness

# DEV ONLY: prove the pipeline plumbing end-to-end with the offline MOCK backend.
# Output is tagged execution=MOCK and is NEVER a real-model result.
python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
    --mock-plumbing --mode smoke --limit 10
```

## Pre-registered acceptance criteria (§15)

The RM1 architecture is *supported* only if a real forward pass is verified **and**: schema-valid
extraction ≥ 0.95; source-span exact match ≥ 0.90; evidence-ID preservation = 1.00; unauthorized-event
inclusion = 0.00; corrupt-record rejection = 1.00; required-event survival ≥ 0.75; `RM3 − RM1 ≥ 0.10`;
`RM4 − RM3 ≥ −0.01` overall and `RM4 − RM3 ≥ 0.05` on the routed relational subset; oracle-to-predicted
gap ≤ 0.15; supported-claim precision ≥ 0.95; unsupported-claim recall ≥ 0.90; qualifier preservation
≥ 0.95. These thresholds are **not** lowered after observing results. Event attention is classified
`TASK_SPECIFIC` (not `VALIDATED`) if it helps some routed relational families but misses the +0.05
bar; extraction is classified `BOTTLENECK` if the oracle-to-predicted gap > 0.15 or required-event
survival < 0.75.

## Scope

> RM1 tests an actual frozen token-language model inside the external governed dual-domain
> architecture. It does not validate FSCS, model-weight adaptation, production deployment, or
> universal superiority of event attention.
