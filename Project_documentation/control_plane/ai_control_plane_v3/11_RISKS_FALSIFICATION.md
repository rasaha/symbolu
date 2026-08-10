# Part 11 — Risks & Falsification

The milestone's core discipline: attempt to falsify the universal-control-plane architecture. For each candidate blocker, determine whether it is a **fundamental blocker**, a **bounded risk**, or **not a real risk**. Honest labeling; repository evidence where possible.

Labels: `FACT` (evidence) · `INTERPRETATION` · `RECOMMENDATION`. Each risk carries a severity: **FUNDAMENTAL** (kills the thesis), **BOUNDED** (real, mitigable), **NOT A BLOCKER**.

---

## R1 — Hidden runtime coupling in the decision logic → **NOT A BLOCKER**

**Falsification attempt.** Does any Control-Plane decision secretly depend on the runtime's internals?
**FACT.** Grep of the ActionGate decision path and the ACP interfaces found **zero** references to prompt/reasoning/memory/planner/reflection/model/orchestration (`gate.py:46–234`; `interfaces.py:24–180`). `gate.evaluate()` is a pure function; ACP consumes only candidate+world; ACP's `provenance` is excluded from identity (`envelopes.py:62`).
**Verdict:** the most important potential blocker was directly tested and **did not materialize.** NOT A BLOCKER.

## R2 — Prompt / reasoning dependence → **NOT A BLOCKER**

**FACT.** The Control Plane never reads a prompt or reasoning trace; ActionGate is "no AI" by design (`gate.py:5`); Context Minimization takes pre-segmented spans, not prompts (grep clean). A runtime's prompt engineering is invisible to governance.
**Verdict:** NOT A BLOCKER.

## R3 — Identity mismatch across runtimes → **BOUNDED (real, with a clean fix)**

**Falsification attempt.** Do two runtimes emitting the *same* action get the *same* governed identity?
**FACT.** No — not today. `runtime`, `model_provider`, `objective` are hashed into `action_hash` (`projection.py:44–46`), so an otherwise-identical action from LangGraph vs Ugence yields **different hashes**, breaking cross-runtime approval/evidence portability. These fields are decision-inert (control has no dependency), but identity does.
**RECOMMENDATION.** Demote the three fields to non-identity metadata (the pattern ACP already uses, `envelopes.py:62`). Then `action_hash` is a pure function of the action, and identity ports across runtimes.
**Verdict:** BOUNDED — a genuine coupling in the *identity projection*, not the *decision*, with a small, well-precedented fix. Must be done in Stage 1 (Part 10).

## R4 — Memory-architecture dependence → **BOUNDED (Context Minimization only)**

**FACT.** ActionGate/ACP have no memory dependence. Context Minimization requires ActionGate-shaped spans (`contrib`, `base`, frozen `source_type`) — a *schema* coupling, and it *silently degenerates* (vacuous guarantee) if a runtime feeds contrib-less text (`extractor.py:76–79`; audit Q6).
**RECOMMENDATION.** Do not present Context Minimization as universal context governance (Part 9). Scope it to the ActionGate pipeline; make the silent-degradation case a hard error (refuse to certify a compression whose signature is constant), so a misuse fails loud instead of vacuously "passing."
**Verdict:** BOUNDED — confined to Context Minimization; mitigated by honest scoping + a fail-loud guard. Does not block the authorization/safety spine.

## R5 — Tool-protocol incompatibility → **BOUNDED (adapter burden)**

**FACT / EXTERNAL KNOWLEDGE.** Runtimes emit tool calls in different shapes (MCP, function-calling, action groups, free-form code). The `operation` taxonomy is fixed (10 ops, `schema.py:34–38`); a free-form code executor (AutoGen) can't always map to it pre-execution.
**RECOMMENDATION.** MCP as the universal adapter (Part 3); `SIMULATE_AND_RETRY`/dry-run to classify code actions before authorizing.
**Verdict:** BOUNDED — an adapter-engineering cost, worst for closed/managed (Bedrock) and code-exec (AutoGen) runtimes. Not a Control-Plane coupling.

## R6 — Authorization ambiguity → **NOT A BLOCKER**

**FACT.** ActionGate's outcome is a closed 6-value enum; "no scalar allow score exists" (`ACP_INTERFACE_CONTRACTS.md`); decisions are deterministic and replayable. There is no ambiguity in *what* the verdict means.
**Verdict:** NOT A BLOCKER. (The *adapter* must map the verdict to a framework-native behavior, but the verdict itself is unambiguous.)

## R7 — Operational ambiguity (ACP domain gap) → **BOUNDED (principled scope, not a coupling)**

**Falsification attempt.** Can ACP govern operational safety for any runtime's actions?
**FACT.** ACP needs a per-domain `WorldStateProvider` (`interfaces.py:24–36`); it ran unchanged across robotics + cloud but each domain supplied its own world-model. A runtime acting in a domain ACP has no model for gets *no operational-safety check* (ACP abstains).
**INTERPRETATION.** This is not runtime coupling — it is the irreducible fact that "safe against live state" is undefined without a model of that state. It bounds *which actions* get operational safety, not *which runtimes* can be governed.
**RECOMMENDATION.** Build domain adapters incrementally (Part 10 Stage 3); until then, ACP fails closed (abstains rather than mis-approves).
**Verdict:** BOUNDED — a domain-coverage roadmap item, fail-closed by default. Not fundamental.

## R8 — Empirical undemonstration → **BOUNDED (the real open question)**

**FACT.** No non-Ugence runtime has driven the pipeline; both demonstrated domains use this repo's offline reader / `MockReader` (`END_TO_END_CONTROL_PLANE_SPEC.md:22–25`). Domain-independence is proven (robotics vs cloud); arbitrary-third-party-runtime independence is *permitted by construction, not demonstrated*.
**RECOMMENDATION.** The Part 7 §4 universality test on real foreign runtimes (Stage 2) is the experiment that resolves this.
**Verdict:** BOUNDED — this is the single honest reason the verdict is PARTIALLY rather than fully SUPPORTED. It is an experiment away from resolution, not an architectural blocker.

## R9 — Maturity / transport / production-readiness → **BOUNDED (productization)**

**FACT.** ActionGate transport is in-process/planned; only the K8s connector is validated; the MCP adapter is "bypassable without network+credential isolation"; everything is shadow-only, no production. The strongest deployment claim is "reference-validated on Kubernetes."
**INTERPRETATION.** These are *productization* gaps, not architecture gaps. The milestone says "optimize for long-term platform strategy, not today's implementation" — so they do not downgrade the *architectural* verdict, but they are the dominant execution risk.
**Verdict:** BOUNDED — the largest execution risk; addressed by Part 10.

## R10 — Enforcement bypass (translate-only adapter) → **BOUNDED (design discipline)**

**FACT.** An adapter that only *observes* the tool call while the runtime keeps a durable credential is monitoring, not enforcement (`ACTIONGATE_VC_BRIEF.md:39–41`). The isolated variant proved real isolation is achievable (27/27 attacks blocked) but requires the adapter to own credential brokering.
**RECOMMENDATION.** Mandate that every adapter brokers credentials (Part 3 §5); a translate-only adapter is not a supported integration.
**Verdict:** BOUNDED — a design-discipline requirement, demonstrably solvable.

---

## Falsification summary

| Risk | Severity | Blocks universality? |
|---|---|---|
| R1 hidden runtime coupling | NOT A BLOCKER | No — tested, absent |
| R2 prompt/reasoning dependence | NOT A BLOCKER | No |
| R3 cross-runtime identity mismatch | BOUNDED | No — small fix (demote provenance from hash) |
| R4 memory/schema (Context Min) | BOUNDED | No — scope Context Min honestly |
| R5 tool-protocol incompatibility | BOUNDED | No — adapter cost; MCP shortcut |
| R6 authorization ambiguity | NOT A BLOCKER | No |
| R7 operational domain gap | BOUNDED | No — fail-closed; domain adapters |
| R8 empirical undemonstration | BOUNDED | **This is why the verdict is PARTIALLY** |
| R9 maturity/transport | BOUNDED | No (architecture); yes (near-term execution) |
| R10 enforcement bypass | BOUNDED | No — adapter must broker credentials |

**INTERPRETATION — the decisive finding.** **No risk is FUNDAMENTAL.** The one risk that could have killed the thesis — hidden runtime coupling in the decision logic (R1/R2) — was directly tested against the code and found absent. Every remaining risk is either a small fix (R3), an honest scoping (R4/R7), an adapter cost (R5/R10), or the missing empirical demonstration (R8) that Stage 2 resolves. The architecture is falsifiable, was attacked, and survived — with real, bounded, named work remaining. That is the basis for a PARTIALLY_SUPPORTED verdict that is *credibly on a path to* UNIVERSAL, rather than a hopeful yes.
