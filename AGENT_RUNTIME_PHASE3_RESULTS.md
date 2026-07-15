# Agent Runtime Phase 3 — Results (Deliverable 7)

Real-model validation. Executed AFTER the preregistration (`AGENT_RUNTIME_PHASE3_PREREGISTRATION.md`,
commit `6bb8fe0`). **No live-model evidence is fabricated; the replay-only study is NOT presented as
Phase-3 evidence.**

Labels: `FACT` (measured) · `INTERPRETATION`.

## 1. Environment probe (§1) — decisive
`FACT`. Probed in order (`model/fixtures/phase3_env_probe.json`):
1. **Live-provider credentials** — none (no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/… set).
2. **Local model server** — none (127.0.0.1:11434/8000/1234/8080 all closed).
3. **Installable local inference** — pip reaches PyPI, **but HuggingFace is blocked (403 CONNECT)**;
   **no weights on disk**, no HF cache → weights cannot be obtained.
4. **Remote endpoint** — none usable (`ANTHROPIC_BASE_URL` set but no token; the harness OAuth token
   is deliberately **not** repurposed for model calls — credential-misuse avoidance).

**No live or local model can run.** Per §1 the milestone stops here rather than repeating replay.

## 2. What was built (ready-to-run, non-fabricating)
`FACT`. A complete real-model path that executes the instant a model exists:
- `model/live.py` — env-driven `LiveHTTPModel` (openai/anthropic/ollama; credentials from env, only
  prompt lengths logged); `build_live_model_from_env()` → `None` without provider+credentials.
- `model/capture.py` — sanitized capture → replay for reproducibility.
- `benchmark/real_model_corpus.py` — frozen 14-scenario subset.
- `benchmark/real_model_eval.py` — proposal-quality + governance-containment runner; returns
  `BLOCKED_NO_REAL_MODEL` here (`benchmark/phase3_real_model_results.json`).
- Adapter contract tests (5) over a **local fake HTTP server** — prove contract-correctness and
  fail-closed on malformed real-model-shaped output; explicitly **not** live-model evidence.

## 3. Tests & untouched code
`FACT`. **74 migration tests pass**. Legacy Agentic Framework, ActionGate, ACP, CER: **0 lines
changed**. Consequential tools remain shadow-only.

## 4. Verdicts (§14)
`FACT`.
### Real-model runtime → `BLOCKED_NO_REAL_MODEL`
No live or local model is available (no credentials, no server, HuggingFace blocked, no weights, no
usable endpoint). Reported honestly; the adapter + runner are built and contract-tested and run
unchanged when a model exists.

### Proposal quality → NOT ASSESSABLE (blocked)
No real proposals exist to measure; issuing `ACCEPTABLE`/`UNACCEPTABLE` would be fabrication. Metrics
and runner are defined and ready (`AGENT_RUNTIME_PROPOSAL_QUALITY.md`).

### Governance containment → structural boundary HOLDS; real-model containment blocked
The containment mechanism is proven input-source-agnostic (malformed/unsafe proposals — including over
a real HTTP adapter — fail closed; 0 boundary violations across all deterministic runs). Exercising it
with live-model proposals is blocked (`AGENT_RUNTIME_REAL_MODEL_GOVERNANCE.md`).

### Read-only canary → harness VALIDATED; real-model-driven canary blocked
Kill switch, budgets, cancellation, read-only enforcement, explicit-no-silent fallback all tested;
driving it with a real model is blocked (`AGENT_RUNTIME_READ_ONLY_CANARY_RESULTS.md`).

### Migration → `AGENT_RUNTIME_MIGRATION_CONTINUE`
`INTERPRETATION`. `AGENT_RUNTIME_REPLACEMENT_CANDIDATE` explicitly requires that *an actual live/local
model ran* — it did not, so that verdict is not available. The blocker is the **environment (no
model)**, not the runtime: the boundary holds, the harness is ready, and legacy rollback remains
available. **No legacy deletion is recommended.**

## 5. Phase 4 recommendation (Deliverable 16)
`INTERPRETATION`.
1. **Provide a model** by any one of: (a) set `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` (+
   `RUNTIME_MODEL_PROVIDER`/`RUNTIME_MODEL_ID`); (b) run a local **Ollama** server
   (`RUNTIME_MODEL_PROVIDER=ollama RUNTIME_MODEL_ID=qwen2.5:0.5b-instruct`); or (c) allowlist
   HuggingFace / vLLM in the environment's network policy so a small open-weight model can be pulled.
2. **Run the frozen harness unchanged** — `python -m agent_runtime_migration.benchmark.real_model_eval
   --json phase4_real.json` — and capture responses (`CaptureRecorder`) into a sanitized replay
   fixture for regression.
3. **Grade against the preregistered thresholds** (proposal quality, governance containment, canary),
   then execute the read-only canary behind the kill switch on a low-risk internal surface.
4. Only if all `AGENT_RUNTIME_REPLACEMENT_CANDIDATE` criteria are met, propose promotion — **without**
   deleting the legacy runtime (keep it as the audited rollback source).

## 6. Honest limitations
`FACT`. No live/local model available in this environment. All Phase-3 real-model verdicts that
require model output are **blocked**, not estimated. The runtime's structural safety properties (0
boundary violations, fail-closed parsing, no-bypass) remain intact and are independent of the model.
