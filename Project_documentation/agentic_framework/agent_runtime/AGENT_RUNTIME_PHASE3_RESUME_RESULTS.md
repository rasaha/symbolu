# Agent Runtime Phase 3 — Resume Attempt (Real Mistral Model)

Resume of Phase 3 triggered by "a valid Mistral API key is now available." The attempt used **only**
the frozen `build_live_model_from_env()` resolution path and modified **no** frozen artifact
(preregistration, prompts, parsing, corpus, thresholds, canary scope, governance logic, CER,
ActionGate, ACP, legacy runtime, adapter). Evidence: `model/fixtures/phase3_resume_probe.json`.

Labels: `FACT` (measured) · `INTERPRETATION`.

## 1. Model-environment verification (§1) — result
`FACT`. Resolving the model exclusively through the frozen path:
- `build_live_model_from_env()` → **`None`** (no provider/credentials configured).
- Model credentials present: **none** — `MISTRAL_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  `RUNTIME_MODEL_PROVIDER`, `RUNTIME_MODEL_ID` all **unset**; no credential in standard file locations
  (`~/.mistral`, `~/.config/mistral/*`, `/run/secrets/mistral_api_key`).
- **Egress policy blocks the Mistral API**: `api.mistral.ai` and `codestral.mistral.ai` both return
  **HTTP 000 (403 CONNECT tunnel failed)**. The proxy README states: *"The destination host is not
  allowed by your organization's egress policy for this session. Do not retry or route around it —
  report the blocked host."* The only model host in the egress allowlist is `anthropic.com`.

No credential values, authorization headers, tokens, or secrets were printed or stored.

## 2. Genuine model response? — No
`FACT`. Per §1, "If the endpoint does not produce a genuine model response, stop again with
`BLOCKED_NO_REAL_MODEL`." No key is configured **and** the named provider's endpoint is egress-denied,
so no genuine Mistral response can be obtained. **The run stops here.**

## 3. What was explicitly NOT done (integrity)
`FACT`.
- Did **not** fabricate a Mistral response or present replay as live evidence.
- Did **not** route around the egress proxy (policy-denied host reported, not bypassed).
- Did **not** repurpose non-model credentials — `AWS_*`, `GH_TOKEN`/`GITHUB_TOKEN`,
  `CLOUDSDK_AUTH_ACCESS_TOKEN`, and the harness OAuth token are **not** Mistral credentials and were
  not used for model calls.
- Did **not** modify any frozen artifact (adapter `model/live.py` unchanged — even a `mistral`
  provider could not reach the egress-blocked host).

## 4. Verdicts (unchanged from Phase 3; no real model ran)
`FACT`.
- **Real-model runtime → `BLOCKED_NO_REAL_MODEL`** (no credential configured; Mistral egress-denied).
- **Proposal quality → NOT ASSESSABLE** (no real proposals to measure).
- **Governance containment → structural boundary HOLDS**; real-model containment blocked (0 boundary
  violations across all deterministic runs; malformed output fails closed even over a live HTTP
  adapter, `test_real_model_adapter.py`).
- **Read-only canary → harness VALIDATED**; real-model-driven canary blocked.
- **Migration → `AGENT_RUNTIME_MIGRATION_CONTINUE`** (`AGENT_RUNTIME_REPLACEMENT_CANDIDATE` requires an
  actual model to have run; the blocker is the environment — a missing credential **and** an
  egress-denied provider — not the runtime). **No legacy deletion recommended.**

## 5. Remediation required (outside this session's control)
`INTERPRETATION`. To unblock, the environment owner must do **both**:
1. **Provide a model credential** the frozen resolver reads — set `RUNTIME_MODEL_PROVIDER=openai`,
   `RUNTIME_MODEL_ID=<mistral model, e.g. mistral-small-latest>`,
   `RUNTIME_MODEL_BASE_URL=https://api.mistral.ai`, and `OPENAI_API_KEY=<the Mistral key>` (Mistral's
   API is OpenAI-compatible, so the frozen adapter runs it unchanged); **and**
2. **Allowlist `api.mistral.ai` in the egress policy** (currently only `anthropic.com` is permitted).
   Alternatively, run a local **Ollama** server (`RUNTIME_MODEL_PROVIDER=ollama`,
   `RUNTIME_MODEL_ID=<local model>`) which needs no egress.

With both in place, run the frozen harness unchanged:
`python -m agent_runtime_migration.benchmark.real_model_eval --json phase3_real.json` — it will
execute the 14-scenario corpus, capture sanitized replay fixtures, and grade against the preregistered
thresholds. Nothing in the evaluation needs to change.

## 6. Environment / branch
`FACT`. Branch `claude/agentic-framework-architecture-review-v1qmrd`. Blocked host reported:
`api.mistral.ai` (403, egress policy). 74 migration tests still pass; legacy runtime, ActionGate, ACP,
CER unchanged.

---

## Addendum — Second resume attempt (owner reports Mistral configured)

`FACT`. Triggered by "the environment owner has now configured the real Mistral endpoint and key"
(provider openai-compatible, model `mistral-small-latest`, base `https://api.mistral.ai/v1`). Resolved
**only** via the frozen `build_live_model_from_env()`. Evidence:
`model/fixtures/phase3_resume2_probe.json`.

**Result: the configuration is NOT visible to this session's process → `BLOCKED_NO_REAL_MODEL`.**
- `build_live_model_from_env()` → `None` (also under a login shell).
- No `RUNTIME_MODEL_PROVIDER` / `RUNTIME_MODEL_ID` / `RUNTIME_MODEL_BASE_URL` / `OPENAI_API_KEY` /
  `MISTRAL_API_KEY` set in this process; no `.env`/config file present.
- Steps 1 and 4 of the resume instruction apply: the resolver did not return a live adapter, so **no
  minimal Mistral request was attempted** — stop and report the sanitized error (no genuine model
  response). No credential was fabricated, self-set, or repurposed; no frozen artifact was modified.

### Config bug found in the expected setup (fix required, not a runtime change)
`FACT`. For `provider=openai` the **frozen** adapter POSTs to
`{RUNTIME_MODEL_BASE_URL}/v1/chat/completions`. The expected base `https://api.mistral.ai/v1` would
yield `https://api.mistral.ai/v1/v1/chat/completions` (**double `/v1` → 404**). The correct value is:
```
RUNTIME_MODEL_BASE_URL=https://api.mistral.ai      # NO trailing /v1
```

### To make the config reach this session (env owner)
Export these in the **session's** process environment (the values must be present where the runner
runs, not only in a separate config store), then re-run:
```
RUNTIME_MODEL_PROVIDER=openai
RUNTIME_MODEL_BASE_URL=https://api.mistral.ai       # not .../v1
RUNTIME_MODEL_ID=mistral-small-latest
OPENAI_API_KEY=<the Mistral key>                    # adapter reads OPENAI_API_KEY for provider=openai
python -m agent_runtime_migration.benchmark.real_model_eval --json .../phase3_real_model_results.json
```
Also required: `api.mistral.ai` allowlisted in the egress policy (it returned 403 in the prior probe).
Verdicts are unchanged from Phase 3 until the runner reports `"status": "EVALUATED"` with real numbers.
