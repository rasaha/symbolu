# Execution Attempt Report — Pre-Execution Gate FAILED (no real run)

**Verdict: the shadow experiment was NOT begun. The pre-execution gate failed at
Step 1 (credential detection) and Step 2 (endpoint verification): no usable real-LLM
endpoint is reachable in this environment. Per the protocol, a stop at the gate is a
valid experimental outcome. No real-model evidence exists; none is fabricated; no
offline-stub result is substituted for real evidence.**

*Attempt timestamp context: session date 2026-07-23. Git commit at attempt:
`887cc273b507e0ac8fc459cf3782d47c269724df`.*

---

## Deliverable 1 — Credential & endpoint verification report

All probes below are **free, read-only** (no paid inference, no secrets printed). Values
are never logged; only presence and validity are reported.

| Check | Method (least-cost) | Result |
|---|---|---|
| LLM provider API keys | env presence: OpenAI, Anthropic, Google/Gemini, Azure, Mistral, Cohere, Together, Groq, Fireworks, DeepSeek, xAI, HF, OpenRouter | **all unset** |
| AWS → Bedrock | `sts:GetCallerIdentity` (free) | **invalid** — `InvalidClientTokenId` |
| AWS → Bedrock models | `bedrock:ListFoundationModels` us-east-1 / us-west-2 (free) | **invalid** — `UnrecognizedClientException` (both regions); no `AWS_SESSION_TOKEN` |
| Google → Vertex | `oauth2/tokeninfo` (free) | **invalid** — `invalid_token` |
| `ANTHROPIC_BASE_URL` present | — | This is the **Claude Code harness's own proxy/OAuth**, not a general-purpose multi-vendor API credential. Using it would misuse the agent's auth and would be single-vendor. **Excluded**, as in the prior phase. |
| Local / open-weight | import `torch`, `transformers`; `ollama` on PATH | **all absent** — no viable local execution |

**Conclusion:** zero usable inference endpoints. `resolve_adapters()` would return
`SELF_TEST` (stub) mode — which the integrity rules forbid using as real evidence.

---

## Gate checklist (pre-execution)

| Step | Requirement | Status |
|---|---|---|
| 1 | Detect provider credentials (no secret logging) | **FAILED — none usable** |
| 2 | Verify endpoint access with least-cost request | **FAILED — all invalid/absent** |
| 3 | Resolve exact model identifiers / regions | Blocked (registry has candidate IDs, but no live endpoint to bind) |
| 4 | Record aliases / immutable snapshots | Blocked (no live endpoint) |
| 5 | Verify provider pricing from authoritative metadata | Partial — registry carries provider-published prices, **flagged not-live-verified**; cannot confirm against live endpoint |
| 6 | ≥4 models / ≥2 providers / ≥3 families executable | **FAILED — 0 executable** |
| 7 | Dry-run cost estimate | Available (harness prints ~$1.36 combined worst-case at current corpus), but moot without endpoints |
| 8 | Set/enforce hard spend cap | Ready (`PILOT_MAX_SPEND_USD`, `CostGuard`) — not exercised (no spend) |
| 9 | Hash & freeze inputs | **Done** (anchors below) — these are pre-registration input hashes, **not a run manifest** |
| 10 | Run all tests | **PASS — 17/17 pilot + 15/15 phase-1 experiment = 32/32** |

Because Steps 1, 2, and 6 failed, **execution did not proceed** (Stages 1–3 not run).

### Frozen-input content hashes (SHA-256, first 16 hex) — reproducibility anchors

```
registry.json          f3e36ce9dd52098a
corpus_dev.json        ba078adaf2a338c7
corpus_shadow.json     d0aefcc04cc0e988
policy.py              883963b28fc94972
scoring.py             737dfe87b712d3dd
execute.py             19fbfc5adb41631a
advisory.py            49d12611ff7269bb
MINIMAL_FALSIFICATION_PROTOCOL.md      2a1096c1e06175f4
FALSIFICATION_PREREGISTRATION.md       847e278fcd3405bb
```

These pin the frozen experiment definition. A real run must emit a full **freeze
manifest** (Stage 2) that additionally binds live model snapshot IDs, the pricing
snapshot, adapter versions, and the resolved sample size — none of which exist without
endpoints.

---

## Deliverable coverage under the gate failure

| # | Deliverable | Status |
|---|---|---|
| 1 | Credential/endpoint verification report | **Delivered (above)** |
| 2 | Dry-run + actual cost ledger | Dry-run only; **actual = $0 (no spend)** |
| 3 | Freeze manifest | Input hashes only; **no run manifest** (no live snapshots to bind) |
| 4–10 | Raw/normalized outputs, scores, blind review, canary/drift, routing predictions, decision records | **N/A — not produced; would require real execution** |
| 11–14 | Primary stats, CIs/effect sizes, ablations, commercial analysis | **N/A — no data; producing these would be fabrication** |
| 15 | Failure analysis | **This report** — the operative failure is the credential gate |
| 16 | Falsification verdict | **UNRESOLVED — experiment not executed** (see below) |
| 17 | One primary recommendation | See below |
| 18 | Reproducibility instructions | See below |

The statistical-power correction, Stage-1 dev pilot, freeze confirmation, shadow
execution, drift controls, human review, primary analysis, ablations, commercial
analysis, and robustness checks are all **downstream of endpoints that do not exist**
and were therefore not run. Fabricating any of them is explicitly prohibited and was
not done.

---

## Falsification verdict

**UNRESOLVED.** The policy-engine hypothesis was **not tested on real models** because
the experiment could not start. This is neither a confirmation nor a refutation — it is
a blocked gate. The only established facts remain those from the prior synthetic
experiment (`../model_selection_experiment/`), whose external validity was explicitly
bounded.

## Primary recommendation (one)

The decision standard's Recommendation 3 (build a bounded governed capability) **requires
all mandatory gates to be met** — they were not, so it **cannot** be selected. No
evidence supports Recommendation 1 ("no meaningful advantage") or 4/5 either, since no
real comparison was made.

> **Interim operating recommendation: Category 2 — retain deterministic static routing —
> as the burden-of-proof DEFAULT until the pilot is executed. This is the null-prior
> default in the absence of demonstrated advantage, NOT an experimental finding. The
> definitive recommendation is DEFERRED pending a real run under the frozen protocol.**

Rationale: without evidence that the governed policy beats a static table on real models,
the simpler system is the correct default (do not build the more complex system on an
untested hypothesis). The moment credentials exist, the frozen protocol can promote or
retire this default with real evidence.

---

## Deliverable 18 — Reproducibility / how to execute when unblocked

1. Provide real credentials for ≥4 models / ≥2 providers / ≥3 families:
   `OPENAI_API_KEY` (gpt-4o, o3-mini), `ANTHROPIC_API_KEY` (haiku, claude-3-7-sonnet),
   valid AWS creds + granted Bedrock access (llama-3.1-70b). Set `PILOT_MAX_SPEND_USD`.
2. Re-verify `registry.json` pricing/context against live endpoints (Gate 5) and update
   with live snapshot IDs; re-freeze and record new hashes.
3. `cd model_selection_pilot && python3 -m pytest tests -q` (expect 17 passing).
4. `python3 harness.py` — it auto-switches to `REAL` when all adapters resolve, runs the
   dev pilot, then (after the power recalculation in `MINIMAL_FALSIFICATION_PROTOCOL.md`
   §3 and the freeze manifest) the shadow set under the cost cap.
5. Grade the three fixed-sequence contrasts against `FALSIFICATION_PREREGISTRATION.md`.
   Re-running the analysis from the stored result set must reproduce every reported
   number before any claim is published.

---

## Integrity statement

No endpoint access, output, price, cost, latency, score, or statistical result in this
report is fabricated. No offline-stub result is presented as real-model evidence. No
frozen experiment was altered. The gate failed; the experiment stopped; that outcome is
reported exactly as it occurred.
