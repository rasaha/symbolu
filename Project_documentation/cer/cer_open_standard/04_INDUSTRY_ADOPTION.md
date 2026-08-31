# Deliverable 7 — Industry Adoption

Could OpenAI, Anthropic, Google, Microsoft, AWS, LangChain, CrewAI, AutoGen, Semantic Kernel, and Claude Code adopt CER? What would stop them? This is the deliverable where the "universal" claim is most at risk (falsification TF2).

Labels: `INTERPRETATION` · `RECOMMENDATION` · `SPECULATION` · `EXTERNAL KNOWLEDGE` (all vendor incentives are inference, not fact; verify against actual positions).

---

## 1. Adoption is two different asks

**INTERPRETATION.** "Adopt CER" means different things for two groups:
- **Runtime/framework vendors** (LangChain, CrewAI, AutoGen, Semantic Kernel, Claude Code, OpenAI/Google/MS *SDKs*): adopt = *emit* CER at their tool boundary (write/ship an adapter). Low technical cost (Deliverable 5); the question is *why they would*.
- **Platform/governor vendors** (AWS, Microsoft, Google, OpenAI/Anthropic *as platforms*): adopt = *consume* CER as their governance interface, or ship a *competing* one. High strategic stakes; they'd rather own the interface.

The standard succeeds only if the first group emits and *someone* (Ugence, an enterprise, or a neutral CP) consumes — the governor need not be a hyperscaler.

## 2. Per-vendor adoption assessment

| Vendor | Would they emit/consume CER? | What would stop them (EXTERNAL KNOWLEDGE / SPECULATION) |
|---|---|---|
| **OpenAI** | *Emit:* plausible via the Agents SDK if enterprise customers demand governance. *Consume/endorse:* unlikely — prefers its own platform primitives. | Strategic preference to own the stack; little incentive to endorse a competitor-stewarded governance layer. |
| **Anthropic** | *Emit:* **Claude Code already has the seam** (PreToolUse hooks, permission modes) — an adapter is natural; MCP is Anthropic-originated and is CER's transport. | Would likely prefer governance expressed via MCP-native mechanisms; endorsement depends on neutrality. Closest to "already does the pattern." |
| **Google** | *Emit:* ADK has clean tool callbacks + MCP; technically easy. | Cloud-platform preference to bundle governance with GCP; would weigh its own offering. |
| **Microsoft** | *Emit:* Semantic Kernel function filters + AutoGen; technically easy. | Azure/Copilot governance strategy; may prefer Entra-integrated controls. Note: `FACT` — the repo's own ActionGate brief positions against "Entra answers *who are you*; ActionGate answers *should this action run*." |
| **AWS** | *Consume:* **least likely** — Bedrock + IAM is an adjacent, competing governance stack; return-control exists but AWS would rather own the gate. | Direct strategic conflict; AWS builds its own. This is the clearest "no." |
| **LangChain / LangGraph** | *Emit:* **likely** — open-source, framework-not-platform, benefits from an external governance layer its enterprise users demand. | Little to lose; wants ecosystem breadth. A probable early adopter. |
| **CrewAI** | *Emit:* **likely** — same logic; small vendor, governance is not their business. | Adapter effort only. |
| **AutoGen** | *Emit:* **partial** — structured tools yes; code-exec needs lower interception (FF2). | Technical (opacity), not strategic. |
| **Semantic Kernel** | *Emit:* **likely** — function-invocation filters are a natural seam; MS may or may not endorse. | Endorsement is a Microsoft-strategy question; the SK community could adopt regardless. |
| **Claude Code** | *Emit:* **most natural** — already separates propose/govern; hooks are the adapter. | Mostly a question of whether Anthropic standardizes the seam or keeps it product-internal. |

## 3. The pattern (and the honest conclusion)

**INTERPRETATION.**
- **Open-source framework vendors (LangChain, CrewAI, AutoGen, Semantic Kernel community, Claude Code)** are *plausible-to-likely emitters* — low cost, and governance isn't their moat, so an external standard *helps* their enterprise adoption.
- **Hyperscalers and frontier platforms (AWS, and to varying degrees OpenAI/Google/Microsoft as platforms)** are *unlikely to endorse* a governance standard they don't control; several will ship competing governance (AWS most clearly).
- **Therefore "universal adoption by every listed vendor" is unlikely** (TF2 confirmed). The realistic outcome is **partial adoption**: the framework layer emits CER; the governor layer fragments (Ugence + neutral CPs + hyperscaler-proprietary).

## 4. What actually drives adoption (the lever that matters)

**RECOMMENDATION.** Vendors do not adopt governance standards because they are elegant; they adopt them when a **buyer with leverage requires it**. The adoption engine for CER is therefore **enterprise + regulatory demand**, not vendor persuasion:
- A regulated enterprise mandating "every agent action must emit a governable request our control plane can authorize" forces its *chosen* runtimes to emit CER — pulling framework vendors in through the buyer, not the vendor.
- Emerging AI-governance regulation (the EU AI Act direction, sectoral rules in finance/healthcare — `EXTERNAL KNOWLEDGE`) creates the "ungoverned agents are unshippable" pressure that OAuth/PCI-DSS-style mandates created for their standards.

**INTERPRETATION.** This reframes the whole adoption question: CER's path to becoming a standard is **demand-side (enterprises/regulators), not supply-side (vendors)** — exactly like OAuth spread through service providers needing delegated auth, not through a vendor evangelizing a format. The `RECOMMENDATION` in Deliverable 12 follows from this: publish it openly and neutrally so *buyers* can mandate it without vendor lock, because a buyer will not mandate a single-vendor proprietary contract.

## 5. What would stop CER entirely (the kill conditions)

**SPECULATION, labeled.**
- **A hyperscaler ships a "good enough" bundled governance layer** before CER reaches neutral-standard status — buyers take the bundled option.
- **MCP absorbs governance** into its own spec — CER becomes redundant as MCP-native.
- **No enterprise/regulatory forcing function materializes** — then no one makes vendors emit, and CER stays a Ugence contract (still useful, not universal).

The first two are the reason **speed to a neutral standard body + an MCP-complementary posture** (Deliverables 9, 6) are strategically urgent, not optional.
