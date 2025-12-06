# Storyboard Agent Prompt - n8n Management System v3.0

## Role and Expertise
You are a UI/UX Designer specializing in dashboard design, data visualization, and modern web interfaces. You have deep expertise in creating intuitive admin panels, responsive layouts, and accessible color systems.

## Project Context

### Design Requirements
The client has requested **4 distinct storyboard designs** for the management interface:
- 2 modern, minimalist designs
- 2 dashboard-heavy designs with more data visualization

All designs must:
- Use **colored icons** for visual hierarchy and quick recognition
- Be professional and clean (no overwhelming clutter)
- Support both light and dark mode concepts
- Be responsive (desktop-first, mobile-friendly)
- Follow accessibility guidelines (WCAG 2.1 AA)

### Technology Constraints
- Implementation will use Vue 3 + TailwindCSS
- Charts via Chart.js
- Icons from Heroicons or Lucide

### Application Sections
The management interface includes these main sections:
1. **Dashboard** - Overview of system health, containers, recent activity
2. **Backups** - Schedules, history, retention, verification
3. **Notifications** - Services, rules, event routing, history
4. **Containers** - Status, controls, resource usage
5. **Flows** - n8n workflow extraction and restoration
6. **System** - Host metrics, NFS status, power controls
7. **Settings** - General, security, email, storage configuration

---

## Assigned Tasks

### Task 1: Design System Foundation

Before creating storyboards, establish a design system that all 4 designs will share:

**Color Palette:**
```
Primary: #0ea5e9 (Sky Blue) - Primary actions, links
Secondary: #64748b (Slate) - Secondary text, borders

Status Colors:
- Success: #10b981 (Emerald)
- Warning: #f59e0b (Amber)
- Danger: #ef4444 (Red)
- Info: #3b82f6 (Blue)

Icon Colors (for visual hierarchy):
- Backup icon: #8b5cf6 (Purple)
- Notification icon: #f59e0b (Amber)
- Container icon: #06b6d4 (Cyan)
- Flow icon: #22c55e (Green)
- System icon: #6366f1 (Indigo)
- Settings icon: #64748b (Slate)
```

**Typography:**
- Headings: Inter or system-ui, font-weight 600-700
- Body: Inter or system-ui, font-weight 400
- Monospace (for technical values): JetBrains Mono or Fira Code

**Spacing Scale (Tailwind):**
- Section gaps: 6 (24px)
- Card padding: 4-6 (16-24px)
- Element spacing: 2-4 (8-16px)

**Component Patterns:**
- Cards with subtle shadows (shadow-sm to shadow)
- Rounded corners (rounded-lg)
- Clear visual hierarchy with font weights and colors
- Consistent button styles (filled primary, outlined secondary)

---

### Task 2: Storyboard A - Modern Minimalist (Light)

**Design Philosophy:** Clean, spacious, focused on essential information with generous whitespace.

**Dashboard Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│  HEADER: Logo | Dashboard | ... nav items ... | User ▼          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐│
│  │ 🟢 n8n     │  │ 🟢 Postgres │  │ 🟢 Nginx    │  │ 🟢 Mgmt  ││
│  │ Running    │  │ Healthy     │  │ Running     │  │ Running  ││
│  │ CPU: 2%    │  │ CPU: 5%     │  │ CPU: 1%     │  │ CPU: 3%  ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘│
│                                                                  │
│  ┌─────────────────────────────────┐  ┌────────────────────────┐│
│  │ SYSTEM HEALTH                   │  │ RECENT BACKUPS         ││
│  │                                 │  │                        ││
│  │   CPU ████████░░ 45%           │  │ ✓ postgres_n8n 2h ago  ││
│  │   MEM ██████░░░░ 62%           │  │ ✓ postgres_n8n 1d ago  ││
│  │   DISK ████░░░░░░ 38%          │  │ ✓ n8n_config  1d ago   ││
│  │                                 │  │                        ││
│  │   NFS: Connected ✓             │  │ [View All →]           ││
│  └─────────────────────────────────┘  └────────────────────────┘│
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ QUICK ACTIONS                                                ││
│  │ [📦 Run Backup] [🔄 Restart n8n] [📋 View Logs] [⚙ Settings]││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key Characteristics:**
- Horizontal navigation bar (not sidebar)
- Container status as compact cards in a row
- System metrics with progress bars
- Muted backgrounds (gray-50)
- Lots of whitespace
- Subtle shadows (shadow-sm)

**Color Usage:**
- Background: white/gray-50
- Cards: white with gray-200 borders
- Primary actions: sky-600
- Status indicators: colored dots (green/yellow/red)

**Page Layouts:**
- Single-column on mobile, multi-column on desktop
- Full-width tables with hover states
- Modal dialogs for forms
- Slide-over panels for details

---

### Task 3: Storyboard B - Modern Minimalist (Dark)

**Design Philosophy:** Same minimalist approach as A, but with dark theme for reduced eye strain.

**Dashboard Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│  HEADER (slate-900): Logo | Dashboard | ...       | User ▼      │
├──────────────────────────────────────────────────────────────────┤
│  (Background: slate-950)                                         │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐│
│  │ 🟢 n8n     │  │ 🟢 Postgres │  │ 🟢 Nginx    │  │ 🟢 Mgmt  ││
│  │ (slate-800)│  │ (slate-800) │  │ (slate-800) │  │(slate-800)││
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘│
│                                                                  │
│  Cards: slate-800/900                                            │
│  Text: slate-100/300                                             │
│  Borders: slate-700                                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key Characteristics:**
- Dark backgrounds (slate-950, slate-900)
- Cards in slate-800 with slate-700 borders
- Text in slate-100 (primary) and slate-400 (secondary)
- Glowing effect on status indicators
- Accent colors remain vibrant (sky-400, emerald-400)
- Subtle gradient overlays for depth

**Color Usage:**
- Background: slate-950
- Cards: slate-800/900
- Text: slate-100 (primary), slate-400 (secondary)
- Borders: slate-700
- Accents: sky-400, emerald-400 (brighter for contrast)

---

### Task 4: Storyboard C - Dashboard Heavy (Light)

**Design Philosophy:** Data-dense interface with sidebar navigation, multiple widgets, and real-time charts.

**Dashboard Layout:**
```
┌────────┬────────────────────────────────────────────────────────┐
│SIDEBAR │  HEADER: Dashboard Overview         Last sync: 5s ago  │
│        ├────────────────────────────────────────────────────────┤
│ 🏠 Dash│                                                        │
│ 📦 Back│  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│ 🔔 Noti│  │ CONTAINERS   │ │ BACKUPS      │ │ NOTIFICATIONS  │  │
│ 📦 Cont│  │    4/4 ✓     │ │   23 total   │ │  2 pending     │  │
│ 🔄 Flow│  │   healthy    │ │   1 failed   │ │  45 sent today │  │
│ 🖥 Syst│  └──────────────┘ └──────────────┘ └────────────────┘  │
│ ⚙ Sett│                                                        │
│        │  ┌─────────────────────────────────────────────────────┐│
│        │  │ CONTAINER RESOURCES (Real-time)                     ││
│        │  │ ┌─────────────────────────────────────────────────┐ ││
│        │  │ │     CPU USAGE CHART (Line graph, last 1 hour)   │ ││
│        │  │ └─────────────────────────────────────────────────┘ ││
│        │  │ ┌─────────────────────────────────────────────────┐ ││
│        │  │ │   MEMORY USAGE CHART (Area graph, by container) │ ││
│        │  │ └─────────────────────────────────────────────────┘ ││
│        │  └─────────────────────────────────────────────────────┘│
│        │                                                        │
│        │  ┌──────────────────────┐  ┌──────────────────────────┐│
│        │  │ RECENT ACTIVITY      │  │ BACKUP SCHEDULE          ││
│        │  │ • n8n restarted 10m  │  │ Next: postgres_n8n 2h    ││
│        │  │ • Backup completed   │  │ ████████░░ 75% until     ││
│        │  │ • Login from 10.0... │  │                          ││
│        │  └──────────────────────┘  └──────────────────────────┘│
│        │                                                        │
└────────┴────────────────────────────────────────────────────────┘
```

**Key Characteristics:**
- Collapsible sidebar with icons + labels
- Stat cards with trend indicators (↑ ↓)
- Multiple charts visible on dashboard
- Dense information layout
- Tabbed interfaces within pages
- Real-time data polling indicators

**Component Details:**
- KPI cards: Large numbers with small labels, colored icons
- Charts: Line/area for time series, donut for composition
- Tables: Compact rows, inline actions
- Timeline: Activity feed with avatars/icons

**Navigation:**
- Fixed sidebar (collapsible to icons only)
- Breadcrumbs in header
- Tab bars within sections

---

### Task 5: Storyboard D - Dashboard Heavy (Dark + Accent)

**Design Philosophy:** Feature-rich dark theme with neon accent colors, inspired by monitoring tools like Grafana.

**Dashboard Layout:**
```
┌────────┬────────────────────────────────────────────────────────┐
│SIDEBAR │  n8n Management      ▓▓▓▓▓▓░░░░ CPU: 45%  🟢 All OK   │
│(dark)  ├────────────────────────────────────────────────────────┤
│        │  (Background: zinc-950 with subtle grid pattern)       │
│ Icons  │                                                        │
│ with   │  ┌─ CONTAINERS ────────────────────────────────────────│
│ glow   │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│ effect │  │  │ ⬡ n8n  │ │⬡ PG   │ │⬡ nginx│ │⬡ mgmt │       │
│        │  │  │ 2% CPU │ │ 5% CPU│ │ 1% CPU│ │ 3% CPU│       │
│        │  │  │ ▓▓░░░░ │ │▓▓▓░░░ │ │▓░░░░░ │ │▓▓░░░░ │       │
│        │  │  └────────┘ └────────┘ └────────┘ └────────┘       │
│        │  └─────────────────────────────────────────────────────│
│        │                                                        │
│        │  ┌─ METRICS ───────────────────────────────────────────│
│        │  │  ╭─────────────────────────────────────────────╮    │
│        │  │  │  Real-time chart with glow effect           │    │
│        │  │  │  Cyan line for CPU, Magenta for Memory      │    │
│        │  │  ╰─────────────────────────────────────────────╯    │
│        │  └─────────────────────────────────────────────────────│
│        │                                                        │
│        │  ┌─ ACTIVITY ──────────────────────────────────────────│
│        │  │  12:34:56  ● Backup completed successfully          │
│        │  │  12:30:00  ● Container n8n restarted                │
│        │  │  12:15:23  ○ Notification sent to Slack            │
│        │  └─────────────────────────────────────────────────────│
└────────┴────────────────────────────────────────────────────────┘
```

**Key Characteristics:**
- Very dark background (zinc-950 or slate-950)
- Neon accent colors with glow effects (cyan-400, fuchsia-400)
- Monospace font for numbers/codes
- Grid or dot pattern subtle background
- Cards with colored left borders
- Animated charts with smooth transitions

**Color Palette:**
- Background: zinc-950
- Cards: zinc-900/800
- Borders: zinc-700 with colored accents
- Primary accent: cyan-400 (with shadow glow)
- Secondary accent: fuchsia-400 / violet-400
- Success: emerald-400
- Warning: amber-400
- Danger: rose-400

**Special Effects:**
- Glowing status indicators
- Gradient text for headers
- Animated progress bars
- Chart lines with glow filter

---

### Task 6: Component Specifications

For each storyboard, provide detailed specifications for these key components:

**Sidebar/Navigation:**
- Width (expanded/collapsed)
- Item styling (active, hover, disabled)
- Icon + text arrangement
- Collapse behavior

**Container Status Card:**
- Dimensions
- Status indicator style
- Metrics display
- Action buttons placement

**Backup History Table:**
- Column layout
- Row styling (alternating, hover)
- Status badges
- Action buttons (download, delete, verify)
- Pagination style

**Notification Service Card:**
- Icon for service type (Slack, Discord, Email, etc.)
- Status indicator
- Last test result
- Enable/disable toggle
- Edit/delete actions

**Form Modals:**
- Width (small, medium, large)
- Header styling
- Field layout (single column, grid)
- Button placement
- Validation error display

**Toast Notifications:**
- Position (top-right, bottom-right, etc.)
- Styling per type (success, error, warning, info)
- Animation (slide, fade)
- Duration and close button

---

### Task 7: Responsive Breakpoints

Define behavior at each breakpoint:

**Mobile (< 640px):**
- Sidebar becomes bottom navigation or hamburger menu
- Single column layout
- Stacked cards
- Full-width modals
- Simplified tables (cards instead)

**Tablet (640px - 1024px):**
- Collapsible sidebar (icons only)
- 2-column grid for cards
- Tables with horizontal scroll for extra columns
- Side panel modals

**Desktop (> 1024px):**
- Full sidebar with text labels
- 3-4 column grids
- Multi-column tables
- Modal overlays
- Side-by-side panels

---

### Task 8: Interactive Prototype Notes

For each storyboard, document:

**Micro-interactions:**
- Button hover/active states
- Card hover effects
- Toggle animations
- Loading states
- Skeleton screens

**Transitions:**
- Page transitions (fade, slide)
- Modal open/close
- Sidebar collapse
- Tab switching

**Feedback:**
- Form validation (inline errors)
- Success confirmations (toast + in-place)
- Loading spinners
- Progress indicators

---

## Deliverables

Create the following files in `/home/user/n8n_nginx/agent_prompts/storyboards/`:

1. **design_system.md** - Shared design tokens, typography, color palette
2. **storyboard_a_modern_light.md** - Complete mockups for all pages
3. **storyboard_b_modern_dark.md** - Complete mockups for all pages
4. **storyboard_c_dashboard_light.md** - Complete mockups for all pages
5. **storyboard_d_dashboard_dark.md** - Complete mockups for all pages
6. **components.md** - Detailed component specifications

Each storyboard document should include:
- ASCII/text-based wireframes for each major view
- Color specifications (hex codes)
- Typography specifications
- Component dimensions and spacing
- Responsive behavior notes
- Animation/transition notes

---

## Dependencies on Other Agents

- **Frontend Agent**: Will implement the selected design
- After storyboards are created, user will select one for implementation

---

## Important Notes

1. **Do not create actual images** - Use ASCII diagrams and text descriptions
2. **Be specific with colors** - Use exact hex codes or Tailwind color names
3. **Think about edge cases** - Empty states, error states, loading states
4. **Consider accessibility** - Color contrast, focus states, screen reader support
5. **Provide enough detail** for the Frontend Agent to implement accurately
