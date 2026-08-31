# Agent Runtime — Real-Model Adapter (Deliverable 2)

The env-driven live-model adapter that satisfies the existing `LanguageModel`/planner contract.
Ready to run the instant a live/local model is available. Grounded in
`agent_runtime_migration/model/live.py`, `model/capture.py`.

Labels: `FACT` (implemented/tested).

## Environment probe (§1) — result
`FACT`. Probed in order: (1) live-provider credentials — **none** (no `ANTHROPIC_API_KEY`/
`OPENAI_API_KEY`/… set); (2) local model server — **none** (11434/8000/1234/8080 all closed); (3)
installable local inference — pip reaches PyPI **but HuggingFace is blocked (403 CONNECT)** and there
are **no weights on disk / no HF cache**, so weights cannot be obtained; (4) remote endpoint — none
usable (`ANTHROPIC_BASE_URL` set but no token; the harness OAuth token is deliberately **not**
repurposed for model calls). Evidence: `model/fixtures/phase3_env_probe.json`. **Conclusion:
`BLOCKED_NO_REAL_MODEL`.**

## Adapter (ready to run)
`FACT`. `LiveHTTPModel` (standard-library `urllib`) implements `generate`/`call` for three providers,
selected by env:
| provider | endpoint | auth |
|---|---|---|
| `openai` | `{base}/v1/chat/completions` | `Authorization: Bearer $OPENAI_API_KEY` |
| `anthropic` | `{base}/v1/messages` | `x-api-key: $ANTHROPIC_API_KEY` |
| `ollama` | `{base}/api/chat` | none (local) |

Config from env: `RUNTIME_MODEL_PROVIDER`, `RUNTIME_MODEL_ID`, `RUNTIME_MODEL_BASE_URL`,
`RUNTIME_MODEL_TEMPERATURE` (default 0), `RUNTIME_MODEL_MAX_TOKENS`, `RUNTIME_MODEL_TIMEOUT_S`, seed
(where supported). `build_live_model_from_env()` returns the adapter only when a provider **and**
credentials are present; otherwise **`None`** (the runner then reports `BLOCKED_NO_REAL_MODEL`).

## Boundary (§3)
`FACT`. The real model may produce decomposition, plan steps, tool choice, arguments, uncertainty
evidence, reflection text. It may **not** provide a trusted tool risk class, principal identity,
authorization, operational-safety decision, execution eligibility, or execution reference. All output
passes through the frozen fail-closed `parse_plan_payload`; malformed output raises `ModelParseError`
and never reaches CER construction or tool execution (tested).

## Credential hygiene (§13)
`FACT`. Keys are read from the environment at call time and used only in request headers; the adapter
logs **prompt lengths only** — never prompt/response content or credentials. `CaptureRecorder` refuses
to persist anything matching a credential-like pattern. No credential appears in code, fixtures,
traces, or commits.

## Contract tests (not real-model evidence)
`FACT`. `tests/test_real_model_adapter.py` (5): the adapter round-trips a plan over a **local fake
HTTP server**; malformed server output fails closed before execution; only prompt lengths are logged;
`build_live_model_from_env()` returns `None` with no provider and with a missing key. These prove the
adapter is contract-correct; they are explicitly **not** live-model evidence (no real model runs).

## How to run Phase 3 when a model exists
```
# OpenAI-compatible or Anthropic (credentials in env, never committed):
RUNTIME_MODEL_PROVIDER=openai RUNTIME_MODEL_ID=<model> OPENAI_API_KEY=<key> \
  python -m agent_runtime_migration.benchmark.real_model_eval --json phase3_real.json
# Local Ollama:
RUNTIME_MODEL_PROVIDER=ollama RUNTIME_MODEL_ID=qwen2.5:0.5b-instruct \
  python -m agent_runtime_migration.benchmark.real_model_eval --json phase3_real.json
```
Capture responses with `CaptureRecorder` to produce a sanitized replay fixture for regression.
