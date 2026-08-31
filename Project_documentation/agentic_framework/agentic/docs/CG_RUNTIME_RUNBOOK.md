# CG Runtime Runbook — `inference_mistral.py`

Operational guide for running the agentic framework from the
`inference_mistral.py` CLI. Covers both paths:

- **Default (API) path** — `MistralAdapter` hitting the hosted Mistral API.
- **`--cg` (CG-runtime) path** — local `MistralCGAdapter` composed
  through `build_cg_mcp_agent(...)` + `CGToolDispatcher` +
  `SafeMCPGateway`. See `RUNTIME_MCP_PATH.md` for the full wiring.

This runbook is deliberately honest about what is proved and what is
still experimental. Read the **Runtime Status** section before
claiming production readiness.

---

## 1. Default (API) path — lightweight, no local model

### Requirements
- `MISTRAL_API_KEY` in environment (or `--api-key`).
- Network access to the Mistral API.
- No torch / transformers / checkpoint needed.

### Run
```bash
# Interactive REPL
python -m agentic.agentic_framework.inference_mistral

# Single query
python -m agentic.agentic_framework.inference_mistral \
    --query "What is quantum computing?"

# Multi-turn demo
python -m agentic.agentic_framework.inference_mistral --demo

# Custom model + verbose pipeline output
python -m agentic.agentic_framework.inference_mistral \
    --model mistral-medium-latest --verbose
```

### What this exercises
- `AgenticLLMWrapper` full pipeline (goal decomposition, memory,
  reflective generation, coherence, safety contract).
- Does **not** exercise the CG/MCP runtime path. No dispatcher, no
  `last_cg_metadata`, no MCP governance on tool calls.

---

## 2. `--cg` path — local CG-capable runtime

### What `--cg` changes
- Replaces `MistralAdapter` with `MistralCGAdapter` (local inference).
- Wires an `AgenticLLMWrapper` via `build_cg_mcp_agent(...)`.
- Every mapped action type (`search` / `compute` / `validate`) is
  routed through `CGToolDispatcher` → `SafeMCPGateway` with
  CG-derived `entropy_result` + `vritti_result`.
- Turns are governed by both `SafetyGate` (turn-level) and
  `SafeMCPGateway` (per-call).

### Requirements (real inference)
- Python ≥ 3.10.
- `torch` (CUDA build recommended; CPU works but is slow).
- `transformers`.
- `symbolu_training.training.unified.mistral_wrapper` importable
  (supplies `MistralCGWrapper`).
- GPU with enough VRAM for the chosen checkpoint:
  - `mistralai/Mistral-7B-v0.3` un-quantized: ~15 GB.
  - `--cg-quantize 4bit`: ~5 GB (requires `bitsandbytes`).
  - `--cg-quantize 8bit`: ~8 GB (requires `bitsandbytes`).
- HuggingFace access token set (if the checkpoint is gated).

### Flags
| Flag              | Default                         | Meaning                                     |
|-------------------|---------------------------------|---------------------------------------------|
| `--cg`            | off                             | Opt into the CG runtime path.               |
| `--cg-model`      | `mistralai/Mistral-7B-v0.3`     | HuggingFace model id for MistralCGWrapper.  |
| `--cg-quantize`   | none                            | `4bit` / `8bit` (requires bitsandbytes).    |
| `--cg-device`     | `auto`                          | Device-map strategy for MistralCGWrapper.   |
| `--cg-allow-stub` | off                             | See §3. Dev/test fallback only.             |

### Run (real inference)
```bash
# CPU / single-GPU 4-bit
python -m agentic.agentic_framework.inference_mistral --cg \
    --cg-model mistralai/Mistral-7B-v0.3 \
    --cg-quantize 4bit \
    --query "Compare self-attention and linear attention briefly."

# Multi-GPU auto placement
python -m agentic.agentic_framework.inference_mistral --cg \
    --cg-device auto --demo --verbose
```

### Actionable errors
- If torch / transformers / MistralCGWrapper are missing **and**
  `--cg-allow-stub` was NOT passed, the CLI exits with:
  ```
  Error: CG runtime requested but MistralCGAdapter could not be
  constructed: <ImportError …>
  Install the heavy inference stack (torch, transformers,
  symbolu_training.training.unified.mistral_wrapper) or pass
  --cg-allow-stub to fall back to StubCGLLMAdapter (deterministic
  fixture — dev/test only).
  ```
- This is intentional. Silent degradation would let a "real" CLI
  invocation secretly run a deterministic stub.

---

## 3. `--cg-allow-stub` — dev/test fallback only

Meaning: if `MistralCGAdapter` cannot be constructed, fall back to
`StubCGLLMAdapter` instead of exiting. `StubCGLLMAdapter` emits a
**deterministic 32D fixture** for its sovereign state
(`IS_STUB = True`, `STATE_PROVENANCE = "deterministic_stub"`). The
CLI prints a visible `[warn]` banner when it falls back.

Use it for:
- smoke-testing the wiring end-to-end without a GPU / checkpoint;
- local REPL loops to validate the CLI itself;
- CI paths that want to exercise the dispatcher+gateway without
  pulling torch.

**Never** use `--cg-allow-stub` in anything resembling a production
evaluation. The stub's sovereign state is a fixture, not an inference
signal. Treating its outputs as real CG metadata will give wrong
answers about governance behavior.

---

## 4. Opt-in smoke test

`tests/test_inference_mistral_cg_smoke.py` exercises the `--cg`
wiring end-to-end with the stub fallback. It is **skipped by default**.

```bash
# Skipped by default
pytest agentic/agentic_framework/tests/test_inference_mistral_cg_smoke.py

# Enable
SYMBOLU_RUN_CG_SMOKE=1 pytest \
    agentic/agentic_framework/tests/test_inference_mistral_cg_smoke.py -v
```

What it pins:
- `create_cg_agent(allow_stub=True)` returns an `AgenticLLMWrapper`
  with a `CGToolDispatcher` and a real `SafeMCPGateway`.
- `agent.run(query)` completes without raising.
- `adapter.last_cg_metadata["state"]` is a 32D list after the run.

It is **not** a correctness proof for real-CG outputs. It is a
wiring-integrity check.

---

## 5. Runtime Status — proved vs experimental

### Fully proved (baseline regression tests, all green)
- MCP-side enrichment is real: `build_governance_enrichment_kwargs`
  attaches `entropy_result` + `vritti_result` on every MCP tool call
  whenever live CG metadata is present.
- `CGToolDispatcher` reads `adapter.last_cg_metadata` and forwards
  per-call to `SafeMCPGateway` — pinned by `test_cg_tool_dispatcher.py`.
- `AgenticLLMWrapper._execute_actions` → dispatcher ordering vs
  `SafetyGate` — pinned by `test_agent_cg_dispatcher.py`.
- Full `agent.run(...)` → MCP audit with
  `vritti_signal_source="real"` — pinned by
  `test_agent_full_run_integration.py`.
- `build_cg_mcp_agent(...)` substitution seam + `IS_STUB` warning —
  pinned by `test_cg_mcp_runtime_factory.py`.

### Partially proved
- `inference_mistral.py --cg` wiring: proved end-to-end **with the
  stub adapter** (opt-in smoke test, green). The path through
  `MistralCGAdapter` (real local inference) has **not** been run
  here — it requires a torch + checkpoint environment that is out
  of scope for this repo's test harness.
- `--cg` CLI → CG-runtime composition: proved at the factory level
  and at the CLI argparse / dispatch level. Real-inference runtime
  correctness is the user's responsibility at first run.

### Intentionally deferred (known limitations)
- **`sovereign_projection_metadata`** is never attached on this
  path. It requires a real `SovereignProjectionResult` producer,
  which is not wired on the MCP/tool-use path.
  See `REQUEST_BOUNDARY_CONVENTION.md` for the omission rule.
- **`AuthorizationRequest`-side enrichment** is not wired. Only
  MCP tool calls go through this runtime. Auth-side enrichment is
  out of scope for the current branch.
- **No honest production runtime caller** of `AgenticLLMWrapper`
  exists outside this CLI today. Voice and other subsystems have
  not been migrated. `inference_mistral.py --cg` is the single
  runnable CG-runtime entry point.
- **Mirror migration** (`agentic/` canonical,
  `symbolu/agentic_framework/` mirror) is still in progress.
  Mirrors are kept in sync by hand on this branch — see the
  "Mirror drift" note below.

---

## 6. Mirror drift note

This branch maintains two locations for identical agentic code:

- **canonical:** `agentic/agentic_framework/`
- **mirror:**    `symbolu/agentic_framework/`

Files differ only in import prefixes (`agentic.` vs `symbolu.`).
When you change one, change the other. Key files kept in sync on
this branch:

- `inference_mistral.py`
- `tests/test_inference_mistral_cg_smoke.py`
- `cg_tool_dispatcher.py`
- `llm_adapters.py`
- `mcp_gateway.py`
- `docs/*.md`

The long-term plan is to retire the `symbolu/agentic_framework/`
mirror; until then treat any drift between the two as a bug.

---

## 7. See also

- `RUNTIME_MCP_PATH.md` — concrete end-to-end wiring diagram.
- `REQUEST_BOUNDARY_CONVENTION.md` — attach/omit rules for
  request-boundary enrichment.
- `../../AGENTIC_ARCHITECTURE.md` — architectural context.
