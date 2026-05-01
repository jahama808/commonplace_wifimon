# Handoff: Common Area Monitor Redesign

## Overview

This handoff packages a **redesigned dashboard UI** for the WiFi Common Area Monitor — the network-operations app that watches eero networks across Hawaiian-island properties — together with the engineering specification for the rebuild on a modern stack.

The design is the **"Atrium"** direction: a calmer, hospitality-forward Network Operations Center aesthetic with a warm dark palette, large island map hero, per-island summary tiles, time-series charts, a 24-hour heatmap, a property table with a slide-in detail drawer, and a live alerts feed. It is intended to replace the current Django/Chart.js server-rendered dashboard described in `SPEC.md`.

This bundle contains:
- A working HTML/React design prototype (the source of truth for visuals and interactions)
- The full rebuild specification (`SPEC.md`)
- Reference screenshots
- An alternate earlier exploration (kept for context)

---

## About the Design Files

The files in `design/` are **design references created in HTML** — a high-fidelity React + inline-CSS prototype showing intended look, layout, motion, and behavior. They are **NOT production code to copy directly**.

Your task is to **recreate this design in the target codebase's environment** using its established patterns and libraries. The target stack from `SPEC.md` is:

- **Frontend:** Next.js 15+ (App Router) + TypeScript + Tailwind CSS + shadcn/ui (Radix primitives) + TanStack Query + Recharts (or ECharts) + react-hook-form + zod
- **Backend:** FastAPI + Pydantic + SQLAlchemy 2.x + PostgreSQL + APScheduler worker
- **Charts:** Recharts (default) or ECharts (richer)

When implementing: lift the **design tokens, layout structure, and interaction patterns** from the prototype, but build the actual components using shadcn/ui primitives, Tailwind utility classes, and Recharts — not the prototype's hand-rolled CSS.

---

## Fidelity

**High-fidelity (hifi).** All colors (in OKLCH), spacing, typography scales, radii, shadows, motion timings, and component states are final and intentional. Reproduce them pixel-accurately.

The prototype was designed at **1440px wide**. Recreate it as a fluid responsive layout that:
- Renders the full multi-column composition at ≥ 1280px
- Collapses gracefully through tablet breakpoints
- Becomes a single-column stack at ≤ 768px (the spec calls out that the current app is broken < 1200px — this is a known regression to fix)

---

## How to Open the Design

1. Open `design/Common Area Monitor.html` in a modern browser (Chrome/Safari/Firefox).
2. The page loads as a `design-canvas` with a single artboard containing the **Atrium** dashboard.
3. **Tweaks panel** (bottom-right, click "Tweaks" toggle): live-edit accent color, density (compact/comfortable), theme (dark/light), and glow intensity. Use these to understand the design's range — ship the **dark** theme and **comfortable** density as defaults (per spec §8.2).

The HTML file is a Babel-transpiled React prototype assembled from these source modules in `design/`:

| File | Purpose |
|---|---|
| `Common Area Monitor.html` | Entry point — loads React 18, Babel, and the JSX modules below. |
| `styles.css` | **Design tokens** (OKLCH colors, radii, spacing, motion). Read this first. |
| `data.jsx` | Mock dataset — properties, islands, networks, time-series, alerts. Mirrors the API shapes the real backend should return. |
| `design-canvas.jsx` | Pan/zoom artboard wrapper used to host design variations. **Not part of the production UI** — drop it in the rebuild. |
| `variation-atrium.jsx` | The Atrium composition (header, hero, summary tiles, table, charts, drawer, alerts feed). **This is the design to ship.** |
| `atrium.jsx` | Atrium-specific subcomponents (sparkline, mini chart helpers). |
| `variation-ops.jsx` | Earlier "Operations Center" variation. **Not shipped** — kept as reference for components like the live ticker, status grid, and alert table styling that the team may want to lift back in. |
| `tweaks-panel.jsx` | Live design-tweak control panel. **Not part of the production UI.** |

The `design/_alternate_v1_canvas/` folder contains an earlier multi-variation comparison file. You can ignore it; it's preserved for context only.

---

## Screens / Views

The prototype focuses on **one screen** — the **Overview Dashboard** — but it implements all of the regions the spec assigns to that page (§5.4) plus elements the spec assigns to Property Detail (§5.5). Treat the prototype as a richer rethink of the dashboard that absorbs property-level summary into a slide-in drawer.

### 1. Overview Dashboard

**Purpose.** At-a-glance network health across every Hawaiian-island property. Operator can spot outages, drill into a property, filter by island, scan recent alerts, and jump to detail views.

**Top-level layout (1440px design width, ~32px outer page padding):**

```
┌────────────────────────────────────────────────────────────────────────┐
│ Sticky Header (height ~78px)                                           │
│  [◈ Logo] Atrium / Network              Nav  [Search ⌘K]  [Island ▾] [JG]│
│            COMMON AREA MONITOR · HST                                   │
├────────────────────────────────────────────────────────────────────────┤
│ Live Alerts Ticker (height 36px, scrolling marquee, red gradient ends) │
├────────────────────────────────────────────────────────────────────────┤
│ Greeting block: "Good morning, John" + subhead              [Export] [+ New Alert Rule]
├────────────────────────────────────────────────────────────────────────┤
│ 4-column Island Summary Tiles (Oahu · Maui · Big Island · Kauai)       │
│  Each tile: properties count · nets · devices · offline count · status pulse
├────────────────────────────────────────────────────────────────────────┤
│ Hero Card — Hawaiian-Islands map                                       │
│  Header: "15 properties · 39 networks · 724 devices online"            │
│  Right side: status pill badges (1 OUTAGE · 1 DEGRADED · 13 ONLINE)    │
│  Body: stylized island silhouettes with property pins (status-colored) │
├────────────────────────────────────────────────────────────────────────┤
│ ──── 2-column grid below ────                                          │
│ ┌─────────────────────────────────┬──────────────────────────────────┐ │
│ │ Property table                  │ Connected Devices Over Time      │ │
│ │ rows: status · name · island ·  │ stacked area chart, gradient fill│ │
│ │   networks · devices · 24h spark│ time-window chips: 24h / 7d / 30d│ │
│ │   click row → detail drawer     │                                  │ │
│ ├─────────────────────────────────┼──────────────────────────────────┤ │
│ │ 24-hour Activity Heatmap        │ Live Alerts Feed                 │ │
│ │  7×24 grid (day×hour)           │ scrollable list of alerts        │ │
│ │  color = device count           │ severity dot, time, message      │ │
│ │  Peak / Quiet hours legend      │                                  │ │
│ └─────────────────────────────────┴──────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘

Slide-in Drawer (right edge, 480px wide, on row/pin click):
  Property name + close
  Stat row: networks · devices · uptime
  Connected-Devices-Over-Time mini chart (24h)
  Networks list (status, name, network_id mono, latest count)
  Devices list with RSSI bars
```

**Components (with exact values):**

#### Header
- Height: ~78px. Sticky at scroll.
- Background: `linear-gradient(180deg, oklch(0.22 0.018 80), oklch(0.18 0.012 60))` with bottom `1px` border `var(--line)`.
- Logo: 38×38 rounded 12px, `linear-gradient(135deg, var(--gold), var(--accent))`, glyph "◈" in `var(--bg-0)` 18px bold, with `box-shadow: 0 0 20px oklch(0.80 0.12 85 / 0.35)`.
- Wordmark: "Atrium" 18px / 600 / -0.01em tracking; "Network" same line at `var(--text-3)` 400.
- Eyebrow: "COMMON AREA MONITOR · HST 08:56:20" — mono 11px, `var(--text-3)`, `letter-spacing: 0.12em`.
- Nav items: 13px, 500 weight, `var(--text-2)`. Active item: `var(--text-0)`, 600, with a 2px underline `linear-gradient(90deg, var(--gold), var(--accent))` glowing.
- Search: pill input, 360px wide, `var(--bg-1)` background, `1px solid var(--line)`, 36px height, mono `⌘K` chip on the right.
- Island filter: outline pill select, 999px radius, `1px solid var(--line-strong)`, padding `6px 14px`, 12px font.
- Avatar: 30×30 round, accent→gold gradient, initials "JG" 11px / 700 in `var(--bg-0)`.

#### Live Alerts Ticker
- 36px tall, full bleed, scrolling marquee (60s linear infinite).
- Background gradient: `linear-gradient(90deg, oklch(0.68 0.21 25 / 0.18) 0%, var(--bg-1) 30%, var(--bg-1) 70%, oklch(0.68 0.21 25 / 0.18) 100%)`.
- Top + bottom borders `1px solid oklch(0.68 0.21 25 / 0.30)` (red-tinted).
- "LIVE" pill on the left: mono 10px / 700, `letter-spacing: 0.15em`, `color: var(--bad)`, on `var(--bg-0)` background, with a right divider.
- Each item: timestamp (mono, `var(--text-2)`) · severity tag (CRITICAL/WARNING/INFO color-coded) · property · message · separator dot.

#### Greeting / Hero Text
- "Good morning, {name}" — 36px / 600, `var(--text-0)`, tracking `-0.02em`.
- Subhead — 14px, `var(--text-2)`, e.g. "Tuesday, April 28, 2026 · One outage needs attention".
- Right-aligned actions: secondary "Export" button (ghost, `1px solid var(--line-strong)`) + primary "+ New Alert Rule" button (gold→accent gradient, `var(--bg-0)` text).

#### Island Summary Tiles (4-up grid, gap 16px)
- Each tile: 200px tall, `var(--bg-1)` background, `1px solid var(--line)`, `border-radius: var(--radius-l)` (18px), padding 18px.
- Eyebrow: island name, mono 10.5px / 700, tracking 0.12em, `var(--text-3)`.
- Headline: count + "properties" — 32px / 600 number, `var(--text-0)`; label 13px `var(--text-2)`.
- Footer row: "X nets · Y devices" + offline count chip if any.
- Pulse dot in the top-right corner — green (`--ok`) if all online, red (`--bad`) if any offline.
- Hover/selected: background → `var(--bg-2)`, border → `var(--accent-line)`.
- Click to filter the page to that island (toggle).

#### Map Hero Card
- `var(--bg-1)` card, 18px radius, `1px solid var(--line)`. Padded 24px.
- Header row: eyebrow "HAWAIIAN ISLANDS · LIVE" mono, headline "15 properties · 39 networks", subhead "724 devices online · 14ms avg latency".
- Right: stack of status pills (`badge-glow.bad` for outages, `.warn` for degraded, `.ok` for online), each pulsing if `.bad`.
- Body: SVG of stylized island silhouettes, `var(--bg-2)` fills, soft `var(--line-strong)` strokes. Property pins are 8–12px circles colored by network status with `box-shadow` glow scaled by `--glow`. Pins are clickable → opens drawer.

#### Connected Devices Over Time Chart (⭐ critical feature, see SPEC §3)
- Stacked area chart, gradient fills (each common area = one stacked layer).
- Axes: x = sample timestamp, y = device count. Light gridlines `var(--line)` at 0.5 alpha.
- Tooltip: dark card `var(--bg-2)`, `1px solid var(--line-strong)`, shows timestamp, per-network breakdown, and total at bottom.
- Time-window chip group: `[24h] [7d] [30d]` — selected chip filled `var(--accent-soft)` with `var(--accent)` text + border.
- Empty state: centered message "No samples in window" `var(--text-3)`.
- **The same dataset must drive a per-SSID variant** (filtered by SSID dropdown). The prototype shows the totals view; the SSID-filtered view is identical visually but with one stack per network filtered to a specific SSID. SPEC §3.2 has the contract.

#### 24-hour Activity Heatmap
- 7 rows × 24 columns grid (day × hour). Cell 14×14, gap 2px.
- Cell color: linear ramp from `var(--bg-2)` (zero) to `var(--accent)` (max), darker = lower.
- Hover: cell scales 1.15, tooltip shows day/hour/count.
- Legend at bottom: peak hour callout + quiet hour callout. E.g. "Peak: 18:00 · 487 devices" and "Quiet: 04:00 · 28 devices".

#### Property Table
- Headers: small caps, mono, 10.5px, `var(--text-3)`.
- Rows: 56px tall, hover `var(--bg-2)`, click → detail drawer slides in.
- Status cell: pulse dot (ok/warn/bad).
- Name cell: 14px / 500.
- Island cell: small chip with island name.
- Networks cell: count + mono `network_id` truncated.
- Devices cell: count + 24h sparkline (120px wide × 36px high, accent gradient under polyline).
- "View" affordance on the right (chevron icon).

#### Live Alerts Feed
- List of alert rows, scrollable.
- Each row: severity dot (color), time (mono, `var(--text-2)`), property (semibold), message.
- "Acknowledged" rows fade to 60% opacity.
- "Mark all read" link at the top.

#### Property Detail Drawer (slide-in from right)
- 480px wide, full height, `var(--bg-1)` background, `1px solid var(--line)` left border.
- Slides in with `transform: translateX(0)` + `opacity: 1`, transition `220ms cubic-bezier(.2,.7,.2,1)`. Backdrop fades in `var(--bg-0)` at 50% opacity.
- Header: property name 22px / 600, close button (`✕`) top-right.
- Stat row: 3 stat blocks — Networks · Devices · Uptime — each with mono number 22px and label 11px tracking 0.1em.
- Mini chart: 24-hour Connected Devices Over Time (smaller stacked area).
- Networks list: rows with status dot + name + mono network_id + latest count badge (`badge-glow.accent`).
- Devices list: rows with device name, MAC mono, RSSI bar (5-segment, colored by signal strength).
- Footer: secondary actions ("Open property page →", "Force check now") + primary "Generate Report".

---

## Interactions & Behavior

- **Sticky header** at scroll. Background gains a subtle backdrop-blur once user scrolls past the greeting.
- **Island summary tiles** are toggle filters. Clicking a tile sets `?island=<island>` in the URL and filters the property table, map pins, and charts. Click the active tile again to clear.
- **Map pins** are hoverable (tooltip with property name + status) and clickable (opens detail drawer).
- **Property rows** are clickable — entire row is the hit target. Opens the drawer (`?property=<id>` in URL).
- **Drawer** closes on `Esc`, on backdrop click, on close button, or when navigating to a different property.
- **Time-window chips** on the chart update the chart in place. URL param `?days=24h|7d|30d`.
- **Search bar** focuses on `/`. `⌘K` (or `Ctrl+K`) opens command-palette mode (omnibox over the page). Search across properties, common areas, and `network_id`.
- **Theme toggle** lives in the user menu (the prototype's Tweaks panel exposes it; production should put it under the avatar dropdown). Persist to `localStorage` and `prefers-color-scheme` media query.
- **Reduced motion**: when `prefers-reduced-motion: reduce`, disable the ticker scroll, the badge pulse, and the pulse-dot ping. Replace with static state.
- **Realtime**: SSE-driven updates from `GET /api/v1/dashboard/stream`. New ticker items prepend with a fade-in. Status changes flip pulse-dot colors with a 200ms cross-fade. Last-updated indicator in the header reads "Updated · {n}s ago".
- **Loading states**: every async card shows a skeleton (`var(--bg-2)` shimmer block at the right shape), not a spinner. No "blank-then-pop".
- **Empty states**: explicit copy + CTA, never a void. Examples: "No alerts in the last 24h — you're good." / "No devices on this SSID in the selected window."
- **Hover states**: cards get a 1px brighter border (`var(--line-strong)`) and a subtle lift `translateY(-1px)`; rows get `background: var(--bg-2)`.
- **Focus states**: 2px outline `var(--accent)` with 2px offset on every interactive element. Don't rely on `:hover` alone.

---

## State Management

Use **TanStack Query** for all backend data (per SPEC §8.1). Keys and cadences:

| Query | Key | Stale time | Trigger |
|---|---|---|---|
| Dashboard payload | `['dashboard', { island }]` | 30s | Mount + island filter change + SSE invalidation |
| Property detail (drawer) | `['property', id]` | 60s | Drawer open |
| Device counts (chart) | `['property', id, 'device-counts', { days, ssid }]` | 60s | Chart open / chip change |
| SSID list | `['property', id, 'ssids']` | 5min | Drawer open |
| Alerts feed | `['alerts', { since }]` | 30s | Mount + SSE invalidation |

URL state (use Next.js `searchParams`):
- `?island=<oahu|maui|...>` — active island filter
- `?property=<id>` — drawer open for property
- `?days=24h|7d|30d` — chart window
- `?ssid=<name>` — chart SSID filter
- `?theme=dark|light` — theme override

Local UI state (React `useState`):
- Drawer open/closed (also reflected in URL above)
- Search palette open/closed
- Tooltip targets

---

## Design Tokens

Read `design/styles.css` for the canonical source. Key values reproduced here:

### Colors (OKLCH)

```css
/* Surfaces — warm dark hospitality-tech palette */
--bg-0: oklch(0.16 0.012 60);     /* page background, warm near-black */
--bg-1: oklch(0.20 0.012 60);     /* card surface */
--bg-2: oklch(0.24 0.012 60);     /* raised surface / hover */
--bg-3: oklch(0.28 0.012 60);     /* selected */
--line: oklch(0.32 0.012 60 / 0.5);
--line-strong: oklch(0.40 0.012 60 / 0.7);

/* Text */
--text-0: oklch(0.97 0.005 60);   /* primary */
--text-1: oklch(0.82 0.008 60);   /* secondary */
--text-2: oklch(0.62 0.012 60);   /* tertiary */
--text-3: oklch(0.45 0.015 60);   /* eyebrow / labels */

/* Accents */
--accent: oklch(0.78 0.13 195);   /* cyan-teal — primary accent */
--accent-soft: oklch(0.78 0.13 195 / 0.16);
--accent-line: oklch(0.78 0.13 195 / 0.35);
--gold: oklch(0.80 0.12 85);      /* warm gold secondary */
--gold-soft: oklch(0.80 0.12 85 / 0.15);

/* Status (semantic — match WCAG AA in both themes) */
--ok:   oklch(0.78 0.16 152);     /* green */
--warn: oklch(0.82 0.14 75);      /* amber */
--bad:  oklch(0.68 0.21 25);      /* coral-red */
--bad-soft: oklch(0.68 0.21 25 / 0.18);
```

Light theme overrides (see `[data-theme="light"]` in `styles.css`):

```css
--bg-0: oklch(0.97 0.008 80);
--bg-1: oklch(0.99 0.005 80);
--bg-2: oklch(0.95 0.008 80);
--bg-3: oklch(0.92 0.010 80);
--line: oklch(0.85 0.010 80 / 0.6);
--line-strong: oklch(0.75 0.012 80 / 0.7);
--text-0: oklch(0.18 0.012 60);
--text-1: oklch(0.32 0.012 60);
--text-2: oklch(0.48 0.012 60);
--text-3: oklch(0.62 0.015 60);
```

Status colors do **not** invert between themes — keep the same hues for green/amber/red so operators trained on them don't have to re-learn.

### Chart Series Palette (color-blind-safe — use Okabe-Ito-derived for stacks)

Use this in Recharts/ECharts for the stacked-area and stacked-bar device charts so SPEC §8.2's color-blind-safe rule holds:

```js
const seriesPalette = [
  'oklch(0.78 0.13 195)',  // teal       (matches --accent)
  'oklch(0.80 0.12 85)',   // gold       (matches --gold)
  'oklch(0.72 0.18 285)',  // violet
  'oklch(0.70 0.15 35)',   // orange
  'oklch(0.78 0.16 152)',  // green
  'oklch(0.74 0.14 245)',  // blue
  'oklch(0.66 0.20 0)',    // rose
  'oklch(0.78 0.10 110)',  // olive
];
```

Cycle through this palette deterministically by `network_id` — same network always gets the same color across the dashboard, drawer, and PDF.

### Spacing

The prototype uses a 4px base. The shadcn/Tailwind defaults match well — use them as-is. Common gaps: `gap-2` (8px), `gap-3` (12px), `gap-4` (16px). Card outer padding: 18–24px.

### Typography

```
font-ui:   'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif
font-mono: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace
```

Use mono for: `network_id`, `wan_ip`, MAC addresses, firmware versions, timestamps, eyebrows, status pills.

Type scale (px):

| Token | Size | Weight | Tracking | Use |
|---|---|---|---|---|
| `display` | 36 | 600 | -0.02em | Page greeting ("Good morning, John") |
| `h1` | 28 | 600 | -0.015em | Card hero numbers ("15 properties · 39 networks") |
| `h2` | 22 | 600 | -0.01em | Drawer header, stat block numbers |
| `h3` | 18 | 600 | -0.01em | Wordmark |
| `card-title` | 13 | 600 | 0.02em | `.card-hd h3` |
| `body` | 14 | 400/500 | 0 | Default body, table cells |
| `nav` | 13 | 500/600 | 0 | Header nav |
| `caption` | 12 | 400 | 0 | Tooltip body, secondary copy |
| `eyebrow` | 10.5 | 700 | 0.12em UPPER | Card eyebrows, ticker LIVE pill, severity tags |
| `label` | 11 | 400 | 0.04em UPPER | Section labels |

Numerics in stats and tables use `font-feature-settings: 'tnum'` so digits align in columns.

### Radii

```
--radius-s: 8px;    /* chips, small badges */
--radius-m: 12px;   /* buttons, search input */
--radius-l: 18px;   /* cards, drawer */
                    /* 999px for pills */
```

### Shadows / Glow

The design uses a `--glow` multiplier (0–1.5) on status indicators rather than blanket drop-shadows on cards. Cards have **no** drop-shadow — only a 1px border + subtle gradient.

Glow patterns (see `styles.css`):

```css
/* Pulse dot — colored ping animation */
.pulse-dot.bad {
  background: var(--bad);
  box-shadow: 0 0 calc(8px * var(--glow)) var(--bad);
}

/* Critical badge — outer + inner glow with pulse */
.badge-glow.bad {
  box-shadow:
    0 0 calc(12px * var(--glow)) oklch(0.68 0.21 25 / calc(0.45 * var(--glow))),
    inset 0 0 calc(8px * var(--glow)) oklch(0.68 0.21 25 / calc(0.15 * var(--glow)));
  animation: badgePulse 2.4s ease-in-out infinite;
}
```

Default `--glow: 1`. When `prefers-reduced-motion: reduce`, set `--glow: 0` and disable the pulse animations.

### Motion

| Animation | Timing | Easing |
|---|---|---|
| Drawer slide-in | 220ms | `cubic-bezier(.2, .7, .2, 1)` |
| Hover state (background, border, transform) | 140ms | `ease-out` |
| Pulse dot ping | 2s | `ease-out` infinite |
| Badge pulse (critical) | 2.4s | `ease-in-out` infinite |
| Ticker scroll | 60s | `linear` infinite |
| Chart re-render (data change) | 320ms | `ease-in-out` |

All animations gated on `prefers-reduced-motion: no-preference`.

---

## Backend Contract (the chart that must not break)

⭐ This is the part of the spec where wrong implementations have historically caused production support tickets. Implement it carefully.

`GET /api/v1/properties/{id}/device-counts?days=1|7|30&ssid=<optional>`

Response shape, ready to render in Recharts/ECharts as a stacked area:

```json
{
  "timestamps": ["2026-04-28T06:00:00-10:00", "..."],
  "series": [
    {
      "network_id": "6422927",
      "network_name": "Lobby",
      "color": "oklch(0.78 0.13 195)",
      "data": [12, 14, 17, ...]
    },
    ...
  ],
  "ssid": null  // or the filter value if provided
}
```

Behavior:
- If `?ssid` omitted → totals (the canonical `ssid=""` "total" rows from `connected_device_count`).
- If `?ssid=<name>` → the per-SSID filtered series.
- The **same sample timestamps** drive both views (SPEC §3.4).
- `color` is server-assigned and stable per `network_id` so the dashboard, the drawer, and the PDF always agree.

Frontend uses this payload **as-is** for both charts (totals + SSID-filtered) on the Property Detail page, the dashboard hero chart, and the drawer mini chart.

---

## Components & Patterns

When recreating in shadcn/ui + Tailwind, the mapping is:

| Prototype | shadcn primitive |
|---|---|
| Card | `Card` + custom radius/border via Tailwind `rounded-[18px] border-line` |
| Drawer | `Sheet` (side="right", w-[480px]) |
| Search palette | `Command` (cmdk) |
| Island filter pill select | `Select` styled as pill, or custom Radix `Toggle` group |
| Time-window chips | `ToggleGroup` |
| Tooltip | `Tooltip` |
| Pulse dot | Custom — see `styles.css` `.pulse-dot` |
| Glow badge | Custom — see `styles.css` `.badge-glow` |
| Sparkline / area / bar charts | `Recharts` `<AreaChart>`, `<BarChart>` with custom `<Tooltip>` |
| Heatmap | Custom — Recharts has no heatmap; use a CSS Grid of cells, or ECharts if going that route |
| Toast (alert acknowledged etc.) | `Sonner` |

Define the design tokens in `tailwind.config.ts` under `theme.extend.colors` using CSS custom properties so dark/light theming works via `data-theme`:

```ts
colors: {
  bg: { 0: 'var(--bg-0)', 1: 'var(--bg-1)', 2: 'var(--bg-2)', 3: 'var(--bg-3)' },
  text: { 0: 'var(--text-0)', 1: 'var(--text-1)', 2: 'var(--text-2)', 3: 'var(--text-3)' },
  line: { DEFAULT: 'var(--line)', strong: 'var(--line-strong)' },
  accent: { DEFAULT: 'var(--accent)', soft: 'var(--accent-soft)' },
  gold: 'var(--gold)',
  ok: 'var(--ok)',
  warn: 'var(--warn)',
  bad: 'var(--bad)',
}
```

Then declare both palettes in a global stylesheet under `:root` and `[data-theme="light"]` exactly as in `design/styles.css`.

---

## Assets

The prototype uses **no external assets** — no logos, no icons. All visual marks are inline SVG (the ◈ glyph in the logo is a unicode character; the island silhouettes are hand-drawn SVG paths in `variation-atrium.jsx`).

For the production rebuild:
- Use `lucide-react` for all line icons (Search, Bell, ChevronRight, Wifi, MoreHorizontal, etc.) — it pairs cleanly with shadcn/ui.
- The Atrium wordmark glyph (◈) can stay unicode, or be replaced with a real brand mark when the team produces one.
- The Hawaiian-island map SVG paths live inline in `variation-atrium.jsx` — extract them into a single `<HawaiianIslandsMap />` component on the rebuild.

No image assets need importing. No fonts need self-hosting beyond `Inter` and `JetBrains Mono` — both available via `next/font/google` or `@fontsource`.

---

## Files in this Bundle

```
design_handoff_common_area_monitor_redesign/
├── README.md                                  ← you are here
├── SPEC.md                                    ← full rebuild specification
├── design/
│   ├── Common Area Monitor.html               ← entry point, open in browser
│   ├── styles.css                             ← design tokens (read first)
│   ├── data.jsx                               ← mock dataset + API shapes
│   ├── design-canvas.jsx                      ← prototype host (don't ship)
│   ├── variation-atrium.jsx                   ← THE design to ship
│   ├── atrium.jsx                             ← Atrium subcomponents
│   ├── variation-ops.jsx                      ← alternate exploration (reference)
│   ├── tweaks-panel.jsx                       ← live-tweak panel (don't ship)
│   └── _alternate_v1_canvas/
│       └── Common Area Monitor v1 (canvas).html  ← earlier multi-variation comparison
└── screenshots/
    ├── 01-dashboard-overview.png              ← top of page
    ├── 02-property-drawer.png                 ← attempted drawer state (drawer didn't open in capture; reference 01 for layout)
    ├── 03-properties-and-charts.png           ← scrolled to property table + chart
    ├── 04-charts-and-heatmap.png              ← chart + heatmap row
    └── 05-bottom-sections.png                 ← bottom sections
```

---

## Reading Order for the Implementing Engineer

1. **`SPEC.md`** — top to bottom. This is the contract for the rebuild.
2. **`design/styles.css`** — the design tokens.
3. **Open `design/Common Area Monitor.html` in a browser**, toggle the Tweaks panel, see the design move.
4. **`design/variation-atrium.jsx`** — the actual layout and component composition.
5. **`design/data.jsx`** — the data shapes the components expect; align the FastAPI response models to match.
6. **Screenshots** — reference for sections you can't pin down from the live page.

When you start implementing, build in this order:

1. **Design tokens** in `tailwind.config.ts` + `app/globals.css`. Verify dark and light both look right with a stub `<Card>` and `<Button>`.
2. **Layout shell** (header, ticker, sticky behavior, page grid).
3. **Backend `GET /api/v1/dashboard`** + the SSE stream — get realtime working before charting.
4. **Charts** (Recharts area chart, then heatmap, then sparklines). Use the stable color-by-`network_id` rule from day one.
5. **Property detail drawer** (Sheet). Wire the URL param.
6. **Island filter tiles** with URL state.
7. **Search palette** (Command + global search endpoint).
8. **Empty / loading / error states** for every async region.
9. **Reduced-motion + light-theme audit.**
10. **Mobile breakpoints** (the spec calls this out explicitly — single-column at ≤ 768px).

---

## Notes on Scope

The prototype designs the **dashboard**. The other pages from SPEC §5.5–§5.6 (Property Detail, Common-Area Detail, Reports modal, Admin onboarding) are **not yet designed**. Recreate the dashboard first, then come back for those — applying the same tokens, components, and patterns.

When you do design those pages: lift the Atrium card chrome (radius, border, header treatment), the chart styling (gradient fills, tooltip, color-by-network rule), the table style (56px rows, hover, mono identifiers), and the drawer pattern. Don't invent new visual language for them.
