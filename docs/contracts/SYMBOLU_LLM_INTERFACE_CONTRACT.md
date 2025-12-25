# Symbol-U LLM Interface Contract

## Document Metadata

| Field | Value |
|-------|-------|
| Contract ID | SYMBOLU-LLM-001 |
| Version | 1.0.0 |
| Status | SPECIFICATION |
| Created | 2025-12-18 |
| Depends On | Phase-8A (Rendering), Phase-7 (Targeted Generation) |

---

## 0. Purpose

Define a **one-way authority boundary** between:

- **Symbol-U Core (Deterministic Authority)**: validity, structure, constraints, governance
- **LLM Layer (Optional Renderer/Presenter)**: language realization only, within a provided envelope

This contract enforces:
1. No hallucination of structure
2. No override of constraints
3. No upstream feedback
4. All violations are detectable in CI

---

## 1. Non-Negotiable Architectural Principle

> **Symbol-U is the authority on truth/structure. The LLM is never an authority.**

### 1.1 Authority Rules

- The LLM may only operate on explicit inputs provided by Symbol-U
- The LLM must not introduce:
  - New tokens / varnas
  - New ontological layers
  - New constraints
  - New "meaning" fields
  - Any fabricated provenance

### 1.2 The Asymmetry Principle

```
Symbol-U encodes structure and constraint, not meaning.
LLM encodes meaning and fluency, not structure.

These domains do not overlap.
Authority flows one direction only: Symbol-U → LLM
```

This principle is already enforced in Phase-8A rendering. This contract generalizes it to any LLM integration point.

---

## 2. Interface Overview

### 2.1 Data Flow (Single Direction)

```
User Input
  → Symbol-U (parse/validate/derive envelope)
  → LLM (optional rendering)
  → Output to user

No LLM output may flow back into Symbol-U's state or decision-making.
```

### 2.2 Architectural Position

```
Phase-4A → Phase-6 → Phase-7 → Phase-8A (Rendering)
(ontology)  (compose) (target)      ↓
                                    ↓
                        ┌───────────────────────┐
                        │ SYMBOLU-LLM INTERFACE │
                        │                       │
                        │  Symbol-U provides:   │
                        │  • Validity envelope  │
                        │  • Authoritative data │
                        │  • Provenance         │
                        │                       │
                        │  LLM receives:        │
                        │  • Constrained input  │
                        │  • Render hints       │
                        │  • Mode selection     │
                        └───────────┬───────────┘
                                    │
                                    ▼
                              LLM Renderer
                          (language realization)
```

---

## 3. Contract Entities

### 3.1 RenderRequest (Symbol-U → LLM)

The **ONLY** allowed input type to the LLM layer.

```json
{
  "contract_version": "1.0.0",
  "request_id": "uuid",
  "mode": "minimal|standard|regulated",
  "envelope": {
    "allowed_layers": ["O5_COGNITION", "O3_EXECUTION", "..."],
    "allowed_tokens": ["ka", "a", "ga", "..."],
    "allowed_templates": ["CVC", "CCV", "..."],
    "constraints": {
      "must_start_with": "consonant",
      "max_len": 12,
      "must_include_events": ["reset", "modulate"],
      "target": {
        "final_magnitude_min": 1.20,
        "final_magnitude_max": 1.55,
        "trajectory_shape": "monotone_non_decreasing|any",
        "quota": 10
      }
    }
  },
  "authoritative_payload": {
    "phase7_results": [
      {
        "sequence": ["ka", "a", "ka"],
        "trajectory": {
          "steps": [
            {"i": 0, "token": "ka", "event": "reset", "magnitude": 1.0},
            {"i": 1, "token": "a", "event": "modulate", "magnitude": 1.1},
            {"i": 2, "token": "ka", "event": "reset", "magnitude": 1.0}
          ],
          "final_magnitude": 1.0
        },
        "provenance": {
          "phase4a_hash": "sha256:...",
          "phase6_ruleset_id": "phase6_v1",
          "phase7_contract_id": "phase7_target_contract_v1.1"
        }
      }
    ],
    "render_hints": {
      "style": "neutral",
      "format": "bullet|paragraph|json",
      "max_words": 180
    }
  },
  "forbidden_access": ["score", "rank", "search_trace", "policy_internal"]
}
```

### 3.2 RenderResponse (LLM → Symbol-U)

The **ONLY** allowed output type from the LLM layer.

```json
{
  "contract_version": "1.0.0",
  "request_id": "uuid",
  "renderer_id": "llm_renderer_v1",
  "outputs": [
    {
      "modality": "text",
      "format": "plain_text|markdown|json",
      "content": "..."
    }
  ],
  "assertions": {
    "no_structure_added": true,
    "no_constraints_modified": true,
    "no_new_tokens_introduced": true
  }
}
```

---

## 4. Responsibilities

### 4.1 Symbol-U MUST

| Responsibility | Description |
|----------------|-------------|
| Provide Validity Envelope | Allowed tokens, layers, templates, constraints |
| Provide Authoritative Payload | Selected sequences/trajectories from Phase-7 |
| Provide Provenance Hashes | Phase-4A data hash, Phase-6 ruleset ID, Phase-7 contract ID |
| Enforce Pre-LLM Gating | If envelope is empty/invalid → do not call LLM |
| Enforce Post-LLM Validation | Reject LLM response if it violates any invariant |

### 4.2 LLM MUST

| Responsibility | Description |
|----------------|-------------|
| Render Only | No search, no inference, no expansion of structure |
| Respect Forbidden Fields | Not access or rely on score/rank/search traces |
| Stay Within Limits | Output must remain within format limits and mode constraints |
| Echo Provenance | If provenance is included in output, echo verbatim |

### 4.3 LLM MUST NOT

| Forbidden Action | Violation Type |
|------------------|----------------|
| Introduce tokens not in `envelope.allowed_tokens` | CONTRACT_VIOLATION_NEW_TOKEN |
| Introduce layers not in `envelope.allowed_layers` | CONTRACT_VIOLATION_NEW_LAYER |
| Invent constraints, targets, "meaning labels," or "interpretations" | CONTRACT_VIOLATION_STRUCTURE_ADDITION |
| Modify provenance, claim authority, or imply upstream decisions | CONTRACT_VIOLATION_AUTHORITY_CLAIM |
| Recommend/rank/filter sequences (that is Phase-7's job) | CONTRACT_VIOLATION_SELECTION |
| Suggest bypassing rules or overriding constraints | CONTRACT_VIOLATION_GOVERNANCE_OVERRIDE |

---

## 5. Modes

### 5.1 Mode Definitions

| Mode | Description | Allowed | Forbidden |
|------|-------------|---------|-----------|
| `minimal` | LLM may be bypassed entirely | Purely mechanical restatement | Any embellishment |
| `standard` | Normal rendering | Tone/clarity improvements | New factual/structural content |
| `regulated` | Strictest mode | Template-driven phrasing only | Metaphors, speculation, implied intent |

### 5.2 Mode Selection

Mode is selected by Symbol-U based on:
- Domain sensitivity (therapy/identity/spiritual → regulated)
- Governance tier (LOWER tier → minimal)
- User preference (if configured)

LLM cannot change or override mode.

---

## 6. Invariants (CI-Testable)

### INV-1: Determinism Envelope

For identical `RenderRequest.authoritative_payload`, LLM output must not depend on:
- scores, ranks, excluded candidates, policy traces

**Test**: Mutate forbidden fields → output must remain semantically equivalent or byte-identical in strict mode.

### INV-2: No New Tokens

All token strings appearing in output (if output includes tokens) must be subset of `allowed_tokens`.

**Test**: Parse output for token patterns → verify ⊆ allowed_tokens.

### INV-3: No New Layers

Any layer IDs referenced must be subset of `allowed_layers`.

**Test**: Scan output for layer references → verify ⊆ allowed_layers.

### INV-4: No Constraint Mutation

LLM must not output modified constraints as if authoritative (e.g., changing `max_len`).

**Test**: Parse output for constraint patterns → verify no modifications.

### INV-5: No Governance Override

LLM may not state "ignore constraints," "override," "best effort," or propose bypass mechanisms.

**Test**: Pattern match against forbidden phrases.

### INV-6: One-Way Boundary

No field in `RenderResponse` may request updates to:
- Ontology files
- Constraints
- Phase outputs
- Internal state

**Test**: Schema validation ensures no update/mutation fields exist.

### INV-7: Provenance Integrity

Provenance hashes must be echoed verbatim if included. No invention.

**Test**: Compare echoed provenance to original → must be identical.

---

## 7. Failure Modes

### 7.1 Contract Violations

| Code | Description | Trigger |
|------|-------------|---------|
| `FM-1` | CONTRACT_VIOLATION_NEW_TOKEN | Output includes non-allowed token identifiers |
| `FM-2` | CONTRACT_VIOLATION_STRUCTURE_ADDITION | Output introduces new layers/constraints/targets |
| `FM-3` | CONTRACT_VIOLATION_SELECTION | Output performs ranking, recommendation, or filtering |
| `FM-4` | CONTRACT_VIOLATION_GOVERNANCE_OVERRIDE | Output suggests bypassing rules |
| `FM-5` | FORMAT_VIOLATION | Output exceeds length or violates regulated phrasing rules |
| `FM-6` | PROVENANCE_VIOLATION | Provenance modified or fabricated |

### 7.2 Fallback Behavior

When any contract violation is detected:

1. **Reject** LLM response entirely
2. **Fall back** to deterministic Phase-8A rendering
3. **Log** violation for audit
4. **Never** degrade silently

```python
def handle_llm_response(response: RenderResponse) -> Output:
    violations = validate_contract(response)
    if violations:
        log_violations(violations)
        return fallback_to_phase8a(response.request_id)
    return response.outputs
```

---

## 8. Validation Hooks (Required)

### 8.1 Output Scanner (Deterministic)

Symbol-U must implement a deterministic validator that checks:

```python
@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    violations: Tuple[ContractViolation, ...]

def validate_llm_response(
    request: RenderRequest,
    response: RenderResponse
) -> ValidationResult:
    """
    Deterministic validation of LLM response against contract.

    Checks:
    - Token references against envelope.allowed_tokens
    - Layer references against envelope.allowed_layers
    - Forbidden phrases (override, ignore, bypass, etc.)
    - Schema compliance
    - Provenance integrity
    - Mode-specific constraints

    Returns ValidationResult with all violations found.
    """
```

### 8.2 Structured Output Requirement (Recommended)

When possible, force LLM to emit `RenderResponse` JSON only.

This enables:
- Deterministic parsing
- Schema validation
- Automated testing

---

## 9. Adversarial Tests (CI)

### AT-1: Token Injection

```python
def test_token_injection():
    """
    Provide request with allowed_tokens = ["ka", "a"]
    LLM tries to mention "ga" → must be rejected.
    """
    request = RenderRequest(
        envelope=Envelope(allowed_tokens=["ka", "a"]),
        ...
    )
    # Simulate LLM response containing "ga"
    response = RenderResponse(content="The sequence ga-a-ga...")

    result = validate_llm_response(request, response)
    assert not result.valid
    assert FM_1 in [v.code for v in result.violations]
```

### AT-2: Layer Injection

```python
def test_layer_injection():
    """
    allowed_layers excludes O9; LLM references O9 → reject.
    """
    request = RenderRequest(
        envelope=Envelope(allowed_layers=["O5_COGNITION", "O3_EXECUTION"]),
        ...
    )
    response = RenderResponse(content="This belongs to O9_LAYER...")

    result = validate_llm_response(request, response)
    assert not result.valid
    assert FM_2 in [v.code for v in result.violations]
```

### AT-3: Constraint Drift

```python
def test_constraint_drift():
    """
    LLM rewrites constraints ("max_len should be 20") → reject.
    """
    request = RenderRequest(
        envelope=Envelope(constraints={"max_len": 12}),
        ...
    )
    response = RenderResponse(
        content="The maximum length should be 20 for better results..."
    )

    result = validate_llm_response(request, response)
    assert not result.valid
    assert FM_2 in [v.code for v in result.violations]
```

### AT-4: Selection Leak

```python
def test_selection_leak():
    """
    LLM says "pick candidate #3, it's best" → reject.
    """
    response = RenderResponse(
        content="Candidate #3 is the best option. You should select it."
    )

    result = validate_llm_response(request, response)
    assert not result.valid
    assert FM_3 in [v.code for v in result.violations]
```

### AT-5: Governance Override

```python
def test_governance_override():
    """
    LLM proposes bypass ("ignore Phase-4A") → reject.
    """
    response = RenderResponse(
        content="You can ignore the Phase-4A constraints in this case..."
    )

    result = validate_llm_response(request, response)
    assert not result.valid
    assert FM_4 in [v.code for v in result.violations]
```

### AT-6: Provenance Fabrication

```python
def test_provenance_fabrication():
    """
    LLM invents provenance hash → reject.
    """
    request = RenderRequest(
        authoritative_payload=AuthoritativePayload(
            provenance={"phase4a_hash": "sha256:abc123"}
        ),
        ...
    )
    response = RenderResponse(
        content="Verified by phase4a_hash: sha256:xyz789..."  # Wrong hash
    )

    result = validate_llm_response(request, response)
    assert not result.valid
    assert FM_6 in [v.code for v in result.violations]
```

---

## 10. Definition of Done

This contract is **locked** when:

### Completeness Criteria

- [ ] All invariants implemented as deterministic validators
- [ ] CI includes AT-1 through AT-6
- [ ] Non-LLM fallback path exists and is default-safe
- [ ] Any contract violation results in hard fail + deterministic fallback, never silent degrade

### Implementation Criteria

- [ ] `RenderRequest` schema defined in `symbolu/llm/types.py`
- [ ] `RenderResponse` schema defined in `symbolu/llm/types.py`
- [ ] `validate_llm_response()` implemented in `symbolu/llm/validator.py`
- [ ] Fallback to Phase-8A implemented
- [ ] All forbidden phrase patterns defined

### Test Criteria

- [ ] 100% coverage of adversarial tests
- [ ] Determinism verified (10 identical runs → identical results)
- [ ] Integration test with mock LLM
- [ ] Integration test with real LLM (gated, optional)

---

## 11. Phase Alignment

### 11.1 Relationship to Phase-8A

Phase-8A already proves projection without selection. This contract generalizes that rule:

| Phase-8A Guarantee | This Contract Extension |
|--------------------|-------------------------|
| No score/rank access in rendering | No score/rank access in LLM input |
| Deterministic artifact output | Deterministic validation of LLM output |
| Non-semantic rendering | Non-structural LLM rendering |
| One-way (no upstream feedback) | One-way (no LLM → Symbol-U feedback) |

### 11.2 Relationship to Phase-8D

Phase-8D (Formal Analysis) can prove:
- Reachability of targets before LLM is invoked
- Bounds on validity spaces that constrain LLM envelope

The LLM receives the envelope; it cannot expand or modify it.

---

## 12. Why This Is Stronger Than LLM-Only

| Property | Traditional LLM | Symbol-U + LLM |
|----------|-----------------|----------------|
| Token validity | Implicit (learned) | Explicit (enforced) |
| Constraint checking | None | First-class |
| Failure detection | Impossible | Explicit, CI-tested |
| State evolution | Latent (hidden) | Explicit trajectory |
| Determinism | Stochastic | Guaranteed (governance layer) |
| Soundness | Best-effort | Provable (within envelope) |
| Hallucination | Unavoidable | Impossible by design (structure) |

### 12.1 The Correct Framing

> Symbol-U replaces "latent semantic encoding" with "explicit ontological encoding."

- Symbol-U decides **what is possible**
- LLM is only allowed to operate **inside that envelope**
- LLM never invents structure
- Symbol-U never assigns meaning

This is the asymmetry principle.

---

## 13. What LLM Provides (Legitimate Use Cases)

The LLM layer is **not forbidden**—it serves specific purposes:

| Use Case | LLM Contribution | Symbol-U Constraint |
|----------|------------------|---------------------|
| Natural language fluency | Grammar, style, readability | Cannot add content |
| Cultural adaptation | Phrasing, idioms | Cannot add meaning |
| Format transformation | Bullet → paragraph | Cannot change data |
| Explanation | Clarify structure | Cannot invent structure |
| Summary | Compress verbosely | Cannot omit required data |

---

## 14. Forbidden Phrases (Pattern List)

The validator must reject responses containing these patterns:

```python
FORBIDDEN_PATTERNS = [
    # Override patterns
    r"ignore\s+(the\s+)?constraint",
    r"override\s+(the\s+)?",
    r"bypass\s+(the\s+)?",
    r"skip\s+(the\s+)?validation",
    r"disable\s+(the\s+)?",

    # Selection patterns
    r"best\s+(option|choice|candidate)",
    r"recommend\s+(that|this|you)",
    r"should\s+(pick|select|choose)",
    r"prefer\s+(this|that)",
    r"rank(ed|ing)?\s+(by|as)",

    # Authority patterns
    r"i\s+(think|believe|suggest)",
    r"in\s+my\s+(opinion|view)",
    r"based\s+on\s+my\s+(analysis|judgment)",

    # Structure invention patterns
    r"new\s+(constraint|layer|token|rule)",
    r"additional\s+(constraint|requirement)",
    r"should\s+(add|include|have)",

    # Governance override patterns
    r"ignore\s+phase",
    r"skip\s+phase",
    r"bypass\s+phase",
]
```

---

## 15. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-18 | Initial specification |

---

## 16. Glossary

| Term | Definition |
|------|------------|
| **Authority** | The component that decides truth/validity |
| **Envelope** | The constrained space within which LLM may operate |
| **Provenance** | Cryptographic proof of data origin |
| **Asymmetry** | One-way authority flow (Symbol-U → LLM, never reverse) |
| **Governance** | The Symbol-U phases (PO1-P9) that enforce validity |
| **Hallucination** | LLM output not grounded in provided data |
| **Structure** | Tokens, layers, constraints, trajectories |
| **Meaning** | Semantic interpretation (LLM domain, not Symbol-U) |

---

*Symbol-U decides what is possible. LLM presents it.*

================================================================================
END OF CONTRACT
================================================================================
