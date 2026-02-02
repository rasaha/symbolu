# Agentic LLM Framework: A Layman's Guide

## What Is This Framework?

Think of this framework as a **smart wrapper** that goes around existing AI assistants (like ChatGPT, Claude, or Gemini) to make them more reliable, self-aware, and safer.

Imagine you hired a new employee. They're smart, but they:
- Sometimes give answers without thinking them through
- Don't remember what you talked about earlier
- Can't tell when they're getting confused
- Might take actions they shouldn't
- Cost a fortune for simple questions

This framework adds a "management layer" that helps AI assistants:
- **Think before speaking** (reflective loop)
- **Remember conversations** (memory store)
- **Know what you actually want** (goal decomposition)
- **Monitor their own quality** (coherence tracking)
- **Stay within safe boundaries** (safety contracts)
- **Be cost-effective** (local critic for cheap reflection)
- **Learn from experience** (adaptive policy engine)
- **Act on confidence, not display it** (confidence gate)

---

## The Eight Core Components

### 1. Goal Decomposition (The "What Do You Really Want?" Module)

**Plain English:** When you ask something, this component figures out what you actually need.

**Example:**
- You say: "Help me fix my login bug"
- Framework understands:
  - Type: Task (not just information)
  - Actions needed: Read code, find bug, suggest fix
  - Agency level: CONFIRM (should ask before making changes)

**Why It Matters:** Regular AI might start rambling. This ensures the AI understands whether you want information, a task done, or creative help.

```
Your Request → [Goal Decomposition] → Clear Action Plan
```

---

### 2. Memory Store (The "I Remember Our Conversation" Module)

**Plain English:** Keeps track of everything discussed, so the AI doesn't forget context or repeat itself.

**How It Works:**
- Stores each exchange (your question + AI's response)
- Tracks quality of each response
- Can recall relevant past conversations
- Never loses important context

**Example:**
```
Turn 1: "What is Python?" → Stored with quality score 0.9
Turn 2: "How do I install it?" → AI knows you mean Python
Turn 3: "Write a hello world" → AI remembers the full context
```

**Why It Matters:** Without memory, every message is like talking to someone with amnesia.

---

### 3. Reflective Loop (The "Let Me Double-Check That" Module)

**Plain English:** Before giving you an answer, the AI reviews its own work and improves it if needed.

**The Process:**
```
Generate Draft → Critique It → Good Enough? → No → Revise → Repeat
                                    ↓
                                   Yes → Send to User
```

**Quality Checks:**
- Is it long enough? (completeness)
- Does it make sense? (coherence)
- Is it accurate? (correctness)
- Does it answer the question? (relevance)

**Example:**
- Draft 1: "Python is good." (Score: 0.3 - too short)
- Draft 2: "Python is a programming language used for..." (Score: 0.7 - better)
- Draft 3: Full explanation with examples (Score: 0.9 - approved!)

**Why It Matters:** First drafts aren't always best. Self-review catches errors before you see them.

---

### 4. Coherence Tracker (The "Am I Making Sense?" Module)

**Plain English:** Monitors whether the AI is staying consistent and logical throughout the conversation.

**7 Metrics Tracked:**

| Metric | What It Measures |
|--------|------------------|
| Internal Consistency | Are my answers contradicting each other? |
| Prediction Reversal Risk | Am I flip-flopping on opinions? |
| Volatility | Is my quality jumping around? |
| Goal Alignment | Am I still focused on what you asked? |
| Factual Alignment | Am I sticking to facts? |
| Identity Stability | Am I behaving consistently? |
| Drift Magnitude | How far have I strayed from the topic? |

**Why It Matters:** Catches when the AI is "going off the rails" before it becomes a problem.

---

### 5. Safety Contract (The "Should I Actually Do This?" Module)

**Plain English:** A gatekeeper that checks if an action should be allowed before the AI takes it.

**How It Works:**
```
Proposed Action → [Safety Gate] → Allowed? → Yes → Proceed
                                     ↓
                                    No → Block + Explain Why
```

**What Gets Blocked:**
- Actions when coherence is too low
- Destructive operations without confirmation
- Tasks outside the AI's authorized scope
- Requests during unstable conversation states

**Fail-Closed Design:** If unsure, the answer is NO. Better safe than sorry.

**Why It Matters:** Prevents AI from taking harmful actions, even if asked to.

---

### 6. Local Critic (The "Don't Break the Bank" Module)

**Plain English:** Uses small, local AI models to evaluate quality instead of expensive API calls, reducing costs by 100x while maintaining quality.

**The Problem It Solves:**
```
Traditional Approach:
  User Query → GPT-4 generates → GPT-4 critiques → GPT-4 revises
  Cost: $0.10+ per interaction (3+ API calls)

Our Approach:
  User Query → GPT-4 generates → Local Phi-3 critiques → Maybe revise
  Cost: $0.03 per interaction (1 API call + free local critique)
```

**How It Works:**

The Local Critic uses small, efficient models running on your own hardware:

| Backend | Model Examples | Best For |
|---------|---------------|----------|
| **Ollama** | phi3:mini, llama3.2:3b | Easy setup, good balance |
| **Transformers** | Phi-3-mini, Mistral-7B | Full control, GPU acceleration |
| **llama.cpp** | Any GGUF model | Minimal dependencies, CPU-friendly |

**Cost Comparison:**

| Method | Cost per 1,000 Evaluations | Speed |
|--------|---------------------------|-------|
| GPT-4 API | $30.00 | 500ms |
| Claude API | $15.00 | 400ms |
| **Local Phi-3** | **$0.10** | **150ms** |
| Rule-based | $0.00 | 1ms |

**Cost-Aware Auto-Selection:**

The framework automatically chooses the right critic based on complexity:

```
Simple Question ("Hi!")
  → Rule-based critic (free, instant)

Medium Question ("What is Python?")
  → Local Phi-3 critic ($0.0001, 150ms)

Complex Question ("Explain quantum computing in detail")
  → API critic if budget allows ($0.01, 500ms)
```

**Configuration Options:**

```python
from symbolu.agentic_framework import create_cost_aware_critic, SelectionStrategy

# Create cost-aware critic with budget constraints
critic = create_cost_aware_critic(
    local_model="phi3:mini",
    strategy=SelectionStrategy(
        max_cost_per_eval=0.01,       # Max $0.01 per evaluation
        complexity_threshold_api=0.8,  # Only use API for very complex
        max_latency_ms=500,            # Must respond within 500ms
    )
)
```

**Why It Matters:**
- Makes quality-focused AI economically viable for production
- 10-100x cost reduction without significant quality loss
- Enables always-on quality monitoring that was previously too expensive
- Keeps sensitive data local (no API calls for evaluation)

---

### 7. Adaptive Policy Engine (The "Learn From Experience" Module)

**Plain English:** The AI learns from past interactions to improve future behavior - not by storing logs, but by adjusting its internal operating parameters.

**This Is NOT Commodity Learning:**
```
❌ Commodity Approach:
   Logs → Embeddings → RAG retrieval
   (Everyone does this. No moat.)

✅ Our Structural Approach:
   Past Performance → Policy Parameters → Behavior Change
   (Real leverage. Modifies budgets, thresholds, tool access.)
```

**What It Actually Modifies:**

| Parameter | How It Changes | Based On |
|-----------|---------------|----------|
| Quality thresholds | Relaxed when improving, tightened when declining | Quality trend |
| Revision budget | Increased when revisions needed frequently | Revision rate |
| Tool permissions | Expanded with good coherence, restricted with instability | Coherence history |
| Response style | "grounded" for fear, "reflective" for hope | Session trajectory |
| Attention budget | Increased for struggling sessions | Trajectory type |
| Decay rates | Slower decay for recovering sessions | Recovery pattern |

**Session Trajectory Classification:**

The engine classifies each session into one of 8 trajectory types:

| Trajectory | Pattern | Policy Response |
|------------|---------|-----------------|
| **hope_driven** | Improving quality, breakthroughs | Encourage exploration, relax thresholds |
| **fear_driven** | Fragmentation, high volatility | Ground responses, increase attention |
| **expansion_driven** | Good quality, exploring | Support growth, allow experimentation |
| **stabilization_driven** | Recovering from decline | Gentle guidance, gradual normalization |
| **overcorrection** | Sharp oscillations | Add damping, reduce revision budget |
| **avoidance_driven** | Flat metrics, low engagement | Encourage engagement, exploratory style |
| **stable** | Consistent high coherence | Allow deeper reflection |
| **unknown** | Not enough data | Default conservative behavior |

**SCC-Inspired Parameter Tuning:**

Uses gradient descent on policy parameters (inspired by CTM+ Self-tuning Coherence Control):

```
θ_{t+1} = θ_t + ρ * ∇_θ C_global(t)

Where:
  θ = Policy parameters (thresholds, budgets, etc.)
  ρ = Learning rate (default 0.05)
  C_global = Global coherence/quality metric
  ∇_θ = Gradient based on recent performance
```

**Example Flow:**

```
Turn 1: Quality=0.5, Coherence=0.4
        → Engine records: "struggling"
        → Increases attention budget

Turn 2: Quality=0.6, Coherence=0.5
        → Engine records: "improving"
        → Classifies as "stabilization_driven"
        → Sets response style to "grounded"

Turn 3: Quality=0.8, Coherence=0.7
        → Engine records: "breakthrough!"
        → Classifies as "hope_driven"
        → Relaxes quality thresholds
        → Upgrades tool permissions
```

**Usage:**

```python
from symbolu.agentic_framework import (
    AdaptivePolicyEngine,
    create_adaptive_policy_engine,
)

# Create engine
engine = create_adaptive_policy_engine(learning_rate=0.05)

# Record turn performance
engine.record_turn(
    session_id="session-123",
    quality_score=0.85,
    revision_count=0,
    coherence_score=0.78,
)

# Get policy decision for next turn
decision = engine.get_policy_decision("session-123")

# Use in your agent
print(f"Quality threshold: {decision.quality_threshold}")
print(f"Revision budget: {decision.revision_budget}")
print(f"Tool permission: {decision.tool_permission}")
print(f"Response style: {decision.response_style}")
print(f"Trajectory: {decision.trajectory}")
```

**Why It Matters:**
- Goes beyond "store what worked" to "modify how I behave"
- Provides structural leverage, not commodity log retrieval
- Based on CTM+ (Coherence Tier Memory) research
- Enables true adaptive behavior without retraining

---

### 8. Confidence Gate (The "Confidence That Controls Behavior" Module)

**Plain English:** Confidence scores that actually CONTROL what the AI does, not just numbers displayed to users.

**This Is NOT Cosmetic Confidence:**
```
❌ Cosmetic Approach:
   Generate response → Compute confidence → Display "85% confident"
   (User sees a number. Nothing changes.)

✅ Behavioral Approach:
   Generate response → Compute confidence → Gate execution
   (Low confidence = more revisions, human escalation, blocked actions)
```

**What Confidence Actually Controls:**

| Control | Low Confidence | High Confidence |
|---------|---------------|-----------------|
| **Escalation** | HALT or CONFIRM required | No escalation |
| **Revisions** | 5 max, 75% quality bar | 2 max, 85% quality bar |
| **Memory** | Don't store (pollutes context) | Store permanently |
| **Execution** | BLOCKED or require confirmation | FULL execution |
| **Attention** | 1.5x compute budget | 0.9x compute budget |

**Escalation Levels:**

```
Confidence ≥ 0.75  →  NONE      (Proceed normally)
0.55 ≤ C < 0.75    →  NOTIFY    (Inform human, but proceed)
0.35 ≤ C < 0.55    →  CONFIRM   (Require human confirmation)
C < 0.35           →  HALT      (Stop and wait for human)
```

**Confidence Signal Sources:**

The gate aggregates existing signals from the framework:

| Signal Source | Signals Used |
|--------------|--------------|
| QualityCritique | overall_score, coherence, correctness |
| CoherenceMetrics | internal_consistency, goal_alignment, volatility |
| AdaptivePolicyEngine | trajectory_confidence, session_stability |
| Action Analysis | complexity, reversibility |

**Example Flow:**

```
User: "Delete all files in /home"

Step 1: Aggregate signals
  - Quality score: 0.6 (ambiguous request)
  - Coherence: 0.7 (consistent with context)
  - Action reversibility: 0.0 (irreversible!)
  - Action complexity: 0.9 (high risk)

Step 2: Compute unified confidence
  - Overall confidence: 0.38 (weighted average)

Step 3: Gate decisions
  - Escalation: CONFIRM (requires human confirmation)
  - Execution: BLOCKED (irreversible + low confidence)
  - Memory: Don't store
  - Budget: 5 revisions allowed, self-check required

Result: "I need confirmation before deleting files. This action is irreversible."
```

**Usage:**

```python
from symbolu.agentic_framework import (
    ConfidenceGate,
    ConfidenceSignals,
    create_confidence_gate,
    create_strict_confidence_gate,
    signals_from_critique,
    signals_from_coherence_metrics,
    merge_signals,
)

# Create gate (or use create_strict_confidence_gate() for high-stakes)
gate = create_confidence_gate()

# Build signals from existing framework components
critique_signals = signals_from_critique(quality_critique)
coherence_signals = signals_from_coherence_metrics(coherence_metrics)
combined = merge_signals(critique_signals, coherence_signals)

# Add action-specific signals
combined.action_complexity = 0.9      # High complexity
combined.action_reversibility = 0.0   # Cannot undo

# Get gating decision
decision = gate.evaluate(combined, action="file_delete")

# Use the decision
if decision.escalation.requires_human:
    await get_human_confirmation(decision.escalation.suggested_questions)

if decision.execution.can_execute:
    execute_action()
else:
    explain_instead()

if decision.memory.should_store:
    store_with_weight(decision.memory.retention_weight)
```

**Quick Check for Simple Cases:**

```python
# Fast check with just quality and coherence
can_proceed, reason = gate.quick_check(
    quality_score=0.8,
    coherence_score=0.9,
    action="search"
)

if not can_proceed:
    print(f"Blocked: {reason}")
```

**Preset Configurations:**

```python
# Standard gate (balanced)
standard_gate = create_confidence_gate()

# Strict gate (high-stakes applications)
strict_gate = create_strict_confidence_gate()
# Thresholds: halt=0.45, confirm=0.65, notify=0.85

# Permissive gate (rapid prototyping)
permissive_gate = create_permissive_confidence_gate()
# Thresholds: halt=0.20, confirm=0.40, notify=0.60
```

**Why It Matters:**
- Confidence CONTROLS behavior, doesn't just annotate output
- Automatic escalation prevents AI from acting on uncertain decisions
- Budget allocation ensures uncertain responses get more scrutiny
- Memory gating prevents low-confidence responses from polluting context
- Action gating provides defense-in-depth beyond safety contracts

---

## How It All Works Together

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR MESSAGE                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              1. GOAL DECOMPOSITION                           │
│         "What does the user actually want?"                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 2. MEMORY STORE                              │
│         "What context do we have?"                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              3. REFLECTIVE LOOP                              │
│         "Generate → Critique → Revise"                       │
│                      │                                       │
│              ┌───────┴───────┐                               │
│              ▼               ▼                               │
│     ┌─────────────┐  ┌─────────────┐                        │
│     │ Local Critic│  │  API Critic │                        │
│     │   (Cheap)   │  │ (Expensive) │                        │
│     │   $0.0001   │  │   $0.01     │                        │
│     └─────────────┘  └─────────────┘                        │
│              │               │                               │
│              └───────┬───────┘                               │
│                      ▼                                       │
│            Cost-Aware Selection                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             4. COHERENCE TRACKER                             │
│         "Is this response consistent?"                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              5. SAFETY CONTRACT                              │
│         "Is this action allowed?"                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FINAL RESPONSE                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Real-World Use Cases

### 1. Customer Support Bot
- **Memory:** Remembers customer history across the conversation
- **Coherence:** Doesn't contradict previous support advice
- **Safety:** Won't promise refunds it can't authorize
- **Local Critic:** Evaluates thousands of responses daily without API costs

### 2. Coding Assistant
- **Goal Decomposition:** Understands if you want explanation vs. code
- **Reflective Loop:** Reviews code for bugs before showing you
- **Safety:** Won't execute destructive commands without confirmation
- **Local Critic:** Fast local evaluation keeps iteration cycles quick

### 3. Research Assistant
- **Memory:** Tracks all sources and findings discussed
- **Coherence:** Maintains consistent analysis throughout
- **Reflective Loop:** Fact-checks claims before presenting
- **Local Critic:** Enables comprehensive quality checks on every response

### 4. Workflow Automation
- **Goal Decomposition:** Breaks complex tasks into steps
- **Safety:** Requires approval before irreversible actions
- **Coherence:** Ensures steps don't contradict each other
- **Local Critic:** Makes continuous monitoring affordable at scale

### 5. High-Volume Applications
- **Local Critic:** Process 100,000+ daily requests affordably
- **Cost-Aware Selection:** Auto-scales critic quality with demand
- **Rule-Based Fallback:** Handles simple queries at zero cost

---

## How We Compare to Other Agentic Models

### Industry Landscape

| Framework | Approach | Our Difference |
|-----------|----------|----------------|
| **LangChain** | Chain prompts together | We add quality monitoring + safety gates + cost optimization |
| **AutoGPT** | Fully autonomous agents | We favor human-in-loop with safety checks |
| **CrewAI** | Multi-agent collaboration | We focus on single-agent coherence first |
| **Microsoft AutoGen** | Conversational agents | We add coherence tracking + fail-closed safety |
| **OpenAI Assistants** | API-based assistants | We wrap any LLM with consistent behavior + local inference |

### Key Differentiators

#### 1. **Coherence-First Design**
Most frameworks assume the AI is always coherent. We don't.

```
Others:     User → LLM → Response
Us:         User → LLM → [Coherence Check] → [Safe?] → Response
```

#### 2. **Fail-Closed Safety**
Most systems fail-open (allow unless explicitly blocked). We fail-closed.

| Approach | If Unsure... | Risk Level |
|----------|--------------|------------|
| Fail-Open | Allow action | Higher |
| **Fail-Closed (Ours)** | Block action | Lower |

#### 3. **Self-Reflection Built-In**
Not an afterthought - the reflective loop is core to every response.

```
LangChain:  Generate → Done
AutoGPT:    Generate → Execute → Maybe check
Us:         Generate → Critique → Revise → Check Coherence → Safety Gate → Done
```

#### 4. **LLM-Agnostic**
Works with any language model:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Open source (Llama, Mistral)
- Custom models

#### 5. **Observable State**
Every decision is trackable:
```python
result = agent.run("Help me with this")

# You can inspect:
result.quality_score      # How good was this response?
result.revision_count     # How many drafts did it take?
result.coherence          # Is the conversation still on track?
result.goal_state         # What did it think you wanted?
```

#### 6. **Cost-Optimized Reflection**
We're the only framework with built-in cost-aware quality evaluation:

```
Others:     Every critique = API call = $$$
Us:         Smart routing: Local ($0.0001) → API ($0.01) only when needed
```

**Monthly Cost Comparison (100K requests):**

| Approach | Monthly Cost |
|----------|-------------|
| Full API critique | $3,000 |
| **Our hybrid approach** | **$100-300** |
| Rule-based only | $0 (but lower quality) |

---

## Comparison Deep Dive

### vs. LangChain

| Aspect | LangChain | Agentic LLM Framework |
|--------|-----------|----------------------|
| Focus | Prompt chaining & tools | Quality & safety & cost |
| Memory | External vector stores | Built-in with semantic search |
| Self-check | Optional chains | Mandatory reflective loop |
| Safety | User-implemented | Built-in fail-closed gates |
| Coherence | Not tracked | 7-metric monitoring |
| **Cost optimization** | None | Local critic + auto-selection |

**When to use LangChain:** Complex tool integrations, RAG systems
**When to use us:** Reliable, safe, cost-effective responses

### vs. AutoGPT

| Aspect | AutoGPT | Agentic LLM Framework |
|--------|---------|----------------------|
| Autonomy | Fully autonomous | Human-in-loop preferred |
| Safety | Limited guardrails | Fail-closed by default |
| Control | Minimal | High observability |
| Use case | Autonomous tasks | Assisted workflows |
| **Cost** | High (many API calls) | Optimized (local critics) |

**When to use AutoGPT:** Fully automated background tasks
**When to use us:** Tasks requiring reliability, oversight, and cost control

### vs. OpenAI Assistants API

| Aspect | OpenAI Assistants | Agentic LLM Framework |
|--------|-------------------|----------------------|
| Provider | OpenAI only | Any LLM provider |
| Memory | OpenAI-managed | User-controlled |
| Quality | Trust OpenAI | Verify with metrics |
| Cost | Per-message | Control your costs |
| **Local inference** | Not available | Built-in support |

**When to use OpenAI Assistants:** Simple OpenAI-only projects
**When to use us:** Multi-provider, quality-critical, cost-sensitive applications

---

## Technical Architecture (Simplified)

```
┌────────────────────────────────────────────────────────────────┐
│                    AgenticLLMWrapper                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ Any LLM API  │ │ Memory Store │ │ Coherence Engine     │    │
│  │ (OpenAI,     │ │ (Append-only │ │ (7 metrics,          │    │
│  │  Claude,     │ │  semantic    │ │  drift detection,    │    │
│  │  Gemini)     │ │  search)     │ │  intervention        │    │
│  └──────────────┘ └──────────────┘ │  triggers)           │    │
│                                     └──────────────────────┘    │
│  ┌──────────────────────────────┐  ┌──────────────────────┐    │
│  │ Reflective Generator         │  │ Safety Gate          │    │
│  │ (Generate → Critique →       │  │ (Fail-closed,        │    │
│  │  Decide → Revise)            │  │  6 preconditions,    │    │
│  └──────────────────────────────┘  │  action filtering)   │    │
│              │                      └──────────────────────┘    │
│              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Cost-Aware Critic Selector                                │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │  │
│  │  │ Rule-Based  │ │ Local Model │ │  API Model  │         │  │
│  │  │   (Free)    │ │  ($0.0001)  │ │   ($0.01)   │         │  │
│  │  │  Simple Qs  │ │  Medium Qs  │ │  Complex Qs │         │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘         │  │
│  │        Ollama │ Transformers │ llama.cpp                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Goal Decomposition (Purpose → Actions → Agency Level)    │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

---

## Quick Start Examples

### Basic Usage

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import OpenAIAdapter

# Wrap any LLM
llm = OpenAIAdapter(api_key="your-key", model="gpt-4")
agent = AgenticLLMWrapper(llm)

# Start a session
agent.new_session("customer-support-123")

# Run with full protection
result = agent.run("How do I reset my password?")

# Inspect the result
print(result.response)           # The actual answer
print(result.quality_score)      # 0.0-1.0 quality rating
print(result.coherence)          # Coherence metrics
print(result.revision_count)     # How many drafts it took
```

### Using Local Critics (Cost-Optimized)

```python
from symbolu.agentic_framework import (
    create_ollama_critic,
    create_cost_aware_critic,
    SelectionStrategy,
    ReflectiveGenerator,
)
from symbolu.agentic_framework.llm_adapters import OpenAIAdapter

# Option 1: Direct local critic (always use local model)
local_critic = create_ollama_critic(model="phi3:mini")

# Option 2: Cost-aware auto-selection (recommended)
smart_critic = create_cost_aware_critic(
    local_model="phi3:mini",
    strategy=SelectionStrategy(
        max_cost_per_eval=0.005,      # Budget cap per evaluation
        complexity_threshold_api=0.8,  # Use API only for complex queries
    )
)

# Use with ReflectiveGenerator
llm = OpenAIAdapter(api_key="your-key", model="gpt-4")
generator = ReflectiveGenerator(
    llm_client=llm,
    critic=local_critic,  # or smart_critic
    threshold_high=0.85,
    max_revisions=3,
)

result = generator.generate("Explain machine learning")
print(f"Quality: {result.quality_score}, Revisions: {result.revision_count}")
```

### Benchmarking Critics

```bash
# Compare rule-based vs local model critics
python -m symbolu.agentic_framework.benchmark_critics

# With specific Ollama model
python -m symbolu.agentic_framework.benchmark_critics --ollama phi3:mini

# Output as JSON for analysis
python -m symbolu.agentic_framework.benchmark_critics --json
```

---

## Summary

| Feature | What It Does | Why It Matters |
|---------|--------------|----------------|
| Goal Decomposition | Understands intent | Right type of response |
| Memory Store | Remembers context | Consistent conversations |
| Reflective Loop | Self-reviews answers | Higher quality output |
| Coherence Tracker | Monitors consistency | Catches degradation early |
| Safety Contract | Gates dangerous actions | Prevents harmful outcomes |
| **Local Critic** | **Cheap quality evaluation** | **100x cost reduction** |
| **Adaptive Policy** | **Learns from experience** | **Structural leverage, not logs** |
| **Confidence Gate** | **Behavioral confidence control** | **Confidence controls, not annotates** |

**Bottom Line:** This framework doesn't make AI smarter - it makes AI more reliable, predictable, safe, and **affordable** by adding oversight layers that catch problems before they reach users, while keeping costs under control through intelligent local inference and behavioral confidence gating.

---

## Local Critic Deep Dive

### Supported Backends

#### 1. Ollama (Recommended for Getting Started)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull phi3:mini

# Start server (runs automatically on install)
ollama serve
```

```python
from symbolu.agentic_framework import create_ollama_critic

critic = create_ollama_critic(
    model="phi3:mini",           # or llama3.2:3b, mistral, etc.
    host="http://localhost:11434"
)
```

#### 2. HuggingFace Transformers (More Control)

```bash
pip install transformers torch
```

```python
from symbolu.agentic_framework import create_transformers_critic

critic = create_transformers_critic(
    model_id="microsoft/phi-3-mini-4k-instruct",
    device="cuda"  # or "cpu", "auto"
)
```

#### 3. llama.cpp (Minimal Dependencies)

```bash
pip install llama-cpp-python
# Download a GGUF model file
```

```python
from symbolu.agentic_framework import create_llamacpp_critic

critic = create_llamacpp_critic(
    model_path="/path/to/phi-3-mini-Q4_K_M.gguf",
    n_gpu_layers=-1  # Use GPU for all layers
)
```

### Recommended Models by Use Case

| Use Case | Model | Size | Quality | Speed |
|----------|-------|------|---------|-------|
| Fast iteration | phi3:mini | 3.8B | Good | Fast |
| Balanced | llama3.2:3b | 3B | Good | Fast |
| Higher quality | mistral:7b | 7B | Better | Medium |
| Code review | codellama:7b | 7B | Best for code | Medium |

### Cost-Aware Selection Strategy

```python
from symbolu.agentic_framework import SelectionStrategy

# Conservative (minimize cost)
cheap_strategy = SelectionStrategy(
    complexity_threshold_local=0.2,  # Use rules for simple queries
    complexity_threshold_api=0.95,   # Almost never use API
    max_cost_per_eval=0.001,
)

# Balanced (good quality/cost trade-off)
balanced_strategy = SelectionStrategy(
    complexity_threshold_local=0.3,
    complexity_threshold_api=0.7,
    max_cost_per_eval=0.01,
)

# Quality-first (best quality, higher cost)
quality_strategy = SelectionStrategy(
    complexity_threshold_local=0.1,
    complexity_threshold_api=0.5,
    max_cost_per_eval=0.05,
)
```

---

## Further Reading

- **Implementation Details:** See `symbolu/agentic_framework/` source code
- **Validation:** Run `python -m symbolu.agentic_framework.validate`
- **Tests:** Run `pytest symbolu/agentic_framework/tests/ -v`
- **Benchmark Critics:** Run `python -m symbolu.agentic_framework.benchmark_critics`
- **Phase-Quad Origins:** See `docs/design/` for theoretical foundations
