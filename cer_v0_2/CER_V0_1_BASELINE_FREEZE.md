# CER V0.1 Baseline Freeze (Deliverable §1)

CER V0.1 is the frozen baseline. No V0.1 artifact may be silently rewritten; any
correction is a versioned additive clarification, a backward-compatible erratum,
or a declared V0.2 profile change. V0.2 lives entirely in `cer_v0_2/` and reuses
the frozen ActionGate v2 identity profile + ACP core **unchanged**.

Labels: `FACT` (measured this milestone).

## Fingerprints (sha256[:16], commit `14a7a7e`)
```
cer_v0_1/spec.py                              085614f8d40d128e
cer_v0_1/cer_v0_1.schema.json                 41ca69d40149339c
cer_v0_1/conformance/vectors.json             3ec7f36d741f6302
cer_v0_1/producers/langgraph_adapter.py       b36eebd7b656ff7e
action_gate_ref/projection.py (v2 profile)    ce458712e7643a27
action_gate_ref/hashing.py                    4a9268ba7e4238ad
action_gate_ref/canon_profile.py              5408ce8ed032dd73
cloud/adapter.py (ACP)                         8d334746b7161804
cloud/composition.py (ACP)                     b810e2f0c3bc0e28
cloud/envelopes.py (ACP)                       e4e7e9362de04dd7
```

## Baseline results (re-verified)
`FACT`. V0.1 + ActionGate suites still green at this commit: **218 passed** (195 ActionGate incl. the 12 v2-profile tests + 23 CER V0.1). V0.1 conformance vectors unchanged (fingerprint `3ec7f36d`).

## What V0.2 will and will not touch
`FACT` / plan:
- **Will not modify:** `cer_v0_1/` (frozen), the ActionGate v2 identity profile, the ACP cloud core, Context Minimization.
- **Will add (in `cer_v0_2/`):** the envelope+profile architecture, `kubernetes.scale.v1` (identity-equivalent to V0.1 scale for the same actuation), the new `kubernetes.rollout.v1` profile, a second real runtime adapter (OpenAI Agents SDK), and the multi-runtime conformance machinery.
- **Reuses unchanged:** ActionGate `identity_profile="v2"`; ACP `CloudShadowAdapter` (which already supports `CloudOperation.ROLLOUT`).

## Selected second runtime (evidence)
`FACT`. Environment probe (preference order):
- OpenAI Agents SDK — initial install blocked by a system-package RECORD conflict; **installed cleanly with `--ignore-installed`; `openai-agents==0.18.2` imports (`from agents import Agent, Runner`).** Verified the **real `Runner` loop executes** with a deterministic model stub and the runtime **genuinely creates a `ResponseFunctionToolCall` / `ToolCallItem`** intercepted before actuation. **SELECTED.**
- Google ADK, CrewAI — install failed (PyYAML RECORD conflict).
- AutoGen (`autogen-agentchat==0.7.5`) — installs/imports (available fallback).
- Semantic Kernel — install failed (pybars4/PyMeta3 wheel build).

Selection: **OpenAI Agents SDK 0.18.2** (highest-preference runtime that installs and exercises its real pre-tool boundary without a live model API). Not `BLOCKED_NO_SECOND_RUNTIME`.

## Selected second profile
`FACT`. **`kubernetes.rollout`** (preferred). Materially distinct from scale: identity-bearing fields absent from scale — image/manifest digest, rollout strategy, maxSurge, maxUnavailable, rollback reference, timeout. ACP supports it natively (`CloudOperation.ROLLOUT`), so no ACP change is required.
