# Agentic Framework Documentation Index

All agentic framework documentation lives under `agentic/docs/`.

---

## Getting started

| Doc | What it covers |
|-----|---------------|
| [Quickstart](QUICKSTART.md) | Prerequisites, install, first agent, API orientation |
| [First Governed Agent](FIRST_GOVERNED_AGENT.md) | Feature-by-feature build guide (streaming, tracing, approvals, budget, structured output, tool discovery) |
| [Mock → Real LLM](MOCK_TO_REAL_LLM.md) | Switch from MockLLMAdapter to OpenAI/Anthropic — what changes, what stays |
| [Goal Decomposition & Action Mapping](GOAL_DECOMPOSITION_AND_ACTION_MAPPING.md) | How prompts become governed actions — types, mapping, normalization, failure modes |
| [Examples Overview](EXAMPLES_OVERVIEW.md) | All runnable examples with recommended reading order |

## Understanding the framework

| Doc | What it covers |
|-----|---------------|
| [What Is Agentic Framework](WHAT_IS_AGENTIC_FRAMEWORK.md) | Overview and positioning |
| [Why Agentic Is Different](WHY_AGENTIC_IS_DIFFERENT.md) | Table-stakes vs differentiators |
| [Agentic Framework Guide](AGENTIC_FRAMEWORK_GUIDE.md) | Layperson-friendly guide to all 10 core components |
| [Framework Status](FRAMEWORK_STATUS.md) | What is proved, what is deferred, version history |

## Runtime and operations

| Doc | What it covers |
|-----|---------------|
| [Runtime MCP Path](RUNTIME_MCP_PATH.md) | Internal CG/MCP wiring diagram |
| [CG Runtime Runbook](CG_RUNTIME_RUNBOOK.md) | Running the `inference_mistral.py --cg` CLI |
| [Request Boundary Convention](REQUEST_BOUNDARY_CONVENTION.md) | Signal attach/omit rules for request enrichment |
| [Validation Guide (Mistral)](VALIDATION_GUIDE_MISTRAL.md) | Mistral CG adapter validation |

## Adoption pilots and validation

| Doc | What it covers |
|-----|---------------|
| [Pilot: Research Assistant](PILOT_RESEARCH_ASSISTANT.md) | First adoption pilot — tool composition + governance |
| [Pilot: Internal Copilot](PILOT_INTERNAL_COPILOT.md) | Second pilot — approval boundary clarity |
| [Pilot: Real-LLM Validation](PILOT_INTERNAL_COPILOT_REAL_LLM.md) | Third pilot — real LLM parsing, normalization, safety gate |
| [Adoption Validation Report](ADOPTION_VALIDATION_REPORT.md) | Second-developer simulation, friction analysis, cold-start verification |
| [External Developer Validation Guide](EXTERNAL_DEVELOPER_VALIDATION.md) | External trial guide — sequence, success criteria, reference links |
| [External Developer Tasks](EXTERNAL_DEVELOPER_TASKS.md) | Three concrete trial tasks for external developers |
| [External Developer Feedback Template](EXTERNAL_DEVELOPER_FEEDBACK_TEMPLATE.md) | Structured feedback form (10 sections) |
| [External Validation Checklist](EXTERNAL_VALIDATION_CHECKLIST.md) | Internal tracking sheet for validation round |

## Design decisions and architecture

| Doc | What it covers |
|-----|---------------|
| [MCP Gateway Design](DESIGN_DECISION_MCP_GATEWAY.md) | Why and how the MCP gateway was designed |
| [Proactive Scheduler Design](DESIGN_DECISION_PROACTIVE_SCHEDULER.md) | Autonomous task execution design |
| [Skill Registry Design](DESIGN_DECISION_SKILL_REGISTRY.md) | Skill discovery system design |
| [Low-Code Interface Spec](LOWCODE_DEVELOPER_INTERFACE_SPEC.md) | Design spec for future developer console (not yet built) |

### Deeper architecture docs (under `design/`)

| Doc | What it covers |
|-----|---------------|
| [Agentic LLM Framework Design](design/AGENTIC_LLM_FRAMEWORK_DESIGN.md) | Original design spec for the framework |
| [Component Deep Dive](design/AGENTIC_FRAMEWORK_COMPONENT_DEEP_DIVE.md) | Technical reference for each component |
| [Governance Architecture](design/AGENTIC_GOVERNANCE_ARCHITECTURE.md) | Post-Phase 0–4 governance rewiring |
| [Governance Fit Analysis](design/AGENTIC_GOVERNANCE_FIT_ANALYSIS.md) | Whether Symbolu qualifies as a standalone governance product |
| [Module Audit](design/MODULE_AUDIT_AGENTIC_FRAMEWORK.md) | Classification of all repo modules vs agentic framework |
| [Adaptive Prompts & Reasoning](design/ADAPTIVE_PROMPTS_AND_REASONING_WORKFLOWS.md) | ComplexityDetector, AdaptivePromptEngine, reasoning depth |

## Metrics and testing

| Doc | What it covers |
|-----|---------------|
| [Sentinel Score](SENTINEL_SCORE.md) | Framework self-assessment (7.5–8/10) |
| [Test Results](TEST_RESULTS.md) | Test coverage summary |
