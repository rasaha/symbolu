# Phase-8C Consumer Interface Contract

## Document Metadata

| Field | Value |
|-------|-------|
| Phase | 8C |
| Name | Consumer Interface Layer |
| Version | 1.0.0 |
| Status | SPECIFICATION |
| Created | 2024 |
| Depends On | Phase-7 (Targeted Generation) |

---

## 1. Purpose

Phase-8C defines the **transport contract** for exposing Phase-7 outputs to external consumers. It is a **window, not a lens** — it reveals structure without suggesting use.

```
Phase-7 Output ──────► Phase-8C Interface ──────► External Consumer
      │                       │                        │
RankedResult            Serialization              Client App
Trajectory              Streaming                  Analytics
ValiditySpace           Predicates                 Downstream System
```

### 1.1 What Phase-8C Does

- **Exposes** Phase-7 outputs in consumable formats
- **Preserves** Phase-7 guarantees without modification
- **Transports** data from system boundary to consumers
- **Projects** component views on request (read-only)

### 1.2 What Phase-8C Does NOT Do

- **Transform**: No rendering (that's Phase-8A)
- **Persist**: No storage logic (that's Phase-8B)
- **Analyze**: No reasoning about validity (that's Phase-8D)
- **Select**: No ranking, filtering by importance, or optimization
- **Suggest**: No recommendations, discovery, or navigation hints

---

## 2. Architectural Principle

> **Phase-8C may expose structure, but must never suggest use.**
>
> If a consumer derives meaning, that happens outside the system boundary.

### 2.1 The Window Metaphor

| Property | Window (Phase-8C) | Lens (Forbidden) |
|----------|-------------------|------------------|
| Transformation | None | Focuses, filters |
| Selection | None | Prioritizes |
| Suggestion | None | Guides attention |
| Interpretation | None | Adds meaning |

Phase-8C must be **boring**. It is infrastructure, not intelligence.

---

## 3. Design Decisions

### 3.1 Decision Summary

| Dimension | Decision | Rationale |
|-----------|----------|-----------|
| Granularity | Full results + projections | Preserve evidence integrity |
| Streaming | Structural only | Reflect iteration, not optimization |
| Filtering | Simple predicates only | Prevent intent encoding |
| Versioning | URL-based (`/v1/`) | Immutability & reproducibility |
| HATEOAS | Disallowed | No discovery or guidance |

### 3.2 Granularity

**Decision**: Expose full results by default, with read-only component accessors.

```
Primary Payload: Full Phase7Result
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
  /trajectory    /sequence     /metrics
  (projection)   (projection)  (projection)
```

**Allowed**:
- Full result retrieval
- Component projections: `/trajectory`, `/sequence`, `/metrics`, `/events`

**Rule**: Partial access is a projection, never a replacement.

**What This Prevents**:
- Clients treating trajectory as "the answer"
- Semantic misuse via partial consumption
- Accidental re-introduction of ranking logic

### 3.3 Streaming Semantics

**Decision**: Streaming reflects time, not quality.

**Allowed**:
- Progressive delivery of candidate batches
- Exclusion-chain iteration snapshots
- Monotonic result set growth

**Forbidden**:
- Early stopping
- "Best-so-far" semantics
- Confidence-weighted updates
- Quality-based ordering in stream

**Invariant**: Streaming reflects iteration, not improvement.

**What This Prevents**:
- Illusion of intelligence
- Client-side premature selection
- Misinterpretation of partial output as convergence

### 3.4 Filter Expressiveness

**Decision**: Strict predicates only. No query language.

**Allowed Predicates**:
| Type | Example | Semantics |
|------|---------|-----------|
| Field Equality | `token=ka` | Exact match |
| Numeric Range | `magnitude_gte=1.0` | Closed interval |
| Membership | `token_in=ka,ga,ta` | Set inclusion |
| Index Slice | `offset=10&limit=20` | Positional access |

**Forbidden**:
- Boolean logic trees (`AND`, `OR`, `NOT` combinations)
- Graph traversal expressions
- Derived expressions (`magnitude > avg(magnitudes)`)
- User-defined functions
- Full-text search
- Relevance scoring

**Rule**: If a filter cannot be expressed as a total function on fields, it is invalid.

**What This Prevents**:
- Semantic creep
- Hidden scoring logic
- "Why did this show up?" ambiguity

### 3.5 Versioning

**Decision**: URL versioning with immutable versions.

```
/v1/generations/{id}    ← Version 1 (frozen)
/v2/generations/{id}    ← Version 2 (new contract)
```

**Rules**:
- Versions are immutable
- New versions = new endpoints, never upgrades
- Breaking changes require new major version
- Old versions remain available until explicit deprecation

**What This Prevents**:
- Silent behavior changes
- Client ambiguity
- Hidden breaking changes

### 3.6 HATEOAS

**Decision**: No HATEOAS. Explicit endpoints only.

**Why Forbidden**:
Hypermedia implies:
- Discovery (suggesting what exists)
- Suggestion (recommending next actions)
- Navigation intent (guiding exploration)

All of these are **selection metaphors** that violate Phase-8C's neutrality.

**What This Prevents**:
- Implicit workflow encoding
- "Recommended next action" leakage
- Tool-driven rather than user-driven exploration

---

## 4. Data Types Exposed

### 4.1 Primary Types

Phase-8C exposes Phase-7 outputs without modification:

```
┌─────────────────────────────────────────────────────────┐
│                    Phase7Result                          │
├─────────────────────────────────────────────────────────┤
│ id: ResultId                                            │
│ request: GenerationRequest                              │
│ ranked_results: List[RankedResult]                      │
│ validity_space: ValiditySpace                           │
│ generation_metadata: GenerationMetadata                 │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                    RankedResult                          │
├─────────────────────────────────────────────────────────┤
│ trajectory: Trajectory                                  │
│ score: float                                            │
│ rank: int                                               │
│ constraint_satisfaction: ConstraintSatisfaction         │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                     Trajectory                           │
├─────────────────────────────────────────────────────────┤
│ sequence: Tuple[str, ...]                               │
│ steps: Tuple[TrajectoryStep, ...]                       │
│ final_magnitude: float                                  │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                   TrajectoryStep                         │
├─────────────────────────────────────────────────────────┤
│ token: str                                              │
│ magnitude: float                                        │
│ event: str  # "reset" | "modulate"                      │
│ position: int                                           │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Projection Types

Component accessors return **projections** (subsets of the full result):

| Projection | Returns | Use Case |
|------------|---------|----------|
| `/trajectory` | Trajectory only | Sequence analysis |
| `/sequence` | Token tuple only | Pattern matching |
| `/metrics` | Scores and metadata | Statistical analysis |
| `/events` | Step events only | Event stream processing |
| `/validity` | ValiditySpace only | Constraint inspection |

**Constraint**: Projections are read-only views. They never replace the full result in semantics.

---

## 5. Serialization Formats

### 5.1 Supported Formats

| Format | Content-Type | Use Case |
|--------|--------------|----------|
| JSON | `application/json` | Default, human-readable |
| MessagePack | `application/msgpack` | Binary, performance |

### 5.2 Format Negotiation

```http
GET /v1/generations/abc123
Accept: application/json

GET /v1/generations/abc123
Accept: application/msgpack
```

Default: JSON if no `Accept` header provided.

### 5.3 Serialization Invariants

| ID | Invariant |
|----|-----------|
| SER-1 | **Lossless**: Serialization preserves all Phase-7 data |
| SER-2 | **Reversible**: Deserialization reproduces exact original |
| SER-3 | **Deterministic**: Same input → same serialized output |
| SER-4 | **No Derived Fields**: Serialization adds no computed values |

### 5.4 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Phase7Result",
  "type": "object",
  "required": ["id", "version", "ranked_results"],
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique result identifier"
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "Contract version"
    },
    "ranked_results": {
      "type": "array",
      "items": { "$ref": "#/definitions/RankedResult" }
    },
    "validity_space": { "$ref": "#/definitions/ValiditySpace" },
    "generation_metadata": { "$ref": "#/definitions/GenerationMetadata" }
  },
  "definitions": {
    "RankedResult": {
      "type": "object",
      "required": ["trajectory", "score", "rank"],
      "properties": {
        "trajectory": { "$ref": "#/definitions/Trajectory" },
        "score": { "type": "number" },
        "rank": { "type": "integer", "minimum": 1 }
      }
    },
    "Trajectory": {
      "type": "object",
      "required": ["sequence", "steps", "final_magnitude"],
      "properties": {
        "sequence": {
          "type": "array",
          "items": { "type": "string" }
        },
        "steps": {
          "type": "array",
          "items": { "$ref": "#/definitions/TrajectoryStep" }
        },
        "final_magnitude": { "type": "number" }
      }
    },
    "TrajectoryStep": {
      "type": "object",
      "required": ["token", "magnitude", "event", "position"],
      "properties": {
        "token": { "type": "string" },
        "magnitude": { "type": "number" },
        "event": { "enum": ["reset", "modulate"] },
        "position": { "type": "integer", "minimum": 0 }
      }
    },
    "ValiditySpace": {
      "type": "object",
      "properties": {
        "constraints_satisfied": { "type": "array", "items": { "type": "string" } },
        "constraints_violated": { "type": "array", "items": { "type": "string" } }
      }
    },
    "GenerationMetadata": {
      "type": "object",
      "properties": {
        "timestamp": { "type": "string", "format": "date-time" },
        "duration_ms": { "type": "number" },
        "phase7_version": { "type": "string" }
      }
    }
  }
}
```

---

## 6. Endpoint Contract

### 6.1 Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/generations/{id}` | Retrieve full result |
| `GET` | `/v1/generations/{id}/trajectory` | Trajectory projection |
| `GET` | `/v1/generations/{id}/sequence` | Sequence projection |
| `GET` | `/v1/generations/{id}/metrics` | Metrics projection |
| `GET` | `/v1/generations/{id}/events` | Events projection |
| `GET` | `/v1/generations/{id}/validity` | Validity projection |
| `GET` | `/v1/generations` | List with predicates |
| `POST` | `/v1/generations/stream` | Streaming endpoint |

### 6.2 Full Result Retrieval

```http
GET /v1/generations/{id}
Accept: application/json

Response 200 OK
Content-Type: application/json

{
  "id": "gen_abc123",
  "version": "1.0.0",
  "ranked_results": [
    {
      "trajectory": {
        "sequence": ["ka", "a", "ga", "i", "ta", "u"],
        "steps": [
          {"token": "ka", "magnitude": 1.0, "event": "reset", "position": 0},
          {"token": "a", "magnitude": 1.1, "event": "modulate", "position": 1},
          {"token": "ga", "magnitude": 1.0, "event": "reset", "position": 2},
          {"token": "i", "magnitude": 1.2, "event": "modulate", "position": 3},
          {"token": "ta", "magnitude": 1.0, "event": "reset", "position": 4},
          {"token": "u", "magnitude": 1.15, "event": "modulate", "position": 5}
        ],
        "final_magnitude": 1.15
      },
      "score": 0.95,
      "rank": 1
    }
  ],
  "validity_space": {
    "constraints_satisfied": ["G1", "G2", "G3", "M1", "M3"],
    "constraints_violated": []
  },
  "generation_metadata": {
    "timestamp": "2024-01-15T10:30:00Z",
    "duration_ms": 42.5,
    "phase7_version": "1.0.0"
  }
}
```

### 6.3 Projection Retrieval

```http
GET /v1/generations/{id}/trajectory
Accept: application/json

Response 200 OK
Content-Type: application/json

{
  "id": "gen_abc123",
  "version": "1.0.0",
  "projection": "trajectory",
  "data": {
    "sequence": ["ka", "a", "ga", "i", "ta", "u"],
    "steps": [
      {"token": "ka", "magnitude": 1.0, "event": "reset", "position": 0},
      {"token": "a", "magnitude": 1.1, "event": "modulate", "position": 1},
      {"token": "ga", "magnitude": 1.0, "event": "reset", "position": 2},
      {"token": "i", "magnitude": 1.2, "event": "modulate", "position": 3},
      {"token": "ta", "magnitude": 1.0, "event": "reset", "position": 4},
      {"token": "u", "magnitude": 1.15, "event": "modulate", "position": 5}
    ],
    "final_magnitude": 1.15
  }
}
```

### 6.4 List with Predicates

```http
GET /v1/generations?magnitude_gte=1.0&magnitude_lte=1.5&limit=10&offset=0
Accept: application/json

Response 200 OK
Content-Type: application/json

{
  "version": "1.0.0",
  "results": [...],
  "pagination": {
    "offset": 0,
    "limit": 10,
    "total": 42
  }
}
```

### 6.5 Streaming Endpoint

```http
POST /v1/generations/stream
Content-Type: application/json
Accept: text/event-stream

{
  "request_id": "req_xyz789",
  "predicates": {
    "sequence_length_gte": 4
  }
}

Response 200 OK
Content-Type: text/event-stream

event: batch
data: {"batch_index": 0, "results": [...], "is_final": false}

event: batch
data: {"batch_index": 1, "results": [...], "is_final": false}

event: batch
data: {"batch_index": 2, "results": [...], "is_final": true}

event: complete
data: {"total_batches": 3, "total_results": 15}
```

**Streaming Constraints**:
- `batch_index` is monotonically increasing
- `is_final` indicates last batch in current iteration
- No quality ordering within or across batches
- Stream reflects generation iteration, not ranking

---

## 7. Predicate Specification

### 7.1 Allowed Predicates

| Predicate | Syntax | Semantics |
|-----------|--------|-----------|
| Field Equality | `field=value` | `result.field == value` |
| Greater Than or Equal | `field_gte=value` | `result.field >= value` |
| Less Than or Equal | `field_lte=value` | `result.field <= value` |
| Membership | `field_in=v1,v2,v3` | `result.field in {v1, v2, v3}` |
| Offset | `offset=N` | Skip first N results |
| Limit | `limit=N` | Return at most N results |

### 7.2 Predicate Fields

| Field | Type | Description |
|-------|------|-------------|
| `sequence_length` | int | Number of tokens in sequence |
| `final_magnitude` | float | Final trajectory magnitude |
| `score` | float | Phase-7 computed score |
| `rank` | int | Phase-7 computed rank |
| `token` | string | Token membership in sequence |
| `event` | string | Event type in steps |

### 7.3 Predicate Examples

```http
# Sequences with 4+ tokens
GET /v1/generations?sequence_length_gte=4

# Final magnitude between 1.0 and 1.5
GET /v1/generations?final_magnitude_gte=1.0&final_magnitude_lte=1.5

# Sequences containing 'ka' token
GET /v1/generations?token_in=ka

# Pagination
GET /v1/generations?offset=20&limit=10
```

### 7.4 Forbidden Predicate Patterns

| Pattern | Example | Why Forbidden |
|---------|---------|---------------|
| Boolean Logic | `(a AND b) OR c` | Encodes intent priority |
| Negation | `NOT token=ka` | Implicit selection logic |
| Aggregation | `magnitude > AVG(*)` | Computed comparison |
| Ordering | `ORDER BY score DESC` | Ranking preference |
| Full-text | `query=meaning` | Semantic interpretation |
| Regex | `token_matches=k.*` | Unbounded computation |

---

## 8. Invariants

### 8.1 Core Invariants

| ID | Name | Statement |
|----|------|-----------|
| INV-1 | **No Mutation** | Interface never modifies Phase-7 output |
| INV-2 | **Format Fidelity** | Serialization is lossless and reversible |
| INV-3 | **Filter Transparency** | Filters are declarative predicates, not computations |
| INV-4 | **Pagination Stability** | Same query + cursor → same results |
| INV-5 | **Version Immutability** | Published versions never change behavior |
| INV-6 | **Idempotency** | GET requests are idempotent |
| INV-7 | **No Side Effects** | Reading never triggers generation |
| INV-8 | **No Suggestion** | Response contains no recommendations |
| INV-9 | **Projection Subset** | Projections are strict subsets of full result |
| INV-10 | **Stream Monotonicity** | Streaming batch indices increase monotonically |

### 8.2 Formal Statements

```
INV-1: ∀ result ∈ Phase7Output:
         interface.expose(result) = result

INV-2: ∀ result:
         deserialize(serialize(result)) = result

INV-3: ∀ predicate P:
         P is a total function: Result → Boolean

INV-4: ∀ query Q, cursor C:
         execute(Q, C, t₁) = execute(Q, C, t₂)

INV-6: ∀ request R:
         GET(R) at t₁ = GET(R) at t₂
         (assuming no underlying data change)

INV-9: ∀ projection P, result R:
         P(R) ⊆ R

INV-10: ∀ stream S:
          S[i].batch_index < S[i+1].batch_index
```

---

## 9. Forbidden Behaviors

### 9.1 Selection Behaviors

| ID | Forbidden Behavior | Violation |
|----|-------------------|-----------|
| FB-1 | Re-ranking results | Introduces preference |
| FB-2 | Filtering by "importance" | Subjective selection |
| FB-3 | Inferring usefulness | Semantic interpretation |
| FB-4 | Optimizing for clients | Client-specific logic |
| FB-5 | Recommending next actions | Navigation guidance |
| FB-6 | Highlighting results | Attention direction |

### 9.2 Transformation Behaviors

| ID | Forbidden Behavior | Violation |
|----|-------------------|-----------|
| FB-7 | Computing derived values | Added logic |
| FB-8 | Aggregating statistics | Computation beyond transport |
| FB-9 | Formatting for display | Rendering (Phase-8A's job) |
| FB-10 | Translating tokens | Semantic modification |

### 9.3 Stateful Behaviors

| ID | Forbidden Behavior | Violation |
|----|-------------------|-----------|
| FB-11 | Caching with invalidation logic | Hidden state |
| FB-12 | Session-based filtering | User-specific selection |
| FB-13 | Learning from access patterns | Adaptive behavior |
| FB-14 | Rate limiting by content | Content-aware logic |

### 9.4 Discovery Behaviors

| ID | Forbidden Behavior | Violation |
|----|-------------------|-----------|
| FB-15 | HATEOAS links | Navigation suggestion |
| FB-16 | Related results | Association inference |
| FB-17 | "Similar to" endpoints | Semantic grouping |
| FB-18 | Auto-complete | Predictive guidance |

---

## 10. Error Contract

### 10.1 Error Categories

Phase-8C errors are **transport errors only**. Domain errors belong to Phase-7.

| Category | HTTP Status | Description |
|----------|-------------|-------------|
| Transport | 5xx | Connection, timeout, infrastructure |
| Format | 400 | Malformed request syntax |
| Not Found | 404 | Unknown identifier |
| Invalid Predicate | 400 | Forbidden predicate pattern |

### 10.2 Error Response Format

```json
{
  "error": {
    "code": "INVALID_PREDICATE",
    "message": "Predicate 'score > AVG(scores)' uses forbidden aggregation",
    "category": "format",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### 10.3 What Phase-8C Does NOT Report

| Error Type | Belongs To | Why Not 8C |
|------------|------------|------------|
| Constraint violation | Phase-7 | Domain logic |
| Invalid sequence | Phase-6 | Composition mechanics |
| Generation failure | Phase-7 | Generation logic |
| Timeout during generation | Phase-7 | Generation concern |

---

## 11. Wire Format Examples

### 11.1 Full Result

```json
{
  "id": "gen_abc123",
  "version": "1.0.0",
  "ranked_results": [
    {
      "trajectory": {
        "sequence": ["ka", "a", "ga", "i", "ta", "u"],
        "steps": [
          {"token": "ka", "magnitude": 1.0, "event": "reset", "position": 0},
          {"token": "a", "magnitude": 1.1, "event": "modulate", "position": 1},
          {"token": "ga", "magnitude": 1.0, "event": "reset", "position": 2},
          {"token": "i", "magnitude": 1.2, "event": "modulate", "position": 3},
          {"token": "ta", "magnitude": 1.0, "event": "reset", "position": 4},
          {"token": "u", "magnitude": 1.15, "event": "modulate", "position": 5}
        ],
        "final_magnitude": 1.15
      },
      "score": 0.95,
      "rank": 1,
      "constraint_satisfaction": {
        "satisfied": ["G1", "G2", "G3", "G4", "M1", "M3"],
        "violated": []
      }
    },
    {
      "trajectory": {
        "sequence": ["ta", "i", "ka", "u"],
        "steps": [
          {"token": "ta", "magnitude": 1.0, "event": "reset", "position": 0},
          {"token": "i", "magnitude": 1.2, "event": "modulate", "position": 1},
          {"token": "ka", "magnitude": 1.0, "event": "reset", "position": 2},
          {"token": "u", "magnitude": 1.15, "event": "modulate", "position": 3}
        ],
        "final_magnitude": 1.15
      },
      "score": 0.87,
      "rank": 2,
      "constraint_satisfaction": {
        "satisfied": ["G1", "G2", "G3", "G4", "M1", "M3"],
        "violated": []
      }
    }
  ],
  "validity_space": {
    "constraints_satisfied": ["G1", "G2", "G3", "G4", "M1", "M2", "M3", "M4", "M5"],
    "constraints_violated": [],
    "total_candidates_explored": 128,
    "valid_candidates_found": 15
  },
  "generation_metadata": {
    "timestamp": "2024-01-15T10:30:00Z",
    "duration_ms": 42.5,
    "phase7_version": "1.0.0",
    "request_constraints": {
      "min_length": 4,
      "max_length": 8,
      "target_magnitude_range": [1.0, 1.5]
    }
  }
}
```

### 11.2 Sequence Projection

```json
{
  "id": "gen_abc123",
  "version": "1.0.0",
  "projection": "sequence",
  "data": {
    "sequences": [
      ["ka", "a", "ga", "i", "ta", "u"],
      ["ta", "i", "ka", "u"]
    ]
  }
}
```

### 11.3 Events Projection

```json
{
  "id": "gen_abc123",
  "version": "1.0.0",
  "projection": "events",
  "data": {
    "event_streams": [
      [
        {"position": 0, "event": "reset", "token": "ka"},
        {"position": 1, "event": "modulate", "token": "a"},
        {"position": 2, "event": "reset", "token": "ga"},
        {"position": 3, "event": "modulate", "token": "i"},
        {"position": 4, "event": "reset", "token": "ta"},
        {"position": 5, "event": "modulate", "token": "u"}
      ],
      [
        {"position": 0, "event": "reset", "token": "ta"},
        {"position": 1, "event": "modulate", "token": "i"},
        {"position": 2, "event": "reset", "token": "ka"},
        {"position": 3, "event": "modulate", "token": "u"}
      ]
    ]
  }
}
```

### 11.4 Streaming Response

```
event: batch
data: {"batch_index": 0, "iteration": 1, "results": [{"trajectory": {...}, "score": 0.95, "rank": 1}], "is_final": false}

event: batch
data: {"batch_index": 1, "iteration": 2, "results": [{"trajectory": {...}, "score": 0.87, "rank": 2}], "is_final": false}

event: batch
data: {"batch_index": 2, "iteration": 3, "results": [{"trajectory": {...}, "score": 0.82, "rank": 3}], "is_final": true}

event: complete
data: {"total_batches": 3, "total_results": 3, "iterations_completed": 3}
```

### 11.5 Error Response

```json
{
  "error": {
    "code": "FORBIDDEN_PREDICATE",
    "message": "Predicate 'ORDER BY score DESC' uses forbidden ordering. Phase-8C does not support result ordering.",
    "category": "format",
    "timestamp": "2024-01-15T10:30:00Z",
    "details": {
      "predicate": "ORDER BY score DESC",
      "violation": "FB-1: Re-ranking results"
    }
  }
}
```

---

## 12. Relationship to Other Phases

```
┌─────────────────────────────────────────────────────────┐
│                    Phase-7 Output                        │
│         (RankedResult, Trajectory, ValiditySpace)        │
└─────────────────────────────────────────────────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ Phase-8A│    │ Phase-8B│    │ Phase-8C│    │ Phase-8D│
    │         │    │         │    │         │    │         │
    │ RENDER  │    │ STORE   │    │ EXPOSE  │    │ ANALYZE │
    │         │    │         │    │         │    │         │
    │ Transform│   │ Persist │    │Transport│    │ Reason  │
    │ to       │    │ to      │    │ to      │    │ about   │
    │ Artifact │    │ Storage │    │ Consumer│    │ Validity│
    │         │    │         │    │         │    │         │
    │ →Symbols│    │ →Index  │    │ →JSON   │    │ →Proofs │
    │ →Audio  │    │ →Query  │    │ →Stream │    │ →Bounds │
    │ →Visual │    │         │    │ →Filter │    │         │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘
        │              │              │              │
        │              │              │              │
        ▼              ▼              ▼              ▼
    Perceivable    Persistent     External       Formal
    Artifacts      Records        Consumers      Proofs
```

### 12.1 Boundary Definitions

| Phase | Receives From | Passes To | Transformation |
|-------|---------------|-----------|----------------|
| 8A | Phase-7 | Human perception | Semantic → Perceivable |
| 8B | Phase-7 | Storage systems | Transient → Persistent |
| 8C | Phase-7 | External systems | Internal → External (pure transport) |
| 8D | Phase-7 | Proof systems | Data → Formal analysis |

### 12.2 Phase-8C Boundaries

**Input Boundary**:
- Receives: `Phase7Result` (frozen, immutable)
- Contract: Must not modify, must not interpret

**Output Boundary**:
- Produces: Serialized `Phase7Result` or projections
- Contract: Lossless, deterministic, format-neutral

---

## 13. Implementation Guidance

### 13.1 Implementation Checklist

| Requirement | Validation |
|-------------|------------|
| No mutation of Phase-7 data | Unit test: input == output (structurally) |
| Serialization is lossless | Round-trip test: deserialize(serialize(x)) == x |
| Predicates are total functions | Type system enforcement |
| No derived fields in output | Schema validation |
| Idempotent GET requests | Repeated request test |
| Streaming is monotonic | Batch index assertion |
| No HATEOAS links | Response schema validation |
| Version in URL | Endpoint pattern matching |

### 13.2 Test Categories

| Category | Purpose | Example |
|----------|---------|---------|
| Fidelity | Ensure no data loss | Serialize/deserialize round-trip |
| Neutrality | Ensure no added logic | No computed fields in response |
| Predicate | Validate filter semantics | Forbidden patterns rejected |
| Streaming | Validate monotonicity | Batch indices increase |
| Idempotency | Validate repeatability | Same request → same response |

### 13.3 Anti-Pattern Detection

Tests should detect and fail on:
- Response containing fields not in Phase-7 output
- Predicates using boolean operators
- Streaming with quality-based ordering
- Any endpoint containing "recommend", "suggest", "similar"
- Response times varying by content (content-aware caching)

---

## 14. Appendix: Design Rationale

### 14.1 Why "Window, Not Lens"?

A lens focuses, filters, and interprets. It makes choices about what matters.

A window reveals without opinion. The observer makes meaning.

Phase-8C must be a window because:
1. Selection is Phase-7's responsibility (already complete)
2. Interpretation is the consumer's responsibility (outside system)
3. Transport should be invisible infrastructure

### 14.2 Why No HATEOAS?

REST purists advocate HATEOAS for discoverability. But discoverability implies:
- "You might want to look at this" (suggestion)
- "Here's what you can do next" (guidance)
- "These are related" (semantic grouping)

All of these encode intent. Phase-8C must encode nothing.

### 14.3 Why Simple Predicates?

Query languages (SQL, GraphQL) are powerful because they express **intent**:
- "Give me the most relevant results" (relevance)
- "Sort by importance" (ranking)
- "Find similar items" (semantic similarity)

Simple predicates express only **structure**:
- "Field X equals value Y" (no interpretation)
- "Field X is between A and B" (no preference)

---

## 15. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024 | Initial specification |

---

## 16. Glossary

| Term | Definition |
|------|------------|
| **Projection** | A read-only subset of a full result |
| **Predicate** | A total function from result to boolean |
| **Transport** | Movement of data without transformation |
| **Window** | Interface that reveals without interpretation |
| **Lens** | Interface that focuses and filters (forbidden) |
| **HATEOAS** | Hypermedia as the Engine of Application State |
| **Monotonic** | Always increasing, never decreasing |
| **Idempotent** | Same input always produces same output |

---

*Phase-8C: Transport without opinion.*
