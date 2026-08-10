# Agent Runtime Phase 2 — Results (Deliverable 6)

Live-model integration, legacy parity, and read-only canary. Executed AFTER the preregistration
(`AGENT_RUNTIME_PARITY_PREREGISTRATION.md`, commit `b2c542b`; fingerprints frozen at `6725ad3`). No
prompt or threshold was tuned after final aggregates. Machine-readable:
`agent_runtime_migration/benchmark/phase2_results.json`, `parity/results.json`.

Labels: `FACT` (measured) · `INTERPRETATION`.

## 1. Environment (§1)
`FACT`. No live-model credentials, no local-model runtime (no `torch`/`transformers`/`ollama`, no
`anthropic` SDK). A live/local model **cannot run** here. Used deterministic recorded-model replay +
a realistic model-shaped mock. **No live-model evidence is fabricated.**

## 2. Model integration (§12)
`FACT`. Parse success on well-formed output: **1/1**; malformed/empty/unknown-tool rejection:
**3/3** (fail closed); deterministic replay identity: **true**; model self-classification of risk and
self-authorization: **ignored** (registry + control plane decide). live_model_used: **false**;
model latency / token use: **n/a** (no live inference).

## 3. Legacy parity (§5, `parity/results.json`)
`FACT`. Shared deterministic model drives both runtimes. Decomposition agreement **16/16** (plan,
tool sequence, arguments); parity scenarios met **6/6**; governed new-side composed outcomes correct
vs preregistered **8/8**; intentional differences **10**; **unexplained regressions 0**. The only
differences are the intended governance-ownership differences (legacy governs in-runtime; new
delegates to the AI Control Plane).

## 4. Governance boundary (§12)
`FACT`. PROCEED executes exactly once; DENY / HELD_BY_ACP / PENDING_AUTHORIZATION each leave the tool
**unrun**. Composed outcomes: PROCEED / BLOCKED_BY_AUTHORIZATION / HELD_BY_ACP / PENDING_AUTHORIZATION
as preregistered. **boundary_violations = 0.** Modified action → new CER; denial not auto-retried;
cancellation + budget prevent execution (security tests, Commit B).

## 5. Canary (§12)
`FACT`. Read-only task success: **true** (2 tool calls, observation return, full trace); cancellation
via kill switch: **true** (0 calls); budget stop: **true** (0 calls); no-silent-fallback: **true**
(new-runtime failure → error, legacy NOT called); explicit audited fallback: **true**; governed tool
refused in the canary registry: **true**; **unauthorized-handler invocations: 0**.

## 6. Tests
`FACT`. **69 migration tests pass** (contracts+CER 13, runtime core 9, tools+exec 10, forbidden-import
3, compatibility 5, model integration 8, security+replan 14, parity+canary 7). Legacy runtime, CER,
ActionGate, ACP: **0 lines changed**.

## 7. Verdicts (§13)
`FACT`.
### Real-model integration → `BLOCKED_NO_REAL_MODEL`
No live or local model can run in this environment (no credentials, no model runtime). Reported
honestly; no live-model evidence fabricated. The integration machinery is built, typed, fail-closed,
and deterministic against real-model-*shaped* output; a live adapter drops in unchanged when
credentials exist.

### Legacy parity → `LEGACY_PARITY_SUPPORTED`
All PARITY scenarios agree on decomposition + tool + arguments (6/6), every governed new-side outcome
matches its preregistered value (8/8), and unexplained regressions = 0. Governance differences are
intentional (ownership boundary), not regressions.

### Canary readiness → `READY_FOR_READ_ONLY_CANARY`
Read-only-only enforced; kill switch, budget, cancellation, full trace, observation return, and
explicit-no-silent fallback all pass; unauthorized-handler invocations = 0; consequential tools remain
shadow-only via CER → ActionGate → ACP.

### Migration progression → `AGENT_RUNTIME_MIGRATION_CONTINUE`
`INTERPRETATION`. The ownership boundary holds (0 violations), legacy parity is supported, and the
read-only canary is ready — but **no live model has been exercised** (`BLOCKED_NO_REAL_MODEL`) and
governance breadth is limited to the three frozen CER profiles over shadow fixtures. That is short of
`AGENT_RUNTIME_REPLACEMENT_CANDIDATE` (which needs live-model evidence + broader parity) and well
short of any stop condition. **No legacy deletion is recommended.**

## 8. Phase 3 recommendation (Deliverable 14)
`INTERPRETATION`.
1. **Live model.** Re-run this exact preregistered harness with a live or local model (credentials or
   an on-box open-weight model). The replay/mock fixtures become the golden set to compare live output
   against; success moves the real-model verdict off `BLOCKED_NO_REAL_MODEL`.
2. **Deploy the read-only canary** behind the kill switch to a low-risk internal surface (repo search,
   doc retrieval) with the explicit legacy fallback armed; keep consequential tools shadow-only.
3. **Broaden parity** to multi-step and tool-heavy tasks and add a frozen planning-quality evaluator.
4. **Add domains/profiles** only via new CER profiles + ACP adapters (never by loosening the boundary).
5. **Do not delete the legacy runtime**; keep it as the audited fallback and rollback source until
   live-model + broader-parity evidence supports `AGENT_RUNTIME_REPLACEMENT_CANDIDATE`.

## 9. Honest limitations
`INTERPRETATION`. No live/local model (recorded replay + mock). Control plane shadow-only over
fixtures. Governed actions limited to three frozen CER profiles. Legacy governance not executed for
parity (architecturally invalid under the boundary — recorded as intentional difference).
