# Symbol-U Frontend

Three-tier frontend UX for Symbol-U presentation layer.

## Architecture

This frontend implements **three distinct user experience tiers**, each providing progressively more features and insights:

### Tier 1: Consumer (`/consumer`)
**Simple, clean chat experience**
- Basic chat interface with message bubbles
- Response quality badges (coherent, grounded, reflective, etc.)
- Hint cards for actionable insights
- Compact session status bar

**Target:** End users who want straightforward interaction
**Backend:** `/dilchat/analyze` with `CONSUMER` config

### Tier 2: Power User (`/power_user`)
**Enhanced chat with insights panel**
- Full chat interface with layer tabs (Symbolic/Practical/Mirror)
- Coherence metrics and trends
- Entropy visualization (H_D, H_G, H_K, H_norm)
- 10D Ontological profile display
- Collapsible insights panel

**Target:** Users who want deeper understanding
**Backend:** `/dilchat/analyze` with `ENTERPRISE_CHAT` config

### Tier 3: Admin (`/admin`)
**Full analytics dashboard**
- Complete chat with all features
- Coherence trend charts
- Risk bands visualization
- Session timeline
- What-if simulator
- Diagnostic information

**Target:** Admins and developers who need full visibility
**Backend:** `/symbolu/analyze` with `DEVELOPMENT` config

## Project Structure

```
frontend/
├── src/
│   ├── api/                    # API client and types
│   │   ├── client.ts           # API client functions
│   │   ├── types.ts            # TypeScript type definitions
│   │   └── index.ts
│   ├── components/             # Reusable UI components
│   │   ├── chat/               # Chat-specific components
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── BadgeDisplay.tsx
│   │   │   ├── HintCard.tsx
│   │   │   ├── LayerTabs.tsx
│   │   │   └── InputArea.tsx
│   │   ├── indicators/         # Status indicators
│   │   │   ├── CoherenceIndicator.tsx
│   │   │   └── SessionStatusBar.tsx
│   │   ├── insights/           # Insight components (Tier 2+)
│   │   │   ├── EntropyMetrics.tsx
│   │   │   └── OntologicalRadar.tsx
│   │   ├── dashboard/          # Dashboard components (Tier 3)
│   │   │   ├── CoherenceTrendChart.tsx
│   │   │   ├── RiskBandsPanel.tsx
│   │   │   ├── SessionTimeline.tsx
│   │   │   └── WhatIfSimulator.tsx
│   │   └── common/             # Shared components
│   │       └── Header.tsx
│   ├── views/                  # Page-level views
│   │   ├── ConsumerTierPage.tsx
│   │   ├── PowerUserTierPage.tsx
│   │   └── AdminTierPage.tsx
│   ├── stores/                 # Zustand state stores
│   │   ├── chatStore.ts
│   │   └── dashboardStore.ts
│   ├── styles/                 # Global styles
│   │   └── index.css
│   ├── App.tsx                 # Main app with tier routing
│   └── main.tsx                # Entry point
├── public/
│   └── favicon.svg
├── index.html
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── vite.config.ts
└── README.md
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Framework | React 18 | Component-based UI |
| Build | Vite | Fast development server |
| State | Zustand | Lightweight state management |
| Styling | Tailwind CSS | Utility-first CSS |
| Charts | Recharts | Data visualization |
| Icons | Lucide React | Modern icon library |
| Language | TypeScript | Type safety |

## Getting Started

### Prerequisites
- Node.js 18+
- npm or yarn

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
# Start development server
npm run dev

# The app will be available at http://localhost:3000
```

### Build

```bash
# Type check
npm run type-check

# Build for production
npm run build

# Preview production build
npm run preview
```

## Backend Integration

The frontend connects to the Symbol-U presentation layer API:

| Endpoint | Purpose | Tier |
|----------|---------|------|
| `POST /dilchat/analyze` | Basic chat analysis | 1, 2 |
| `POST /symbolu/analyze` | Full unified analysis | 3 |
| `POST /session/start` | Start conversation session | All |
| `POST /session/{id}/analyze` | Analyze within session | All |
| `GET /session/{id}/summary` | Session summary | 2, 3 |
| `GET /sessions/{id}/dashboard` | Dashboard data | 3 |
| `GET /sessions/{id}/resonance/what_if` | What-if simulation | 3 |

### Environment Variables

Create a `.env` file:

```env
VITE_API_URL=http://localhost:8000
```

## Design Principles

1. **Progressive Disclosure**: Features revealed based on tier
2. **Tier-Specific Theming**: Each tier has distinct visual identity
3. **Real-Time Feedback**: Immediate UI updates on responses
4. **Accessibility**: Semantic HTML, ARIA labels, keyboard navigation
5. **Responsive**: Mobile-first design approach
6. **Performance**: Lazy loading, efficient state updates

## Component Guidelines

### Tier-Aware Components
Components receive a `tier` prop to conditionally render features:

```tsx
<MessageBubble message={msg} tier="power_user" />
```

### State Management
- Use `useChatStore` for chat state
- Use `useDashboardStore` for analytics state

### Styling
- Use Tailwind utility classes
- Custom colors defined in `tailwind.config.js`
- Tier-specific gradients and accents

## Testing

```bash
# Run linter
npm run lint

# Type check
npm run type-check
```

## License

Internal use only - Symbol-U project.
