# Limitations & claims discipline

## What this package is

- **Extractive only.** Retain / remove / restore / fall back. Never rewrite,
  paraphrase, summarize, or synthesize.
- **Equivalence-preserving *relative to the supplied oracle*.** The guarantee is
  exactly as strong as the oracle you inject. The package creates no authorization.
- **Structurally lossless** for verified exact duplicates / declared redundancy sets
  (structural mode only).

## What this package is not

- Not context admission, evidence admissibility, or enterprise policy.
- Not ActionGate, Action Clearance, Decision Authority, TAP, or any governance
  authority. ActionGate is an *optional* concrete oracle integration that lives
  outside this package — not a core dependency.
- Not summarization, paraphrasing, retrieval, embeddings, or model routing.
- Not execution or enforcement.
- **Not H22** multi-workflow orchestration. H22 is unrelated and not implemented here.

## Package maturity

`IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` — the package builds, installs into a clean
`--no-index` venv, and passes its suite + isolated demo locally. Upgrade the claim to
`IMPLEMENTED_AND_CI_VERIFIED` only after observing the scoped GitHub Actions run green
(URL in the PR body).

## Algorithm-evidence classification

This is a **packaging / boundary-hardening / behaviour-verification** phase, not a new
research phase. The canonical package's own guarantees are `SYNTHETICALLY_VALIDATED`
(deterministic unit tests against fake oracles).

Historical algorithm evidence lives with the frozen experiment and does **not** transfer
automatically to this package:

- `FROZEN_BENCHMARK_VALIDATED` — the experiment's frozen naturalistic benchmark
  (`compressor_results.json`, recommendation `LIMITED_GO`, max removable ≈ 66%, 100%
  decision invariance & protected recall at every budget on the deterministic gate).
- `REAL_MODEL_VALIDATED (n=3)` — Qwen2.5-7B, Qwen2.5-14B, Mistral-7B
  (`CONSISTENT_REPLICATION`). Llama-3.1-8B / Gemma-2-9b were **not** run.
- `LIVE_ENTERPRISE_NOT_VALIDATED` — the corpus is authored-synthetic / naturalistic;
  there is **no** real customer data and **no** live-enterprise validation.

Quantitative figures (32–50% typical / ~66% max token reduction; detector held-out
recall/precision to 100% *via the fail-closed hybrid*; 1.3–2.6% decision flips by a
protection-unaware control) are the **experiment's** frozen numbers, verified against
its artifacts. Do **not** present them as this package's production evidence, and do not
describe any of it as live-enterprise validation.

## Token accounting (CM-TA1) limitations

- **No provider tokenizer.** The bundled `DefaultApproximateRequestCounter` is a
  word/punctuation approximation (`DEFAULT_APPROXIMATE`), never exact provider
  tokenization. Exact counts require an injected `RequestTokenCounter` from outside.
- **No cost / no invoice.** No price is computed and no billing figure is claimed; that
  needs an explicit, versioned external pricing source. Provider-reported usage is
  authoritative only for the API response reconciled — it is **not** invoice reconciliation.
- **No persistence.** The core defines the `TokenAccountingSink` protocol and an
  in-memory reference only; durable storage is an external concern.
- **Ghost tokens are surfaced, not eliminated.** Failed/exception attempts with unknown
  usage are recorded as `UNAVAILABLE_*` (never zero); the summary reports the gap
  (`complete = False`). The package does not *guarantee* complete elimination of unmeasured
  ("ghost") token consumption — it makes gaps auditable.
