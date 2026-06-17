# real_cg wiring — exact repo functions, real vs stubbed, what remains

This documents how `RealCGFeatureExtractor` (in `features.py`) extracts the four
internal governance signals — entropy, coherence, vritti, JEPA disagreement — from a
CG adapter's 32-D state, and exactly what is real vs stubbed today.

> **Status:** the real_cg extraction path is **wired and tested with deterministic stub
> state** (`make signal-gov-realcg-smoke`). This is *plumbing validation, not evidence*
> that model-internal signals improve governance.

---

## Exact repo functions used (all in `agentic/agentic_framework/`, all torch-free)

| Step | Repo symbol | File:where | Output used |
|---|---|---|---|
| 1. Forward pass → 32-D state | `StubCGLLMAdapter.call` / `MistralCGAdapter.call` | `llm_adapters.py:845` / `:510` | `adapter.last_cg_metadata` = `{state(32-D), delta_S, …}` |
| 2. metadata → engine results | `governance_inputs_from_cg_metadata(cg_metadata, tier)` | `sovereign_bridge.py:873` | `{entropy_result, vritti_result}` |
| ↳ 2a. state → entropy | `entropy_from_sovereign_state` | `sovereign_bridge.py:543` | canonical `EntropyResult` |
| ↳ 2b. state → vritti | `vritti_from_sovereign_state` | `sovereign_bridge.py:719` | canonical `ChittaVrittiResult` |
| 3. resolve entropy signal | `resolve_entropy_signal(entropy_result=…)` | `signal_adapters/entropy_adapter.py:91` | `EntropyResolution.combined_entropy`, `.available`, `.confidence_penalty` |
| 4. resolve vritti signal | `resolve_vritti_signal(vritti_result=…, layer_weights=…)` | `signal_adapters/vritti_adapter.py:67` | `VrittiResolution.distribution`, `.coherence`, `.degraded`, `.source` |
| 5. ontology layer weights | `approximate_layer_weights(...)` | `jepa_governance.py:1308` | neutral (0.5) prior for JEPA |
| 6. JEPA residual check | `safe_jepa_governance_check(...)` | `jepa_governance.py:1055` | `JEPAGovernanceAssessment.regime`, `.confidence_adjustment` |

This mirrors the gateway's own consumption path (`mcp_gateway.py:_jepa_check`, lines
~863–914), so the harness reads signals the same way production governance does.

### Signal derivation (in `features.map_resolutions_to_signals`)
- `entropy` = `EntropyResolution.combined_entropy` (higher = riskier). **Missing → fail
  closed** to `MISSING_SIGNAL_RISK = 1.0`, flagged in provenance; `strict_signals=True`
  raises `RealCGSignalError`. Never silently 0.0.
- `coherence` = `VrittiResolution.coherence` (higher = safer; inverted in `internal_risk`).
- `vritti_risk` = `viparyaya + vikalpa + nidra` from `VrittiResolution.distribution`
  (the non-grounded vritti mass; `pramana`+`smrti` are the grounded modes).
- `jepa_disagreement` = `max(regime_severity, |confidence_adjustment|/0.5)` where
  `regime_severity`: normal=0, process_drift/semantic_shift=0.5, dual_anomaly/unknown=1.0
  (unknown regime fails closed high).

---

## What is REAL vs STUBBED

**Real (in both stub and live modes):**
- The entire derivation chain in steps 2–6 — `sovereign_bridge`, the entropy engine
  (`agentic/entropy/`), the chitta-vritti engine (`agentic/chitta_vritti/`), the entropy
  and vritti signal adapters, and the JEPA residual governor — is the **actual repo code**.
  None of it is reimplemented in the harness; the harness only orchestrates and maps.
- Fail-closed semantics and provenance tagging are real and tested.

**Stubbed (in `--real-cg-stub` / `use_stub=True`):**
- **The 32-D state itself.** `StubCGLLMAdapter` returns a **fixed, hand-picked fixture**
  (`llm_adapters.py:836`, `STATE_PROVENANCE="deterministic_stub"`) on every `call()`,
  regardless of the prompt. So the derived signals are **constant across scenarios** and
  cannot discriminate safe from unsafe. This is why a stub run shows
  `AUROC(C4) == AUROC(C3)` and the report is marked *plumbing validation, not evidence*.
- **`text_confidence`** is a neutral placeholder (`0.5`); the stub `MockLLMAdapter` cannot
  self-report. A real model elicits this from its text output.

**Observed deterministic stub outputs** (the wiring-contract snapshot in
`tests/test_realcg_smoke.py::test_realcg_stub_snapshot_values`): entropy≈0.119,
coherence=0.5, vritti_risk=1.0 (nidra-dominant fixture), jepa_disagreement=0.5
(process_drift regime).

---

## What remains before running against a real checkpoint

1. **Provide a real CG adapter.** Swap `StubCGLLMAdapter` for `MistralCGAdapter` with a
   checkpoint: `--mode real_cg --checkpoint <path>` (no `--real-cg-stub`). Requires
   `torch` + the model weights + the `symbolu_training` wrapper. Everything downstream of
   the adapter is unchanged.
2. **Per-scenario forward passes.** With a real model the state varies per decision point,
   so the internal signals become discriminative. Confirm `extract` builds a sensible
   decision-point prompt (`features._decision_prompt`) for your model's chat format.
3. **Cache + analyze.** Real forward passes are expensive. `--mode real_cg` **auto-writes a
   reusable `features.jsonl`** into `--out` (disable with `--no-cache-write`); the schema is
   identical to `--mode cached`, so re-run analysis offline with
   `--mode cached --features <out>/features.jsonl` for fast, deterministic, metric-identical
   iteration (provenance `real_cg:<…>` is carried into the replay).
4. **Real text-level confidence.** Replace the `0.5` placeholder by eliciting a
   self-reported safety confidence from the model's text output (so C3 is a fair
   text-level baseline).
5. **Full balanced benchmark + held-out split + weight fitting.** Wire AgentDojo /
   InjecAgent (`dataset.load_external`), fit C3/C4 weights on a TRAIN split (and keep the
   zero-tuning variant), then judge against the pre-registered success/failure criteria in
   `../../AGENTIC_FRAMEWORK_SIGNAL_GOVERNANCE_EXPERIMENT.md`.

Only after steps 1–5 does a result constitute evidence about model-internal signals.
