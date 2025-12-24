/**
 * Research Articles Data
 *
 * Sample articles for the Symbol-μ research page.
 */

export interface Article {
  id: string;
  title: string;
  shortDescription: string;
  content: string;
  publishedAt: string;
  author: string;
  tags: string[];
}

export const articles: Article[] = [
  {
    id: 'ontological-substrate',
    title: 'The 10-Dimensional Ontological Substrate',
    shortDescription: 'Exploring the foundational layers that enable structured cognition in Symbol-μ.',
    content: `The Symbol-μ framework operates on a novel 10-dimensional ontological substrate that provides the foundation for structured cognitive processing. Unlike traditional language models that operate in high-dimensional embedding spaces without explicit semantic structure, our approach defines discrete ontological layers with clear contracts and invariants.

## The Ten Dimensions

Each dimension in our substrate corresponds to a fundamental aspect of human cognition and understanding:

1. **Existential** - Core being and identity markers
2. **Temporal** - Time-aware reasoning and sequencing
3. **Spatial** - Spatial relationships and navigation
4. **Causal** - Cause-effect reasoning chains
5. **Intentional** - Goal and purpose modeling
6. **Epistemic** - Knowledge and belief states
7. **Deontic** - Normative and ethical reasoning
8. **Affective** - Emotional and sentiment processing
9. **Social** - Interpersonal dynamics modeling
10. **Meta-cognitive** - Self-reflection and monitoring

## Layer Interactions

The power of this substrate comes from how layers interact. Each query activates a unique profile across dimensions, creating a coherent representation that can be tracked, audited, and explained. This enables unprecedented transparency in AI reasoning.

## Practical Applications

This ontological approach enables several capabilities not possible with traditional LLMs:
- Traceable reasoning paths
- Coherence measurement across conversations
- Explicit uncertainty quantification
- Domain-aware response calibration`,
    publishedAt: '2025-01-15',
    author: 'Symbol-μ Research',
    tags: ['ontology', 'architecture', 'foundations'],
  },
  {
    id: 'entropy-coherence',
    title: 'Entropy Metrics and Coherence Tracking',
    shortDescription: 'How Symbol-μ measures uncertainty and maintains conversation coherence.',
    content: `Coherence is the cornerstone of meaningful dialogue. Symbol-μ introduces a novel approach to measuring and maintaining coherence through entropy-based metrics that provide real-time visibility into response quality.

## The Entropy Framework

We define four primary entropy metrics:

### H_D (Domain Entropy)
Measures uncertainty about the semantic domain of a query. High H_D indicates ambiguity about the topic area, triggering additional clarification strategies.

### H_G (Global Entropy)
Captures overall uncertainty across all ontological dimensions. This provides a holistic view of response confidence.

### H_K (Knowledge Entropy)
Quantifies uncertainty in factual claims. Low H_K indicates high confidence in retrieved knowledge, while high H_K triggers epistemic humility markers.

### H_norm (Normalized Entropy)
A composite metric that normalizes entropy across the session, enabling trend analysis and drift detection.

## Coherence as a First-Class Citizen

Unlike systems that treat coherence as an emergent property, Symbol-μ makes it explicit and measurable. Each turn in a conversation updates the coherence score based on:
- Semantic consistency with prior statements
- Persona stability (avoiding contradictions)
- Goal alignment with session intent
- Temporal narrative coherence

## Real-Time Monitoring

The Developer tier exposes these metrics in real-time, enabling:
- Early detection of conversation drift
- Proactive intervention when coherence drops
- Post-hoc analysis of successful interactions
- A/B testing of response strategies`,
    publishedAt: '2025-01-10',
    author: 'Symbol-μ Research',
    tags: ['entropy', 'coherence', 'metrics'],
  },
  {
    id: 'semantic-renderers',
    title: 'Three Semantic Renderers: Symbolic, Practical, Mirror',
    shortDescription: 'Understanding the triple perspective system that powers nuanced responses.',
    content: `Symbol-μ processes every query through three distinct semantic renderers, each offering a unique perspective on meaning and response. This triple-view approach ensures comprehensive coverage of user intent.

## The Symbolic Renderer

The Symbolic layer interprets queries through the lens of abstract meaning, concepts, and philosophical significance. When asked "What is success?", the Symbolic renderer explores:
- Cultural definitions and variations
- Historical philosophical perspectives
- Abstract qualities and attributes
- Relationship to other concepts

This layer is essential for questions about meaning, purpose, and abstract reasoning.

## The Practical Renderer

The Practical layer focuses on actionable, concrete responses. For the same question "What is success?", it might explore:
- Measurable outcomes and metrics
- Steps to achieve goals
- Real-world examples
- Implementation strategies

This layer excels at how-to questions, problem-solving, and task-oriented queries.

## The Mirror Renderer

The Mirror layer reflects the query back through the user's likely personal context and emotional state. It considers:
- Personal relevance to the user
- Emotional undertones in the query
- Individual perspective taking
- Empathetic understanding

This layer enables personalized, emotionally intelligent responses.

## Fusion and Presentation

The three renderings are fused based on query characteristics and user tier:
- **Explorer tier**: Receives a balanced blend, optimized for clarity
- **Analyst tier**: Can view each layer separately via tabs
- **Developer tier**: Full access to layer weights and fusion parameters`,
    publishedAt: '2025-01-05',
    author: 'Symbol-μ Research',
    tags: ['renderers', 'semantics', 'fusion'],
  },
  {
    id: 'governance-gates',
    title: 'Governance Gates and Quality Assurance',
    shortDescription: 'Built-in safeguards that ensure response quality and safety.',
    content: `Quality and safety cannot be afterthoughts in AI systems. Symbol-μ implements governance gates as first-class architectural components, ensuring every response meets defined quality thresholds before delivery.

## The Gate Architecture

Governance gates are checkpoints in the response pipeline that validate outputs against configurable criteria:

### Quality Gates
- **Coherence Threshold**: Responses below the coherence threshold are flagged or regenerated
- **Confidence Minimum**: Uncertain responses must acknowledge limitations
- **Completeness Check**: Partial responses are detected and completed

### Safety Gates
- **Risk Band Classification**: Queries are classified into risk bands (LOW, MEDIUM, HIGH)
- **Content Filtering**: Harmful or inappropriate content is blocked
- **Sensitivity Detection**: Topics requiring extra care are identified

### Compliance Gates
- **Domain Restrictions**: Enterprise deployments can restrict topic areas
- **Audit Logging**: All decisions are logged for compliance review
- **Policy Enforcement**: Custom policies can be defined and enforced

## What-If Simulation

The Developer tier includes a What-If Simulator that allows testing how different gate configurations affect responses. This enables:
- Tuning thresholds for specific use cases
- Understanding edge cases
- Validating policy changes before deployment

## Graceful Degradation

When gates block a response, Symbol-μ doesn't simply fail. It provides:
- Explanation of why the response was blocked
- Alternative approaches when possible
- Escalation paths for human review`,
    publishedAt: '2024-12-28',
    author: 'Symbol-μ Research',
    tags: ['governance', 'safety', 'quality'],
  },
  {
    id: 'rag-integration',
    title: 'RAG Integration: Knowledge Base Lookup Architecture',
    shortDescription: 'How Symbol-μ integrates with retrieval-augmented generation pipelines.',
    content: `Symbol-μ is designed from the ground up to work with Retrieval-Augmented Generation (RAG) systems. The Explorer tier provides a streamlined interface for knowledge base lookup that combines the power of semantic search with our structured cognitive framework.

## The RAG Pipeline

Our RAG integration follows a multi-stage process:

### 1. Query Understanding
Before retrieval, queries are analyzed through the ontological substrate to determine:
- Primary knowledge domains
- Required information types
- Confidence requirements
- Temporal constraints

### 2. Intelligent Retrieval
Retrieval is guided by ontological understanding:
- Domain-aware embedding selection
- Hierarchical search strategies
- Relevance scoring with context
- Source diversity optimization

### 3. Knowledge Fusion
Retrieved documents are processed through:
- Conflict detection and resolution
- Source credibility weighting
- Temporal relevance adjustment
- Coherence with session context

### 4. Response Generation
Final responses include:
- Synthesized knowledge presentation
- Source attribution
- Confidence indicators
- Suggested follow-up queries

## Quality Indicators

The Explorer tier surfaces quality through simple, intuitive badges:
- **Trust badges**: Indicate source reliability
- **Freshness indicators**: Show knowledge recency
- **Coverage markers**: Highlight comprehensive answers

## Enterprise Integration

For enterprise deployments, Symbol-μ RAG supports:
- Custom knowledge base connections
- Access control integration
- Usage analytics and reporting
- Feedback loop integration`,
    publishedAt: '2024-12-20',
    author: 'Symbol-μ Research',
    tags: ['RAG', 'retrieval', 'knowledge'],
  },
  {
    id: 'session-management',
    title: 'Session Intelligence and Persona Stability',
    shortDescription: 'Maintaining coherent, stable interactions across multi-turn conversations.',
    content: `Long conversations present unique challenges for AI systems. Symbol-μ addresses these through sophisticated session management that maintains coherence, tracks persona stability, and enables intelligent intervention.

## Session State Tracking

Every session maintains rich state information:
- **Turn history**: Complete conversation record
- **Coherence trajectory**: How coherence has evolved
- **Topic graph**: Semantic map of discussed topics
- **User model**: Inferred preferences and patterns
- **Commitment log**: Statements the system has committed to

## Persona Stability

Persona drift—where an AI gradually contradicts its earlier statements—is a major challenge. Symbol-μ addresses this through:

### Commitment Tracking
Every factual claim is logged with context. Before making new claims, the system checks for potential contradictions.

### Style Consistency
Response style (formality, verbosity, tone) is monitored and maintained unless explicitly adjusted.

### Role Coherence
If the system is playing a specific role, that role's constraints are continuously enforced.

## Intervention Strategies

When coherence drops or persona drift is detected, the system can:
- **Self-correct**: Acknowledge and correct inconsistencies
- **Clarify**: Ask for clarification to resolve ambiguity
- **Reset**: Offer to restart a confused conversation
- **Escalate**: Flag for human review in critical cases

## Timeline Visualization

The Developer tier includes a Session Timeline that visualizes:
- Key events in the conversation
- Coherence changes over time
- Intervention points
- Topic transitions

This enables both real-time monitoring and post-hoc analysis of conversation dynamics.`,
    publishedAt: '2024-12-15',
    author: 'Symbol-μ Research',
    tags: ['sessions', 'persona', 'coherence'],
  },
];

export function getArticleById(id: string): Article | undefined {
  return articles.find(article => article.id === id);
}

export function getArticlesByTag(tag: string): Article[] {
  return articles.filter(article => article.tags.includes(tag));
}
