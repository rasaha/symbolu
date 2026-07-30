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

---

## RM1-v1.1 — bounded extraction-normalization phase

The first real-model run (**RM1-v1**, `rm1.0.0`) established four facts: a real Mistral-7B executed
(VERIFIED); the governance boundary **failed closed** (evidence-ID preservation 1.0, unauthorized 0);
raw token answers sometimes guessed correctly but were not evidence-grounded; and the
token→EvidenceRecord **serialization contract was too brittle** for real-model output
(required-event survival ≈ 0.10, construction gap ≈ 0.9). This is a failure of the *interface*, not
of the dual architecture — the model often understood the text but was required to behave like a
deterministic parser.

**RM1-v1.1** (`rm1.1.0`) adds a deterministic normalization layer *between* the probabilistic model
output and exact enterprise identity. It does **not** relax evidence validation. Two bounded fixes:

1. **Source-document binding** (`extraction.resolve_document`): the model's `source_document_id` is a
   hint, never trusted. A span is bound to an authorized permitted document by, in order,
   `EXACT_ID` → `REGISTERED_ALIAS` → `SINGLE_PERMITTED_DOCUMENT` → `UNIQUE_SPAN_MATCH`; a span found
   in more than one permitted doc is `AMBIGUOUS` (quarantined), and a span in none is `UNRESOLVED`.
   Each proposal records `model_supplied_document_id`, `resolved_document_id`,
   `document_resolution_method`.
2. **Strict entity parsing** (`evidence_pipeline._parse_ent`): accept only the canonical token
   `\bent_[0-9]+\b` (so "the subject is ent_532" resolves, "subject 532" does not), then require the
   entity to exist in the instance ledger. Strict identity is preserved; normal phrasing is tolerated.

Both are covered by negative controls (`tests/test_rm1_v1_1_normalization.py`) proving no increase in
false admission: invented-id+unique-span → authorized doc only; invented-id+absent-span → quarantine;
same span in two docs → ambiguous; `ent_999` outside the ledger → not admitted; bare `532` → not
resolved; cross-tenant valid-looking entity → rejected; correct span from an unauthorized document →
rejected.

Two extraction metrics are reported separately so a semantically-correct-but-strictly-mis-serialized
model is visible: **`raw_model_field_exact_match`** (model supplied the exact document id itself) vs
**`post_normalization_resolved_match`** (resolved after the normalization layer).

### Frozen comparison protocol (do not overwrite RM1-v1)

RM1-v1 vs RM1-v1.1 changes **only** the deterministic interface. Kept identical: extraction prompts,
acceptance thresholds, model revision, decoding, dataset split/seed, event reasoner, routing policy,
deterministic outcome rules, event-attention operator, and the TAP/faithfulness evaluator.

```bash
# 1. FREEZE the existing RM1-v1 artifacts (on the machine that produced them)
cd experiments/hybrid_token_event_attention/real_model/results
mkdir -p rm1_v1
cp REAL_MODEL_RESULTS.json  rm1_v1/RM1_v1_RESULTS.json
cp REAL_MODEL_TRACES.jsonl  rm1_v1/RM1_v1_TRACES.jsonl
cp RESOURCE_MANIFEST.json   rm1_v1/RM1_v1_RESOURCE_MANIFEST.json
# derive the v1 failure taxonomy from the frozen traces (no model needed):
cd /workspace/symbolu
python -m experiments.hybrid_token_event_attention.real_model.analyze_traces \
    experiments/hybrid_token_event_attention/real_model/results/rm1_v1/RM1_v1_TRACES.jsonl \
    -o experiments/hybrid_token_event_attention/real_model/results/rm1_v1/RM1_v1_FAILURE_TAXONOMY.json

# 2. RERUN the identical corpus + seed after the fixes as RM1-v1.1 (writes results/rm1_v1.1/)
python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
    --model-id /workspace/models/mistral-7b-instruct-v0.3 --mode smoke --limit 20 --seed 0 \
    --offline --run-label rm1_v1.1
```

`--run-label` writes every artifact under `results/<label>/` so the baseline is never overwritten.
Provenance (git commit, prompt-set hash, dataset hash, seed, decoding config) is recorded in each
run's `REAL_MODEL_RESULTS.json`. Compare `results/rm1_v1/` (strict interface) with
`results/rm1_v1.1/` (normalized interface): the decisive movement should be in
`required_event_survival` and `post_normalization_resolved_match`, with governance invariants
unchanged.

The natural-language corpus is a **separate later phase (RM2)** — do not change the corpus here, or
the interface-robustness and language-extraction hypotheses become confounded.
