# Pilot Status — Empirical Phase BLOCKED on Credentials

**Status: the real-model shadow pilot is fully built and one command from running,
but NO real model could be executed in this environment. Per the workstream's own
instruction, no real-model results are fabricated. The harness was validated with a
deterministic offline stub (self-test); the empirical question remains OPEN.**

---

## What was checked (credential + capability probe)

| Probe | Result |
|---|---|
| LLM provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`, `AZURE_OPENAI_API_KEY`, `MISTRAL/COHERE/TOGETHER/GROQ`, `HF_TOKEN`) | **all empty/unset** |
| AWS credentials → Bedrock | `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` present but **invalid for AWS API** — STS `GetCallerIdentity` returned `InvalidClientTokenId`; Bedrock `ListFoundationModels` returned `UnrecognizedClientException` in us-east-1 and us-west-2. No `AWS_SESSION_TOKEN`. Likely infra-scoped, not inference creds. |
| Google `CLOUDSDK_AUTH_ACCESS_TOKEN` → Vertex | token present but **invalid** — `oauth2/tokeninfo` returned `invalid_token`. |
| `ANTHROPIC_BASE_URL` | present, but it is the **Claude Code harness's own proxy/OAuth**, not a general-purpose multi-vendor API credential; using it would be (a) misuse of the agent's auth and (b) single-vendor, defeating a heterogeneous pilot. Not used. |
| Local / open-weight execution | `torch`, `transformers`, `ollama` **all absent**; no `aws` CLI. A local pilot would need heavy installs + multi-GB weight downloads over a restricted proxy, and one tiny local model is not a heterogeneous 3–5-model pilot. Not viable here. |

**Conclusion:** no usable path to executing real models. The pilot therefore ran in
`SELF_TEST` mode (deterministic stub), which validates the harness but produces **no
real-model evidence**.

> Note: `resolve_adapters()` reports the Bedrock (`open_weight`) adapter as
> "available" because `BedrockAdapter.available()` only checks credential *presence*
> + `boto3` import — it cannot prove the creds are valid or that model access is
> granted. The probe above proves these AWS creds are in fact invalid. Because 4 of 5
> models still lack keys, the harness correctly stays in `SELF_TEST` mode.

---

## What is delivered and ready (blocked-branch deliverables)

All non-execution deliverables are complete, isolated (no production imports), and
tested (`python3 -m pytest tests -q` → 17 passing):

1. Isolated pilot package (`model_selection_pilot/`).
2. Verified model registry with per-field provenance + `date_verified` +
   `verification_status` (`data/registry.json`, `registry.py`).
3. Versioned document-intelligence corpus, dev/shadow split (`data/corpus_*.json`).
4. Routing policies incl. the mandated **F1 (soft-quality) vs F2 (hard minimum-quality
   gate)** correction (`policy.py`).
5. All routing arms A–E, F1, F2, G (`arms.py`, `policy.py`).
6. Execution adapters — Anthropic / OpenAI / Bedrock (proxy-aware, ready-to-run) +
   deterministic stub (`provider.py`).
7. Cost guard: dry-run, worst-case, hard cap, per-call abort (`costguard.py`).
8. Full counterfactual runner: run every eligible model on every task, capture raw,
   validate schema, score, record latency/cost/retries (`execute.py`).
9. Deterministic scoring framework, rule-based per class, no LLM judge (`scoring.py`).
10. Regime-gated telemetry snapshots (cold/partial/mature) (`telemetry.py`).
11. Metrics incl. commercial comparison vs strongest-eligible (`metrics.py`).
12. Decision records + consistency check; raw and normalized result stores separated
    (`results/raw/`, `results/normalized/`).

## How to UNBLOCK and run for real

```bash
export OPENAI_API_KEY=...        # medium_general (gpt-4o), strong_reason (o3-mini)
export ANTHROPIC_API_KEY=...     # fast_small (haiku), long_context (claude-3-7-sonnet)
# and valid AWS creds + granted Bedrock access for open_weight (llama-3.1-70b)
export PILOT_MAX_SPEND_USD=5.00  # hard cap; harness aborts before exceeding
cd model_selection_pilot
python3 registry.py && python3 build_corpus.py
python3 harness.py               # resolve_adapters flips to REAL when all 5 keys resolve
```

Before real spend the harness prints a dry-run estimate and worst-case (currently
**~$1.36 combined worst-case** for dev+shadow at 2 retries) and enforces the cap.

**Re-verify** `registry.json` pricing/context against live endpoints first — the
shipped values are provider-published (not live-verified in this sandbox) and stamped
`verification_status: published-docs-not-live-verified`.
