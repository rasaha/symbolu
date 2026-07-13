# ActionGate — Architecture Study (documentation only)

Design/architecture study answering whether ActionGate generalizes from a Kubernetes/DevOps
authorization system into a general deterministic transaction/commit engine for autonomous AI
systems. **No production code was changed** — the study identified no concrete deficiency requiring
implementation; the gaps it found (production crypto, a formal safety model, scale evidence, a
non-cloud domain prototype) are hardening/validation work, not core changes.

Every claim is tagged **[fact]** (grounded in `action_gate_ref/` + `action_gateway/` code/tests),
**[interpretation]** (architectural reading), or **[speculative]/[gap]/evidence-required** (not yet
demonstrated).

| document | question(s) |
|---|---|
| `ACTIONGATE_ARCHITECTURAL_ABSTRACTION.md` | (1) smallest abstraction + minimal primitives |
| `ACTIONGATE_DOMAIN_GENERALIZATION.md` | (2) universal vs domain-specific; (3) ERP/banking/robotics/SaaS/agents/multi-agent |
| `ACTIONGATE_COMPARISON_MATRIX.md` | (4) vs CyberArk/Okta/AWS IAM/Boundary/OPA/LangGraph/CrewAI/OpenAI Agents SDK |
| `ACTIONGATE_TRANSACTION_ANALYSIS.md` | (6) BEGIN/VALIDATE/LOCK/PREPARE/COMMIT/ROLLBACK mapping |
| `ACTIONGATE_RESEARCH_POSITION.md` | (5) most accurate category; (7) publishable research? |
| `ACTIONGATE_EXECUTIVE_SUMMARY.md` | investor-facing summary |

## Headline findings
- **Smallest abstraction:** a pure deterministic decision function wrapped in a single-action commit
  protocol; the DevOps flavor is *data* (operation vocabulary + one fact adapter + signed policy),
  not engine.
- **Generalization:** the engine and security model are domain-free; new domains need policy + a
  fact adapter, not a new engine — except multi-action atomicity (sagas) and continuous/real-time
  control, which are genuine extensions.
- **Category:** most precisely a **deterministic action-commit protocol** whose core is an
  authorization engine; "AI Transaction Manager" is partly accurate but overstates
  locking/2PC/rollback.
- **Transactions:** BEGIN/VALIDATE/PREPARE/COMMIT map genuinely; LOCK is a commit critical-section +
  optimistic state check; ROLLBACK is atomic pre-commit abort + reversibility-aware refusal, **not**
  resource rollback.
- **Research:** a credible security/systems-security paper contingent on a formal safety model and
  production threat model; the transaction-processing paper is not yet warranted; the product
  architecture is solid today.
