# Tier 3: Admin UX Design

## Version 1.0 | December 2025

---

## Overview

The Admin tier provides a **full analytics dashboard** with comprehensive visibility into the Symbol-U pipeline. Designed for administrators, developers, and analysts who need complete diagnostic information and simulation capabilities.

---

## 1. Design Principles

| Principle | Description |
|-----------|-------------|
| **Full Visibility** | All metrics, diagnostics, and data accessible |
| **Data-Dense Layout** | Efficient use of space for multiple panels |
| **Flexible Views** | Switch between chat, dashboard, or split view |
| **Actionable Analytics** | Charts and simulations for decision making |
| **Professional/Technical** | Orange/amber theme for admin authority |

---

## 2. Page Layout

### 2.1 View Modes

The Admin tier supports **three view modes**:

| Mode | Layout | Use Case |
|------|--------|----------|
| **Chat** | Full-width chat | Active conversation |
| **Split** | 50/50 chat + dashboard | Monitor while chatting |
| **Dashboard** | Full-width analytics | Session analysis |

### 2.2 Master Wireframe (Split View)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    HEADER                                            │
│  ┌────┐  Symbol-U                                                       [⚙ Settings]│
│  │ 🛡 │  Admin Console                                                              │
│  └────┘                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                               VIEW MODE BAR                                          │
│  [💬 Chat]  [⊞ Split View●]  [📊 Dashboard]     Session: abc12345 │ 🔄 │ ⚙        │
├─────────────────────────────────────┬───────────────────────────────────────────────┤
│                                     │                                                │
│          CHAT PANEL                 │            DASHBOARD PANEL                     │
│          (50% width)                │              (50% width)                       │
│                                     │                                                │
│  ┌───────────────────────────────┐  │  ┌───────────────────────────────────────┐   │
│  │ USER MESSAGE                  │  │  │ ANALYTICS DASHBOARD                   │   │
│  │ "Analyze this deeply"         │  │  │ 5 turns analyzed                      │   │
│  └───────────────────────────────┘  │  └───────────────────────────────────────┘   │
│                                     │                                                │
│  ┌───────────────────────────────┐  │  ┌─────────────────┐ ┌─────────────────┐     │
│  │ ASSISTANT MESSAGE             │  │  │ COHERENCE TREND │ │ RISK BANDS      │     │
│  │ with full layer tabs...       │  │  │   /\    /\      │ │ Stability: LOW  │     │
│  │                               │  │  │  /  \__/  \__   │ │ Drift: LOW      │     │
│  │ [Symbolic] [Practical] [Mirr] │  │  │ /              \ │ │ Semantic: MED   │     │
│  │ ┌─────────────────────────┐   │  │  │                 │ │ Motiv: LOW      │     │
│  │ │ Layer content...        │   │  │  └─────────────────┘ └─────────────────┘     │
│  │ └─────────────────────────┘   │  │                                                │
│  └───────────────────────────────┘  │  ┌─────────────────┐ ┌─────────────────┐     │
│                                     │  │ ENTROPY METRICS │ │ ONTOLOGICAL     │     │
│  💬 Processing pipeline...          │  │ H_D: 0.42       │ │ Dominant:       │     │
│                                     │  │ H_G: 0.38       │ │ O5_COGNITION     │     │
│                                     │  │ H_K: 0.45       │ │ ████████░░ 0.62 │     │
│                                     │  │ Norm: 0.41      │ │ ████░░░░░░ 0.45 │     │
│                                     │  └─────────────────┘ └─────────────────┘     │
│                                     │                                                │
│                                     │  ┌───────────────────────────────────────┐   │
│                                     │  │ SESSION TIMELINE                      │   │
│                                     │  │  ●───●───●───●───●                    │   │
│                                     │  │  1   2   3   4   5                    │   │
│                                     │  └───────────────────────────────────────┘   │
│                                     │                                                │
│                                     │  ┌───────────────────────────────────────┐   │
│                                     │  │ WHAT-IF SIMULATOR                     │   │
│                                     │  │ Preset: [safety_first ▼]  [▶ Run]    │   │
│                                     │  │                                       │   │
│                                     │  │ Original   →   Simulated              │   │
│                                     │  │   0.42           0.36                 │   │
│                                     │  │ THINKING       OBSERVING              │   │
│                                     │  └───────────────────────────────────────┘   │
│                                     │                                                │
│                                     │  ┌───────────────────────────────────────┐   │
│                                     │  │ DIAGNOSTIC INFO                       │   │
│                                     │  │ Engine: DEVELOPMENT │ Domain: phil    │   │
│                                     │  │ Session: abc12345   │ Stable: Yes     │   │
│                                     │  └───────────────────────────────────────┘   │
├─────────────────────────────────────┴───────────────────────────────────────────────┤
│                                   INPUT AREA                                         │
│  Domain: [Philosophy ▼]    [Enter query for analysis...]                   [➤ Send]│
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                   STATUS BAR                                         │
│ ✓ SESSION: Stable │ COHERENCE: 0.85 ↑ │ DRIFT: 0.08 │ TURNS: 5 │ Style: analytical  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Full Dashboard View

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    HEADER                                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  [💬 Chat]  [⊞ Split]  [📊 Dashboard●]          Session: abc12345 │ 5 turns        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│                          ANALYTICS DASHBOARD                                         │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         COHERENCE TREND CHART                                │   │
│  │                                                                              │   │
│  │   1.0 │                                                                     │   │
│  │       │      ╭──╮                    ╭──────────╮                           │   │
│  │   0.8 │   ╭──╯  ╰──╮              ╭──╯          │                           │   │
│  │       │ ──╯        ╰──────────────╯             │  ── Stability             │   │
│  │   0.6 │                                         │  ── Drift                 │   │
│  │       │                                         │                           │   │
│  │   0.4 │─────────────────────────────────────────│                           │   │
│  │       │                                                                     │   │
│  │   0.2 │                                                                     │   │
│  │       │                                                                     │   │
│  │   0.0 └──────┬──────┬──────┬──────┬──────┬─────                            │   │
│  │              1      2      3      4      5     Turn                         │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌────────────────────────────┐  ┌────────────────────────────┐                    │
│  │     RISK BANDS             │  │     ENTROPY OVER TIME      │                    │
│  │                            │  │                            │                    │
│  │  Stability  ████ LOW       │  │   ─────                    │                    │
│  │  Drift      ████ LOW       │  │        ────                │                    │
│  │  Semantic   ████████ MED   │  │            ───             │                    │
│  │  Motivation ████ LOW       │  │               ──           │                    │
│  │                            │  │                            │                    │
│  │  Overall: All Clear ✓      │  │   H_norm: 0.41             │                    │
│  └────────────────────────────┘  └────────────────────────────┘                    │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                          SESSION TIMELINE                                    │   │
│  │                                                                              │   │
│  │      ●━━━━━━━━●━━━━━━━━●━━━━━━━━●━━━━━━━━●                                  │   │
│  │      1        2        3        4        5                                  │   │
│  │    [phil]   [phil]   [ethics] [ethics] [ethics]                             │   │
│  │    coh:0.75 coh:0.82 coh:0.79 coh:0.85 coh:0.88                             │   │
│  │                                                                              │   │
│  │   Selected: Turn 3                                                           │   │
│  │   Domain: ethics │ Coherence: 0.79 │ Highlight: Domain shift                │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌────────────────────────────┐  ┌────────────────────────────┐                    │
│  │   ONTOLOGICAL PROFILE      │  │   WHAT-IF SIMULATOR        │                    │
│  │                            │  │                            │                    │
│  │   Dominant: O5_COGNITION    │  │   Preset: [safety_first ▼] │                    │
│  │                            │  │                            │                    │
│  │   Thinking   ██████████░░  │  │   [▶ Run Simulation]       │                    │
│  │   Observing  ████████░░░░  │  │                            │                    │
│  │   Reasoning  █████████░░░  │  │   ORIGINAL    →  SIMULATED │                    │
│  │   Unifying   ██████░░░░░░  │  │     0.42           0.36    │                    │
│  │   Purposing  ████████░░░░  │  │   THINKING      OBSERVING  │                    │
│  │   ...                      │  │                            │                    │
│  │                            │  │   ↓ Entropy decreased 0.06 │                    │
│  └────────────────────────────┘  └────────────────────────────┘                    │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         DIAGNOSTIC INFORMATION                               │   │
│  │                                                                              │   │
│  │   Engine Tier: DEVELOPMENT      │  Session ID: abc12345-6789-...            │   │
│  │   Domain: philosophy            │  Session Stable: Yes                       │   │
│  │   Config: show_reasoning=true   │  Needs Grounding: No                       │   │
│  │                                                                              │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Specifications

### 3.1 Header (Orange Theme)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ ┌────┐                                                                              │
│ │ 🛡 │  Symbol-U                                                        ⚙ Settings │
│ └────┘  Admin Console                                                               │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Background: `gradient(from-orange-600 to-amber-500)`
- Icon: Shield, 40x40px
- Title: 20px bold white
- Subtitle: 12px orange-100

### 3.2 View Mode Bar

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  [💬 Chat]  [⊞ Split View●]  [📊 Dashboard]          Session: abc12345 │ 🔄 │ ⚙   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Height: 44px
- Background: `white/80` backdrop blur
- Mode buttons:
  - Active: orange-100 bg, orange-700 text
  - Inactive: transparent, gray-600 text
- Session ID: monospace, truncated
- Refresh: 24px icon, spins when loading

### 3.3 Coherence Trend Chart

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  COHERENCE TREND                                                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   1.0 │                                                      ── Stability (green)   │
│       │      ╭──╮                    ╭──────────╮            ── Drift (orange)      │
│   0.8 │   ╭──╯  ╰──╮              ╭──╯          │                                   │
│       │ ──╯        ╰──────────────╯             │                                   │
│   0.6 │                                         │                                   │
│       │                                         │                                   │
│   0.4 │─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│  (drift line, lower)              │
│       │                                                                             │
│   0.2 │                                                                             │
│       │                                                                             │
│   0.0 └──────┬──────┬──────┬──────┬──────┬──────────────────────────               │
│              1      2      3      4      5     Turn                                  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Chart library: Recharts
- Height: 200px
- Lines:
  - Stability: green-500, 2px stroke, dot markers
  - Drift: orange-500, 2px stroke, dot markers
- Grid: gray-200 dashed
- Axes: gray-500 text, 11px
- Y-axis: 0.0 to 1.0
- X-axis: Turn numbers
- Legend: bottom right
- Tooltip: white bg, rounded, shows values

### 3.4 Risk Bands Panel

```
┌────────────────────────────────────┐
│  🛡 RISK BANDS                     │
├────────────────────────────────────┤
│                                    │
│  ┌──────────────────────────────┐  │
│  │ Stability Risk         LOW   │  │
│  │ ████████░░░░░░░░░░░░░░  ✓   │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ Drift Risk             LOW   │  │
│  │ ████████░░░░░░░░░░░░░░  ✓   │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ Semantic Risk        MEDIUM  │  │
│  │ ████████████████░░░░░░  ⚠   │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ Motivation Risk        LOW   │  │
│  │ ████████░░░░░░░░░░░░░░  ✓   │  │
│  └──────────────────────────────┘  │
│                                    │
│  ────────────────────────────────  │
│  Overall Assessment: All Clear ✓   │
│                                    │
└────────────────────────────────────┘
```

**Risk Level Styles:**

| Level | Background | Border | Bar Color | Icon |
|-------|------------|--------|-----------|------|
| LOW | green-50 | green-200 | green-500 | ✓ CheckCircle |
| MEDIUM | amber-50 | amber-200 | amber-500 | ⚠ AlertTriangle |
| HIGH | red-50 | red-200 | red-500 | ⚠ AlertCircle |

**Specifications:**
- Card border radius: 8px
- Bar height: 8px
- Risk label: 12px bold
- Level text: 12px semibold, colored

### 3.5 Session Timeline

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  SESSION TIMELINE                                                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│      ●━━━━━━━━●━━━━━━━━●━━━━━━━━●━━━━━━━━●                                          │
│      1        2        3        4        5                                          │
│    [phil]   [phil]   [ethics] [ethics] [ethics]                                     │
│                        ▲                                                             │
│                     Selected                                                         │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  Turn 3                                                    [ethics]          │   │
│  │  ─────────────────────────────────────────────────────────────────────────  │   │
│  │  Coherence: 0.79                                                            │   │
│  │  Highlights:                                                                 │   │
│  │  - Domain shift from philosophy                                              │   │
│  │  - Slight coherence dip                                                      │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Turn Circle Specifications:**
- Size: 32px
- Border: 2px
- Color: Based on coherence level
  - ≥0.7: green-500 bg, green-600 border
  - 0.4-0.7: amber-500 bg, amber-600 border
  - <0.4: red-500 bg, red-600 border
- Selected: ring-2 ring-offset-2 ring-indigo-500
- Number: 12px bold white

**Connection Line:**
- Height: 2px
- Color: gray-200
- Style: solid

### 3.6 What-If Simulator

```
┌────────────────────────────────────┐
│  WHAT-IF SIMULATOR                 │
├────────────────────────────────────┤
│                                    │
│  Preset:                           │
│  ┌────────────────────────────┐   │
│  │ safety_first            ▼ │   │
│  └────────────────────────────┘   │
│                                    │
│  Prioritize safety and reliability │
│                                    │
│  ┌────────────────────────────┐   │
│  │     ▶ Run Simulation       │   │
│  └────────────────────────────┘   │
│                                    │
│  ═══════════════════════════════   │
│                                    │
│   ORIGINAL    →    SIMULATED       │
│                                    │
│    ┌──────┐       ┌──────┐        │
│    │ 0.42 │       │ 0.36 │        │
│    └──────┘       └──────┘        │
│   THINKING       OBSERVING         │
│                                    │
│  ┌────────────────────────────┐   │
│  │ ↓ Entropy decreased 0.06   │   │
│  │   This preset improves     │   │
│  │   coherence.               │   │
│  └────────────────────────────┘   │
│                                    │
└────────────────────────────────────┘
```

**Specifications:**
- Preset dropdown: full width, gray-50 bg
- Run button: indigo-600 bg, white text, icon
- Results layout: 3-column (original | arrow | simulated)
- Value boxes: 48px font, centered
- Delta indicator:
  - Negative (good): green-500, TrendingDown icon
  - Positive (bad): red-500, TrendingUp icon
  - Zero: gray-500, Minus icon

**Available Presets:**
```
safety_first    - Prioritize safety and reliability
insight_heavy   - Maximize depth of insights
balanced        - Balance between all dimensions
performance     - Optimize for quick responses
creative        - Encourage creative exploration
analytical      - Focus on analytical reasoning
```

### 3.7 Diagnostic Information Panel

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  DIAGNOSTIC INFORMATION                                                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   Engine Tier        DEVELOPMENT        Session ID         abc12345-6789-...        │
│   Domain             philosophy         Session Stable     ● Yes                     │
│   Config             show_reasoning     Needs Grounding    No                        │
│   API Endpoint       /symbolu/analyze   Recommended Style  analytical               │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Layout: 2-column grid
- Label: 12px gray-500
- Value: 12px monospace gray-700
- Boolean values: colored (green=yes, red=no)

---

## 4. Color Palette

### Theme Colors (Orange/Amber)
```
Orange-600:  #ea580c  (Header gradient start)
Amber-500:   #f59e0b  (Header gradient end)
Orange-100:  #ffedd5  (Active mode button bg)
Orange-700:  #c2410c  (Active mode button text)
```

### Chart Colors
```
Green-500:   #22c55e  (Stability line)
Orange-500:  #f97316  (Drift line)
Blue-500:    #3b82f6  (Entropy H_D)
Emerald-500: #10b981  (Entropy H_G)
Purple-500:  #a855f7  (Entropy H_K)
Amber-500:   #f59e0b  (Entropy H_norm)
```

### Status Colors
```
Green (LOW):    #22c55e bg, #dcfce7 light, #166534 text
Amber (MEDIUM): #f59e0b bg, #fef3c7 light, #92400e text
Red (HIGH):     #ef4444 bg, #fee2e2 light, #991b1b text
```

---

## 5. Grid System

### Dashboard Grid (Full View)
```
┌────────────────────────────────────────────────────────────────────┐
│                    COHERENCE TREND (span 2)                        │
├──────────────────────────┬─────────────────────────────────────────┤
│     RISK BANDS           │          ENTROPY METRICS                │
├──────────────────────────┴─────────────────────────────────────────┤
│                    SESSION TIMELINE (span 2)                       │
├──────────────────────────┬─────────────────────────────────────────┤
│    ONTOLOGICAL PROFILE   │          WHAT-IF SIMULATOR              │
├──────────────────────────┴─────────────────────────────────────────┤
│                   DIAGNOSTIC INFO (span 2)                         │
└────────────────────────────────────────────────────────────────────┘
```

**Grid Specifications:**
- Columns: 2
- Gap: 16px
- Padding: 16px

---

## 6. Interactions

### 6.1 View Mode Switching
```
Click Chat    → Full chat view, dashboard hidden
Click Split   → 50/50 split view
Click Dashboard → Full dashboard, chat hidden
```
- Transition: 300ms ease-out
- State persisted in URL params

### 6.2 Timeline Turn Selection
```
Click turn circle → Circle gets selection ring
Selected turn → Details panel appears below
Turn data → Populates detail view
```

### 6.3 What-If Simulation
```
Select preset → Description updates
Click Run → Loading spinner on button
API call → Results populate
Results → Show comparison with delta
```

### 6.4 Refresh Dashboard
```
Click refresh → Icon spins
API call → All panels update
Complete → Icon stops spinning
```

---

## 7. Data Flow

### 7.1 Dashboard Data Sources

| Component | API Endpoint | Refresh Trigger |
|-----------|--------------|-----------------|
| Coherence Chart | `/sessions/{id}/dashboard` | Turn change |
| Risk Bands | `/sessions/{id}/dashboard` | Turn change |
| Session Timeline | `/sessions/{id}/dashboard` | Turn change |
| Entropy Metrics | `/symbolu/analyze` | Message response |
| Ontological Profile | `/symbolu/analyze` | Message response |
| What-If Results | `/sessions/{id}/resonance/what_if` | On demand |

### 7.2 Auto-Refresh Options
```
┌────────────────────────────────────┐
│  Auto-refresh: [Off ▼]             │
│                                    │
│    - Off                           │
│    - Every 5 seconds               │
│    - Every 10 seconds              │
│    - Every 30 seconds              │
└────────────────────────────────────┘
```

---

## 8. Responsive Design

### Breakpoints

| Viewport | Layout |
|----------|--------|
| < 768px | Stack all panels vertically, no split view |
| 768px - 1024px | Reduced 2-column grid |
| 1024px - 1440px | Full split view available |
| > 1440px | Full layout with larger charts |

### Mobile View
- No split view option (chat or dashboard only)
- Dashboard: single column stack
- Charts: reduced height (150px)
- Timeline: horizontal scroll

---

## 9. Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` | Switch to Chat view |
| `2` | Switch to Split view |
| `3` | Switch to Dashboard view |
| `R` | Refresh dashboard |
| `←` / `→` | Navigate timeline turns |
| `Enter` | Run what-if simulation |

---

## 10. Accessibility

| Requirement | Implementation |
|-------------|----------------|
| Chart accessibility | aria-label with data summary |
| Timeline navigation | Keyboard accessible circles |
| Color contrast | All text meets WCAG AA |
| Screen reader | Full descriptions for metrics |
| Focus management | Logical tab order through panels |

---

*Document Version: 1.0*
*Last Updated: December 2025*
