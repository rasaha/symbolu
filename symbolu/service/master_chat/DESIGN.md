# Master Chat System - Design Document

## Executive Summary

The Master Chat system implements a **single continuous conversation paradigm** for each user, replacing traditional multi-session chat interfaces. Instead of fragmenting knowledge across multiple chat sessions, all user interactions accumulate in a persistent session with **bucket-based context retrieval** driven by ontological signals.

This architecture solves the "Chaotic Mind" problem—when users switch rapidly between topics, traditional RAG systems struggle to maintain relevance. The Master Chat system uses **Signal-Based Routing** to dynamically activate appropriate knowledge buckets, ensuring contextually appropriate information is surfaced without cross-contamination.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Master Chat System                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   User Message                                                      │
│        │                                                            │
│        ▼                                                            │
│   ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐       │
│   │   Signal    │───▶│   Bucket     │───▶│    Context      │       │
│   │  Extractor  │    │   Router     │    │   Assembler     │       │
│   └─────────────┘    └──────────────┘    └─────────────────┘       │
│        │                    │                     │                 │
│        │                    ▼                     ▼                 │
│        │            ┌──────────────┐      ┌─────────────────┐      │
│        │            │   Buckets    │      │  LLM Context    │      │
│        │            │  (15 types)  │      │   Injection     │      │
│        │            └──────────────┘      └─────────────────┘      │
│        │                    ▲                                       │
│        ▼                    │                                       │
│   ┌─────────────────────────┴──────────────┐                       │
│   │        Knowledge Harvester             │                       │
│   │   (Salience Scoring + Deduplication)   │                       │
│   └────────────────────────────────────────┘                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Message Reception**: User message enters the system
2. **Signal Extraction**: Ontological signals (12D, Kosha, Vritti, Guna) are computed
3. **Bucket Routing**: Signals are matched against bucket profiles to determine activation
4. **Context Assembly**: Entries from activated buckets are formatted for LLM injection
5. **Response Generation**: LLM generates response with injected context
6. **Knowledge Harvesting**: Facts are extracted from the turn and stored in appropriate buckets

---

## Core Components

### 1. Bucket Models (`bucket_models.py`)

#### BucketCategory Enum

15 semantic categories mapped from the 12D Ontological framework:

| Category | 12D Layer | Description |
|----------|-----------|-------------|
| ASPIRATIONS | 1 (POTENTIAL) | Goals, dreams, future possibilities |
| SELF | 2 (IDENTITY) | Personal facts, preferences, identity |
| ACTIONS | 3 (EXECUTION) | Tasks, to-dos, commitments |
| SYSTEMS | 4 (STRUCTURE) | Processes, workflows, organizations |
| LEARNING | 5 (COGNITION) | Knowledge, insights, understanding |
| DECISIONS | 6 (AGENCY) | Choices, rationale, trade-offs |
| ANALYSIS | 7 (REASONING) | Logic, arguments, evaluations |
| VALUES | 8 (PURPOSE) | Beliefs, principles, motivations |
| RELATIONSHIPS | 9 (WITNESSES) | People, entities, connections |
| SYNTHESIS | 10 (UNIFYING) | Patterns, themes, integrations |
| PROJECTS | 11 (INTEGRATION) | Multi-domain initiatives |
| CLOSURE | 12 (ABSOLVING) | Completions, resolutions |
| PREFERENCES | Cross-cutting | Explicit preferences |
| EMOTIONS | Cross-cutting | Emotional states |
| TEMPORAL | Cross-cutting | Time-sensitive information |

#### SignalProfile

Each bucket has an ideal activation profile:

```python
@dataclass(frozen=True)
class SignalProfile:
    ontology_layers: tuple[int, ...]      # Preferred 12D layers
    kosha_range: tuple[float, float]       # Kosha activation range
    vritti_types: tuple[str, ...]          # Preferred motion types
    guna_bias: Optional[str]               # Preferred guna
    entropy_range: tuple[float, float]     # Entropy tolerance
```

#### MessageSignals

Input signal structure from MLCR/TTOR pipeline:

```python
@dataclass
class MessageSignals:
    ontology_layers: Dict[int, float]      # Layer activations
    kosha_activations: Dict[str, float]    # Kosha weights
    guna_distribution: Dict[str, float]    # Guna probabilities
    vritti_distribution: Dict[str, float]  # Vritti distribution
    dominant_vritti: str                   # Primary motion type
    normalized_entropy: float              # Combined entropy
```

#### BucketEntry

Individual knowledge entry with deduplication support:

```python
@dataclass
class BucketEntry:
    entry_id: str
    content: str
    source_turn_id: str
    timestamp: datetime
    importance_score: float       # Salience-based
    confidence_score: float
    embedding: Optional[List[float]]
    signal_snapshot: Dict[str, Any]
    entities: List[str]
    metadata: Dict[str, Any]
```

#### Bucket

Semantic container with smart deduplication:

```python
@dataclass
class Bucket:
    bucket_id: str
    category: BucketCategory
    signal_profile: SignalProfile
    entries: List[BucketEntry]
    centroid_embedding: Optional[List[float]]

    def add_entry(self, entry, deduplicate=True, similarity_threshold=0.85) -> bool:
        """
        Adds entry with automatic deduplication:
        - If similar entry exists with lower importance: UPDATE existing
        - If similar entry exists with higher importance: REINFORCE existing
        - Otherwise: ADD as new entry
        """
```

---

### 2. Bucket Router (`bucket_router.py`)

The router computes activation scores using a **multi-signal matching** algorithm.

#### Activation Score Formula

```
activation = (
    w_layer × layer_match +
    w_kosha × kosha_match +
    w_vritti × vritti_match +
    w_guna × guna_match +
    w_entropy × entropy_match +
    w_semantic × semantic_match
)
```

Where:
- `layer_match`: Jaccard similarity between signal layers and bucket's preferred layers
- `kosha_match`: Whether kosha level falls within bucket's preferred range
- `vritti_match`: Overlap of vritti types
- `guna_match`: Match against bucket's preferred guna
- `entropy_match`: Whether entropy falls within tolerance range
- `semantic_match`: Cosine similarity between query embedding and bucket centroid

#### RouterConfig

```python
@dataclass
class RouterConfig:
    layer_weight: float = 0.30      # 12D layer importance
    kosha_weight: float = 0.15      # Kosha importance
    vritti_weight: float = 0.10     # Vritti importance
    guna_weight: float = 0.10       # Guna importance
    entropy_weight: float = 0.10    # Entropy importance
    semantic_weight: float = 0.25   # Embedding similarity importance

    activation_threshold: float = 0.3   # Minimum score to activate
    max_buckets: int = 3                # Maximum concurrent activations
    max_entries_per_bucket: int = 5     # Entries to retrieve per bucket
```

#### Context Assembler

Formats activated bucket entries for LLM injection:

```xml
<relevant_context>
[Projects & Initiatives]
- User is building the SymbolU training pipeline
- Using PyTorch with curriculum learning strategy

[Learning & Knowledge]
- Learned that P-Pram stagnation occurs at -0.98 early in training
</relevant_context>
```

---

### 3. Knowledge Harvester (`knowledge_harvester.py`)

#### Extraction Patterns

16 pattern groups with ~60+ regex patterns:

| Pattern Group | Example Pattern | Target Bucket |
|--------------|-----------------|---------------|
| preferences | "I prefer X" | PREFERENCES |
| identity | "I am a X" | SELF |
| actions | "I need to X" | ACTIONS |
| decisions | "I decided X because Y" | DECISIONS |
| learning | "I learned that X" | LEARNING |
| aspirations | "My goal is to X" | ASPIRATIONS |
| relationships | "My colleague X" | RELATIONSHIPS |
| projects | "I'm building X" | PROJECTS |
| emotions | "I feel X about Y" | EMOTIONS |
| values | "I believe X" | VALUES |
| skills | "I know X" | LEARNING |
| analysis | "X is better than Y" | ANALYSIS |
| systems | "Our process is X" | SYSTEMS |
| temporal | "Deadline is X" | TEMPORAL |
| closure | "I finished X" | CLOSURE |
| synthesis | "I noticed a pattern that X" | SYNTHESIS |

#### Salience Scoring (Vritti vs Samskara)

Distinguishes permanent knowledge (Samskara) from conversational noise (Vritti):

```python
def calculate_salience(text, signals, is_novel=True) -> float:
    score = 0.5  # Base

    # 1. Linguistic markers (±0.25)
    # Strong: "always", "never", "prefer", "decided", "learned"
    # Weak: "maybe", "guess", "might", "sometimes"

    # 2. Signal intensity (±0.2)
    # Sattva + Rajas = stronger encoding
    # Tamas = weaker encoding

    # 3. Novelty boost (+0.15)

    # 4. Content length heuristic (±0.1)

    # 5. Entity presence boost (+0.05)

    return clamp(score, 0.0, 1.0)
```

#### Salience Threshold Recommendations

| Score Range | Classification | Action |
|-------------|---------------|--------|
| 0.0 - 0.3 | Noise (Vritti) | Discard or TEMPORAL bucket |
| 0.3 - 0.6 | Moderate | Store with lower importance |
| 0.6 - 1.0 | Permanent (Samskara) | Store with high importance |

---

### 4. Master Session Store (`master_session.py`)

#### MasterSession

Per-user session container:

```python
@dataclass
class MasterSession:
    user_id: str
    session_id: str
    buckets: Dict[str, Bucket]      # 15 pre-created buckets
    turn_count: int
    total_entries: int
    created_at: datetime
    last_activity: datetime
```

#### MasterSessionStore

Thread-safe store with get-or-create pattern:

```python
class MasterSessionStore:
    def get_or_create(self, user_id: str) -> MasterSession
    def get_context(self, user_id, message, signals) -> TurnContext
    def harvest_turn(self, user_id, user_msg, assistant_msg, signals) -> int
    def search_buckets(self, user_id, query, bucket_ids, limit) -> List[BucketEntry]
```

#### TurnContext

Result of context retrieval:

```python
@dataclass
class TurnContext:
    turn_id: str
    activated_buckets: List[ActivatedBucket]
    context_text: str                    # For LLM injection
    signals: MessageSignals
    routing_metadata: Dict[str, Any]     # Debug info
```

---

### 5. Embeddings (`embeddings.py`)

#### Providers

| Provider | Use Case | Dimensions |
|----------|----------|------------|
| SentenceTransformerProvider | Production | 384 |
| SimpleHashProvider | Testing/Fallback | Configurable |

#### Hash Provider Algorithm

Deterministic fallback when sentence-transformers unavailable:

```python
def embed(self, text: str) -> List[float]:
    # 1. Hash text to seed random generator
    # 2. Generate deterministic pseudo-random vector
    # 3. L2 normalize to unit vector
```

#### Similarity Functions

```python
def cosine_similarity(a: List[float], b: List[float]) -> float
def find_most_similar(query, candidates, top_k) -> List[Tuple[int, float]]
```

---

### 6. Integration (`integration.py`)

#### MasterChatService

Wraps existing ChatService with bucket context:

```python
class MasterChatService:
    async def chat(
        self,
        user_id: str,
        message: str,
        system_prompt: Optional[str] = None,
    ) -> MasterChatResponse:
        # 1. Get signals from MLCR pipeline
        # 2. Get context from master session
        # 3. Inject context into system prompt
        # 4. Call underlying ChatService
        # 5. Harvest knowledge from turn
        # 6. Return response with bucket metadata
```

#### SignalExtractor

Bridges MLCR pipeline output to MessageSignals:

```python
class SignalExtractor:
    def extract(self, mlcr_result: Dict) -> MessageSignals
```

---

### 7. API Endpoints (`api.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/master-chat/context` | POST | Get context for a message |
| `/master-chat/harvest` | POST | Harvest knowledge from a turn |
| `/master-chat/buckets/{user_id}` | GET | List user's bucket summary |
| `/master-chat/buckets/{user_id}/{bucket_id}` | GET | Get bucket entries |
| `/master-chat/search` | POST | Search across buckets |
| `/master-chat/stats/{user_id}` | GET | Get session statistics |

---

## Key Algorithms

### 1. Context Jump Isolation

The router ensures that switching topics results in clean context separation:

```
Turn 1: "Explain Rahu-Ketu axis" → VALUES bucket activated
Turn 2: "Fix CUDA OOM error"    → PROJECTS/SYSTEMS activated

Context for Turn 2 contains NO astrology terms.
```

This is achieved by:
1. **Signal Mismatch Penalty**: Buckets with mismatched signals score low
2. **Entropy Filtering**: High-entropy queries (topic switches) are more selective
3. **Activation Threshold**: Only buckets exceeding threshold are activated

### 2. Deduplication Algorithm

When adding entries:

```
1. Compute embedding for new entry
2. For each existing entry with embedding:
   a. Compute cosine similarity
   b. If similarity > 0.85:
      - If new.importance > existing.importance:
        → Update existing with new content
      - Else:
        → Reinforce existing (increment access count)
      - Return (merged)
3. If no match found:
   → Add as new entry
```

### 3. Salience Scoring

Combines linguistic and ontological signals:

```
Salience = Base(0.5)
         + LinguisticMarkers(±0.25)
         + SignalIntensity(±0.2)
         + Novelty(+0.15)
         + ContentLength(±0.1)
         + EntityPresence(+0.05)
```

---

## Configuration

### RouterConfig Defaults

```python
DEFAULT_ROUTER_CONFIG = RouterConfig(
    layer_weight=0.30,
    kosha_weight=0.15,
    vritti_weight=0.10,
    guna_weight=0.10,
    entropy_weight=0.10,
    semantic_weight=0.25,
    activation_threshold=0.3,
    max_buckets=3,
    max_entries_per_bucket=5,
)
```

### Tuning Recommendations

| Scenario | Adjustment |
|----------|------------|
| More focused context | Increase `activation_threshold` to 0.4+ |
| Broader context retrieval | Decrease `activation_threshold` to 0.2 |
| Stronger semantic matching | Increase `semantic_weight` to 0.35+ |
| Stronger ontological routing | Increase `layer_weight` to 0.40+ |
| Topic switch leakage | Decrease `max_buckets` to 2 |

---

## Testing Strategy

### Unit Tests

- `test_bucket_models.py`: Data structures, mappings, profiles
- `test_bucket_router.py`: Signal matching, activation scoring
- `test_knowledge_harvester.py`: Pattern extraction, salience
- `test_master_session.py`: Session management, context retrieval
- `test_embeddings.py`: Embedding providers, similarity

### Integration Tests

- `test_context_jump.py`: **Critical** - Validates topic isolation
  - Astrology → CUDA switch
  - Technical → Emotional switch
  - Rapid multi-topic switching

### Running Tests

```bash
# Requires pytest
pip install pytest

# Run all master_chat tests
pytest symbolu/service/master_chat/tests/ -v

# Run specific test
python -m unittest symbolu.service.master_chat.tests.test_context_jump
```

---

## Usage Examples

### Basic Usage

```python
from symbolu.service.master_chat import (
    get_master_session_store,
    MessageSignals,
    get_embedding_provider,
)

# Initialize store with embeddings
store = get_master_session_store(
    embedding_provider=get_embedding_provider(),
)

# Get context for a message
signals = MessageSignals(
    ontology_layers={11: 0.8, 3: 0.6},
    guna_distribution={"sattva": 0.3, "rajas": 0.6, "tamas": 0.1},
)

context = store.get_context(
    user_id="user123",
    message="How is my project going?",
    signals=signals,
)

# Use context in LLM call
system_prompt = f"""
You are a helpful assistant.

{context.context_text}
"""

# After response, harvest knowledge
await store.harvest_turn(
    user_id="user123",
    user_message="How is my project going?",
    assistant_response=llm_response,
    signals=signals,
)
```

### With MasterChatService Integration

```python
from symbolu.service.master_chat import get_master_chat_service

service = get_master_chat_service()

response = await service.chat(
    user_id="user123",
    message="Help me with my training pipeline",
)

print(response.content)
print(f"Activated buckets: {response.activated_buckets}")
```

---

## Future Enhancements

### Planned

1. **Temporal Expiry**: Auto-expire entries in TEMPORAL bucket after configurable TTL
2. **Bucket Compression**: Summarize old entries to reduce storage
3. **Cross-User Patterns**: Identify common knowledge patterns across users
4. **Active Learning**: Use feedback to tune routing weights

### Considered (Not Implemented)

1. **LLM-Based Extraction**: Rejected due to latency concerns
2. **JSON-LD Format**: Rejected as over-engineering for in-memory store
3. **Hard Signal Suppression**: Rejected due to over-filtering risk

---

## Glossary

| Term | Definition |
|------|------------|
| **12D Ontology** | 12-layer consciousness framework (POTENTIAL → ABSOLVING) |
| **Kosha** | 5-sheath model of consciousness (annamaya → anandamaya) |
| **Vritti** | Mental motion types (inertia, activation, oscillation, tension, release) |
| **Guna** | Three qualities (sattva=clarity, rajas=activity, tamas=inertia) |
| **Samskara** | Permanent knowledge impression worth storing |
| **Vritti (noise)** | Temporary thought/conversational chatter to discard |
| **Sattvic Flush** | Clean context switch when topic changes |
| **Bucket Activation** | Process of determining which buckets contain relevant context |
| **Signal Profile** | Ideal ontological signature for a bucket category |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-12 | Initial implementation |
| 1.1 | 2026-01-12 | Added salience scoring, deduplication, context jump tests |

---

## References

- MLCR Engine: `symbolu/service/chat_service/mlcr/mlcr_engine.py`
- TTOR Router: `symbolu/service/chat_service/ttor/router.py`
- Ontological Router: `symbolu/service/chat_service/ontological_router_r1.py`
- Kosha/Guna Metrics: `symbolu/service/chat_service/guna_kosha_resonance.py`
