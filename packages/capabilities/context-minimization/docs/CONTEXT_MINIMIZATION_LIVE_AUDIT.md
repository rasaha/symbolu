# Context Minimization — Live Audit

**Phase:** independent packaging + boundary hardening + behaviour verification.
**Not** H22, not an ActionGate redesign, not a new compression-research / LLM-training /
real-model-benchmark / execution phase.

## 1. Verified live state (before any change)

| Fact | Value |
| --- | --- |
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default HEAD | `9496fcf25321dcf1bbfa9a27c19917f34295da16` |
| Working branch | `claude/package-context-minimization-independently-8798ac` (started at default HEAD) |
| PR #1290 | **MERGED** 2026-08-02T17:57:16Z; merge commit `9496fcf2` (= current HEAD); base `a34f4399`; head `1aa601c5` |
| Governance Contracts hardening | present on the default branch (PR #1290 is exactly that merge) |

The default branch contains the merged Governance Contracts hardening; this work
branches from that exact HEAD.

## 2. Where Context Minimization lives (discovered)

- **Sole real implementation:** `experiments/actiongate_context_ablation/`
  (`actiongate_context_ablation/compressor.py` — `compress` + `structural_compress`;
  `units.py`; `adapter.py` + `extractor.py` = the ActionGate oracle;
  `protected_detector.py` = a trainable detector; plus a large benchmark/corpus/
  real-model harness and frozen `results/`).
- **VC brief:** `CONTEXT_MINIMIZATION_VC_BRIEF.md` (claims cross-checked in §8).
- **Two runtime code consumers**, both via fragile `sys.path.insert`:
  - `ugence_console_api/capabilities/context_gateway.py` — **structural dedup only**,
    no oracle.
  - `robotics_reliability_bench/acp_control_plane/context_pipeline.py` — **full**
    `compress(...)` with the signed **ActionGate policy** as the oracle.
- **CER v0.1/0.2/0.3 control planes:** reference `context_minimization` only as a
  **string status field** (`"APPLIED"` / `"SKIPPED_NO_ACTIONGATE_CONTEXT"`) — no code
  dependency.
- **No existing independent distribution.** No `pyproject.toml`/`setup.py` names context
  minimization anywhere; the experiment has no packaging and is imported purely by path
  injection. `packages/capabilities/` already hosts `action-clearance`,
  `decision-authority`, `model-selection`, `storygraph` — establishing the target
  convention, with **no** `context-minimization` yet.
- **No competing implementation.** Searches for context compression / pruning / gateway
  / semantic filtering / protected-span filtering / token-budget reduction / retrieval
  filtering / context admission returned only **name collisions** in unrelated domains
  (candidate-text filters in `symbolu_core/providers/**`, KV/edge quantization in
  `simulator/` and `CTM_plus/`, agent token-budget accounting in `agentic/`). The
  `token_compression/` directory is a **docs-only** research workspace ("ContextGuard"),
  no importable code.

Full classification: `artifacts/context_minimization_ownership_matrix.json`.

## 3. Primary verdict

**`INDEPENDENT_EXTRACTION_REQUIRED`** (primary).

Secondary verdicts that also apply and are addressed here:
- **`ALGORITHM_CONTRACT_CONFLICT_FOUND`** — the prototype's `structural_compress` accepts
  `protected_ids` but **ignores** them (a protected duplicate could be removed), and its
  equivalence `signature()` is an unstable `repr()`-based tuple over ActionGate internals.
- **`BOUNDARY_HARDENING_REQUIRED`** — consumers reach the implementation via `sys.path`
  hacks; the implementation hard-depends on out-of-tree `cyber_security/action_gate_reference`.

## 4. Package extraction decision

Create a clean, stdlib-only leaf at `packages/capabilities/context-minimization/`:

- distribution `ugence-context-minimization`, namespace `ugence_context_minimization`,
  version `0.1.0`, contract version `1.0.0`, `requires-python >=3.10`, `src` layout,
  `py.typed`, zero runtime dependencies.
- Two explicit modes: **structural** (`structural_minimize` / `deduplicate_context`,
  no oracle) and **oracle-verified** (`minimize_context`, requires a neutral oracle).
- A neutral `InvarianceOracle` protocol; **no ActionGate import in the core**.

## 5. Canonical ownership boundary

**Owns:** immutable context/unit models; context + span identity; structural dedup;
protected-span masks; extractive keep/drop selection; deterministic budget policy;
neutral invariance-oracle interface; equivalence-key comparison; span restoration;
full-context fallback; minimization results; provenance + fingerprints; deterministic
reason codes; error taxonomy; audit-friendly keep/drop records.

**Does not own:** context admission; evidence admissibility; enterprise policy;
ActionGate authorization; Action Clearance; Decision Authority; TAP; governance
authority; LLM reasoning; summarization/paraphrasing; retrieval; model routing; Agent
Runtime; provider execution; credentials; external systems; agent planning/memory.

## 6. Two minimization modes (preserved distinction)

- **Mode A — structural** (`structural_minimize`): structurally-lossless removal of exact
  duplicates / declared redundancy sets. No oracle. Narrower than full Context
  Minimization (documented as such; not called authorization-preserving).
- **Mode B — oracle-verified** (`minimize_context`): protected-mask → extractive select →
  oracle verify → restore → fallback. Requires a neutral oracle; never operates without
  one while claiming equivalence preservation.

## 7. Neutral oracle design & ActionGate outcome

The core depends on `InvarianceOracle.evaluate(context, *, evaluation_time) ->
OracleEvaluation`. `OracleEvaluation` carries an **opaque** `equivalence_key`, `oracle_id`,
`contract_version`, and optional `evaluation_ref` / `correlation_id` / `valid_until` /
`reason_codes` / `metadata`. The core compares keys by equality and never interprets
them. A concrete **ActionGate adapter is deferred** to a later integration phase and will
live outside the core; the frozen experiment retains its own ActionGate oracle. See
`artifacts/invariance_contract.json` and `docs/INVARIANCE_CONTRACT.md`.

## 8. Guarantee boundary, evidence status & claims discipline

- Package maturity: **`IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED`** (upgrade to
  `IMPLEMENTED_AND_CI_VERIFIED` only after the scoped Actions run is observed green).
- Algorithm evidence does **not** transfer automatically from the VC brief. Verified
  against repo artifacts: frozen fingerprint `sha256:ac4e0692…`; compressor bench
  `LIMITED_GO`, max removable ≈ **0.6596**, 100% decision-invariance & protected recall
  at every budget (deterministic gate); real-model `CONSISTENT_REPLICATION` over **n=3**
  (Qwen2.5-7B, Qwen2.5-14B, Mistral-7B); **Llama-3.1-8B / Gemma-2-9b NOT run**; detector
  held-out recall/precision reach 100% **only via the fail-closed hybrid**. Corpus is
  authored-synthetic / naturalistic. **No live-enterprise validation** (the brief itself
  disclaims it). The canonical package's own guarantee is `SYNTHETICALLY_VALIDATED`.
- Do not describe historical benchmark evidence as live-enterprise evidence.

## 9. Frozen-evidence disposition

The experiment's `results/**` (fingerprint, corpus manifest, Qwen/Mistral result dirs,
plots), `test_frozen_invariance.py`, corpus, harnesses, detector-training, and RunPod
scripts are **preserved bit-for-bit and NOT rewired**. A compatibility test asserts the
experimental compressor does not import the canonical package, so the frozen path cannot
silently drift. Migrating the experiment onto the canonical core is intentionally
**deferred** to protect the frozen fingerprints.

## 10. Consumers & migration

See `artifacts/context_minimization_consumer_matrix.json` and `docs/COMPATIBILITY.md`.

- **Console (Outcome A — migrated):** now imports `ugence_context_minimization`
  (structural mode); `sys.path` hack removed. One hardening: protected duplicates are
  now retained. Parity proven by the compatibility test + the unchanged governed-loop test.
- **Robotics bench (Outcome C — coexistence):** full ActionGate-oracle path; left frozen.
- **CER v0.1/0.2/0.3 (not a consumer):** string status field only; untouched.

## 11. Protected-span contract (v1)

A protected unit is never removed by any stage; dedup applies only to unprotected units;
two protected duplicates are both retained. Uncertainty retains. This corrects the
prototype's ignored-`protected_ids` bug. See `docs/PROTECTION_CONTRACT.md`.

## 12. Invariance-signature: current vs corrected

- **Current (experiment):** `signature()` built from `repr()` of ActionGate envelope +
  decision outputs, computed inside the compressor — unstable, non-versioned, coupled.
- **Corrected (canonical):** the oracle returns a canonical, versioned, **opaque** key;
  the reducer compares equality only and imports no ActionGate. The experiment keeps its
  own signature (frozen); the canonical contract does not broaden equivalence.

## 13. Fidelity & migration

Function-by-function comparison: `artifacts/context_minimization_fidelity_matrix.json`.
Highlights — structural dedup: `PRESENT_HARDENED`; extractive selection:
`PRESENT_EQUIVALENT`; equivalence signature: `PRESENT_CHANGED`; detector:
`INTENTIONALLY_EXCLUDED`; ActionGate adapter: `ACTIONGATE_ADAPTER_ONLY`;
benchmark/corpus/real-model/RunPod: `EXPERIMENT_ONLY`.

## 14. Work explicitly deferred

- A packaged ActionGate `InvarianceOracle` integration adapter.
- Migrating the robotics bench / the experiment onto the canonical core.
- A `protected_equivalence_group` v2 contract.
- Any real-model benchmark rerun (not required, not authorized this phase).
- H22 — unrelated, **not implemented**.
