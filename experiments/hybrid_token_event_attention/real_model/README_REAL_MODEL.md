# RM1 — Real-Model Validation of the Dual-Domain Hybrid LLM

RM1 replaces the local token-model **stand-in** used in the controlled experiment with an **actual
open-weight causal LM** loaded through Hugging Face `transformers`, and tests the *frozen external*
architecture:

```
real token model → provisional evidence extraction → deterministic validation/normalization
  → exact EvidenceRecords → P5 smallest-sufficient-set → contract-aware reasoning router
  → deterministic reasoning by default → bounded event attention only for relational contracts
  → typed evidence-linked findings → real-model explanation → RM1 faithfulness evaluation
```

The base model is **frozen** (no fine-tuning, no LoRA, no adapters, no FSCS, no Phase). This phase
isolates one change: the token stand-in → a real model.

> **Scope.** RM1 tests an actual frozen token-language model inside the external governed dual-domain
> architecture. It does not validate FSCS, model-weight adaptation, production deployment, or
> universal superiority of event attention.

## What the model may and may not do (§5)

The model performs only **(A) interpret source language into provisional evidence proposals** and
**(B) explain an already-computed typed result**. It never assigns evidence IDs, provenance hashes,
authority, versions, access, decision authority, or execution rights — the **deterministic bridge**
does. The model proposes semantic fields + exact source spans; everything authoritative is assigned
deterministically.

## Running

```bash
pip install -r experiments/hybrid_token_event_attention/real_model/requirements-real-model.txt
export UGENCE_REAL_MODEL_ID=<hf-repo-or-local-dir>        # e.g. mistralai/Mistral-7B-v0.3
export UGENCE_MODEL_REVISION=<commit-or-tag>              # optional pin

python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
    --model-id "$UGENCE_REAL_MODEL_ID" --revision "$UGENCE_MODEL_REVISION" \
    --mode smoke --limit 20
```

Key flags: `--mode smoke|full`, `--limit`, `--device auto|cuda|mps|cpu`, `--dtype auto|bf16|fp16|fp32`,
`--load-in-4bit` (CUDA + bitsandbytes only; never silent), `--max-input-tokens`, `--max-new-tokens`,
`--clarification-limit`, `--dataset-jsonl <path>` (adjudicated mode), `--offline`, `--resume`,
`--trust-remote-code` (default **false**). Decoding is deterministic (`do_sample=False`).

`--self-test-mock` runs a **clearly-labelled MockBackend wiring smoke** (writes
`MOCK_HARNESS_SMOKE.json`) — it is NOT a real-model result and makes no scientific claim.

## Resource gate (§2)

The harness probes the environment before loading weights. It uses bf16 when genuinely supported,
fp16 on compatible CUDA/MPS, fp32 on CPU. It never silently quantizes and never silently switches
model families. If the model cannot be loaded it terminates with **`RESOURCE_BLOCKED`** (exit code 3),
writing `REAL_MODEL_RESULTS.json`, `REAL_MODEL_VALIDATION_REPORT.md`, and `RESOURCE_MANIFEST.json`
with the detected hardware, the missing package/access requirement, and the exact command to run on
a suitable machine.

**This sandbox is RESOURCE_BLOCKED**: no `torch`/`transformers`, no GPU, and `huggingface.co` returns
HTTP 403 through the egress proxy. The committed `REAL_MODEL_RESULTS.json` therefore records
`RESOURCE_BLOCKED` — not a fabricated real-model result. Reproduce the real run on a CUDA machine
(≈16 GB VRAM for a 7B bf16 model) with the dependencies installed and Hub access (or a local model
directory + `--offline`).

## Arms (§9) and comparisons

`RM0` model over raw text · `RM1` model over retrieved packet · `RM2` model + validated events,
model answers · `RM3` extraction→validation→deterministic reasoner · `RM4` +router+event attention
for relational · `RM5` oracle→deterministic (ceiling) · `RM6` oracle→router+event attention ·
`RM7` best outcome→model explanation→faithfulness. Decisive deltas: RM1−RM0, RM2−RM1, RM3−RM2,
RM4−RM3, RM5−RM3 (construction gap), RM6−RM4. RM4−RM0 must **not** be credited to event attention.

## Modules

```
run_real_model.py     single CLI entrypoint + resource gate + artifact writer
hf_backend.py         env probe, HFBackend (lazy torch), MockBackend, ResourceBlocked
prompts.py            schema-guided extraction + explanation prompts (no gold leakage)
extraction.py         parse model JSON, bounded ≤2 retries with validator feedback (no gold)
clarification.py      bounded, append-only, replayable ClarificationRequest contract
evidence_pipeline.py  deterministic validate→normalize→states→P5 (reuses frozen bridge)
reasoning_router.py   deterministic contract router (DET_ONLY / DET+EVENT / QUARANTINE)
explanation.py        real-model explanation + RM1_FAITHFULNESS_EVALUATOR (deterministic)
evaluation.py         RM0–RM7 arms, metrics, §14 causal controls, §15 acceptance, event checkpoint
mock_corpus.py        deterministic MockBackend responders (tests / wiring smoke only)
tests/                mock-backend unit tests (no torch required)
```

## Reuse & integrity

RM1 reuses the frozen `EventRecord` schema, normalization conventions, P5 policy, deterministic
reasoner, H2 pooling baseline, gated-residual H3 operator, causal controls, and evidence-ID checks.
The event operator is **not** redesigned. The event checkpoint is trained once on the existing
training split (frozen architecture/hyperparameters), saved with a content hash, and never touched
by RM1 held-out data. The controlled-run canonical artifacts are **not** modified.

## Faithfulness (§13)

The repository ships no callable TAP API for free-text enterprise explanations, so RM1 uses a
deterministic, gold-and-record-grounded `RM1_FAITHFULNESS_EVALUATOR` (never the model judging its own
output). It is **not** called "TAP". If a real TAP API is later exposed, wire it in without weakening
it.
