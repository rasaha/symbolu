# Tier 2: Power User UX Design

## Version 1.0 | December 2025

---

## Overview

The Power User tier provides an **enhanced analytical experience** with deeper insights into response quality, semantic layers, and cognitive metrics. Designed for users who want to understand the "why" behind responses.

---

## 1. Design Principles

| Principle | Description |
|-----------|-------------|
| **Insight Depth** | Surface meaningful metrics without overwhelming |
| **Progressive Disclosure** | Show more details on demand |
| **Visual Clarity** | Use charts and indicators for complex data |
| **Professional Aesthetic** | Purple/violet theme for sophistication |
| **Dual-Panel Layout** | Chat + Insights side-by-side |

---

## 2. Page Layout

### 2.1 Master Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  HEADER                                          │
│  ┌────┐  Symbol-U                                                   [Settings]  │
│  │ S  │  Power User Experience                                                  │
│  └────┘                                                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                               METRICS BAR                                        │
│  🎯 Coherence: ████████░░ 0.85 ↑          [Insights Panel ◀] │
├────────────────────────────────────────────────┬────────────────────────────────┤
│                                                │                                 │
│              CHAT AREA                         │        INSIGHTS PANEL           │
│           (Collapsible)                        │         (320px width)           │
│                                                │                                 │
│  ┌──────────────────────────────────────┐     │  ┌─────────────────────────┐   │
│  │ USER MESSAGE                          │     │  │ RESPONSE INSIGHTS       │   │
│  │ "Analyze consciousness deeply"        │     │  │                         │   │
│  └──────────────────────────────────────┘     │  │ COHERENCE               │   │
│                                                │  │ ● Stable  0.85 ↑        │   │
│  ┌──────────────────────────────────────┐     │  └─────────────────────────┘   │
│  │ ASSISTANT MESSAGE                     │     │                                │
│  │                                       │     │  ┌─────────────────────────┐   │
│  │ Response text...                      │     │  │ ENTROPY METRICS         │   │
│  │                                       │     │  │                         │   │
│  │ ┌────────┐ ┌────────┐ ┌────────┐     │     │  │ H_D  ████████░░ 0.42   │   │
│  │ │✓ coher │ │◉ deep  │ │💭 refl │     │     │  │ H_G  ███████░░░ 0.38   │   │
│  │ └────────┘ └────────┘ └────────┘     │     │  │ H_K  █████████░ 0.45   │   │
│  │                                       │     │  │ Norm ████████░░ 0.41   │   │
│  │ 💡 Insight hint here                  │     │  └─────────────────────────┘   │
│  │                                       │     │                                │
│  │ ┌─────────────────────────────────┐  │     │  ┌─────────────────────────┐   │
│  │ │ [Symbolic●] [Practical] [Mirror]│  │     │  │ ONTOLOGICAL PROFILE     │   │
│  │ ├─────────────────────────────────┤  │     │  │                         │   │
│  │ │ SYMBOLIC LAYER                  │  │     │  │ Thinking   ██████░░ 0.62│   │
│  │ │ Fusion Score: 0.82              │  │     │  │ Observing  █████░░░ 0.45│   │
│  │ │ Source: reasoning_model         │  │     │  │ Reasoning  █████░░░ 0.55│   │
│  │ │ High contemplative processing   │  │     │  │ ...                     │   │
│  │ └─────────────────────────────────┘  │     │  └─────────────────────────┘   │
│  │                                       │     │                                │
│  │ [▼ Details]                 10:31 AM │     │                                │
│  └──────────────────────────────────────┘     │                                │
│                                                │                                │
├────────────────────────────────────────────────┴────────────────────────────────┤
│                              INPUT AREA                                          │
│  Domain: [Philosophy ▼]  Mode: [domain_relative ▼]                              │
│  ┌────────────────────────────────────────────────────────────────────┬────┐   │
│  │ Ask something profound...                                          │ ➤  │   │
│  └────────────────────────────────────────────────────────────────────┴────┘   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                             STATUS BAR                                           │
│  ✓ SESSION: Stable │ 🎯 COHERENCE: ████████░░ 0.85 ↑ │ # TURNS: 5 │ Style: deep │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layout Specifications

| Element | Width | Height | Position |
|---------|-------|--------|----------|
| Header | 100% | 64px | Fixed top |
| Metrics Bar | 100% | 44px | Fixed below header |
| Chat Area | Flex (100% - 320px) | Flexible | Scrollable |
| Insights Panel | 320px | 100% | Fixed right |
| Input Area | 100% | Auto | Fixed bottom |
| Status Bar | 100% | 52px | Fixed bottom |

---

## 3. Component Specifications

### 3.1 Header (Purple Theme)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ ┌────┐                                                                          │
│ │ 🧠 │  Symbol-U                                                    ⚙ Settings │
│ └────┘  Power User Experience                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Background: `gradient(from-purple-600 to-violet-500)`
- Logo: Brain icon, 40x40px
- Title: 20px bold white
- Subtitle: 12px purple-100

### 3.2 Metrics Bar

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  🎯 Coherence: ● Stable ████████░░ 0.85 ↑              [🔍 Insights Panel ◀]   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Height: 44px
- Background: `white/80` with backdrop blur
- Border bottom: `1px solid gray-200`
- Coherence indicator: inline with progress bar
- Toggle button: purple-100 background, purple-700 text

### 3.3 Layer Tabs (Inside Message)

```
┌─────────────────────────────────────────────────────────────────┐
│  [Symbolic ●]  [Practical]  [Mirror]                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SYMBOLIC LAYER                                                  │
│  ─────────────                                                   │
│  Fusion Score: 0.82                                              │
│  Selected Source: reasoning_model                                │
│                                                                  │
│  The response was generated through high O5_COGNITION            │
│  activation, indicating deep contemplative processing.          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Tab Specifications:**

| Tab | Icon | Active Color | Description |
|-----|------|--------------|-------------|
| Symbolic | ✨ Sparkles | Indigo-600 | WHY - Meaning & themes |
| Practical | 🎯 Target | Emerald-600 | WHAT/HOW - Actions & facts |
| Mirror | 🪞 Mirror | Purple-600 | Reflection - Contradictions |

**Tab Button:**
- Height: 32px
- Padding: 8px 12px
- Active: white background, shadow, colored text
- Inactive: transparent, gray-600 text
- Dot indicator: 6px colored circle

**Tab Content:**
- Background: `gray-50`
- Border radius: 8px
- Padding: 12px
- Min height: 60px
- Text: 14px gray-700

### 3.4 Insights Panel

```
┌─────────────────────────────────────┐
│  🔍 Response Insights               │
├─────────────────────────────────────┤
│                                     │
│  ┌───────────────────────────────┐  │
│  │ COHERENCE                     │  │
│  │ ● Stable  ████████░░ 0.85 ↑   │  │
│  │                               │  │
│  │ Trend: Improving over 3 turns │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ ENTROPY METRICS               │  │
│  │                               │  │
│  │ H_D (Domain)     0.42        │  │
│  │ ████████████░░░░░░░░         │  │
│  │                               │  │
│  │ H_G (Global)     0.38        │  │
│  │ ██████████░░░░░░░░░░         │  │
│  │                               │  │
│  │ H_K (Knowledge)  0.45        │  │
│  │ █████████████░░░░░░░         │  │
│  │                               │  │
│  │ H_norm           0.41        │  │
│  │ ███████████░░░░░░░░░         │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ 10D ONTOLOGICAL PROFILE       │  │
│  │                               │  │
│  │ Dominant: Thinking            │  │
│  │                               │  │
│  │ Thinking   ████████████░░ 0.62│  │
│  │ Observing  █████████░░░░░ 0.45│  │
│  │ Reasoning  ███████████░░░ 0.55│  │
│  │ Unifying   ██████░░░░░░░░ 0.32│  │
│  │ Forming    ████░░░░░░░░░░ 0.21│  │
│  │ ...                           │  │
│  └───────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
```

**Panel Specifications:**
- Width: 320px
- Background: white
- Border left: `1px solid gray-200`
- Shadow: `-4px 0 6px rgba(0,0,0,0.05)`
- Padding: 16px
- Scrollable: yes

**Card Specifications:**
- Background: white
- Border: `1px solid gray-200`
- Border radius: 8px
- Padding: 16px
- Margin bottom: 16px
- Header: 12px semibold gray-800

### 3.5 Entropy Metrics Display

```
┌─────────────────────────────────────┐
│  ENTROPY METRICS                    │
├─────────────────────────────────────┤
│                                     │
│  Domain (H_D)                  0.42 │
│  ████████████░░░░░░░░░░░░░░░░░░░░  │
│                                     │
│  Global (H_G)                  0.38 │
│  ██████████░░░░░░░░░░░░░░░░░░░░░░  │
│                                     │
│  Knowledge (H_K)               0.45 │
│  █████████████░░░░░░░░░░░░░░░░░░░  │
│                                     │
│  Normalized                    0.41 │
│  ███████████░░░░░░░░░░░░░░░░░░░░░  │
│                                     │
└─────────────────────────────────────┘
```

**Specifications:**
- Bar height: 8px
- Bar background: `gray-100`
- Bar colors: H_D=blue, H_G=emerald, H_K=purple, Norm=amber
- Value: 12px monospace right-aligned
- Label: 12px gray-600

### 3.6 Ontological Profile

```
┌─────────────────────────────────────┐
│  10D ONTOLOGICAL PROFILE            │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ Dominant: Thinking          │   │
│  └─────────────────────────────┘   │
│                                     │
│  O1 Thinking    ████████████░░ 0.62 │  ← Highlighted
│  O8 Observing   █████████░░░░░ 0.45 │
│  O6 Reasoning   ███████████░░░ 0.55 │
│  O9 Unifying    ██████░░░░░░░░ 0.32 │
│  O7 Purposing   ████████░░░░░░ 0.42 │
│  O5 Directing   ███████░░░░░░░ 0.35 │
│  O4 Tagging     █████░░░░░░░░░ 0.28 │
│  O2 Forming     ████░░░░░░░░░░ 0.21 │
│  O10 Absolving  ███░░░░░░░░░░░ 0.18 │
│  O3 Acting      ███░░░░░░░░░░░ 0.15 │
│                                     │
└─────────────────────────────────────┘
```

**Specifications:**
- Sorted by value (highest first)
- Dominant badge: indigo-100 background, indigo-700 text
- Row height: 28px
- Bar width: 120px
- Bar height: 8px
- Colors: gradient from blue to purple based on value
- Dominant row: gray-50 background highlight

### 3.7 Enhanced Status Bar

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ ✓ SESSION: Stable │ 🎯 COHERENCE: ████████░░ 0.85 ↑ │ # TURNS: 5 │ Style: deep │
│                   │ Drift: 0.08                     │            │              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Height: 52px
- Background: `gray-50`
- Two-row layout
- Row 1: Primary metrics
- Row 2: Secondary details (drift, recommended style)
- Dividers: 1px gray-300

---

## 4. Color Palette

### Theme Colors (Purple/Violet)
```
Purple-600:  #9333ea  (Header gradient start)
Violet-500:  #8b5cf6  (Header gradient end)
Purple-100:  #f3e8ff  (Accent backgrounds)
Purple-700:  #7c3aed  (Accent text)
```

### Metric Colors
```
Blue-500:    #3b82f6  (H_D entropy)
Emerald-500: #10b981  (H_G entropy)
Purple-500:  #a855f7  (H_K entropy)
Amber-500:   #f59e0b  (H_norm entropy)
Indigo-500:  #6366f1  (Symbolic layer)
```

### Ontological Dimension Colors
```
O1 Thinking:    #3b82f6  (Blue)
O2 Forming:     #06b6d4  (Cyan)
O3 Acting:      #10b981  (Emerald)
O4 Tagging:     #14b8a6  (Teal)
O5 Directing:   #22c55e  (Green)
O6 Reasoning:   #eab308  (Yellow)
O7 Purposing:   #f97316  (Orange)
O8 Observing:   #ef4444  (Red)
O9 Unifying:    #ec4899  (Pink)
O10 Absolving:  #a855f7  (Purple)
```

---

## 5. Interactions

### 5.1 Panel Toggle
```
[Insights Panel ◀]  →  Click  →  Panel slides out
[Insights Panel ▶]  →  Click  →  Panel slides in
```
- Animation: 300ms ease-out
- Chat area expands/contracts accordingly

### 5.2 Message Selection
```
Click on assistant message → Purple ring highlight
Selected message data → Populates insights panel
```

### 5.3 Layer Tab Switching
```
Click tab → Content transitions with fade
Active tab → White background, shadow, colored text
Inactive → Transparent, gray text
```

### 5.4 Expand/Collapse Details
```
[▼ Details] → Expands to show full layer content
[▲ Collapse] → Hides extended content
```

---

## 6. Welcome State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                  │
│                          ┌────────────────┐                                     │
│                          │      🧠        │                                     │
│                          │   Symbol-U     │                                     │
│                          └────────────────┘                                     │
│                                                                                  │
│                    Power User Experience                                         │
│                                                                                  │
│       Explore deeper insights with layer analysis, coherence metrics,           │
│       and ontological profiling. Click any response to see detailed             │
│       breakdowns.                                                                │
│                                                                                  │
│       ┌──────────────────────┐  ┌──────────────────────┐                        │
│       │ Analyze consciousness│  │ Explore frameworks   │                        │
│       └──────────────────────┘  └──────────────────────┘                        │
│                    ┌──────────────────────┐                                     │
│                    │ Dive into epistemology│                                    │
│                    └──────────────────────┘                                     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Responsive Design

### Panel Behavior

| Viewport | Insights Panel |
|----------|----------------|
| < 1024px | Hidden by default, overlay when opened |
| ≥ 1024px | Side panel, toggleable |
| ≥ 1440px | Side panel, always visible |

### Mobile Insights (< 1024px)
```
┌─────────────────────────────────────┐
│  ✕                                  │  ← Close button
│                                     │
│  INSIGHTS PANEL                     │
│  (Full screen overlay)              │
│                                     │
└─────────────────────────────────────┘
```

---

## 8. Animation Specifications

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Panel slide | translateX | 300ms | ease-out |
| Tab switch | fade | 200ms | ease |
| Message expand | height + opacity | 250ms | ease-out |
| Progress bar | width | 500ms | ease-out |
| Badge hover | scale | 150ms | ease |

---

## 9. Accessibility

| Requirement | Implementation |
|-------------|----------------|
| Panel toggle | Keyboard accessible, aria-expanded |
| Tab navigation | Arrow keys within tabs, aria-selected |
| Metrics | Screen reader descriptions for values |
| Color blind | Icons + text, not just colors |
| Focus management | Trap focus in panel when open (mobile) |

---

*Document Version: 1.0*
*Last Updated: December 2025*
