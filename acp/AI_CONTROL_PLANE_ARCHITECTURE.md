# AI Control Plane — Architecture Diagram (V2.2 §11.10)

The complete Ugence AI Control Plane: three frozen, independent layers on one
bound Kubernetes operation, shadow-only.

```mermaid
flowchart TD
    OC[Original Context<br/>spans: action, approvals, evidence,<br/>state + filler/history/redundant/stale/logs]
    CM["Context Minimization (REAL, frozen)<br/>compressor.compress + protect_fn<br/>preserves ActionGate- & ACP-critical spans"]
    RC[Reduced Context]
    LLM["LLM stage (deterministic reader, offline)<br/>reads proposed action from surviving spans"]
    PA[Proposed Action<br/>KubernetesOperation]
    AG["ActionGate (REAL, frozen)<br/>gate.evaluate + K8s policy<br/>is this AUTHORIZED?"]
    ACP["ACP (REAL, frozen core + cloud_controller)<br/>readiness / blast / capacity / freeze / rollback<br/>is this OPERATIONALLY SAFE now?"]
    COMP{Compose<br/>8 classes}
    HE[Hypothetical Execution<br/>eligible iff BOTH pass — never executed]

    OC --> CM --> RC --> LLM --> PA --> AG --> ACP --> COMP
    COMP -->|AUTHORIZED_AND_OPERATIONALLY_SAFE| HE
    COMP -->|BLOCKED_BY_AUTHORIZATION / HELD_BY_OPERATIONAL_SAFETY /<br/>BLOCKED_BY_BOTH / REQUEST_* / *_MISMATCH / SHADOW_ERROR| STOP[Not eligible]

    LLM -.->|critical span missing| INS[INSUFFICIENT_CONTEXT]
    PA -.->|action != what context authorized| MIS[CONTEXT_IDENTITY_MISMATCH]

    subgraph IDENTITY[Full-chain identity binding — fail closed]
      CD[context digest] --> AH[action hash] --> CI[ACP candidate identity] --> EI[execution identity]
    end
```

## Layer independence & ownership (disjoint)

```mermaid
flowchart LR
    subgraph relevance[Context Minimization]
      R[owns: what to SEE]
    end
    subgraph proposal[LLM reader]
      P[owns: what to PROPOSE]
    end
    subgraph authz[ActionGate]
      A[owns: MAY it be done?]
    end
    subgraph opsafe[ACP]
      O[owns: is it SAFE now?]
    end
    R --> P --> A --> O
    R -. never authorizes / never judges safety .-> A
    A -. never judges operational readiness .-> O
    O -. never authorizes .-> A
```

## Key properties (measured)

- **Compression:** ~72 % avg token reduction; ActionGate- and ACP-critical spans
  preserved 100 %.
- **Downstream invariance under compression:** 100 % — compressed context yields
  the identical action, authorization, and operational verdict as the full context.
- **One bound identity** from context digest to hypothetical execution; fail-closed
  on any break.
- **Disjoint ownership:** 0 duplicated-logic, 0 ownership violations.
- **Shadow-only:** 0 cluster mutations, 0 authoritative behaviour changes, fully
  deterministic.

All layers are frozen and only invoked; nothing here modifies the Context
Minimization algorithm, the ActionGate runtime, or the ACP V1 core.
