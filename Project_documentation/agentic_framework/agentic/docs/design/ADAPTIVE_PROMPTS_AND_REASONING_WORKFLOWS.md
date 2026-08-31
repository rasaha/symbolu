# Adaptive Prompts and Reasoning Workflows

## Status: TECHNICAL REFERENCE

**Author**: Symbol-U Architecture
**Date**: February 2026
**Version**: 2.0
**Modules**: `symbolu.agentic_framework.adaptive_prompts`, `symbolu.agentic_framework.reasoning_workflows`

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Design Philosophy](#2-design-philosophy)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Component 1: ComplexityDetector](#4-component-1-complexitydetector)
5. [Component 2: AdaptivePromptEngine](#5-component-2-adaptivepromptengine)
6. [Component 3: AutoReasoningPipeline](#6-component-3-autoreasoningpipeline)
7. [Reasoning Depth Levels](#7-reasoning-depth-levels)
8. [Progressive Disclosure Model](#8-progressive-disclosure-model)
9. [Reasoning Workflow Catalog](#9-reasoning-workflow-catalog)
   - [9.1 LinearChain](#91-linearchain)
   - [9.2 TreeOfThought](#92-treeofthought)
   - [9.3 IterativeRefinement](#93-iterativerefinement)
   - [9.4 Debate (Adversarial)](#94-debate-adversarial)
   - [9.5 MapReduce](#95-mapreduce)
   - [9.6 SocraticProgressive](#96-socraticprogressive)
   - [9.7 Metacognitive](#97-metacognitive)
10. [Workflow Selection: Signal-to-Workflow Mapping](#10-workflow-selection-signal-to-workflow-mapping)
11. [Workflow Comparison Matrix](#11-workflow-comparison-matrix)
12. [When To Use Which Workflow](#12-when-to-use-which-workflow)
13. [Invariants](#13-invariants)
14. [Integration Points](#14-integration-points)
15. [Configuration Reference](#15-configuration-reference)
16. [Test Coverage](#16-test-coverage)

---

## 1. Problem Statement

Standard LLM interactions have a fundamental limitation: they apply the same reasoning effort to every query regardless of complexity. A user asking "What is 2+2?" gets the same computational structure as a user asking "Compare the philosophical implications of quantum entanglement with theories of consciousness and design a framework for testing these ideas."

This creates two problems:

1. **Simple queries get over-processed**: Wasted compute, slower responses, and unnecessary complexity in the output that confuses the user.

2. **Complex queries get under-processed**: A single LLM call cannot reliably perform multi-step reasoning, leading to surface-level answers that miss nuance, causal chains, and edge cases.

Additionally, even when a system detects that deeper reasoning is needed, automatically dumping 4 steps of analysis on the user creates **information overload**. The system pushes faster than the user can assimilate.

### What We Need

A system that:
- Detects query complexity automatically (10 signal types)
- Knows HOW DEEP it can reason (4 depth levels)
- Knows WHICH WORKFLOW fits the problem type (7 workflow patterns)
- Starts with a concise answer (progressive disclosure)
- Lets the USER pull deeper reasoning at their own pace
- Exposes the full reasoning trace transparently

---

## 2. Design Philosophy

### Progressive Disclosure (Pull, Not Push)

```
OLD MODEL (Push):
    User asks → System detects complexity → Auto-dumps 4-step analysis
    Problem: Information overload. User didn't ask for this.

NEW MODEL (Pull):
    User asks → System answers concisely → Hints: "deeper available"
    User says "go deeper" → System goes one level deeper
    User says "go deeper" → System goes another level
    User stops when satisfied
```

### Core Principles

1. **Start SHALLOW always**. One LLM call. Concise answer. Respect the user's attention.

2. **Detect but don't act**. The ComplexityDetector runs on every query to know what's available, but the system does NOT auto-escalate by default.

3. **One level at a time**. `deepen()` goes SHALLOW → MODERATE → DEEP → RECURSIVE. Never jumps two levels. Each step is an incremental enrichment.

4. **Right workflow for right problem**. A comparison question needs MapReduce, not LinearChain. A conditional-logic question needs Debate, not TreeOfThought. The system knows which pattern fits.

5. **Glass box, not black box**. Every step is traced. The user can inspect `get_reasoning_trace()` to see exactly how the system reasoned.

---

## 3. System Architecture Overview

```
                            USER QUERY
                                │
                    ┌───────────▼───────────┐
                    │   ComplexityDetector   │
                    │   (10 signal types)    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Complexity Analysis  │
                    │   - signals detected   │
                    │   - depth_available    │
                    │   - workflow suggested │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                   │
     ┌────────▼────────┐  ┌────▼────┐  ┌──────────▼──────────┐
     │ AdaptivePrompt   │  │ Workflow │  │  WorkflowSelector   │
     │ Engine (depth)   │  │ Registry │  │  (signal → workflow) │
     └────────┬────────┘  └────┬────┘  └──────────┬──────────┘
              │                 │                   │
              └─────────────────┼───────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │ AutoReasoningPipeline  │
                    │   OR                   │
                    │ Selected Workflow       │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   SHALLOW Result       │
                    │   + depth_hint         │
                    │   + can_deepen         │
                    └───────────┬───────────┘
                                │
                          User decides
                         to deepen()?
                          /        \
                        No          Yes
                        │            │
                     DONE    ┌──────▼──────┐
                             │  Next depth  │
                             │  level       │
                             └──────┬──────┘
                                    │
                              (repeat until
                               max depth or
                               user stops)
```

### Module Structure

```
symbolu/agentic_framework/
├── adaptive_prompts.py         # ComplexityDetector, AdaptivePromptEngine,
│                                # AutoReasoningPipeline, progressive disclosure
├── reasoning_workflows.py      # 7 workflow patterns, WorkflowSelector,
│                                # WorkflowRegistry, MetacognitiveWorkflow
└── tests/
    ├── test_adaptive_prompts.py    # 72 tests
    └── test_reasoning_workflows.py # 103 tests
```

---

## 4. Component 1: ComplexityDetector

### Purpose

Analyzes every user input to classify its complexity across three dimensions and detect specific complexity signals. Runs automatically on every query.

### Three Dimensions of Complexity

| Dimension | What It Measures | Weight | Example |
|-----------|-----------------|--------|---------|
| **Lexical** | Word length, sentence structure, vocabulary diversity, total length | 0.20 | Long sentences with diverse vocabulary → higher |
| **Structural** | Question count, nested clauses, enumeration, code markers, conditionals | 0.25 | Multiple questions with numbered lists → higher |
| **Semantic** | Conceptual depth from detected signals, weighted by signal difficulty | 0.55 | Causal + abstract signals → much higher |

### 10 Complexity Signals

| Signal | Detection Pattern | Weight | Example Query |
|--------|------------------|--------|--------------|
| `MULTI_PART_QUESTION` | "X and Y?", "also", numbered lists, multiple `?` | 0.3 | "What is X, and also how does Y work?" |
| `CAUSAL_REASONING` | "why", "because", "cause", "how does", "explain" | 0.5 | "Why does increasing X cause Y?" |
| `COMPARISON_REQUEST` | "compare", "versus", "pros and cons", "better" | 0.4 | "Compare the advantages of A vs B" |
| `ABSTRACT_CONCEPT` | "concept", "theory", "philosophy", "implications" | 0.6 | "Explain the nature of consciousness" |
| `CONDITIONAL_LOGIC` | "if", "unless", "assuming", "hypothetically" | 0.5 | "If we assume X, what would happen?" |
| `TEMPORAL_REASONING` | "timeline", "evolution", "over time", "sequence" | 0.4 | "Trace the evolution of X over time" |
| `CREATIVE_SYNTHESIS` | "design", "create", "novel", "combine", "synthesize" | 0.6 | "Design a novel approach combining X and Y" |
| `DOMAIN_EXPERTISE` | (reserved for future domain-specific detection) | 0.5 | Domain-specific terminology density |
| `AMBIGUITY_DETECTED` | Short question (<8 words) with `?` and no other signals | 0.3 | "What is it?" |
| `META_REASONING` | "how to think about", "reasoning about reasoning" | 0.7 | "How should I think about thinking?" |

### Complexity Score Aggregation

```
base = lexical * 0.20 + structural * 0.25 + semantic * 0.55
boost = min(0.20, signal_count * 0.08)
overall = min(1.0, base + boost)
```

Multiple signals compound: a query with 3 signals gets a +0.24 boost on top of the weighted base.

### Depth Thresholds

| Overall Complexity | Recommended Depth | LLM Calls |
|-------------------|-------------------|-----------|
| 0.00 - 0.24 | SHALLOW | 1 |
| 0.25 - 0.44 | MODERATE | 2 |
| 0.45 - 0.64 | DEEP | 3 |
| 0.65 - 1.00 | RECURSIVE | 4 |

### Signal-Based Overrides

Two signal combinations override threshold-based depth:
- `META_REASONING` detected → always RECURSIVE
- `CAUSAL_REASONING` + `ABSTRACT_CONCEPT` → at least DEEP

### Example Classifications

| Query | Signals | Score | Depth |
|-------|---------|-------|-------|
| "Hello" | (none) | 0.05 | SHALLOW |
| "What is Python?" | (none) | 0.12 | SHALLOW |
| "Why does X cause Y?" | causal | 0.35 | MODERATE |
| "Compare A vs B and explain the implications" | comparison, causal, multi_part | 0.72 | RECURSIVE |
| "How to think about reasoning about reasoning?" | meta_reasoning | 0.55 | RECURSIVE (override) |

---

## 5. Component 2: AdaptivePromptEngine

### Purpose

Builds multi-step prompt chains for each depth level. Each step's prompt is constructed dynamically from the previous step's output.

### Prompt Templates

**DECOMPOSE** (used at MODERATE, DEEP, RECURSIVE):
```
Break this query into ordered sub-problems.
For each: what it asks, what reasoning is needed,
how it connects to other sub-problems.
```

**ANALYZE** (used at DEEP, RECURSIVE):
```
Given the decomposition, provide thorough analysis of each sub-problem.
Detailed reasoning steps, key principles, edge cases, confidence level.
```

**CRITIQUE** (used at RECURSIVE only):
```
Review the analysis for gaps, errors, missed perspectives.
Logical gaps? Alternative views? Edge cases? Sound reasoning chain?
```

**SYNTHESIZE** (used at all depths):
```
Combine all reasoning into a clear, coherent, actionable response.
Directly answers query, integrates all stages, accessible to user.
```

**DIRECT** (used at SHALLOW only):
```
Answer the query directly and concisely.
```

### Chain Construction by Depth

```
SHALLOW:   [DIRECT_ANSWER]                              → 1 call
MODERATE:  [DECOMPOSE] → [SYNTHESIZE]                   → 2 calls
DEEP:      [DECOMPOSE] → [ANALYZE] → [SYNTHESIZE]       → 3 calls
RECURSIVE: [DECOMPOSE] → [ANALYZE] → [CRITIQUE] → [SYNTHESIZE] → 4 calls
```

### Dynamic Prompt Building

Steps after DECOMPOSE don't have pre-built prompts. They are constructed at runtime:

```
Step 1 (DECOMPOSE):  prompt = pre-built from query + context
Step 2 (ANALYZE):    prompt = built using Step 1's response
Step 3 (CRITIQUE):   prompt = built using Step 2's response
Step 4 (SYNTHESIZE): prompt = built using ALL previous responses
```

This means the SYNTHESIZE prompt at RECURSIVE depth contains the full reasoning chain from DECOMPOSE + ANALYZE + CRITIQUE, giving the LLM maximum context for the final answer.

---

## 6. Component 3: AutoReasoningPipeline

### Purpose

Orchestrates the full pipeline: detection → chain building → execution → result construction. Implements progressive disclosure via `deepen()`.

### Pipeline Flow

```python
# 1. Detect complexity (always runs)
complexity = detector.analyze(query)

# 2. Determine depth
if auto_escalate:
    depth = complexity.recommended_depth
else:
    depth = SHALLOW  # progressive disclosure default

# 3. Build chain
chain = engine.build_chain(query, depth, context)

# 4. Execute chain step by step
for step in chain:
    step.prompt = engine.build_step_prompt(query, step, completed_steps)
    step.response = llm.call(step.prompt)
    step.quality_score = evaluate(step.response)

# 5. Return result with progressive disclosure metadata
return AdaptivePromptResult(
    final_response = last_step.response,
    depth_used = depth,
    depth_available = complexity.recommended_depth,
    can_deepen = (depth < depth_available),
    depth_hint = "Deeper reasoning available: MODERATE..."
)
```

### The `deepen()` Method

```python
def deepen(result):
    """Go exactly one level deeper."""
    if not result.can_deepen:
        return result  # Already at max

    next_depth = result.depth_used + 1
    return self.run(
        result._query,      # Same query
        result._context,     # Same context
        forced_depth=next_depth
    )
```

Key properties:
- Incremental: SHALLOW → MODERATE → DEEP → RECURSIVE
- Preserves original query and context
- Returns same result object if already at max depth (no wasted calls)
- Each deepen() is a full re-run at the new depth (not appending to previous)

---

## 7. Reasoning Depth Levels

### SHALLOW (1 LLM call)

```
    QUERY → DIRECT_ANSWER → OUTPUT
```

**What it does**: Single LLM call with a concise prompt. No decomposition, no analysis.

**When to use**: Simple factual questions, greetings, straightforward requests.

**Example**:
- Input: "Is stock market going up today?"
- Output: "Markets are mixed. Check live financial data for real-time direction."

### MODERATE (2 LLM calls)

```
    QUERY → DECOMPOSE → SYNTHESIZE → OUTPUT
```

**What it does**: Breaks the problem into sub-parts, then synthesizes an answer that addresses each part.

**When to use**: Questions with 2-3 related aspects, simple "why" questions, basic comparisons.

**Example**:
- Input: "Why has the stock market been volatile?"
- Step 1 (DECOMPOSE): "Sub-problems: 1) Which market? 2) What macro drivers? 3) What timeframe?"
- Step 2 (SYNTHESIZE): "Volatility stems from Fed rate uncertainty. Check S&P futures and VIX for signals."

### DEEP (3 LLM calls)

```
    QUERY → DECOMPOSE → ANALYZE → SYNTHESIZE → OUTPUT
```

**What it does**: Decomposes, then does deep analysis of each sub-problem with reasoning steps and evidence, then synthesizes.

**When to use**: Multi-faceted questions requiring expertise, causal analysis, quantitative reasoning.

**Example**:
- Input: "How does Fed policy affect tech vs energy sectors?"
- Step 1 (DECOMPOSE): Identifies rate sensitivity, sector rotation, historical patterns, prediction limits.
- Step 2 (ANALYZE): "Tech: -2.3% per 25bp hike. Energy: +1.8% on inflation expectations. VIX correlation: 0.6."
- Step 3 (SYNTHESIZE): Comprehensive framework with quantitative evidence and actionable indicators.

### RECURSIVE (4 LLM calls)

```
    QUERY → DECOMPOSE → ANALYZE → CRITIQUE → SYNTHESIZE → OUTPUT
```

**What it does**: Full chain with self-critique. The CRITIQUE step catches gaps, biased assumptions, and missing perspectives before final synthesis.

**When to use**: Questions requiring epistemic humility, meta-reasoning, complex tradeoffs, high-stakes analysis.

**Example**:
- Input: "Compare philosophical implications of quantum entanglement with consciousness theories"
- Step 1 (DECOMPOSE): 4 sub-problems identified
- Step 2 (ANALYZE): Deep analysis with cross-domain connections
- Step 3 (CRITIQUE): "Gap: assumed US-centric physics tradition. Missing: Eastern philosophical parallels. Strength: measurement problem analysis is sound."
- Step 4 (SYNTHESIZE): Final answer incorporating critique's corrections and honest uncertainty bounds.

---

## 8. Progressive Disclosure Model

### The Problem It Solves

```
WITHOUT progressive disclosure:
    User: "Is stock market going up?"
    System: [4 paragraphs of decomposition]
            [3 paragraphs of analysis]
            [2 paragraphs of critique]
            [3 paragraphs of synthesis]
    User: "I just wanted a yes or no..."
```

### How It Works

```
WITH progressive disclosure:
    User: "Is stock market going up?"
    System: "Markets are mixed today. Check live data."
            [Hint: deeper reasoning available]

    User: (satisfied, moves on)
    --- OR ---
    User: "Tell me more" → calls deepen()

    System: "Sub-problems: which index, what drivers, what timeframe.
            Synthesis: Check S&P futures and VIX for direction."
            [Hint: even deeper available]

    User: (satisfied, or deepens again)
```

### Result Object Fields

| Field | Type | Purpose |
|-------|------|---------|
| `final_response` | str | The answer at current depth |
| `depth_used` | ReasoningDepth | What depth was actually executed |
| `depth_available` | ReasoningDepth | What depth the system CAN go to |
| `can_deepen` | bool | Whether `deepen()` would produce more |
| `depth_hint` | str | Human-readable hint: "Deeper available: MODERATE (causal_reasoning). Call deepen()." |
| `reasoning_chain` | List[ReasoningStep] | Full trace of all steps executed |
| `complexity_analysis` | ComplexityAnalysis | What signals were detected and scores |
| `was_auto_escalated` | bool | Whether system auto-escalated (only when `auto_escalate=True`) |

### Modes of Operation

| Mode | `auto_escalate` | Behavior |
|------|-----------------|----------|
| **Progressive** (default) | `False` | Always starts SHALLOW. User calls `deepen()`. |
| **Auto-escalate** | `True` | Automatically goes to detected depth. Push model. |
| **Always-deep** | N/A (`min_depth=DEEP`) | Skips SHALLOW entirely. Always at least 3 calls. |
| **Conservative** | `True` (high thresholds) | Only auto-escalates for very complex queries. |

---

## 9. Reasoning Workflow Catalog

Seven distinct reasoning patterns, each suited to different problem types. All implement the same `ReasoningWorkflow` interface and return the same `WorkflowResult` structure.

### 9.1 LinearChain

```
    DECOMPOSE → ANALYZE → CRITIQUE → SYNTHESIZE
```

**What it does**: Sequential pipeline where each step feeds into the next. Step 2 sees Step 1's output. Step 3 sees Step 2's output. Step 4 sees everything.

**Internal flow**:
1. DECOMPOSE: Break query into ordered sub-problems
2. ANALYZE: Deep analysis using decomposition as input
3. CRITIQUE: Self-critique using analysis as input
4. SYNTHESIZE: Final answer using analysis + critique

**Strengths**:
- Deterministic and easy to trace
- Each step has a clear, single purpose
- Natural fit for problems with inherent logical sequence

**Weaknesses**:
- One bad decomposition poisons all downstream steps
- Linear cost: always 4 LLM calls
- Doesn't explore alternative framings of the problem
- Self-critique has correlated blind spots (same model critiques itself)

**Best for**: Problems with clear causal structure, temporal sequences, or domain-specific analysis where the right framing is obvious.

**LLM calls**: 4 (fixed)

---

### 9.2 TreeOfThought

```
            QUERY
         /    |    \
     Path1  Path2  Path3     ← N different decompositions
       |      |      |
     Score  Score  Score     ← LLM evaluates each
        \     |
        Best path
           |
       SYNTHESIZE
```

**What it does**: Instead of committing to one decomposition, generates N different approaches to the problem, scores them, then deep-dives on the best one.

**Internal flow**:
1. BRANCH_1, BRANCH_2, BRANCH_3: Generate 3 distinct decompositions, each taking a different angle
2. SCORE_BRANCHES: LLM evaluates all branches for relevance, completeness, insight quality
3. SYNTHESIZE_BEST: Deep synthesis using only the winning branch

**Strengths**:
- Finds the right framing for ambiguous problems
- Avoids "locked in" to a bad decomposition
- Self-selecting: the scoring step acts as quality control

**Weaknesses**:
- More expensive: N + 1 + 1 = 5 LLM calls for 3 branches
- Wasted computation on discarded branches
- Scoring step may not reliably identify the best path
- Still relies on single model's judgment for scoring

**Best for**: Ambiguous questions where multiple valid interpretations exist, abstract concepts that can be approached from different philosophical angles.

**LLM calls**: N + 2 (default N=3, so 5 calls)

---

### 9.3 IterativeRefinement

```
    GENERATE initial draft
        ↓
    CRITIC evaluates → score + feedback
        ↓
    score >= threshold? → OUTPUT
    score < threshold?  → REVISE
        ↓
    CRITIC evaluates again
        ↓
    (repeat until threshold met or max_revisions reached)
```

**What it does**: Generates a draft, evaluates it, and iteratively improves it based on specific feedback. Closest to how humans actually write and think.

**Internal flow**:
1. GENERATE_v1: Initial draft response
2. CRITIC_v1: Evaluate with score (N/10) + specific improvement suggestions
3. REVISE_v2: Incorporate critic feedback into improved version
4. CRITIC_v2: Re-evaluate revised version
5. (repeat or stop)

**Strengths**:
- Converges toward quality through targeted iteration
- Each revision addresses specific weaknesses (not random changes)
- Natural stopping condition (quality threshold)
- Variable cost: may stop after 2 calls if first draft is good

**Weaknesses**:
- Variable and unpredictable cost (2 to 2*N+1 calls)
- May loop without meaningful improvement (diminishing returns)
- Critic quality bounds overall quality (bad critic = bad revisions)
- Can't improve beyond the model's capabilities through iteration alone

**Best for**: Creative tasks (writing, design proposals), code generation, any task where quality is on a spectrum and incremental improvement is possible.

**LLM calls**: 2 to 2*max_revisions + 1 (variable)

---

### 9.4 Debate (Adversarial)

```
    ADVOCATE_A (argues FOR position)
    ADVOCATE_B (argues AGAINST position)
        ↓
    REBUTTAL_A (responds to B's points)
        ↓
    JUDGE (synthesizes, weighs evidence, decides)
```

**What it does**: Simulates a structured debate between two opposing positions. A judge synthesizes the strongest arguments from both sides.

**Internal flow**:
1. ADVOCATE_A: Argues strongly for one position with evidence
2. ADVOCATE_B: Argues for the opposing position, challenging A's assumptions
3. REBUTTAL_A: Advocate A responds to B's strongest points
4. JUDGE: Impartial synthesis weighing both sides' evidence

**Strengths**:
- Surfaces hidden assumptions that self-critique misses
- Forces examination of genuine tradeoffs
- Breaks correlated blind spots (opposing positions probe different weaknesses)
- Natural fit for decisions with real stakes

**Weaknesses**:
- Debate framing doesn't fit all question types (e.g., "What is X?" has no opposing position)
- Judge may be biased toward more eloquent advocate
- 4 LLM calls even for simple tradeoffs
- Both advocates come from the same model (truly independent perspectives are impossible)

**Best for**: Conditional logic ("if X, what happens?"), policy decisions, tradeoff analysis, any question with legitimate opposing viewpoints.

**LLM calls**: 4 (fixed)

---

### 9.5 MapReduce

```
    DECOMPOSE into N sub-problems
        ↓
    SOLVE_1  SOLVE_2  SOLVE_3   (each solved independently)
        \       |       /
          REDUCE (merge)
```

**What it does**: Breaks the problem into independent sub-problems, solves each with its own focused LLM call, then merges all solutions into a coherent answer.

**Internal flow**:
1. DECOMPOSE: Identify N independent sub-problems (numbered)
2. SOLVE_1 through SOLVE_N: Each sub-problem gets its own focused prompt with full context
3. REDUCE: Merge all solutions into a single coherent response

**Strengths**:
- Each sub-problem gets undivided attention (not competing for tokens)
- No cross-contamination between sub-problem solutions
- Natural fit for comparison queries (evaluate each option independently)
- Decomposition quality is auditable (you can see if the split was good)

**Weaknesses**:
- Assumes sub-problems are truly independent (may not hold for interdependent aspects)
- Decomposition quality is critical: bad split = bad everything
- More calls: 1 + N + 1 (3 sub-problems = 5 calls)
- REDUCE step may struggle to reconcile conflicting sub-solutions

**Best for**: Comparison requests ("compare A vs B vs C"), multi-part questions with independent sub-questions, evaluation tasks.

**LLM calls**: N + 2 (variable, depends on sub-problem count)

---

### 9.6 SocraticProgressive

```
    SHALLOW answer to full query
        ↓
    IDENTIFY which aspect has most depth potential
        ↓
    FOCUSED DEEP DIVE on just that aspect
        ↓
    SYNTHESIZE shallow + deep into final
```

**What it does**: Answers broadly first, then identifies the SINGLE aspect that would benefit most from deeper analysis, and deep-dives on only that. Avoids information overload by being selective.

**Internal flow**:
1. SHALLOW_ANSWER: Quick, concise answer to the full query
2. IDENTIFY_DEPTH: Analyze which aspect needs depth + formulate clarifying question
3. FOCUSED_DEEP_DIVE: Thorough analysis of only the identified aspect
4. SYNTHESIZE: Combine broad shallow answer with focused deep dive

**Strengths**:
- Maximum relevance: goes deep on what matters most
- Avoids information overload: selective depth, not uniform depth
- Surfaces which aspect actually needs attention (diagnostic value)
- Most aligned with progressive disclosure philosophy

**Weaknesses**:
- May miss important aspects the system doesn't identify as deepest
- In auto mode, self-answers the clarifying question (loses the interactive benefit)
- Still 4 LLM calls even though only one aspect goes deep
- Aspect identification may be wrong

**Best for**: General use when user intent is unclear, questions where one aspect is clearly more complex than others, educational contexts.

**LLM calls**: 4 (fixed)

---

### 9.7 Metacognitive

```
    QUERY → COMPLEXITY DETECTOR → WORKFLOW SELECTOR
                                    /    |     \
                              Linear  ToT  Debate  MapReduce...
                                    \    |     /
                                    RESULT
```

**What it does**: Reasons about which workflow to use, then delegates to it. The "master" workflow that picks the right tool for the job.

**Internal flow**:
1. Run ComplexityDetector to identify signals
2. Apply signal → workflow priority mapping
3. Delegate execution to selected workflow
4. Tag result with metacognitive metadata (which workflow was chosen and why)

**Strengths**:
- Right tool for the right problem
- Avoids forcing one pattern onto all problem types
- Self-documenting: explains why it chose the workflow it chose
- Extensible: new workflows can be registered

**Weaknesses**:
- Selection may be wrong (wrong signal detection → wrong workflow)
- Adds overhead of detection step
- Relies on signal detection accuracy
- Avoids META_REASONING signal to prevent infinite recursion (delegates to LinearChain instead)

**Best for**: Default when problem type is unknown, or as the entry point for a system that handles diverse query types.

**LLM calls**: Variable (depends on selected workflow)

---

## 10. Workflow Selection: Signal-to-Workflow Mapping

The WorkflowSelector maps detected ComplexitySignals to the optimal workflow using a priority-ordered ruleset. First matching rule wins.

### Priority-Ordered Mapping

| Priority | Signal | Selected Workflow | Rationale |
|----------|--------|-------------------|-----------|
| 1 | `CONDITIONAL_LOGIC` | Debate | Argue for/against each branch |
| 2 | `COMPARISON_REQUEST` | MapReduce | Evaluate each option independently |
| 3 | `MULTI_PART_QUESTION` | MapReduce | Solve independent parts separately |
| 4 | `AMBIGUITY_DETECTED` | TreeOfThought | Explore multiple framings |
| 5 | `ABSTRACT_CONCEPT` | TreeOfThought | Multiple conceptual lenses |
| 6 | `CREATIVE_SYNTHESIS` | IterativeRefinement | Draft → revise → refine |
| 7 | `CAUSAL_REASONING` | LinearChain | Cause → effect → implication chain |
| 8 | `TEMPORAL_REASONING` | LinearChain | Sequence → analyze → synthesize |
| 9 | `META_REASONING` | LinearChain | Avoids infinite recursion |
| 10 | `DOMAIN_EXPERTISE` | LinearChain | Structured expert analysis |
| (default) | (no signals) | LinearChain | Safe fallback |

### Why Priority Order Matters

A query like "If we assume infinite resources, compare capitalism vs socialism" triggers both `CONDITIONAL_LOGIC` and `COMPARISON_REQUEST`. The priority order ensures `CONDITIONAL_LOGIC` wins (Debate), because the conditional framing is more structurally important than the comparison aspect.

---

## 11. Workflow Comparison Matrix

| Property | Linear | ToT | Iterative | Debate | MapReduce | Socratic | Meta |
|----------|--------|-----|-----------|--------|-----------|----------|------|
| **LLM Calls** | 4 | N+2 | 2 to 2N+1 | 4 | N+2 | 4 | varies |
| **Cost Predictability** | Fixed | Fixed | Variable | Fixed | Semi-fixed | Fixed | Variable |
| **Explores Alternatives** | No | Yes | No | Yes | No | No | Yes |
| **Self-Corrects** | Via critique | Via scoring | Via revision | Via rebuttal | No | No | No |
| **Handles Ambiguity** | Poorly | Well | Poorly | Moderately | Poorly | Well | Well |
| **Handles Tradeoffs** | Moderately | Moderately | Poorly | Well | Moderately | Poorly | Well |
| **Risk of Bad Start** | High (one path) | Low (N paths) | Medium (can revise) | Low (two sides) | High (one decomp) | Medium | Medium |
| **Information Overload Risk** | High | Medium | Low | Medium | Medium | Low | Varies |

---

## 12. When To Use Which Workflow

### Decision Tree

```
Is the question about tradeoffs or "should we do X?"
    YES → Debate

Is it comparing multiple distinct options?
    YES → MapReduce

Is the question ambiguous or abstract with no clear framing?
    YES → TreeOfThought

Is it a creative task (write, design, build)?
    YES → IterativeRefinement

Does it have clear causal structure (why X → Y → Z)?
    YES → LinearChain

Is user intent unclear?
    YES → SocraticProgressive

Don't know?
    → Metacognitive (let the system decide)
```

### Real-World Examples

| User Query | Best Workflow | Why |
|-----------|---------------|-----|
| "Why does inflation cause interest rates to rise?" | LinearChain | Clear causal chain |
| "Compare React vs Vue vs Angular" | MapReduce | Independent evaluation of each |
| "If AI achieves consciousness, should it have rights?" | Debate | Genuine opposing positions |
| "What is the meaning of life?" | TreeOfThought | Multiple valid framings |
| "Write a proposal for a new product" | IterativeRefinement | Creative, quality-convergent |
| "Tell me about quantum computing" | SocraticProgressive | Broad topic, needs focus |
| (mixed/unclear) | Metacognitive | Let system classify |

---

## 13. Invariants

### Adaptive Prompts Invariants

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| INV-AP-1 | Never downgrade below `min_depth` | `depth = max(min_depth, depth)` in pipeline |
| INV-AP-2 | Depth metadata always exposed | `depth_available`, `can_deepen`, `depth_hint` always populated |
| INV-AP-3 | Reasoning chain deterministic for same input + state | No randomness in detection or chain building |
| INV-AP-4 | User can always access full reasoning trace | `get_reasoning_trace()` on every result |
| INV-AP-5 | Default mode never auto-escalates | `auto_escalate=False` default |

### Reasoning Workflow Invariants

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| INV-WF-1 | Every workflow produces a `WorkflowResult` with full trace | Abstract base class requires `execute()` → `WorkflowResult` |
| INV-WF-2 | No workflow exceeds `max_llm_calls` budget | `_call_llm()` helper checks budget before every call |
| INV-WF-3 | `WorkflowSelector` mapping is deterministic | Priority-ordered signal matching, no randomness |
| INV-WF-4 | All workflows start at SHALLOW in progressive mode | Pipeline enforces SHALLOW default, workflow runs at requested depth |

---

## 14. Integration Points

### With Existing Agentic Framework

| Component | Integration |
|-----------|-------------|
| `ReflectiveGenerator` | IterativeRefinement uses same generate → critic → revise pattern |
| `ConfidenceGate` | Quality scores from workflows feed into confidence signals |
| `AdaptivePolicyEngine` | Session trajectory can adjust workflow selection over time |
| `CoherenceEngine` | Coherence metrics can trigger workflow switches mid-conversation |
| `SafetyContract` | All workflow outputs pass through safety gating before action execution |

### With Phase-Quad

| Component | Integration |
|-----------|-------------|
| `ReflectivePhaseQuad` | Quality history tracking mirrors workflow quality scoring |
| `HPQuadBlock` | Multi-level processing maps to multi-depth reasoning |
| `Phase Governance (P01-P55)` | Workflow selection respects phase authority hierarchy |

---

## 15. Configuration Reference

### ComplexityDetector

```python
ComplexityDetector(
    shallow_threshold=0.25,     # Below → SHALLOW
    moderate_threshold=0.45,    # Below → MODERATE
    deep_threshold=0.65,        # Below → DEEP, above → RECURSIVE
    complexity_boost_per_signal=0.08,  # Boost per detected signal
)
```

### AutoReasoningPipeline

```python
AutoReasoningPipeline(
    llm_client=llm,                       # Required: any LLM with .call()
    complexity_detector=None,             # Auto-created with defaults
    prompt_engine=None,                   # Auto-created with defaults
    min_depth=ReasoningDepth.SHALLOW,     # Floor
    max_depth=ReasoningDepth.RECURSIVE,   # Ceiling
    auto_escalate=False,                  # Progressive disclosure default
    quality_evaluator=None,               # Optional: fn(query, response) → float
)
```

### Workflow Configurations

```python
TreeOfThoughtWorkflow(num_branches=3)           # How many branches to explore
IterativeRefinementWorkflow(max_revisions=3, quality_threshold=0.8)
MapReduceWorkflow(max_sub_problems=4)           # Max independent sub-problems
```

### Factory Functions

| Factory | Mode | Behavior |
|---------|------|----------|
| `create_progressive_pipeline(llm)` | Progressive (RECOMMENDED) | Starts SHALLOW, user pulls deeper |
| `create_adaptive_pipeline(llm)` | Progressive (default) | Same as progressive, more configurable |
| `create_always_deep_pipeline(llm)` | Always Deep | Skips SHALLOW, minimum DEEP |
| `create_conservative_pipeline(llm)` | Conservative Auto | Auto-escalates but only for clearly complex queries |

---

## 16. Test Coverage

### Adaptive Prompts Tests (72 tests)

| Test Class | Count | What It Tests |
|-----------|-------|---------------|
| TestComplexityDetector | 17 | All 10 signal types, scoring bounds, thresholds, empty input |
| TestAdaptivePromptEngine | 10 | Chain building at each depth, dynamic prompt construction, context flow |
| TestAutoReasoningPipeline | 14 | Pipeline execution, forced depth, min/max enforcement, quality evaluator |
| TestFactoryFunctions | 4 | All factory function configurations |
| TestEnums | 4 | Enum ordering, values |
| TestDataClasses | 4 | Serialization, truncation, reasoning trace formatting |
| TestIntegration | 5 | Full recursive chain, context flow, invariant enforcement |
| TestProgressiveDisclosure | 14 | deepen(), depth hints, progressive flow, auto-escalate compatibility |

### Reasoning Workflows Tests (103 tests)

| Test Class | Count | What It Tests |
|-----------|-------|---------------|
| TestDataClasses | 4 | WorkflowStep/Result serialization |
| TestLinearChainWorkflow | 6 | 4-step execution, step names, context, budget respect |
| TestTreeOfThoughtWorkflow | 6 | Branch generation, scoring, synthesis, custom branch count |
| TestIterativeRefinementWorkflow | 6 | Generation, critic, max revisions, early stop, score extraction |
| TestDebateWorkflow | 6 | Two advocates, rebuttal, judge, role metadata |
| TestMapReduceWorkflow | 7 | Decompose, solve, reduce, sub-problem parsing, max respect |
| TestSocraticProgressiveWorkflow | 5 | Shallow answer, depth identification, deep dive, synthesis |
| TestMetacognitiveWorkflow | 8 | Delegation to correct workflow per signal, complexity analysis |
| TestWorkflowSelector | 5 | Default mapping, priority ordering, custom mapping, no-signal default |
| TestWorkflowRegistry | 5 | Registration, lookup, listing, custom workflow |
| TestFactoryFunctions | 3 | Factory function configurations |
| TestInvariants | 42 | Cross-workflow: result type, budget, steps, duration, serialization, trace (7 tests x 6 workflows) |

**Total: 175 tests passing.**
