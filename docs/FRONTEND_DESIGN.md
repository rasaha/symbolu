# Symbol-U Frontend Design Document

## Version 0.1 (Preliminary) | December 2025

---

## Table of Contents

1. [Overview](#1-overview)
2. [Core Views](#2-core-views)
3. [Component Architecture](#3-component-architecture)
4. [Backend Integration](#4-backend-integration)
5. [Data Flow](#5-data-flow)
6. [UI Components](#6-ui-components)
7. [Analytics Dashboard](#7-analytics-dashboard)
8. [Tech Stack Recommendations](#8-tech-stack-recommendations)

---

## 1. Overview

### 1.1 Design Goals

- **Conversational Interface**: Primary chat-based interaction
- **Layered Transparency**: Progressive disclosure of pipeline insights
- **Real-time Feedback**: Live coherence and persona indicators
- **Analytics Integration**: Dashboard for session analysis

### 1.2 User Personas

| Persona | Primary Use | Key Features |
|---------|-------------|--------------|
| End User | Chat interaction | Simple chat, badges, hints |
| Power User | Deep analysis | Layer views, coherence metrics |
| Admin | System monitoring | Dashboard, what-if simulations |
| Developer | Debugging | Full unified output, phase inspection |

### 1.3 View Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                      SYMBOL-U APP                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │    CHAT     │  │  INSIGHTS   │  │  DASHBOARD  │          │
│  │    VIEW     │  │    VIEW     │  │    VIEW     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│         │               │                │                   │
│         ▼               ▼                ▼                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              SHARED COMPONENTS                       │    │
│  │  • Message Bubble    • Coherence Indicator          │    │
│  │  • Badge Display     • Layer Panel                  │    │
│  │  • Hint Cards        • Timeline Chart               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Views

### 2.1 Chat View (Primary)

The main conversational interface.

```
┌─────────────────────────────────────────────────────────────┐
│  SYMBOL-U                              [Settings] [Dashboard]│
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   MESSAGES AREA                      │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐   │    │
│  │  │ USER                                          │   │    │
│  │  │ What is the meaning of consciousness?         │   │    │
│  │  └──────────────────────────────────────────────┘   │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐   │    │
│  │  │ SYMBOL-U                    [coherent] [deep] │   │    │
│  │  │                                               │   │    │
│  │  │ Consciousness is the subjective experience   │   │    │
│  │  │ of awareness and perception...               │   │    │
│  │  │                                               │   │    │
│  │  │ ┌─────────────────────────────────────────┐  │   │    │
│  │  │ │ 💡 Consider exploring: self-awareness   │  │   │    │
│  │  │ └─────────────────────────────────────────┘  │   │    │
│  │  │                                               │   │    │
│  │  │ [Symbolic] [Practical] [Mirror] [Details ▼]  │   │    │
│  │  └──────────────────────────────────────────────┘   │    │
│  │                                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ [Domain: philosophy ▼]  [Mode: domain_relative ▼]   │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │ Type your message...                        [Send]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ SESSION: stable | COHERENCE: 0.85 | TURNS: 5        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Chat View Elements

| Element | Backend Source | Update Trigger |
|---------|----------------|----------------|
| Message text | `response.text` | On response |
| Badges | `response.badges[]` | On response |
| Hints | `response.hints[]` | On response |
| Layer tabs | `response.layers.*` | On expand |
| Domain selector | User input | On change |
| Mode selector | `/preferences/user` | On change |
| Session status | `response.session_policy` | On response |
| Coherence score | `response.coherence.stability` | On response |

### 2.2 Insights View

Detailed breakdown of the current response.

```
┌─────────────────────────────────────────────────────────────┐
│  INSIGHTS                                      [← Back]     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ SYMBOLIC LAYER                                       │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │ Fusion Score: 0.82                                   │    │
│  │ Selected Source: reasoning_model                     │    │
│  │ Reasoning: High O5_COGNITION activation detected...   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ PRACTICAL LAYER                                      │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │ Confidence: 0.78                                     │    │
│  │ Relevance: 0.85                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ ENTROPY METRICS                                      │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │                                                      │    │
│  │  H_D ████████░░ 0.42    H_G ███████░░░ 0.38         │    │
│  │  H_K █████████░ 0.45    Norm ████████░░ 0.42        │    │
│  │                                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 10D ONTOLOGICAL PROFILE                              │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │                                                      │    │
│  │  O5_COGNITION    ████████████░░ 0.62                 │    │
│  │  O4_STRUCTURE     ████░░░░░░░░░░ 0.21                 │    │
│  │  O3_EXECUTION      ███░░░░░░░░░░░ 0.15                 │    │
│  │  O8_OBSERVING   █████████░░░░░ 0.45                 │    │
│  │  O10_UNIFYING    ██████░░░░░░░░ 0.32                 │    │
│  │                                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Dashboard View

Session analytics and monitoring.

```
┌─────────────────────────────────────────────────────────────┐
│  DASHBOARD                          [Session: abc123 ▼]     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │ COHERENCE TREND      │  │ PERSONA DRIFT        │        │
│  │    ___/\___/──       │  │      /\              │        │
│  │   /         \        │  │   __/  \___          │        │
│  │  /                   │  │  /                   │        │
│  │ Avg: 0.82            │  │ Avg: 0.12            │        │
│  └──────────────────────┘  └──────────────────────┘        │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │ ENTROPY OVER TIME    │  │ RISK BANDS           │        │
│  │  ───────────         │  │ ┌─────────────────┐  │        │
│  │       ────           │  │ │ Stability: LOW  │  │        │
│  │          ───         │  │ │ Drift: MEDIUM   │  │        │
│  │ H_norm: 0.41         │  │ │ Semantic: LOW   │  │        │
│  └──────────────────────┘  └─┴─────────────────┴──┘        │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ SESSION TIMELINE                                     │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │ Turn 1  ●────●  Turn 2  ●────●  Turn 3  ●────●      │    │
│  │ [phil]       [phil]          [ethics]               │    │
│  │ coh:0.8      coh:0.85        coh:0.79               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ WHAT-IF SIMULATION                                   │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │ Preset: [safety_first ▼]    [Run Simulation]        │    │
│  │                                                      │    │
│  │ Original Entropy: 0.42  →  Simulated: 0.36          │    │
│  │ Dominant: O5_COGNITION   →  O8_OBSERVING             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Component Architecture

### 3.1 Component Tree

```
App
├── Header
│   ├── Logo
│   ├── NavigationTabs
│   └── SettingsButton
│
├── ChatView
│   ├── MessageList
│   │   ├── UserMessage
│   │   └── AssistantMessage
│   │       ├── BadgeDisplay
│   │       ├── HintCard
│   │       └── LayerTabs
│   │           ├── SymbolicPanel
│   │           ├── PracticalPanel
│   │           └── MirrorPanel
│   ├── InputArea
│   │   ├── DomainSelector
│   │   ├── ModeSelector
│   │   └── MessageInput
│   └── SessionStatusBar
│       ├── CoherenceIndicator
│       └── TurnCounter
│
├── InsightsView
│   ├── SymbolicLayerCard
│   ├── PracticalLayerCard
│   ├── EntropyMetrics
│   └── OntologicalProfile
│
├── DashboardView
│   ├── CoherenceTrendChart
│   ├── PersonaDriftChart
│   ├── EntropyTimelineChart
│   ├── RiskBandsPanel
│   ├── SessionTimeline
│   └── WhatIfSimulator
│
└── SettingsModal
    ├── UserPreferences
    ├── InsightModeSelector
    └── DomainDefaults
```

### 3.2 Core Components

#### MessageBubble

```typescript
interface MessageBubbleProps {
  role: 'user' | 'assistant';
  text: string;
  badges?: string[];
  hints?: string[];
  layers?: {
    symbolic: LayerData;
    practical: LayerData;
    mirror: LayerData;
  };
  coherence?: number;
  timestamp: Date;
}
```

#### CoherenceIndicator

```typescript
interface CoherenceIndicatorProps {
  value: number;           // 0.0 - 1.0
  trend: 'up' | 'down' | 'stable';
  sessionStable: boolean;
}

// Visual states
// value >= 0.7  → Green (stable)
// value 0.4-0.7 → Yellow (moderate)
// value < 0.4   → Red (unstable)
```

#### BadgeDisplay

```typescript
interface BadgeProps {
  badges: string[];
}

// Badge types from backend:
// "coherent" → Green check
// "grounded" → Blue anchor
// "reflective" → Purple thought
// "deep" → Indigo layers
// "practical" → Orange tool
```

#### OntologicalRadar

```typescript
interface OntologicalRadarProps {
  dimensions: {
    O5_COGNITION: number;
    O4_STRUCTURE: number;
    O3_EXECUTION: number;
    O4_TAGGING: number;
    O6_AGENCY: number;
    O7_REASONING: number;
    O8_PURPOSE: number;
    O9_WITNESSES: number;
    O10_UNIFYING: number;
    O12_ABSOLVING: number;
  };
}

// Renders as radar/spider chart
```

---

## 4. Backend Integration

### 4.1 API Client

```typescript
// api/client.ts

const API_BASE = process.env.SYMBOLU_API_URL || 'http://localhost:8000';

interface AnalyzeRequest {
  text: string;
  domain: string;
  user_id?: string;
  org_id?: string;
  metadata?: Record<string, any>;
}

interface DILchatResponse {
  text: string;
  badges: string[];
  hints: string[];
  coherence: { stability: number; drift: number };
  domain: string;
  layers: {
    symbolic: string | null;
    practical: string | null;
    mirror: string | null;
  };
  session_policy: {
    session_is_stable: boolean;
    session_is_fragmented: boolean;
    session_needs_grounding: boolean;
    session_recommended_style: string;
  };
  metadata: Record<string, any>;
}

export const api = {
  // Basic chat analysis
  async analyze(req: AnalyzeRequest): Promise<DILchatResponse> {
    const res = await fetch(`${API_BASE}/dilchat/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return res.json();
  },

  // Full unified analysis
  async analyzeUnified(req: AnalyzeRequest): Promise<UnifiedResponse> {
    const res = await fetch(`${API_BASE}/symbolu/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return res.json();
  },

  // Session management
  async startSession(domain: string): Promise<{ session_id: string }> {
    const res = await fetch(`${API_BASE}/session/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain }),
    });
    return res.json();
  },

  async analyzeInSession(sessionId: string, req: AnalyzeRequest): Promise<DILchatResponse> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return res.json();
  },

  async getSessionSummary(sessionId: string): Promise<SessionSummary> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/summary`);
    return res.json();
  },

  async getSessionDashboard(sessionId: string): Promise<DashboardData> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/dashboard`);
    return res.json();
  },

  // What-if simulations
  async resonanceWhatIf(sessionId: string, preset: string): Promise<WhatIfResult> {
    const res = await fetch(
      `${API_BASE}/sessions/${sessionId}/resonance/what_if?preset=${preset}`
    );
    return res.json();
  },

  // Preferences
  async setUserPreference(userId: string, mode: string): Promise<void> {
    await fetch(`${API_BASE}/preferences/user`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, preferred_interaction_mode: mode }),
    });
  },
};
```

### 4.2 Endpoint to View Mapping

| View/Component | Endpoint | Polling/Trigger |
|----------------|----------|-----------------|
| ChatView | `/dilchat/analyze` | On send |
| ChatView (session) | `/session/{id}/analyze` | On send |
| InsightsView | `/symbolu/analyze` | On expand |
| DashboardView | `/sessions/{id}/dashboard` | On view |
| CoherenceTrend | `/session/{id}/summary` | 5s polling |
| WhatIfSimulator | `/sessions/{id}/resonance/what_if` | On click |
| ModeSelector | `/preferences/user` | On change |
| SessionStatusBar | Response `session_policy` | On response |

---

## 5. Data Flow

### 5.1 Chat Message Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  User   │────▶│  Input  │────▶│   API   │────▶│ Backend │
│  Types  │     │  Area   │     │ Client  │     │ Server  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                                                      │
                                                      ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Message │◀────│  State  │◀────│   API   │◀────│Response │
│ Display │     │  Store  │     │ Client  │     │  JSON   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                    UI Updates                            │
│  • Add message bubble                                    │
│  • Display badges                                        │
│  • Show hints                                            │
│  • Update coherence indicator                            │
│  • Update session status                                 │
└─────────────────────────────────────────────────────────┘
```

### 5.2 State Management

```typescript
// stores/chatStore.ts

interface ChatState {
  // Session
  sessionId: string | null;
  domain: string;
  insightMode: 'recent_memory' | 'domain_relative' | 'new_possibilities';

  // Messages
  messages: Message[];

  // Session metrics
  coherence: number;
  turnCount: number;
  sessionPolicy: SessionPolicy;

  // UI state
  isLoading: boolean;
  expandedMessageId: string | null;
  showInsights: boolean;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;

  // Backend response data (assistant only)
  badges?: string[];
  hints?: string[];
  layers?: LayerData;
  coherence?: CoherenceData;
  metadata?: Record<string, any>;
}

// Actions
type ChatAction =
  | { type: 'START_SESSION'; domain: string }
  | { type: 'SEND_MESSAGE'; text: string }
  | { type: 'RECEIVE_RESPONSE'; response: DILchatResponse }
  | { type: 'SET_DOMAIN'; domain: string }
  | { type: 'SET_INSIGHT_MODE'; mode: string }
  | { type: 'TOGGLE_INSIGHTS'; messageId: string }
  | { type: 'SET_LOADING'; loading: boolean };
```

### 5.3 Response Processing

```typescript
// utils/responseProcessor.ts

function processResponse(response: DILchatResponse): ProcessedResponse {
  return {
    // Primary content
    text: response.text,

    // Visual indicators
    badges: response.badges.map(b => ({
      name: b,
      icon: getBadgeIcon(b),
      color: getBadgeColor(b),
    })),

    // Actionable hints
    hints: response.hints.map(h => ({
      text: h,
      action: getHintAction(h),
    })),

    // Coherence visualization
    coherenceLevel: categorizeCoherence(response.coherence.stability),
    coherenceColor: getCoherenceColor(response.coherence.stability),

    // Session status
    sessionStatus: {
      stable: response.session_policy.session_is_stable,
      style: response.session_policy.session_recommended_style,
      needsGrounding: response.session_policy.session_needs_grounding,
    },

    // Layer data for expansion
    layers: response.layers,
  };
}

function categorizeCoherence(value: number): 'high' | 'medium' | 'low' {
  if (value >= 0.7) return 'high';
  if (value >= 0.4) return 'medium';
  return 'low';
}
```

---

## 6. UI Components

### 6.1 Badge System

| Badge | Icon | Color | Meaning |
|-------|------|-------|---------|
| coherent | ✓ | Green | High coherence score |
| grounded | ⚓ | Blue | Well-grounded in context |
| reflective | 💭 | Purple | Deep reflection mode |
| deep | ◉ | Indigo | Multi-layer analysis |
| practical | 🔧 | Orange | Actionable response |
| caution | ⚠ | Yellow | Needs attention |

### 6.2 Hint Cards

```
┌─────────────────────────────────────────────────────────┐
│ 💡 INSIGHT                                              │
│                                                         │
│ Consider exploring: self-awareness, qualia             │
│                                                         │
│ [Explore →]                                    [Dismiss]│
└─────────────────────────────────────────────────────────┘
```

### 6.3 Layer Tabs

```
┌─────────────────────────────────────────────────────────┐
│ [Symbolic ●] [Practical] [Mirror]                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ SYMBOLIC LAYER                                          │
│ ─────────────                                           │
│ Fusion Score: 0.82                                      │
│ Source: reasoning_model                                 │
│                                                         │
│ The response was generated through high O5_COGNITION     │
│ activation, indicating deep contemplative processing.   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.4 Coherence Indicator (Compact)

```
SESSION: ● stable | COHERENCE: ████████░░ 0.85 ↑ | TURNS: 5
```

### 6.5 Ontological Profile (Radar)

```
              O5_COGNITION
                  ●
                / | \
     O10_ABS ●   |   ● O4_STRUCTURE
              \  |  /
               \ | /
    O9_UNIFY ●──●──● O3_EXECUTION
               / | \
              /  |  \
    O8_META ●   |   ● O4_TAGGING
                |
     O7_PURP ●──●── O6_AGENCY
                |
           O7_REASONING
```

---

## 7. Analytics Dashboard

### 7.1 Dashboard Components

#### Coherence Trend Chart

```typescript
interface CoherenceTrendProps {
  data: Array<{
    turn: number;
    stability: number;
    drift: number;
  }>;
  timeRange: '5m' | '30m' | '1h' | 'session';
}

// Line chart with:
// - X axis: Turn number or time
// - Y axis: 0.0 - 1.0
// - Two lines: stability (green), drift (orange)
```

#### Risk Bands Panel

```typescript
interface RiskBandsProps {
  bands: {
    stability: 'low' | 'medium' | 'high';
    drift: 'low' | 'medium' | 'high';
    semantic: 'low' | 'medium' | 'high';
    motivation: 'low' | 'medium' | 'high';
  };
}

// Visual: Colored bars or traffic lights
```

#### Session Timeline

```typescript
interface SessionTimelineProps {
  turns: Array<{
    number: number;
    domain: string;
    coherence: number;
    highlights: string[];
  }>;
}

// Horizontal timeline with:
// - Circles for each turn
// - Domain labels below
// - Coherence color coding
// - Click to expand details
```

#### What-If Simulator

```typescript
interface WhatIfSimulatorProps {
  sessionId: string;
  presets: string[];  // ['safety_first', 'insight_heavy', 'balanced', ...]
}

// UI:
// - Preset dropdown
// - "Run Simulation" button
// - Before/After comparison display
// - Entropy difference
// - Dominant metric changes
```

### 7.2 Dashboard Layout

```
┌────────────────────────────────────────────────────────────────┐
│                         HEADER                                  │
│  Session: abc123  |  Domain: philosophy  |  Turns: 12          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │   COHERENCE TREND       │  │    PERSONA DRIFT        │      │
│  │      [Line Chart]       │  │      [Line Chart]       │      │
│  │                         │  │                         │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
│                                                                 │
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │   ENTROPY METRICS       │  │    RISK BANDS           │      │
│  │      [Area Chart]       │  │    [Status Bars]        │      │
│  │                         │  │                         │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              SESSION TIMELINE                         │      │
│  │   ●────●────●────●────●────●────●────●────●────●     │      │
│  │   1    2    3    4    5    6    7    8    9    10    │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              WHAT-IF SIMULATOR                        │      │
│  │   Preset: [safety_first ▼]     [Run Simulation]      │      │
│  │                                                       │      │
│  │   ORIGINAL          →          SIMULATED             │      │
│  │   Entropy: 0.42                Entropy: 0.36         │      │
│  │   Dominant: THINKING           Dominant: OBSERVING   │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 8. Tech Stack Recommendations

### 8.1 Recommended Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Framework | React 18+ / Next.js 14 | Component model, SSR support |
| State | Zustand or Redux Toolkit | Simple state management |
| Styling | Tailwind CSS | Rapid styling, dark mode |
| Charts | Recharts or Victory | React-native charts |
| HTTP | Axios or fetch | API communication |
| Types | TypeScript | Type safety |

### 8.2 Alternative Stacks

| Stack | Best For |
|-------|----------|
| Vue 3 + Pinia | Teams familiar with Vue |
| Svelte + SvelteKit | Performance-critical apps |
| Solid.js | Fine-grained reactivity needs |

### 8.3 Folder Structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts
│   │   └── types.ts
│   ├── components/
│   │   ├── chat/
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── BadgeDisplay.tsx
│   │   │   ├── HintCard.tsx
│   │   │   └── LayerTabs.tsx
│   │   ├── indicators/
│   │   │   ├── CoherenceIndicator.tsx
│   │   │   └── SessionStatusBar.tsx
│   │   ├── dashboard/
│   │   │   ├── CoherenceTrendChart.tsx
│   │   │   ├── RiskBandsPanel.tsx
│   │   │   └── WhatIfSimulator.tsx
│   │   └── common/
│   │       ├── Header.tsx
│   │       └── Modal.tsx
│   ├── views/
│   │   ├── ChatView.tsx
│   │   ├── InsightsView.tsx
│   │   └── DashboardView.tsx
│   ├── stores/
│   │   ├── chatStore.ts
│   │   └── dashboardStore.ts
│   ├── utils/
│   │   └── responseProcessor.ts
│   └── App.tsx
├── public/
├── package.json
└── tsconfig.json
```

---

## 9. Implementation Phases

### Phase 1: Core Chat (MVP)
- [ ] Basic chat interface
- [ ] `/dilchat/analyze` integration
- [ ] Message display with text
- [ ] Domain selector

### Phase 2: Enhanced Chat
- [ ] Badge display
- [ ] Hint cards
- [ ] Coherence indicator
- [ ] Session status bar

### Phase 3: Insights Panel
- [ ] Layer tabs (Symbolic/Practical/Mirror)
- [ ] Entropy metrics display
- [ ] Ontological profile radar

### Phase 4: Session Management
- [ ] Session creation
- [ ] Multi-turn tracking
- [ ] Session summary view

### Phase 5: Analytics Dashboard
- [ ] Coherence trend chart
- [ ] Persona drift chart
- [ ] Risk bands panel
- [ ] Session timeline

### Phase 6: Advanced Features
- [ ] What-if simulator
- [ ] Preference management
- [ ] Dark mode
- [ ] Mobile responsive

---

## Next Steps

1. **Design Review**: Get feedback on wireframes
2. **Component Library**: Set up Storybook for component development
3. **API Contract**: Finalize TypeScript types from backend schema
4. **MVP Build**: Implement Phase 1 core chat
5. **Iterate**: Add features per phase roadmap

---

*Document Version: 0.1 (Preliminary)*
*Last Updated: December 2025*
*Status: Draft for Review*
