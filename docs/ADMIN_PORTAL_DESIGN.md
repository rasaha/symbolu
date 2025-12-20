# Symbol-U Admin Portal Design Document

## Version 0.1 (Preliminary) | December 2025

---

## Table of Contents

1. [Overview](#1-overview)
2. [User Roles & Permissions](#2-user-roles--permissions)
3. [Core Modules](#3-core-modules)
4. [Dashboard Views](#4-dashboard-views)
5. [Cross-Domain Configuration](#5-cross-domain-configuration)
6. [Session Management](#6-session-management)
7. [User & Org Management](#7-user--org-management)
8. [System Monitoring](#8-system-monitoring)
9. [Analytics & Reports](#9-analytics--reports)
10. [API Integration](#10-api-integration)

---

## 1. Overview

### 1.1 Purpose

The Admin Portal provides system administrators with tools to:

- **Configure** cross-domain learning policies
- **Monitor** system health and performance
- **Manage** users, organizations, and preferences
- **Analyze** session patterns and learning outcomes
- **Audit** system activity and policy violations

### 1.2 Design Principles

| Principle | Description |
|-----------|-------------|
| Zero-LLM Admin | All admin operations are deterministic |
| Non-Invasive | Admin changes don't interrupt live sessions |
| Audit Trail | All configuration changes are logged |
| Progressive Disclosure | Simple overview → detailed drill-down |

### 1.3 Portal Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ADMIN PORTAL                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │DASHBOARD │ │ DOMAINS  │ │ SESSIONS │ │ SYSTEM   │           │
│  │ Overview │ │ Config   │ │ Manager  │ │ Health   │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  USERS   │ │  ORGS    │ │ ANALYTICS│ │  AUDIT   │           │
│  │ Manager  │ │ Manager  │ │ Reports  │ │  Logs    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. User Roles & Permissions

### 2.1 Role Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                      SUPER ADMIN                                 │
│  • Full system access                                            │
│  • Cross-domain config                                           │
│  • User/Org management                                           │
│  • System settings                                               │
├─────────────────────────────────────────────────────────────────┤
│                       ORG ADMIN                                  │
│  • Org-level settings                                            │
│  • Org user management                                           │
│  • Org session analytics                                         │
│  • Org preference overrides                                      │
├─────────────────────────────────────────────────────────────────┤
│                       ANALYST                                    │
│  • Read-only dashboard                                           │
│  • Analytics & reports                                           │
│  • Session viewing                                               │
│  • No configuration access                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Permission Matrix

| Feature | Super Admin | Org Admin | Analyst |
|---------|-------------|-----------|---------|
| System Dashboard | ✓ | ✓ (org only) | ✓ (read) |
| Cross-Domain Config | ✓ | ✗ | ✗ |
| Domain Pair Rules | ✓ | ✗ | ✗ |
| Block/Allow Domains | ✓ | ✗ | ✗ |
| User Management | ✓ | ✓ (org only) | ✗ |
| Org Management | ✓ | ✗ | ✗ |
| Preference Override | ✓ | ✓ (org only) | ✗ |
| Session Analytics | ✓ | ✓ (org only) | ✓ (org only) |
| System Health | ✓ | ✗ | ✗ |
| Audit Logs | ✓ | ✓ (org only) | ✗ |
| Counter Reset | ✓ | ✗ | ✗ |

---

## 3. Core Modules

### 3.1 Module Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         MODULES                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DASHBOARD          System-wide metrics and alerts           │
│  2. CROSS-DOMAIN       Domain pair policies and thresholds      │
│  3. SESSIONS           Active/historical session management     │
│  4. USERS              User preferences and settings            │
│  5. ORGANIZATIONS      Org-level overrides and policies         │
│  6. SYSTEM             Health, performance, configuration       │
│  7. ANALYTICS          Reports, trends, insights                │
│  8. AUDIT              Activity logs and change history         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Navigation Structure

```
Admin Portal
├── Dashboard
│   ├── System Overview
│   ├── Alert Center
│   └── Quick Actions
│
├── Cross-Domain Learning
│   ├── Global Settings
│   ├── Domain Pairs
│   │   ├── Blocked Pairs
│   │   ├── High-Threshold Pairs
│   │   └── Monitored Pairs
│   ├── Thresholds
│   └── Counters & Stats
│
├── Sessions
│   ├── Active Sessions
│   ├── Session History
│   ├── Session Search
│   └── Session Analytics
│
├── Users & Orgs
│   ├── Users
│   │   ├── User List
│   │   ├── User Preferences
│   │   └── User Sessions
│   └── Organizations
│       ├── Org List
│       ├── Org Settings
│       └── Org Overrides
│
├── System
│   ├── Health Monitor
│   ├── API Metrics
│   ├── Configuration
│   └── Maintenance
│
├── Analytics
│   ├── Cross-Domain Reports
│   ├── Coherence Trends
│   ├── Usage Patterns
│   └── Export Data
│
└── Audit
    ├── Activity Log
    ├── Config Changes
    └── Policy Violations
```

---

## 4. Dashboard Views

### 4.1 System Overview Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  SYMBOL-U ADMIN                    [Super Admin] [🔔 3] [Logout]│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    SYSTEM STATUS                             ││
│  │  ● API: Healthy    ● Pipeline: Running    ● Sessions: 142   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │ CROSS-DOMAIN STATS  │  │ SESSION METRICS     │               │
│  ├─────────────────────┤  ├─────────────────────┤               │
│  │                     │  │                     │               │
│  │ Successful: 1,247   │  │ Active: 142         │               │
│  │ Blocked:      89    │  │ Today: 1,892        │               │
│  │ Failed:      156    │  │ Avg Duration: 12m   │               │
│  │                     │  │ Avg Coherence: 0.78 │               │
│  │ Success Rate: 88.9% │  │                     │               │
│  │                     │  │ [View All →]        │               │
│  │ [View Details →]    │  │                     │               │
│  └─────────────────────┘  └─────────────────────┘               │
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │ PROBLEM PAIRS       │  │ RECENT ALERTS       │               │
│  ├─────────────────────┤  ├─────────────────────┤               │
│  │                     │  │                     │               │
│  │ ⚠ sci_philosophy    │  │ ⚠ High failure rate │               │
│  │   42 failures       │  │   sci_philosophy    │               │
│  │                     │  │   2 min ago         │               │
│  │ ⚠ tech_art          │  │                     │               │
│  │   28 failures       │  │ ℹ Config updated    │               │
│  │                     │  │   finance_politics  │               │
│  │ [Tune Thresholds]   │  │   15 min ago        │               │
│  │                     │  │                     │               │
│  └─────────────────────┘  └─────────────────────┘               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ TRANSFER ACTIVITY (Last 24h)                                 ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │     ▃▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆                         ││
│  │     0h        6h        12h       18h       24h              ││
│  │                                                              ││
│  │  ── Successful   -- Blocked   ·· Threshold Failures         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Alert Center

```
┌─────────────────────────────────────────────────────────────────┐
│  ALERT CENTER                               [Mark All Read]     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 🔴 CRITICAL                                                  ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ No critical alerts                                           ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 🟡 WARNING                                            [2]    ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ ⚠ High failure rate detected                                ││
│  │   Domain pair: science_philosophy                            ││
│  │   Failures: 42 (last hour) | Threshold: 10                   ││
│  │   [View Pair] [Adjust Threshold] [Dismiss]                   ││
│  │                                                   2 min ago  ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │ ⚠ Unusual blocking pattern                                  ││
│  │   Domain pair: tech_art                                      ││
│  │   Block rate: 65% (normally 12%)                             ││
│  │   [Investigate] [Monitor] [Dismiss]                          ││
│  │                                                  18 min ago  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 🔵 INFO                                               [5]    ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ ℹ Configuration updated: finance_politics thresholds        ││
│  │ ℹ New organization created: Acme Corp                       ││
│  │ ℹ Counter reset performed by admin@example.com              ││
│  │ [Show All]                                                   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Cross-Domain Configuration

### 5.1 Global Settings

```
┌─────────────────────────────────────────────────────────────────┐
│  CROSS-DOMAIN LEARNING > GLOBAL SETTINGS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ MASTER SWITCH                                                ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ Cross-Domain Learning:  [●━━━━━━━━━] ENABLED                ││
│  │                                                              ││
│  │ ⚠ Disabling will prevent ALL cross-domain pattern transfer  ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ DEFAULT POLICY                                               ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ When no specific rule exists:                                ││
│  │                                                              ││
│  │ (●) ALLOW      - Permit transfer with default thresholds    ││
│  │ ( ) BLOCK      - Block all unless explicitly allowed        ││
│  │ ( ) MONITOR    - Allow but log all attempts                 ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ DEFAULT THRESHOLDS                                           ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ Structural (10D Similarity):  [━━━━━●━━━━] 0.50             ││
│  │ Min: 0.0                                        Max: 1.0    ││
│  │                                                              ││
│  │ Causal (Chain Overlap):       [━━━●━━━━━━] 0.30             ││
│  │ Min: 0.0                                        Max: 1.0    ││
│  │                                                              ││
│  │ Combined Score:               [━━━━●━━━━━] 0.40             ││
│  │ Min: 0.0                                        Max: 1.0    ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  [Save Changes]                    Last updated: 2025-12-20     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Domain Pairs Manager

```
┌─────────────────────────────────────────────────────────────────┐
│  CROSS-DOMAIN LEARNING > DOMAIN PAIRS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [+ Add Pair]  [Import]  [Export]           🔍 [Search pairs...] │
│                                                                  │
│  Filter: [All ▼] [Blocked ▼] [High Threshold ▼] [Monitored ▼]   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ DOMAIN PAIR          POLICY      THRESHOLDS     STATS       ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ 🚫 fiction ↔ medicine                                        ││
│  │    BLOCKED           -           Blocked: 23                 ││
│  │    "Fictional medical patterns dangerous"                    ││
│  │                                    [Edit] [Unblock] [Stats]  ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │                                                              ││
│  │ 🚫 fiction ↔ finance                                         ││
│  │    BLOCKED           -           Blocked: 15                 ││
│  │    "Fictional financial patterns unreliable"                 ││
│  │                                    [Edit] [Unblock] [Stats]  ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │                                                              ││
│  │ ⚠ finance ↔ politics                                        ││
│  │    REQUIRE_HIGH      S:0.75 C:0.50 M:0.60                   ││
│  │    "Political-financial transfers need high confidence"      ││
│  │    Success: 45 | Failures: 12                                ││
│  │                                    [Edit] [Block] [Stats]    ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │                                                              ││
│  │ ✓ biology ↔ finance                                          ││
│  │    ALLOW             S:0.50 C:0.30 M:0.40                   ││
│  │    "Growth, decay patterns transfer well"                    ││
│  │    Success: 127 | Failures: 8                                ││
│  │                                    [Edit] [Block] [Stats]    ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │                                                              ││
│  │ 👁 science ↔ philosophy                                      ││
│  │    MONITOR           S:0.50 C:0.30 M:0.40                   ││
│  │    "Watching for transfer quality issues"                    ││
│  │    Success: 89 | Failures: 42 ⚠                             ││
│  │                                    [Edit] [Block] [Stats]    ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Showing 1-5 of 12 pairs              [< Prev] [1] [2] [3] [>]  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Add/Edit Domain Pair Modal

```
┌─────────────────────────────────────────────────────────────────┐
│  EDIT DOMAIN PAIR                                      [✕]      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Domain A:  [finance        ▼]                                  │
│  Domain B:  [politics       ▼]                                  │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  Policy:                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ (○) ALLOW         Standard thresholds, full transfer      │  │
│  │ (●) REQUIRE_HIGH  Elevated thresholds (1.5x multiplier)   │  │
│  │ (○) MONITOR       Allow + detailed logging                │  │
│  │ (○) BLOCK         No transfer permitted                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  Custom Thresholds (optional):                                   │
│                                                                  │
│  [✓] Override defaults                                          │
│                                                                  │
│  Structural:  [━━━━━━━━●━] 0.75                                 │
│  Causal:      [━━━━━●━━━━] 0.50                                 │
│  Combined:    [━━━━━━●━━━] 0.60                                 │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  Reason:                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Political-financial transfers need high confidence        │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│                                      [Cancel]  [Save Changes]   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Counters Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  CROSS-DOMAIN LEARNING > COUNTERS & STATISTICS                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Time Range: [Last 24h ▼]  [Last 7d] [Last 30d] [All Time]      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      SUMMARY                                 ││
│  ├──────────────┬──────────────┬──────────────┬────────────────┤│
│  │  SUCCESSFUL  │   BLOCKED    │   FAILED     │  SUCCESS RATE  ││
│  │    1,247     │      89      │     156      │     88.9%      ││
│  │   ↑12.3%     │   ↓5.2%      │   ↑3.1%      │    ↑1.8%       ││
│  └──────────────┴──────────────┴──────────────┴────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ TRANSFER TREND                                               ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │  150│    ╭─╮                                                 ││
│  │     │   ╭╯ ╰╮    ╭─╮         ╭──╮                           ││
│  │  100│  ╭╯   ╰────╯ ╰╮      ╭─╯  ╰─╮                         ││
│  │     │ ╭╯            ╰──────╯      ╰───                      ││
│  │   50│─╯                                                      ││
│  │     │                                                        ││
│  │    0└────────────────────────────────────────────────────   ││
│  │      6h    12h    18h    24h    30h    36h    42h    48h    ││
│  │                                                              ││
│  │  ━━ Successful   ── Blocked   ·· Threshold Failures         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌──────────────────────────────┐ ┌────────────────────────────┐│
│  │ TOP SUCCESSFUL PAIRS         │ │ PROBLEM PAIRS              ││
│  ├──────────────────────────────┤ ├────────────────────────────┤│
│  │ 1. biology_finance    127    │ │ 1. science_philosophy  42  ││
│  │ 2. history_politics    98    │ │ 2. tech_art            28  ││
│  │ 3. physics_engineering 87    │ │ 3. music_math          15  ││
│  │ 4. psych_marketing     76    │ │ 4. literature_science  12  ││
│  │ 5. econ_sociology      65    │ │ 5. art_engineering      9  ││
│  │                              │ │                            ││
│  │ [View All]                   │ │ [Tune Thresholds]          ││
│  └──────────────────────────────┘ └────────────────────────────┘│
│                                                                  │
│  [Reset Counters]                 Last reset: 2025-12-15 08:00  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Session Management

### 6.1 Active Sessions

```
┌─────────────────────────────────────────────────────────────────┐
│  SESSIONS > ACTIVE                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Active Sessions: 142    Avg Duration: 8m 32s    Avg Turns: 4.2 │
│                                                                  │
│  🔍 [Search by session ID, user, org...]                        │
│                                                                  │
│  Filter: [All Orgs ▼] [All Domains ▼] [Coherence: Any ▼]        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ SESSION          USER         ORG       DOMAIN   COH  TURNS ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ abc123...        user_456     Acme      philos.  0.85   5   ││
│  │ Started: 3m ago                                 [View] [End] ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │                                                              ││
│  │ def789...        user_789     Beta      finance  0.72   8   ││
│  │ Started: 12m ago                         ⚠     [View] [End] ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │                                                              ││
│  │ ghi012...        user_123     Acme      tech     0.91   3   ││
│  │ Started: 1m ago                                 [View] [End] ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  [Refresh]              Auto-refresh: [Every 30s ▼]             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Session Detail View

```
┌─────────────────────────────────────────────────────────────────┐
│  SESSION: abc123-def456-789                          [← Back]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ SESSION INFO                                                 ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ User: user_456        Org: Acme Corp                         ││
│  │ Domain: philosophy    Started: 2025-12-20 14:32:15           ││
│  │ Status: ● Active      Duration: 8m 42s                       ││
│  │ Turns: 5              Coherence: 0.85                        ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ COHERENCE TIMELINE                                           ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ 1.0│                                                         ││
│  │    │    ●────●         ●────●                                ││
│  │ 0.8│   /              /                                      ││
│  │    │  ●              ●                                       ││
│  │ 0.6│ /                                                       ││
│  │    │●                                                        ││
│  │ 0.4└─────────────────────────────────────────                ││
│  │     T1    T2    T3    T4    T5                               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ TURN HISTORY                                                 ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ T1 │ "What is consciousness?"                                ││
│  │    │ Coherence: 0.45 │ Badges: [deep]                        ││
│  │────│────────────────────────────────────────────────────────││
│  │ T2 │ "Can machines be conscious?"                            ││
│  │    │ Coherence: 0.72 │ Badges: [coherent, reflective]        ││
│  │────│────────────────────────────────────────────────────────││
│  │ T3 │ "What about qualia?"                                    ││
│  │    │ Coherence: 0.88 │ Badges: [coherent, deep]              ││
│  │                                                              ││
│  │ [Show All Turns]                                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌───────────────────────┐  ┌──────────────────────────────────┐│
│  │ SESSION POLICY        │  │ ACTIONS                          ││
│  ├───────────────────────┤  ├──────────────────────────────────┤│
│  │ Stable: ✓             │  │                                  ││
│  │ Fragmented: ✗         │  │ [View Full Dashboard]            ││
│  │ Needs Grounding: ✗    │  │ [Export Session]                 ││
│  │ Recommended: reflective│  │ [End Session]                    ││
│  └───────────────────────┘  └──────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. User & Org Management

### 7.1 User Preferences

```
┌─────────────────────────────────────────────────────────────────┐
│  USERS > USER PREFERENCES                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🔍 [Search users...]                                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ USER ID      ORG          PREF MODE         LAST ACTIVE     ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ user_456     Acme Corp    domain_relative   2 min ago       ││
│  │                                              [Edit] [View]   ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │                                                              ││
│  │ user_789     Beta Inc     new_possibilities 15 min ago      ││
│  │                                              [Edit] [View]   ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │                                                              ││
│  │ user_123     Acme Corp    recent_memory     1 hour ago      ││
│  │                                              [Edit] [View]   ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Organization Settings

```
┌─────────────────────────────────────────────────────────────────┐
│  ORGANIZATIONS > ACME CORP                           [← Back]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ORGANIZATION INFO                                            ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ Org ID: org_acme_001         Created: 2025-01-15            ││
│  │ Name: Acme Corporation       Users: 42                       ││
│  │ Plan: Enterprise             Active Sessions: 12             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ INTERACTION MODE OVERRIDE                                    ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ [✓] Enable org-level override                                ││
│  │                                                              ││
│  │ Force all users to:                                          ││
│  │                                                              ││
│  │ ( ) recent_memory      - Insights from recent interactions  ││
│  │ (●) domain_relative    - Domain-specific patterns           ││
│  │ ( ) new_possibilities  - Cross-domain discoveries           ││
│  │                                                              ││
│  │ ℹ This overrides individual user preferences                ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ORG USAGE STATS                                              ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ Sessions (30d): 1,247    Avg Coherence: 0.82                ││
│  │ Avg Duration: 12m        Cross-Domain Success: 91%          ││
│  │                                                              ││
│  │ [View Detailed Analytics]                                    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ORG ADMINS                                                   ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ admin@acme.com          Owner         [Remove]               ││
│  │ mgr@acme.com            Admin         [Remove]               ││
│  │                                                              ││
│  │ [+ Add Admin]                                                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│                                              [Save Changes]      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. System Monitoring

### 8.1 Health Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  SYSTEM > HEALTH MONITOR                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    SYSTEM STATUS                             ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │  ● API Server        HEALTHY     Uptime: 14d 6h 32m         ││
│  │  ● Pipeline          HEALTHY     Processing: 23 req/s       ││
│  │  ● Session Store     HEALTHY     Sessions: 142 active       ││
│  │  ● Config Service    HEALTHY     Last reload: 2h ago        ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌──────────────────────────────┐ ┌────────────────────────────┐│
│  │ API LATENCY (p50/p95/p99)    │ │ REQUEST RATE               ││
│  ├──────────────────────────────┤ ├────────────────────────────┤│
│  │                              │ │                            ││
│  │ /dilchat/analyze             │ │  50│    ╭──╮               ││
│  │   45ms / 120ms / 280ms       │ │    │   ╭╯  ╰╮  ╭─╮        ││
│  │                              │ │  25│  ╭╯    ╰──╯ ╰─       ││
│  │ /symbolu/analyze             │ │    │ ╭╯                    ││
│  │   85ms / 210ms / 450ms       │ │   0└────────────────────   ││
│  │                              │ │     1h   2h   3h   4h      ││
│  │ /session/*/analyze           │ │                            ││
│  │   52ms / 140ms / 310ms       │ │ Current: 23 req/s          ││
│  │                              │ │                            ││
│  └──────────────────────────────┘ └────────────────────────────┘│
│                                                                  │
│  ┌──────────────────────────────┐ ┌────────────────────────────┐│
│  │ MEMORY USAGE                 │ │ ERROR RATE                 ││
│  ├──────────────────────────────┤ ├────────────────────────────┤│
│  │                              │ │                            ││
│  │ ████████████░░░░░░  68%      │ │ Last Hour: 0.02%           ││
│  │ 5.4 GB / 8 GB                │ │ Last 24h:  0.03%           ││
│  │                              │ │                            ││
│  │ Sessions: 2.1 GB             │ │ ████░░░░░░ 0.02%           ││
│  │ Cache:    1.8 GB             │ │                            ││
│  │ Other:    1.5 GB             │ │ Threshold: 1.0%            ││
│  │                              │ │                            ││
│  └──────────────────────────────┘ └────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 API Metrics

```
┌─────────────────────────────────────────────────────────────────┐
│  SYSTEM > API METRICS                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Time Range: [Last 1h ▼]  [Last 24h] [Last 7d] [Last 30d]       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ENDPOINT BREAKDOWN                                           ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ Endpoint                  Calls    Avg     Errors   Rate    ││
│  │ ──────────────────────────────────────────────────────────  ││
│  │ POST /dilchat/analyze     8,432    45ms    12       0.14%   ││
│  │ POST /symbolu/analyze     1,245    85ms     3       0.24%   ││
│  │ POST /session/*/analyze   3,892    52ms     8       0.21%   ││
│  │ GET  /session/*/summary     892    23ms     0       0.00%   ││
│  │ GET  /sessions/*/dashboard  234    180ms    2       0.85%   ││
│  │ GET  /health             12,456     5ms     0       0.00%   ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ STATUS CODE DISTRIBUTION                                     ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ 200 ████████████████████████████████████████████  98.2%     ││
│  │ 400 ██                                              1.1%     ││
│  │ 404 ░                                               0.3%     ││
│  │ 500 ░                                               0.2%     ││
│  │ 503 ░                                               0.2%     ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Analytics & Reports

### 9.1 Cross-Domain Report

```
┌─────────────────────────────────────────────────────────────────┐
│  ANALYTICS > CROSS-DOMAIN LEARNING REPORT                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Report Period: [Last 30 days ▼]               [Export PDF]     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ EXECUTIVE SUMMARY                                            ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ • Total cross-domain transfers: 12,847                       ││
│  │ • Overall success rate: 89.2% (up 2.1% from last period)    ││
│  │ • Most active pair: biology ↔ finance (1,247 transfers)     ││
│  │ • Highest failure pair: science ↔ philosophy (42% failures) ││
│  │ • Recommended action: Increase thresholds for sci_phil      ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ DOMAIN PAIR HEATMAP                                          ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │         bio  fin  pol  sci  art  eng  his  psy  med  rel   ││
│  │   bio    -   ███  ██   ██   █    ███  █    ██   ▓▓▓  █     ││
│  │   fin   ███   -   ▓▓▓  ██   █    ██   ██   ███  ███  ▓▓    ││
│  │   pol   ██   ▓▓▓   -   ██   █    █    ███  ██   ███  ▓▓    ││
│  │   sci   ██   ██   ██    -   ██   ███  ██   ██   ███  ▓▓    ││
│  │   art   █    █    █    ██    -   ██   ██   ██   ███  █     ││
│  │   ...                                                        ││
│  │                                                              ││
│  │   ███ High success  ▓▓▓ Require_high  ░░░ Blocked          ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ RECOMMENDATIONS                                              ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ 1. ⚠ science_philosophy: Consider REQUIRE_HIGH policy       ││
│  │    Current failure rate: 42% | Suggested threshold: 0.65    ││
│  │    [Apply Recommendation]                                    ││
│  │                                                              ││
│  │ 2. ✓ biology_finance: Lower thresholds possible              ││
│  │    Success rate: 95% | Current: 0.50, Suggested: 0.40       ││
│  │    [Apply Recommendation]                                    ││
│  │                                                              ││
│  │ 3. 👁 tech_art: Add to MONITOR for further observation       ││
│  │    Inconsistent results | Need more data                     ││
│  │    [Apply Recommendation]                                    ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Coherence Trends

```
┌─────────────────────────────────────────────────────────────────┐
│  ANALYTICS > COHERENCE TRENDS                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Segment: [All Users ▼] [All Orgs ▼] [All Domains ▼]            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ SYSTEM-WIDE COHERENCE                                        ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                              ││
│  │ 1.0│                                                         ││
│  │    │     ╭──────╮        ╭──────────────╮                   ││
│  │ 0.8│ ╭───╯      ╰────────╯              ╰────╮               ││
│  │    │ │                                       │               ││
│  │ 0.6│─╯                                       ╰───            ││
│  │    │                                                         ││
│  │ 0.4│                                                         ││
│  │    └─────────────────────────────────────────────────────   ││
│  │      Week 1    Week 2    Week 3    Week 4                   ││
│  │                                                              ││
│  │ Average: 0.78     Trend: ↑ Improving                         ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌──────────────────────────────┐ ┌────────────────────────────┐│
│  │ BY DOMAIN                    │ │ BY ORGANIZATION            ││
│  ├──────────────────────────────┤ ├────────────────────────────┤│
│  │                              │ │                            ││
│  │ philosophy   0.82 ████████░░│ │ Acme Corp    0.85 █████████░││
│  │ science      0.79 ████████░░│ │ Beta Inc     0.78 ████████░░││
│  │ finance      0.76 ████████░░│ │ Gamma LLC    0.72 ███████░░░││
│  │ technology   0.74 ███████░░░│ │ Delta Co     0.68 ███████░░░││
│  │ arts         0.71 ███████░░░│ │ Epsilon      0.65 ██████░░░░││
│  │                              │ │                            ││
│  └──────────────────────────────┘ └────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. API Integration

### 10.1 Admin API Endpoints (Proposed)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/config` | GET | Get current cross-domain config |
| `/admin/config` | PUT | Update cross-domain config |
| `/admin/config/pairs` | GET | List all domain pairs |
| `/admin/config/pairs` | POST | Add new domain pair |
| `/admin/config/pairs/{key}` | PUT | Update domain pair |
| `/admin/config/pairs/{key}` | DELETE | Remove domain pair |
| `/admin/counters` | GET | Get counter report |
| `/admin/counters/reset` | POST | Reset counters |
| `/admin/sessions` | GET | List sessions (paginated) |
| `/admin/sessions/{id}` | GET | Get session details |
| `/admin/sessions/{id}` | DELETE | End session |
| `/admin/users` | GET | List users |
| `/admin/users/{id}/preferences` | GET/PUT | User preferences |
| `/admin/orgs` | GET | List organizations |
| `/admin/orgs/{id}` | GET/PUT | Org settings |
| `/admin/orgs/{id}/override` | PUT | Set org mode override |
| `/admin/health` | GET | System health status |
| `/admin/metrics` | GET | API metrics |
| `/admin/audit` | GET | Audit log entries |

### 10.2 Admin API Client

```typescript
// api/adminClient.ts

const ADMIN_API = process.env.SYMBOLU_ADMIN_API || 'http://localhost:8000/admin';

export const adminApi = {
  // Cross-Domain Config
  async getConfig(): Promise<CrossDomainConfig> {
    return fetch(`${ADMIN_API}/config`).then(r => r.json());
  },

  async updateConfig(config: Partial<CrossDomainConfig>): Promise<void> {
    await fetch(`${ADMIN_API}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
  },

  async getDomainPairs(): Promise<DomainPairConfig[]> {
    return fetch(`${ADMIN_API}/config/pairs`).then(r => r.json());
  },

  async updateDomainPair(key: string, config: DomainPairConfig): Promise<void> {
    await fetch(`${ADMIN_API}/config/pairs/${key}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
  },

  async blockPair(domainA: string, domainB: string, reason: string): Promise<void> {
    await fetch(`${ADMIN_API}/config/pairs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain_a: domainA,
        domain_b: domainB,
        policy: 'block',
        reason,
      }),
    });
  },

  // Counters
  async getCounters(): Promise<CounterReport> {
    return fetch(`${ADMIN_API}/counters`).then(r => r.json());
  },

  async resetCounters(): Promise<void> {
    await fetch(`${ADMIN_API}/counters/reset`, { method: 'POST' });
  },

  // Sessions
  async getSessions(params: SessionListParams): Promise<PaginatedSessions> {
    const qs = new URLSearchParams(params as any).toString();
    return fetch(`${ADMIN_API}/sessions?${qs}`).then(r => r.json());
  },

  async getSession(id: string): Promise<SessionDetail> {
    return fetch(`${ADMIN_API}/sessions/${id}`).then(r => r.json());
  },

  async endSession(id: string): Promise<void> {
    await fetch(`${ADMIN_API}/sessions/${id}`, { method: 'DELETE' });
  },

  // Organizations
  async getOrgs(): Promise<Organization[]> {
    return fetch(`${ADMIN_API}/orgs`).then(r => r.json());
  },

  async setOrgOverride(orgId: string, mode: string): Promise<void> {
    await fetch(`${ADMIN_API}/orgs/${orgId}/override`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ forced_interaction_mode: mode }),
    });
  },

  // System
  async getHealth(): Promise<HealthStatus> {
    return fetch(`${ADMIN_API}/health`).then(r => r.json());
  },

  async getMetrics(range: string): Promise<APIMetrics> {
    return fetch(`${ADMIN_API}/metrics?range=${range}`).then(r => r.json());
  },

  // Audit
  async getAuditLog(params: AuditLogParams): Promise<AuditLogEntry[]> {
    const qs = new URLSearchParams(params as any).toString();
    return fetch(`${ADMIN_API}/audit?${qs}`).then(r => r.json());
  },
};
```

### 10.3 Type Definitions

```typescript
// types/admin.ts

interface CrossDomainConfig {
  enabled: boolean;
  default_policy: 'allow' | 'block' | 'monitor';
  default_structural_threshold: number;
  default_causal_threshold: number;
  default_combined_threshold: number;
  domain_pairs: Record<string, DomainPairConfig>;
  blocked_pairs: string[];
  counters: CounterData;
  version: string;
  last_updated: string;
}

interface DomainPairConfig {
  domain_a: string;
  domain_b: string;
  policy: 'allow' | 'block' | 'require_high' | 'monitor';
  min_structural_threshold?: number;
  min_causal_threshold?: number;
  min_combined_threshold?: number;
  reason: string;
  created_at: string;
  updated_at: string;
}

interface CounterReport {
  summary: {
    total_successful: number;
    total_blocked: number;
    total_threshold_failures: number;
    success_rate: number;
  };
  problem_pairs: Array<[string, number]>;
  top_successful: Array<[string, number]>;
  top_blocked: Array<[string, number]>;
  last_reset: string;
}

interface SessionDetail {
  session_id: string;
  user_id: string;
  org_id: string;
  domain: string;
  created_at: string;
  turns: TurnData[];
  coherence_trend: number[];
  session_policy: SessionPolicy;
}

interface HealthStatus {
  api: 'healthy' | 'degraded' | 'unhealthy';
  pipeline: 'healthy' | 'degraded' | 'unhealthy';
  session_store: 'healthy' | 'degraded' | 'unhealthy';
  uptime_seconds: number;
  active_sessions: number;
}

interface AuditLogEntry {
  timestamp: string;
  actor: string;
  action: string;
  resource: string;
  details: Record<string, any>;
  ip_address: string;
}
```

---

## 11. Implementation Phases

### Phase 1: Core Admin (MVP)
- [ ] Login/authentication
- [ ] System overview dashboard
- [ ] Cross-domain global settings
- [ ] Domain pairs list view

### Phase 2: Cross-Domain Management
- [ ] Add/edit domain pair modal
- [ ] Block/unblock pairs
- [ ] Threshold configuration
- [ ] Counter dashboard

### Phase 3: Session Management
- [ ] Active sessions list
- [ ] Session detail view
- [ ] Session search
- [ ] End session action

### Phase 4: User/Org Management
- [ ] User list and preferences
- [ ] Organization settings
- [ ] Org mode overrides
- [ ] Admin role management

### Phase 5: System Monitoring
- [ ] Health dashboard
- [ ] API metrics
- [ ] Error tracking
- [ ] Performance charts

### Phase 6: Analytics & Audit
- [ ] Cross-domain reports
- [ ] Coherence trends
- [ ] Audit log viewer
- [ ] Export functionality

---

*Document Version: 0.1 (Preliminary)*
*Last Updated: December 2025*
*Status: Draft for Review*
