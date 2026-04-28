# n8n Management Suite — End-User Manual Design

**Date:** 2026-04-25
**Author:** rjsears (with Claude assistance)
**Status:** Approved

## Goal

Build a comprehensive, post-installation end-user manual for the n8n Management
Suite as a fully-styled HTML/CSS website. The manual must cover every option
exposed in the management UI, with annotated screenshots for every view, sub-tab,
and modal. The look-and-feel mirrors
`https://github.com/rjsears/sim_port_control/blob/main/docs/manual/index-template.html`
but adapted to a multi-page structure to remain navigable at scale.

## Non-Goals

- Installation/setup instructions (already covered by the existing `docs/*.md`
  documentation set).
- API reference (covered by `docs/API.md`).
- Migration content (covered by `docs/MIGRATION.md`).
- Marketing copy. The audience is operators who have already deployed.

## Source Site

Documentation will be captured live from
`https://n8n01.n8nmanagement.net/management/` (the operator's test
deployment). Screenshots will contain real data; sensitive values will be
flagged for post-capture blurring rather than redacted in capture.

## Information Architecture

The manual is split into three "Parts" that mirror the reference template's
narrative arc:

### Part 1 — End-User Guide (everyday operations)

| Page | Covers |
|---|---|
| `dashboard.html` | Top stats cards, system overview widgets, status indicators, refresh controls |
| `containers.html` | Container list, per-container actions (start/stop/restart), logs, stats, health indicators |
| `flows.html` | Workflow list, executions, toggle/execute, link to n8n, filters |
| `backups.html` | Schedules, history, run-now, verification, retention, NFS status |
| `notifications.html` | Channels (services), groups, rules, NTFY topics, history, webhook integration |

### Part 2 — Administration

| Page | Covers |
|---|---|
| `system.html` | Health, full health, info, network, SSL detail + force-renewal, Cloudflare, Tailscale, terminal targets, external services, debug |
| `settings.html` | Every settings sub-tab: env variables, NFS config, Tailscale reset, debug mode, access control + IP ranges, external routes, email config + templates, Cache (Redis), system notifications globals |

### Part 3 — Appendix

| Page | Covers |
|---|---|
| `appendix.html` | Troubleshooting tables, keyboard shortcuts, master screenshot security index |

### Cover

`index.html` is the cover page: short intro, big TOC linking to all Part pages,
last-updated timestamp, theme toggle preview.

## File Layout

```
docs/manual/
├── index.html
├── dashboard.html
├── containers.html
├── flows.html
├── backups.html
├── notifications.html
├── system.html
├── settings.html
├── appendix.html
└── styles.css

images/screenshots/
└── <all PNG screenshots>
```

Screenshots are referenced from HTML as `../../images/screenshots/<filename>`
to keep them in the operator-specified directory.

## Visual Design

### Themes
- Light + dark, toggle in top nav, defaults to OS `prefers-color-scheme`.
- Theme persisted in `localStorage`.

### Typography
- Body: Inter (Google Fonts), system-ui fallback.
- Code: JetBrains Mono, monospace fallback.

### Color tokens

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#fafafa` | `#0d1117` |
| `--surface` | `#ffffff` | `#161b22` |
| `--text` | `#1f2937` | `#e5e7eb` |
| `--text-muted` | `#6b7280` | `#9ca3af` |
| `--accent` | `#2563eb` | `#60a5fa` |
| `--border` | `#e5e7eb` | `#30363d` |
| `--code-bg` | `#f3f4f6` | `#1f2937` |
| `--note` | `#dbeafe` / `#1e40af` border | `#1e3a8a` / `#3b82f6` border |
| `--tip` | `#dcfce7` / `#15803d` border | `#14532d` / `#22c55e` border |
| `--warn` | `#fef3c7` / `#b45309` border | `#78350f` / `#f59e0b` border |
| `--danger` | `#fee2e2` / `#b91c1c` border | `#7f1d1d` / `#ef4444` border |

### Layout
- **Top nav** (sticky, full width): logo/title, Part 1 / Part 2 / Part 3 dropdowns, search input (deferred — Phase 5+), theme toggle.
- **Per-page sidebar** (sticky, left, 260px): jumps to that page's subsections; hides under hamburger ≤ 900px viewport.
- **Main content** (max-width 900px, comfortable line length).
- **Footer**: prev / next page links, "back to top".

### Components
- `<figure class="screenshot">` with `<img>` and `<figcaption>`.
- Info boxes: `.info-box.note` / `.tip` / `.warn` / `.danger` with leading emoji.
- Step lists: `<ol class="steps">`.
- Reference tables: zebra-striped via `:nth-child(even)`.
- Code blocks: copy-to-clipboard button injected via small JS.
- Security flag badge (red, sticky at bottom of figure):
  `<div class="security-flag">🔒 SECURITY: …</div>`.

## Screenshots

### Capture mix (per Q2=C)
- **Full-page hero** at top of each section.
- **Cropped close-ups** of buttons, cards, modals, dropdowns.
- Per Q4=A, every modal, every sub-tab, every dropdown gets its own image.

### Naming
```
<section>-<NN>-<descriptor>.png
```
Examples:
- `dashboard-01-overview.png`
- `dashboard-02-stats-card-cpu.png`
- `settings-23-access-control-edit-modal.png`
- `system-08-ssl-certificate-detail.png`

`<NN>` is two-digit, zero-padded sequence within section to allow alphabetical
ordering matching reading order.

### Capture mechanism
Order of preference:
1. `mcp__claude-in-chrome__computer` if it exposes screenshot capability.
2. `mcp__claude-in-chrome__javascript_tool` injecting `html2canvas` to render
   element → blob → download.
3. **Manual fallback**: produce an exact list of screenshots needed; operator
   captures with macOS `Cmd+Shift+4` (or full-page extension), drops into
   `images/screenshots/` matching the naming convention.

The first viable mechanism is selected in Phase 2 and used throughout.

## Security Flagging

### What gets flagged
- API tokens: Cloudflare, Tailscale, NTFY, n8n credentials, DNS provider.
- Database passwords / connection strings.
- SSL private cert paths/keys.
- Server hostnames / IPs (operator confirmed).
- User email addresses.
- Internal subnet info shown on access-control panels.

### How it's flagged
Three layers:
1. **HTML markup** on each `<figure>`: `class="has-security-flag"` and a
   visible `.security-flag` div with a one-line description of what to blur.
2. **Master index in `appendix.html`**: table of every flagged screenshot,
   filename, what it contains, blur instructions.
3. **HTML comment near the figure**: `<!-- SECURITY: blur Cloudflare token -->`
   for grep-ability.

The screenshots themselves are captured unredacted; the operator runs
post-process blurring before publishing.

## Implementation Phases

| Phase | Scope | Approval gate |
|---|---|---|
| 1 | Build `styles.css` and `index.html` scaffolding (no content yet, just nav, theme toggle, layout primitives) | Operator opens `index.html` locally, confirms look-and-feel before content build-out |
| 2 | Verify screenshot capture mechanism. Capture and document **one** end-to-end page (Dashboard) so the visual format is locked in | Operator reviews `dashboard.html` for content depth, screenshot quality, security-flag handling |
| 3 | Iterate through remaining Part 1 + Part 2 pages: Containers → Flows → Backups → Notifications → System → Settings | Operator may review at any cut-over; otherwise continuous |
| 4 | Build `appendix.html`: troubleshooting tables (sourced from existing `docs/TROUBLESHOOTING.md`) and master security-flag index | — |
| 5 | Final QA: verify all internal links, all `<img>` paths resolve, print-preview each page, light/dark theme parity | Operator ships |

## Operator Constraints (project-specific)

- **No git operations**: don't commit, push, branch, or PR anything. The
  operator handles git themselves. Recorded in
  `~/.claude/projects/.../memory/feedback_no_prs.md`.
- **Local files only**: every artifact stays on disk under
  `/Users/rsears/Google Drive/PycharmProjects/n8n_nginx/`.
- **No `Co-Authored-By: Claude` trailers**: relevant only if commits are ever
  authorized later (they aren't here).

## Open Questions / Risks

- **Screenshot tool availability** — verified in Phase 2; manual fallback
  exists.
- **Login session expiry** — if the chrome tab session expires mid-tour, the
  operator re-logs in; capture resumes.
- **Modal coverage completeness** — the spec promises "every modal" but some
  may only appear under specific data conditions (e.g., a backup-failure modal
  only appears when a backup actually fails). Where a modal can't be triggered,
  it's omitted with a note in the appendix.
- **Live data drift** — the test site's data changes over time; screenshots
  taken in one session may not match later. Captures will be batched as
  contiguously as possible to minimize drift.
