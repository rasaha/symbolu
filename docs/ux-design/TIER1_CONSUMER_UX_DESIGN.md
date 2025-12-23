# Tier 1: Consumer UX Design

## Version 1.0 | December 2025

---

## Overview

The Consumer tier provides a **simple, intuitive chat experience** designed for end users who want straightforward interaction without technical complexity. The design prioritizes ease of use, clarity, and conversational flow.

---

## 1. Design Principles

| Principle | Description |
|-----------|-------------|
| **Simplicity First** | Remove all non-essential elements; focus on conversation |
| **Friendly & Approachable** | Warm colors, soft edges, conversational tone |
| **Progressive Trust** | Build confidence through clear feedback indicators |
| **Zero Learning Curve** | Familiar chat patterns; no training required |
| **Mobile-First** | Responsive design that works on all devices |

---

## 2. Page Layout

### 2.1 Wireframe

```
┌─────────────────────────────────────────────────────────────────┐
│                          HEADER                                  │
│  ┌──────────┐                                                   │
│  │ Logo [S] │  Symbol-U                              [Settings] │
│  └──────────┘  Consumer Experience                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                      MESSAGE AREA                                │
│                    (Scrollable)                                  │
│                                                                  │
│    ┌─────────────────────────────────────────────────────┐      │
│    │ [USER BUBBLE - Right aligned]                       │      │
│    │ "What is the meaning of life?"                      │      │
│    │                                          10:30 AM   │      │
│    └─────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ [ASSISTANT BUBBLE - Left aligned]                   │        │
│  │                                                     │        │
│  │ Response text here...                               │        │
│  │                                                     │        │
│  │ ┌────────┐ ┌────────┐ ┌─────────┐                  │        │
│  │ │✓ coher │ │⚓ ground│ │💭 reflec│  ← BADGES       │        │
│  │ └────────┘ └────────┘ └─────────┘                  │        │
│  │                                                     │        │
│  │ ┌─────────────────────────────────────────────┐    │        │
│  │ │ 💡 Consider exploring: self-awareness       │    │        │
│  │ └─────────────────────────────────────────────┘    │        │
│  │                                          10:31 AM  │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                       INPUT AREA                                 │
│  ┌────────────────────┐                                         │
│  │ Domain: [General ▼]│                                         │
│  ├────────────────────┴──────────────────────────────┬─────┐   │
│  │ Type your message...                              │ ➤  │   │
│  └───────────────────────────────────────────────────┴─────┘   │
│  Press Enter to send, Shift+Enter for new line                  │
├─────────────────────────────────────────────────────────────────┤
│                     STATUS BAR                                   │
│  ● Stable │ ████████░░ 0.85 │ 5 turns                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Layout Specifications

| Element | Width | Height | Position |
|---------|-------|--------|----------|
| Header | 100% | 64px | Fixed top |
| Message Area | 100% (max 768px) | Flexible | Scrollable |
| Input Area | 100% (max 768px) | Auto | Fixed bottom |
| Status Bar | 100% | 40px | Fixed bottom |

---

## 3. Component Specifications

### 3.1 Header

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌────┐                                                          │
│ │ S  │  Symbol-U                                    ⚙ Settings  │
│ └────┘  Consumer Experience                                     │
└─────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Background: `gradient(from-blue-600 to-blue-500)`
- Logo: 40x40px rounded square, white "S"
- Title: 20px bold white
- Subtitle: 12px blue-100
- Settings icon: 24px, white, hover opacity

### 3.2 Message Bubbles

#### User Message
```
                              ┌─────────────────────────────────┐
                              │ You                             │
                              │ Message text here...            │
                              │                       10:30 AM  │
                              └─────────────────────────────────┘
```

**Specifications:**
- Background: `#6366f1` (symbolu-primary)
- Text: White
- Border radius: 16px (bottom-right: 4px)
- Max width: 85%
- Alignment: Right
- Padding: 16px
- Shadow: `0 1px 2px rgba(0,0,0,0.05)`

#### Assistant Message
```
┌─────────────────────────────────────────────────────────────┐
│ Symbol-U                                                     │
│                                                              │
│ Response text displayed here with proper line height         │
│ for readability...                                           │
│                                                              │
│ ┌──────────┐ ┌──────────┐                                   │
│ │ ✓ coher  │ │ ⚓ ground │  ← Inline Badges                 │
│ └──────────┘ └──────────┘                                   │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐  │
│ │ 💡 Consider exploring: self-awareness, consciousness   │  │
│ └────────────────────────────────────────────────────────┘  │
│                                                   10:31 AM  │
└─────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Background: `white`
- Border: `1px solid #e5e7eb`
- Text: `#1f2937` (gray-800)
- Border radius: 16px (bottom-left: 4px)
- Max width: 85%
- Alignment: Left
- Padding: 16px
- Line height: 1.6

### 3.3 Badge Display

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ ✓ coher  │ │ ⚓ ground │ │ 💭 reflec│ │ ⚠ caution│
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

**Badge Types:**

| Badge | Icon | Color | Meaning |
|-------|------|-------|---------|
| coherent | ✓ CheckCircle | Green-500 | High coherence score |
| grounded | ⚓ Anchor | Blue-500 | Well-grounded response |
| reflective | 💭 Brain | Purple-500 | Deep reflection |
| deep | ◉ Layers | Indigo-500 | Multi-layer analysis |
| practical | 🔧 Wrench | Orange-500 | Actionable content |
| caution | ⚠ Alert | Yellow-500 | Needs attention |

**Badge Specifications:**
- Height: 24px
- Padding: 8px 12px
- Border radius: 12px (pill)
- Background: `#f9fafb` (gray-50)
- Border: `1px solid #e5e7eb`
- Font: 12px medium
- Icon: 14px
- Gap between badges: 6px

### 3.4 Hint Card

```
┌─────────────────────────────────────────────────────────────┐
│ 💡 Consider exploring: self-awareness, qualia, perception   │
└─────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Background: `#eff6ff` (blue-50)
- Border: `1px solid #bfdbfe` (blue-200)
- Border radius: 8px
- Padding: 8px 12px
- Icon: 14px, blue-500
- Text: 12px, blue-800
- Max lines: 2 (truncate)

**Hint Types:**

| Type | Background | Border | Icon |
|------|------------|--------|------|
| Insight | blue-50 | blue-200 | 💡 Lightbulb |
| Action | emerald-50 | emerald-200 | → ArrowRight |
| Warning | amber-50 | amber-200 | ⚠ AlertTriangle |

### 3.5 Input Area

```
┌────────────────────────────────────────────────────────────────┐
│ Domain: [General        ▼]                                      │
├────────────────────────────────────────────────────────────────┤
│                                                          ┌────┐│
│ Ask me anything...                                       │ ➤ ││
│                                                          └────┘│
└────────────────────────────────────────────────────────────────┘
  Press Enter to send, Shift+Enter for new line
```

**Specifications:**
- Domain selector: 12px, gray-600, dropdown
- Input background: `#f9fafb` (gray-50)
- Input border: `1px solid #e5e7eb`
- Input border radius: 12px
- Input padding: 12px 16px
- Placeholder: 14px, gray-400
- Send button: 44px circle, primary color
- Send icon: 20px white arrow

### 3.6 Status Bar (Compact)

```
┌─────────────────────────────────────────────────────────────────┐
│  ● Stable  │  ████████░░ 0.85  │  5 turns                       │
└─────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Height: 40px
- Background: `#f9fafb` (gray-50)
- Border top: `1px solid #e5e7eb`
- Status dot: 8px circle (green/amber/red)
- Progress bar: 60px width, 4px height
- Text: 12px, gray-600
- Dividers: 1px gray-300

---

## 4. Color Palette

### Primary Colors
```
Blue-600:  #2563eb  (Header gradient start)
Blue-500:  #3b82f6  (Header gradient end, links)
Indigo-600: #4f46e5 (Primary button, user bubbles)
```

### Status Colors
```
Green-500:  #22c55e  (Stable, High coherence)
Amber-500:  #f59e0b  (Moderate, Caution)
Red-500:    #ef4444  (Unstable, Low coherence)
Gray-400:   #9ca3af  (Unknown, Disabled)
```

### Surface Colors
```
White:      #ffffff  (Backgrounds, cards)
Gray-50:    #f9fafb  (Input backgrounds)
Gray-100:   #f3f4f6  (Hover states)
Gray-200:   #e5e7eb  (Borders)
Gray-800:   #1f2937  (Primary text)
Gray-500:   #6b7280  (Secondary text)
```

---

## 5. Typography

| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Header Title | Inter | 20px | Bold | White |
| Header Subtitle | Inter | 12px | Normal | Blue-100 |
| Message Text | Inter | 14px | Normal | Gray-800 |
| Role Label | Inter | 12px | Medium | Gray-400 |
| Badge Text | Inter | 12px | Medium | Gray-700 |
| Hint Text | Inter | 12px | Normal | Blue-800 |
| Timestamp | Inter | 11px | Normal | Gray-400 |
| Status Text | Inter | 12px | Normal | Gray-600 |

---

## 6. Interactions

### 6.1 Send Message Flow
```
User types message
    │
    ▼
User presses Enter or clicks Send
    │
    ▼
Input cleared, user message appears
    │
    ▼
Loading indicator: "Symbol-U is thinking..."
    │
    ▼
Assistant message appears with badges/hints
    │
    ▼
Status bar updates (coherence, turn count)
```

### 6.2 Hover States

| Element | Hover Effect |
|---------|--------------|
| Send Button | `opacity: 0.9`, `scale: 1.02` |
| Badge | `background: gray-100` |
| Domain Selector | `border-color: gray-300` |
| Settings Icon | `opacity: 0.8` |

### 6.3 Loading States

```
┌─────────────────────────────────────────────────────────────┐
│  💬 Symbol-U is thinking...                                 │
│  ████████████░░░░░░░░░░░░░░░░░░░░  (animated pulse)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Welcome State

When no messages exist:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                     ┌────────────────┐                          │
│                     │       ✨       │                          │
│                     │    Symbol-U    │                          │
│                     └────────────────┘                          │
│                                                                  │
│               Welcome to Symbol-U                                │
│                                                                  │
│    Start a conversation and explore ideas together.             │
│    I'll provide thoughtful responses with helpful insights.     │
│                                                                  │
│    ┌────────────────────┐ ┌────────────────────┐               │
│    │ What is conscious? │ │ Explain AI ethics  │               │
│    └────────────────────┘ └────────────────────┘               │
│                    ┌────────────────────┐                       │
│                    │ Tell me creativity │                       │
│                    └────────────────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Icon container: 80px, gradient background
- Title: 24px bold, gray-800
- Description: 16px, gray-600, max-width 400px
- Suggestion pills: white background, gray-200 border, hover: gray-50

---

## 8. Responsive Design

### Mobile (< 640px)
- Header height: 56px
- Message max-width: 95%
- Input area padding: 12px
- Status bar text: hide "turns" label

### Tablet (640px - 1024px)
- Message max-width: 90%
- Centered content area

### Desktop (> 1024px)
- Max content width: 768px
- Centered with side margins

---

## 9. Accessibility

| Requirement | Implementation |
|-------------|----------------|
| Color contrast | WCAG AA minimum (4.5:1) |
| Focus indicators | 2px ring, primary color |
| Screen reader | ARIA labels on all interactive elements |
| Keyboard nav | Tab order: Input → Send → Settings |
| Motion | `prefers-reduced-motion` support |

---

## 10. Error States

### Network Error
```
┌─────────────────────────────────────────────────────────────┐
│ ⚠ Connection lost. Retrying...                              │
│ [Retry Now]                                                  │
└─────────────────────────────────────────────────────────────┘
```

### API Error
```
┌─────────────────────────────────────────────────────────────┐
│ Symbol-U                                    [🔴 error]       │
│                                                              │
│ Sorry, I encountered an error processing your request.      │
│ Please try again.                                            │
│                                                   10:31 AM   │
└─────────────────────────────────────────────────────────────┘
```

---

*Document Version: 1.0*
*Last Updated: December 2025*
