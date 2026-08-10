# Deliverable 12 — Executive Recommendation

As CTO: publish CER as an open standard, or keep it proprietary? The tradeoffs, and a decision.

Labels: `FACT` · `INTERPRETATION` · `RECOMMENDATION` · `SPECULATION`.

---

## 1. The real decision is not binary

**INTERPRETATION.** "Open vs proprietary" is a false binary. There are three assets, and they can be licensed differently:
1. **The CER spec** (envelope, identity rule, canonicalization, operation classes, authority model, verdict contract, conformance suite).
2. **The control-plane implementation** (ActionGate's determinism, ACP's cross-domain operational safety, Context Minimization) — the hard engineering.
3. **The stewardship position** (who chairs the working group, who runs the reference control plane).

The CTO question is *which asset to open and which to keep* — the OAuth/Kubernetes/OpenTelemetry pattern: **open the spec, compete on the implementation, hold the stewardship.**

## 2. The tradeoffs

### Publish the spec openly
| Upside | Downside |
|---|---|
| Only path to *universal* adoption — buyers won't mandate a single-vendor proprietary contract (`FACT`-adjacent: Deliverable 7's demand-side thesis) | Cedes control of the contract's evolution to a working group |
| Competitors' runtimes become *emitters* into your standard — reach without building runtimes (Deliverable 7) | Competitors can also build *conformant control planes* (commoditizes the interface, not the implementation) |
| Neutral governance defeats the "vendor lock" credibility killer (T4) | Slower: standards bodies move in quarters/years |
| Defensive: pre-empts a hyperscaler defining a competing standard (T13) | Reveals the architecture publicly |

### Keep it proprietary
| Upside | Downside |
|---|---|
| Full control of evolution and monetization | **Almost certainly forfeits "universal"** — it stays a Ugence contract; hyperscalers route around it (Deliverable 7) |
| Faster iteration | The "open standard" pitchbook claim (Deliverable 11) becomes non-credible (T4) |
| Protects the specific design | A proprietary governance interface competes *against* MCP's openness — likely loses the interface war |

## 3. The decision

**RECOMMENDATION — as CTO: publish the CER *spec* openly under neutral governance; keep the *control-plane implementation* proprietary; hold the *stewardship* position.**

Concretely:
1. **Open:** the CER envelope, identity/canonicalization rules, operation-class taxonomy, authority model, verdict contract, the core domain profiles, and the compliance suite (donate the existing `fixtures/conformance_vectors.json` seed, `FACT`). Home it in **CNCF** (CloudEvents/OCI neighbor, Deliverable 9).
2. **Keep proprietary:** the *best implementation* — ACP's cross-domain non-compensatory operational safety, ActionGate's hardened enforcement, Context Minimization, the domain world-models. The spec says *what* a conformant control plane does; Ugence's implementation is *how well* it does it (the way nginx/Envoy compete on implementing open HTTP).
3. **Hold:** the working-group stewardship and the reference control plane — influence without control.

**Why this is the strongest position (technical reasoning, not preference):**
- The moat was already established (across prior milestones) to be the **Control Plane, not the runtime or the wire format** (`../execution_proposal_engine/` Deliverable 6). Opening the wire format therefore gives away *nothing that was the moat* and gains the adoption that makes the moat valuable.
- Universality is **demand-driven** (Deliverable 7): enterprises/regulators will only mandate an *open, neutral* contract. Proprietary CER cannot be mandated broadly, so it cannot be universal — which was the milestone's entire objective.
- The falsification found **no technical blocker** and **two non-technical ones** (adoption T2, governance T4). Opening the spec directly resolves T4 and materially helps T2. Keeping it proprietary resolves neither.

## 4. What I would NOT do

**RECOMMENDATION.**
- **Do not** publish it as "open" while retaining unilateral control — that is the worst of both (the T4 credibility hit without the neutrality benefit).
- **Do not** open-source the control-plane implementation — that *is* the moat; the OAuth analogy is "open spec, competitive implementations," not "give away the engine."
- **Do not** front-run the standard with universality claims before the cross-runtime conformance experiment (`../execution_proposal_universality/05`) passes — the honest claim today is "actuation-boundary equivalence, designed to be an open standard," not "the universal contract."
- **Do not** position CER against MCP — position it as MCP's missing governance layer (Deliverable 6), or risk the ecosystem picking MCP-native governance instead (T13).

## 5. Final word

**INTERPRETATION.** The milestone asked whether CER can be an open industry standard. The falsification verdict is `PARTIALLY_SUPPORTED`: *technically yes and largely pre-built; universally-adopted only if governed neutrally and pulled by enterprise/regulatory demand.* The CTO decision that turns PARTIALLY into a real bet is to **open the spec, keep the implementation, steward the standard, and let enterprise demand — not vendor persuasion — drive adoption.** That converts an architecture the repo already embodies into the one position competitors can't easily take: not the best runtime (a race Ugence is losing), and not a proprietary gate (which no one will standardize on), but **the steward of the open governance contract and the operator of its best implementation.**

**The strengthening, not mere agreement:** the standard survives falsification only if two things the design must make *non-negotiable* are enforced — **neutral governance** (or it isn't open, T4) and **mandatory credential brokering** (or it isn't governing, T7/T16). Publish with those two as hard requirements, or don't publish at all.
