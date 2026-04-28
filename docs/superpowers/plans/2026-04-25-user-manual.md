# n8n Management Suite User Manual — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a comprehensive HTML/CSS end-user manual covering every UI option in the n8n Management Suite, with annotated screenshots and security flags for sensitive views.

**Architecture:** Multi-page static HTML site under `docs/manual/`, shared `styles.css`, light/dark theme via `localStorage`. One HTML file per top-level UI section (8 content pages + cover + appendix). Screenshots captured live from `https://n8n01.n8nmanagement.net/management/` and stored under `images/screenshots/`. Sensitive screenshots are flagged inline + indexed in appendix; operator blurs them post-capture before publishing.

**Tech Stack:** Static HTML5, CSS3 (custom properties for theming), minimal vanilla JS (theme toggle, copy-to-clipboard, mobile sidebar toggle). No build step. No framework. No external runtime dependencies. Google Fonts (Inter, JetBrains Mono) loaded via CDN.

**Spec:** `docs/superpowers/specs/2026-04-25-user-manual-design.md`

**Operator-specific constraints:**
- ⛔ **No git operations.** All "Commit" steps in this plan are SKIPPED. The operator runs git themselves. Do not run `git add`, `git commit`, `git push`, `git checkout -b`, `gh pr create`, or any equivalent.
- ⛔ **No `Co-Authored-By: Claude` in any text artifact.**
- All work product stays local under `/Users/rsears/Google Drive/PycharmProjects/n8n_nginx/`.

**Post-launch TODOs (for the operator, after the manual is accepted):**
- Update the management console's **Help & Documentation** modal (Vue/frontend code) to repoint each User Guides / Infrastructure Docs link from the legacy `docs/*.md` markdown to the new HTML pages under `docs/manual/`. The Swagger UI / ReDoc / OpenAPI Schema links and external Project Resources links stay as-is.
- Once HTML pages are accepted as canonical, archive or delete the legacy `docs/*.md` (per decision: HTML is single source of truth, no parallel maintenance).

---

## File Structure

```
docs/manual/
├── index.html              # Cover page + master TOC
├── dashboard.html          # Part 1: Dashboard
├── containers.html         # Part 1: Containers
├── flows.html              # Part 1: Flows
├── backups.html            # Part 1: Backups
├── notifications.html      # Part 1: Notifications
├── system.html             # Part 2: System
├── settings.html           # Part 2: Settings
├── appendix.html           # Part 3: Troubleshooting + security index
├── styles.css              # Shared theme
└── manual.js               # Theme toggle, copy buttons, sidebar toggle

images/screenshots/         # All PNG screenshots (existing dir per operator)
```

Every HTML page shares the same shell (header, nav, sidebar slot, content slot, footer). Because there's no build step, the shell is duplicated across pages — keep it byte-identical so a future search-and-replace cleanly applies to all pages.

---

## Chunk 1: Foundation

Goal: a working visual shell — open `index.html` and see the styled cover page, theme toggle works, navigation links exist (even if pointing at empty pages).

### Task 1.1: Create the CSS theme file

**Files:**
- Create: `docs/manual/styles.css`

- [ ] **Step 1: Define design tokens (light + dark) and base layout**

Create `docs/manual/styles.css` with:
- `:root` light tokens: `--bg`, `--surface`, `--text`, `--text-muted`, `--accent`, `--border`, `--code-bg`, `--note-bg`, `--note-border`, `--tip-bg`, `--tip-border`, `--warn-bg`, `--warn-border`, `--danger-bg`, `--danger-border`, `--security-bg`, `--security-border`.
- `:root[data-theme="dark"]` dark token overrides per the spec's color palette table.
- `* { box-sizing: border-box }`, `html { scroll-behavior: smooth }`, base body using `var(--bg)` and Inter.
- Layout grid: `body` is a single column; `.app` uses CSS grid `grid-template-columns: 260px 1fr` on `min-width: 901px`, single column below.
- Sticky top nav `.topnav` (height 56px, full-width, `position: sticky; top: 0; z-index: 100`).
- Sticky sidebar `.sidebar` (`position: sticky; top: 56px; align-self: start; max-height: calc(100vh - 56px); overflow-y: auto`).
- Main content `.content` (max-width 900px, padding 32px, line-height 1.7).
- Footer `.pagefoot` (prev/next links, "back to top").

- [ ] **Step 2: Style components**

Add styles for:
- Headings (h1–h4) with consistent vertical rhythm.
- Links (accent color, underline on hover).
- Code blocks: `pre, code` using JetBrains Mono, `pre` with `background: var(--code-bg)`, padding 16px, border-radius 8px, `overflow-x: auto`.
- Inline code: `code` with subtle background, padding 2px 6px, border-radius 4px.
- Info boxes: `.info-box` base + `.info-box.note`, `.tip`, `.warn`, `.danger` variants. Each has a leading emoji rendered via `::before`. Border-left 4px solid the variant color.
- Step lists: `<ol class="steps">` with bigger numbers and spacing.
- Reference tables: `table` with full width, zebra `:nth-child(even) { background: var(--surface) }`, border-collapse, padding 8px 12px, sticky header `thead { position: sticky; top: 56px }`.
- Figures: `figure.screenshot { margin: 24px 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface); }`. `figcaption` with padding 8px 12px, italic, smaller font.
- Security flag badge: `.security-flag { background: var(--security-bg); color: var(--security-border); padding: 8px 12px; font-size: 0.875rem; font-weight: 600; border-top: 1px solid var(--security-border); }`.
- Theme toggle button: pill-shaped, 32px height, icon + label.
- Copy-to-clipboard button: `position: absolute; top: 8px; right: 8px;` on `pre` (parent set `position: relative`).

- [ ] **Step 3: Visual verification**

Open any HTML file (after Task 1.2) in a browser. Confirm:
- Light mode renders with cream/white background and dark text.
- No layout shift on load.
- Sticky nav stays at top on scroll.
- Sidebar stays at left and scrolls independently.
- No scrollbar artifacts on body.

- [ ] **Step 4: Skip commit (operator handles git)**

### Task 1.2: Create the JavaScript helper

**Files:**
- Create: `docs/manual/manual.js`

- [ ] **Step 1: Theme toggle**

```javascript
const THEME_KEY = 'n8n-manual-theme';
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
}
function initTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(stored || (prefersDark ? 'dark' : 'light'));
}
function toggleTheme() {
  const current = document.documentElement.dataset.theme || 'light';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}
```

- [ ] **Step 2: Copy-to-clipboard**

```javascript
function attachCopyButtons() {
  document.querySelectorAll('pre').forEach(pre => {
    if (pre.querySelector('.copy-btn')) return;
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.addEventListener('click', async () => {
      const code = pre.querySelector('code') || pre;
      await navigator.clipboard.writeText(code.innerText);
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
    });
    pre.style.position = 'relative';
    pre.appendChild(btn);
  });
}
```

- [ ] **Step 3: Mobile sidebar toggle**

```javascript
function initSidebarToggle() {
  const btn = document.getElementById('sidebarToggle');
  const sidebar = document.querySelector('.sidebar');
  if (!btn || !sidebar) return;
  btn.addEventListener('click', () => sidebar.classList.toggle('open'));
}
```

- [ ] **Step 4: Bootstrap on DOM ready**

```javascript
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  attachCopyButtons();
  initSidebarToggle();
  const tt = document.getElementById('themeToggle');
  if (tt) tt.addEventListener('click', toggleTheme);
});
```

- [ ] **Step 5: Skip commit**

### Task 1.3: Build the shared HTML shell template

The shell repeats verbatim across every page. Define it once here so every page uses the exact same markup (only the `<title>`, `data-page` attribute, sidebar contents, and main content differ).

**Shell skeleton:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{PAGE_TITLE}} — n8n Management Suite Manual</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body data-page="{{PAGE_SLUG}}">
  <header class="topnav">
    <a class="brand" href="index.html">n8n Management Manual</a>
    <nav class="topnav-links">
      <a href="index.html">Home</a>
      <details class="topnav-dropdown">
        <summary>Part 1: User Guide</summary>
        <div class="dropdown-menu">
          <a href="dashboard.html">Dashboard</a>
          <a href="containers.html">Containers</a>
          <a href="flows.html">Flows</a>
          <a href="backups.html">Backups</a>
          <a href="notifications.html">Notifications</a>
        </div>
      </details>
      <details class="topnav-dropdown">
        <summary>Part 2: Administration</summary>
        <div class="dropdown-menu">
          <a href="system.html">System</a>
          <a href="settings.html">Settings</a>
        </div>
      </details>
      <a href="appendix.html">Appendix</a>
    </nav>
    <button id="themeToggle" class="theme-toggle">🌙 Dark</button>
    <button id="sidebarToggle" class="sidebar-toggle" aria-label="Toggle sidebar">☰</button>
  </header>
  <div class="app">
    <aside class="sidebar">
      {{SIDEBAR_TOC}}
    </aside>
    <main class="content">
      {{CONTENT}}
      <nav class="pagefoot">
        <a class="prev" href="{{PREV_HREF}}">← {{PREV_TITLE}}</a>
        <a class="next" href="{{NEXT_HREF}}">{{NEXT_TITLE}} →</a>
      </nav>
    </main>
  </div>
  <script src="manual.js"></script>
</body>
</html>
```

- [ ] **Step 1: Save the shell skeleton in this plan as the canonical template** (already done above).

- [ ] **Step 2: For every page in this manual, copy this skeleton verbatim and substitute only the four template variables: `{{PAGE_TITLE}}`, `{{PAGE_SLUG}}`, `{{SIDEBAR_TOC}}`, `{{CONTENT}}`, plus the four prev/next variables.** Do NOT vary header markup between pages — if a future change is needed (e.g., add a search box), it must apply to all pages identically.

### Task 1.4: Build `index.html` (cover page)

**Files:**
- Create: `docs/manual/index.html`

- [ ] **Step 1: Substitute the shell**

`{{PAGE_TITLE}}` = `Home`. `{{PAGE_SLUG}}` = `home`.

`{{SIDEBAR_TOC}}`:
```html
<h2 class="sidebar-title">On this page</h2>
<ul class="sidebar-toc">
  <li><a href="#welcome">Welcome</a></li>
  <li><a href="#how-to-read">How to read this manual</a></li>
  <li><a href="#part-1">Part 1: User Guide</a></li>
  <li><a href="#part-2">Part 2: Administration</a></li>
  <li><a href="#part-3">Part 3: Appendix</a></li>
  <li><a href="#legend">Legend</a></li>
</ul>
```

`{{CONTENT}}`:
```html
<h1>n8n Management Suite — User Manual</h1>
<p class="lede">Comprehensive guide to operating the n8n Management Console after installation. Every UI option, every modal, every sub-tab.</p>

<section id="welcome">
  <h2>Welcome</h2>
  <p>This manual is intended for operators who have already installed and deployed the n8n Management Suite. It does not cover initial installation — see <a href="https://github.com/rjsears/n8n_nginx/blob/main/README.md">README.md</a> for setup.</p>
</section>

<section id="how-to-read">
  <h2>How to read this manual</h2>
  <p>The manual is organized in three parts. Read sequentially, or jump directly to the section you need via the navigation above.</p>
  <div class="info-box note">📝 <strong>Note:</strong> Screenshots in this manual were captured from a live test deployment. Some screenshots contain sensitive data (API tokens, internal IPs) which are flagged inline and indexed in the <a href="appendix.html#security-index">Security Flag Index</a>.</div>
</section>

<section id="part-1">
  <h2>Part 1: User Guide</h2>
  <p>Everyday operations.</p>
  <ul class="card-list">
    <li><a href="dashboard.html"><strong>Dashboard</strong> — system overview at a glance</a></li>
    <li><a href="containers.html"><strong>Containers</strong> — start/stop/inspect docker services</a></li>
    <li><a href="flows.html"><strong>Flows</strong> — view and trigger n8n workflows</a></li>
    <li><a href="backups.html"><strong>Backups</strong> — schedule, run, verify, restore</a></li>
    <li><a href="notifications.html"><strong>Notifications</strong> — channels, groups, rules</a></li>
  </ul>
</section>

<section id="part-2">
  <h2>Part 2: Administration</h2>
  <ul class="card-list">
    <li><a href="system.html"><strong>System</strong> — health, SSL, network, integrations</a></li>
    <li><a href="settings.html"><strong>Settings</strong> — every configuration knob</a></li>
  </ul>
</section>

<section id="part-3">
  <h2>Part 3: Appendix</h2>
  <ul class="card-list">
    <li><a href="appendix.html#troubleshooting"><strong>Troubleshooting</strong></a></li>
    <li><a href="appendix.html#security-index"><strong>Security Flag Index</strong> — screenshots requiring blur before publishing</a></li>
  </ul>
</section>

<section id="legend">
  <h2>Legend</h2>
  <div class="info-box note">📝 <strong>Note:</strong> additional context, not required reading.</div>
  <div class="info-box tip">💡 <strong>Tip:</strong> a recommended approach.</div>
  <div class="info-box warn">⚠️ <strong>Warning:</strong> behavior that may surprise you.</div>
  <div class="info-box danger">🚫 <strong>Danger:</strong> destructive or irreversible action.</div>
  <div class="info-box security">🔒 <strong>Security flag:</strong> screenshot contains sensitive data; blur before publishing.</div>
</section>
```

`{{PREV_HREF}}` = `index.html`, `{{PREV_TITLE}}` = `Home` (self — hide via CSS). `{{NEXT_HREF}}` = `dashboard.html`, `{{NEXT_TITLE}}` = `Dashboard`.

- [ ] **Step 2: Open `docs/manual/index.html` in a browser, verify**:
  - Top nav renders with all dropdowns.
  - Theme toggle button works (click cycles light/dark; refresh persists).
  - Sidebar TOC renders, anchor links scroll to sections.
  - All four info-box variants render with correct color and emoji.
  - Footer prev/next exists.
  - Cards in card-list render with subtle hover state.
- [ ] **Step 3: Skip commit**

### Task 1.5: Stub the remaining 8 page files

For each of `dashboard.html`, `containers.html`, `flows.html`, `backups.html`, `notifications.html`, `system.html`, `settings.html`, `appendix.html`:

- [ ] **Step 1: Copy the shell skeleton and substitute placeholders**

`{{PAGE_TITLE}}` = the page name (e.g., `Dashboard`).
`{{PAGE_SLUG}}` = lowercase slug (e.g., `dashboard`).
`{{SIDEBAR_TOC}}` = `<h2 class="sidebar-title">On this page</h2><p class="muted">Content coming in Phase 2.</p>`.
`{{CONTENT}}` = `<h1>{{PAGE_TITLE}}</h1><p>This page will be populated as the manual is built out.</p>`.
Set prev/next according to logical sequence:

| Page | Prev | Next |
|---|---|---|
| dashboard | index.html / Home | containers.html / Containers |
| containers | dashboard.html / Dashboard | flows.html / Flows |
| flows | containers.html / Containers | backups.html / Backups |
| backups | flows.html / Flows | notifications.html / Notifications |
| notifications | backups.html / Backups | system.html / System |
| system | notifications.html / Notifications | settings.html / Settings |
| settings | system.html / System | appendix.html / Appendix |
| appendix | settings.html / Settings | index.html / Home |

- [ ] **Step 2: Open each stub page in a browser, confirm nav and theme work and prev/next link to the correct neighbors.**
- [ ] **Step 3: Skip commit**

### Chunk 1 verification

Open `docs/manual/index.html` and click through every nav link, every dropdown, every prev/next. Toggle theme. Confirm:
- All 9 pages load (no 404s in DevTools console).
- Theme persists across page navigation.
- No CSS errors in DevTools.
- Mobile viewport (≤ 900px) collapses sidebar correctly.

**STOP — operator review checkpoint.** Before proceeding to Chunk 2, the operator opens `docs/manual/index.html` and confirms the look-and-feel matches expectations. Any styling tweaks happen now, before content build-out.

---

## Chunk 2: Screenshot pipeline + Dashboard reference page

Goal: lock in the screenshot capture mechanism and produce one fully-built page (`dashboard.html`) that future pages mimic.

### Task 2.1: Verify screenshot capture mechanism

- [ ] **Step 1: Inspect available chrome MCP tools.** Check whether `mcp__claude-in-chrome__computer` exposes a `screenshot` action. Try a small test capture targeting the current tab.

- [ ] **Step 2: If `computer.screenshot` works:** record the exact tool invocation pattern in this plan as `<<CAPTURE-METHOD: computer>>` and use throughout.

- [ ] **Step 3: If `computer.screenshot` doesn't exist or fails:** try `javascript_tool` injecting `html2canvas` from CDN, calling `html2canvas(document.body)` then triggering a download via `canvas.toBlob` + `<a download>`. Record the saved-file path.

- [ ] **Step 4: If neither works:** fall back to **manual capture mode**. Operator captures each screenshot with macOS `Cmd+Shift+4`, drops into `images/screenshots/`. The plan still produces an exact list of every screenshot needed and its naming.

- [ ] **Step 5: Record decision in the plan.** Update this section with `CAPTURE-METHOD: <chosen>` so subsequent tasks use the same approach.

### Task 2.2: Tour the Dashboard view and record its IA

Before writing `dashboard.html`, navigate the chrome tab through the Dashboard and inventory every visible widget, button, modal, and tooltip.

- [ ] **Step 1: Navigate to `https://n8n01.n8nmanagement.net/management/`** (already open).
- [ ] **Step 2: Use `read_page` with `filter: "all"`** to enumerate all elements.
- [ ] **Step 3: Hover or click each interactive element** (without taking destructive actions like Logout, Restart, etc.) to surface tooltips, dropdowns, and inline modals.
- [ ] **Step 4: Build a section list** for the Dashboard page sidebar. Likely sections: `overview`, `stats-cards`, `service-status`, `recent-activity`, `refresh-controls`. Adjust based on what's actually present.
- [ ] **Step 5: Identify any view-modes** (e.g., compact/expanded toggle). Each gets its own screenshot.

### Task 2.3: Capture Dashboard screenshots

- [ ] **Step 1: Full-page hero**: capture the entire dashboard view → `dashboard-01-overview.png`.
- [ ] **Step 2: Each stats card**: cropped close-up → `dashboard-02-stats-card-<name>.png` (e.g., `cpu`, `memory`, `disk`).
- [ ] **Step 3: Service status panel**: cropped → `dashboard-03-service-status.png`. If any service is shown as down/degraded, capture additionally → `dashboard-03b-service-status-degraded.png`.
- [ ] **Step 4: Each control button** (refresh, force-refresh, time-range selector if present): cropped → `dashboard-04-<control>.png`.
- [ ] **Step 5: Any modal triggered from dashboard** (e.g., clicking a card opens a detail modal): capture both the trigger state and the modal → `dashboard-05-card-modal-<name>.png`.

For every screenshot, record:
- Filename
- Brief alt text / caption
- Whether it contains anything sensitive (yes/no, what to blur)

Track this in a temporary scratchpad — fed into `appendix.html` security index later.

### Task 2.4: Write `dashboard.html` content

**Files:**
- Modify: `docs/manual/dashboard.html`

- [ ] **Step 1: Replace the stub `{{SIDEBAR_TOC}}`** with the real sub-section TOC discovered in Task 2.2.

- [ ] **Step 2: Replace the stub `{{CONTENT}}`** with full prose. Structure:

```html
<h1>Dashboard</h1>
<p class="lede">The Dashboard is the home view after login. It surfaces the most-needed at-a-glance information about your n8n stack: container health, system resource usage, recent backup status, and notification activity.</p>

<figure class="screenshot">
  <img src="../../images/screenshots/dashboard-01-overview.png" alt="Dashboard overview, full width">
  <figcaption>Figure 1: Dashboard overview after login.</figcaption>
</figure>

<section id="stats-cards">
  <h2>Stats cards</h2>
  <p>The top row shows live system metrics. Each card auto-refreshes every <em>N</em> seconds (configurable in <a href="settings.html#refresh-interval">Settings → Refresh interval</a>).</p>
  <!-- one figure per stats card, with descriptive prose between them -->
</section>

<section id="service-status">
  <h2>Service status</h2>
  <!-- ... -->
</section>

<!-- etc. -->
```

- [ ] **Step 3: Inline every screenshot from Task 2.3** with proper `<figure class="screenshot">` markup, `<img>` `src` pointing at `../../images/screenshots/<file>`, and a descriptive `<figcaption>`.

- [ ] **Step 4: Wrap any sensitive figure** with `class="screenshot has-security-flag"` and append:

```html
<div class="security-flag">🔒 SECURITY: Blur <specific item> before publishing.</div>
```

Insert an HTML comment above each flagged figure: `<!-- SECURITY: blur <item> -->`.

- [ ] **Step 5: Cross-link related sections.** When prose mentions a setting or another view, link to it (e.g., "see <a href='containers.html#logs'>container logs</a>").

- [ ] **Step 6: Open `docs/manual/dashboard.html` in browser. Verify**:
  - All `<img>` paths resolve (no broken images in DevTools console).
  - All `<a>` internal links resolve.
  - Sidebar TOC scrolls correctly.
  - Light/dark theme parity.
  - Print preview is acceptable (no overflow, screenshots not split awkwardly).

- [ ] **Step 7: Skip commit**

### Chunk 2 verification

Open `dashboard.html`, scroll top to bottom, confirm:
- Every UI element of the Dashboard view is documented.
- Every screenshot has a caption.
- Every sensitive screenshot is flagged.
- The page reads well as a standalone tour of the Dashboard.

**STOP — operator review checkpoint.** Operator reviews `dashboard.html` for content depth, screenshot quality, prose tone, and security-flag formatting. The format approved here is the template for all remaining pages.

---

## Chunk 3: Part 1 content pages

Goal: complete `containers.html`, `flows.html`, `backups.html`, `notifications.html` using the Dashboard format as template.

Each page follows the same per-page workflow:
1. **Tour** the live UI for that section (Task X.1).
2. **Capture** screenshots (Task X.2).
3. **Write** the HTML content (Task X.3).
4. **Verify** in browser (Task X.4).
5. **Skip commit.**

### Task 3.1: Containers page

- [ ] **Tour `https://n8n01.n8nmanagement.net/management/containers`.** Inventory:
  - Container list table (columns, sort indicators, filter controls).
  - Per-row actions: start, stop, restart, logs, stats, inspect.
  - Any bulk-action controls.
  - Logs viewer modal/page.
  - Stats / metrics view.
  - Health indicators (icons, hover-tooltip text).
  - Any "force refresh" button.

- [ ] **Capture screenshots**:
  - `containers-01-list.png` (full list view)
  - `containers-02-row-actions.png` (cropped row showing the action button cluster)
  - `containers-03-logs-modal.png` (logs viewer)
  - `containers-04-logs-search.png` (logs viewer with search active)
  - `containers-05-stats-view.png` (per-container stats)
  - `containers-06-restart-confirm.png` (confirmation dialog if any)
  - `containers-07-health-badge-<states>.png` (one per health state visible: healthy / unhealthy / starting / degraded)
  - `containers-08-filter-active.png` (with filter applied)
  - Additional images as needed for full Q4=A coverage.

- [ ] **Write `containers.html`** following dashboard format. Sub-sections:
  - Overview / list view
  - Sorting and filtering
  - Per-container actions (with destructive-action warning info-box)
  - Logs viewer
  - Stats / metrics
  - Health indicators

- [ ] **Verify in browser. Skip commit.**

### Task 3.2: Flows page

- [ ] **Tour `https://n8n01.n8nmanagement.net/management/flows`.** Inventory:
  - Workflow list (columns, filters, search).
  - Per-row actions: toggle active, execute, view in n8n.
  - Executions list (if visible separately).
  - Stats overview.
  - Link/jump to n8n itself.

- [ ] **Capture screenshots**:
  - `flows-01-list.png` (full list)
  - `flows-02-row-actions.png` (cropped)
  - `flows-03-toggle-active.png` (toggle interaction)
  - `flows-04-execute-confirm.png` (execute action and any confirmation)
  - `flows-05-executions-list.png`
  - `flows-06-stats-overview.png`
  - `flows-07-n8n-jump.png` (button or link that opens n8n)
  - Additional images for full coverage.

- [ ] **Write `flows.html`.** Sub-sections:
  - Workflow list
  - Toggling workflows active/inactive
  - Executing on demand
  - Executions history
  - Jumping to n8n itself
  - Workflow stats

- [ ] **Verify. Skip commit.**

### Task 3.3: Backups page

- [ ] **Tour `https://n8n01.n8nmanagement.net/management/backups`.** This is a large section. Inventory:
  - Schedules tab: list, create-schedule modal, edit, delete confirmation.
  - History tab: list, filter, status indicators, delete-backup confirmation.
  - Run-now button + dialog.
  - Verification: how to trigger, what the result looks like.
  - Retention settings.
  - NFS status indicator.
  - Stats / overview cards.

- [ ] **Capture screenshots**:
  - `backups-01-overview.png`
  - `backups-02-schedules-list.png`
  - `backups-03-create-schedule-modal.png`
  - `backups-04-create-schedule-modal-cron-help.png` (if cron help is shown)
  - `backups-05-edit-schedule.png`
  - `backups-06-delete-schedule-confirm.png`
  - `backups-07-history-list.png`
  - `backups-08-history-filter.png`
  - `backups-09-history-row-detail.png`
  - `backups-10-run-now-dialog.png`
  - `backups-11-run-now-progress.png`
  - `backups-12-verification-result.png`
  - `backups-13-retention-settings.png`
  - `backups-14-nfs-status.png`
  - `backups-15-delete-backup-confirm.png`
  - `backups-16-stats.png`
  - Add as needed for every modal and sub-tab.

- [ ] **Write `backups.html`.** Heavy use of `<div class="info-box danger">` for destructive actions (delete backup, disable schedule). Use `<div class="info-box warn">` for verification timeouts and NFS connectivity.

- [ ] **Verify. Skip commit.**

### Task 3.4: Notifications page

- [ ] **Tour `https://n8n01.n8nmanagement.net/management/notifications`.** Inventory:
  - Channels (services) tab: list, create-channel modal (every channel type if a chooser exists), test-channel button.
  - Groups tab: list, create-group, member-channel association.
  - Rules tab: list, create-rule wizard or modal.
  - NTFY topics (if integrated here).
  - Webhook integration: webhook URL display, key generation/regeneration.
  - History tab.
  - Event types reference.

- [ ] **Capture screenshots**: aim for ~20–30 images. Naming: `notifications-NN-<descriptor>.png`. Cover every channel type if create-channel surfaces a type selector.

- [ ] **Write `notifications.html`.** Sub-sections:
  - Channels (services) — every channel type
  - Groups
  - Rules
  - NTFY topic management
  - Webhook integration with n8n
  - History viewer
  - Event types reference

- [ ] **Verify. Skip commit.**

### Chunk 3 verification

- All four Part 1 pages exist with full content.
- Every screenshot referenced has a corresponding file in `images/screenshots/`.
- Every page renders correctly in light + dark themes.
- All cross-page links work.

**STOP — operator review checkpoint** (optional; operator may review now or after Chunk 4).

---

## Chunk 4: Part 2 content pages — System and Settings

Goal: complete `system.html` and `settings.html`. These are the heaviest pages — most sub-tabs, most security-sensitive content.

### Task 4.1: System page

- [ ] **Tour `https://n8n01.n8nmanagement.net/management/system`.** Sub-tabs to inventory (based on `docs/API.md` and the API service):
  - Health overview
  - Full health (detailed endpoint check)
  - System info
  - Network (interfaces, DNS, routing)
  - SSL detail
  - Cloudflare integration status
  - Tailscale integration status
  - Terminal targets
  - External services
  - Debug page

- [ ] **Capture screenshots**: ~30+ images. Heavy security flagging here:
  - SSL detail panels reveal cert paths, expiry dates, SAN entries → 🔒 flag.
  - Cloudflare panel may reveal account info, domain → 🔒 flag.
  - Tailscale panel may reveal hostname, login email, peer IPs → 🔒 flag.
  - Network panel shows internal subnets / IPs → 🔒 flag.

- [ ] **Write `system.html`.** Sub-sections in same order as the UI tabs. Use:
  - `<div class="info-box note">` for "what this view tells you"
  - `<div class="info-box tip">` for refresh and `force_refresh` parameter usage
  - `<div class="info-box warn">` for SSL renewal caveats (random sleep delay, 5-minute timeout — already documented in `docs/CERTBOT.md` and `docs/TROUBLESHOOTING.md`; cross-link to those)
  - `<div class="info-box danger">` for the "Force Renew" button — destructive in the sense it consumes Let's Encrypt rate-limit allowance.

- [ ] **Cross-link existing markdown docs** where relevant: link to `../CERTBOT.md`, `../TROUBLESHOOTING.md`, `../CLOUDFLARE.md`, `../TAILSCALE.md` since those are the canonical references for those integrations. The manual focuses on the **UI**, not the underlying mechanics.

- [ ] **Verify. Skip commit.**

### Task 4.2: Settings page

This is the largest section. Q4=A means every sub-tab and every input field gets documented.

- [ ] **Tour `https://n8n01.n8nmanagement.net/management/settings`.** Sub-tabs (per `docs/API.md`):
  - Generic settings list (with category filter)
  - NFS configuration + status
  - Tailscale management (reset, status)
  - Debug mode toggle
  - Container restart helpers
  - Access control: list IP ranges, add/edit/delete, defaults, reload nginx
  - External routes: list, add, delete
  - Email config + test + templates + preview
  - Environment variable management (list, get, update — sensitive)
  - System notification global settings
  - Cache (Redis) status, keys, flush

- [ ] **Capture screenshots**: ~50+ images. Highest density of security flags:
  - Environment variables view → 🔒 flag (may show every secret).
  - Email config → 🔒 flag (SMTP credentials).
  - NFS config → 🔒 flag (server address, mount path).
  - Tailscale reset → potentially shows auth keys → 🔒 flag.
  - Access control IP ranges → 🔒 flag (internal subnets).
  - External routes → 🔒 flag (internal target hosts).
  - Cache/Redis keys view → 🔒 flag (cached secrets possible).

- [ ] **Write `settings.html`.** Each sub-tab is its own `<section>` with:
  - Brief intro paragraph
  - Annotated screenshot
  - Field-by-field explanation table
  - Any modal/dialog covered with its own screenshot
  - Destructive actions wrapped in `<div class="info-box danger">`

- [ ] **Verify. Skip commit.**

### Chunk 4 verification

- `system.html` and `settings.html` exist with full content.
- Every modal, sub-tab, and significant input field is screenshotted.
- Security flagging is consistent across both pages.
- Cross-links to existing markdown docs work.

---

## Chunk 5: Appendix

Goal: build `appendix.html` with troubleshooting tables and the master security flag index.

### Task 5.1: Troubleshooting section

- [ ] **Read `docs/TROUBLESHOOTING.md`** in full.
- [ ] **Convert it into HTML** under `appendix.html#troubleshooting`. Use the same info-box and table styles as the rest of the manual. **Do not duplicate verbatim** — the source markdown remains canonical; the appendix presents a UI-focused summary keyed to the manual's sections, with "see the canonical [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for the complete list" pointer.

- [ ] **Add quick-reference tables**:
  - Common symptom → which manual section to consult.
  - Keyboard shortcuts (if any exist in the UI).
  - Default ports/paths that operators often look up.

### Task 5.2: Security flag index

- [ ] **Walk every HTML page** in `docs/manual/` and grep for `class="has-security-flag"` (and the `<!-- SECURITY: -->` comments).

- [ ] **Build a master index table** in `appendix.html#security-index`:

```html
<section id="security-index">
  <h2>Security Flag Index</h2>
  <p>Screenshots in this manual that contain sensitive data. Blur the indicated regions before publishing or sharing this manual outside your organization.</p>
  <table>
    <thead>
      <tr><th>Screenshot</th><th>Page</th><th>Contains</th><th>What to blur</th></tr>
    </thead>
    <tbody>
      <!-- one row per flagged screenshot -->
    </tbody>
  </table>
</section>
```

- [ ] **For each flagged screenshot, populate one row.** The "What to blur" column lists the specific UI region (e.g., "Cloudflare API token field, top right of the panel").

### Task 5.3: Verify appendix

- [ ] Open `appendix.html`. Confirm:
  - Troubleshooting section reads cleanly.
  - Security index table is complete (count rows; should match the count of `has-security-flag` figures across all pages).
  - All links to manual sections work.
  - All links to canonical markdown docs (`../TROUBLESHOOTING.md`, etc.) work.

- [ ] **Skip commit.**

---

## Chunk 6: Final QA

Goal: catch broken links, missing images, theme regressions, and accessibility issues before declaring done.

### Task 6.1: Link integrity

- [ ] **Step 1: Run a link check** across all 9 HTML files. From the project root:

```bash
cd "/Users/rsears/Google Drive/PycharmProjects/n8n_nginx/docs/manual"
# Quick sanity check - find every <a href> and report broken refs
grep -hoE 'href="[^"]+"' *.html | sort -u > /tmp/manual-links.txt
wc -l /tmp/manual-links.txt
```

Manually inspect the list for typos (`dashbboard.html`, `appendix.htm`, etc.).

- [ ] **Step 2: Click through every prev/next link** — verify the chain `index → dashboard → containers → flows → backups → notifications → system → settings → appendix → index` works and matches the table in Task 1.5.

### Task 6.2: Image integrity

- [ ] **Step 1: List all `<img src>` references**:

```bash
grep -hoE 'src="[^"]+"' docs/manual/*.html | sort -u > /tmp/manual-images.txt
wc -l /tmp/manual-images.txt
```

- [ ] **Step 2: Verify every referenced image exists**:

```bash
while IFS= read -r src; do
  path="${src#src=\"}"; path="${path%\"}"
  resolved="docs/manual/$path"
  [ -f "$resolved" ] || echo "MISSING: $path"
done < /tmp/manual-images.txt
```

Any "MISSING" line is a broken image.

- [ ] **Step 3: Verify every captured screenshot is referenced** (orphan check):

```bash
ls images/screenshots/*.png | while read f; do
  base=$(basename "$f")
  grep -lq "$base" docs/manual/*.html || echo "ORPHAN: $base"
done
```

Orphans waste disk and indicate either an unused capture (delete) or a missing reference (fix the page).

### Task 6.3: Theme parity

- [ ] **Step 1: Open `index.html`. Toggle dark theme. Walk every page.** Confirm:
  - No unreadable contrast.
  - No sections where the white-on-white or black-on-black bug appears.
  - Code blocks legible in both themes.
  - Info boxes legible in both themes.
  - Screenshot frames have visible borders in both themes.

### Task 6.4: Print preview

- [ ] **Step 1: For each of the 9 pages, run print preview** (Cmd+P → Save as PDF). Confirm:
  - Headings don't get orphaned.
  - Screenshots don't split across pages awkwardly.
  - Top nav and sidebar collapse or hide in print (add `@media print` rules if not).
  - Page numbers visible.

If print is broken, add to `styles.css`:

```css
@media print {
  .topnav, .sidebar, .pagefoot, .theme-toggle, .sidebar-toggle, .copy-btn { display: none; }
  .content { max-width: 100%; padding: 0; }
  figure.screenshot { page-break-inside: avoid; }
}
```

### Task 6.5: Accessibility quick-pass

- [ ] **Step 1: Confirm every `<img>` has descriptive `alt` text** (not empty, not "screenshot"):

```bash
grep -E '<img [^>]*alt=""' docs/manual/*.html
# Should produce no output
```

- [ ] **Step 2: Confirm every `<figcaption>` reads as a complete sentence.**

- [ ] **Step 3: Confirm color contrast** — open DevTools, check critical text against background in both themes. Should pass WCAG AA (≥4.5:1 for body, ≥3:1 for large text).

### Task 6.6: Final manifest

- [ ] **Generate a manifest** at `docs/manual/MANIFEST.txt`:

```bash
cd "/Users/rsears/Google Drive/PycharmProjects/n8n_nginx"
{
  echo "n8n Management Manual — Build Manifest"
  echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo ""
  echo "=== HTML pages ==="
  ls -1 docs/manual/*.html
  echo ""
  echo "=== Stylesheets / JS ==="
  ls -1 docs/manual/*.css docs/manual/*.js
  echo ""
  echo "=== Screenshots ==="
  ls -1 images/screenshots/*.png 2>/dev/null | wc -l
  echo "screenshots, listed below:"
  ls -1 images/screenshots/*.png 2>/dev/null
  echo ""
  echo "=== Security-flagged screenshots ==="
  grep -l 'has-security-flag' docs/manual/*.html | xargs -I{} sh -c 'echo "--- {} ---"; grep -B1 has-security-flag "{}" | grep -oE "[a-z]+-[0-9]+-[a-z-]+\.png"'
} > docs/manual/MANIFEST.txt
cat docs/manual/MANIFEST.txt
```

This is the operator's hand-off artifact — it lists everything the manual contains.

### Chunk 6 verification

- All checklists above pass.
- No broken links.
- No missing images.
- No orphaned screenshots.
- Themes legible in both modes.
- Print preview produces clean PDF.

---

## Chunk 7: Reference Guides (extension of the manual)

Goal: convert each currently-markdown User Guide and Infrastructure Doc that the live app's Help modal links to into a fully-styled HTML page under `docs/manual/`, matching the manual's look-and-feel exactly. After acceptance the markdown originals are archived (HTML becomes the single source of truth).

**Scheduling:** runs **after Chunks 3–6 are accepted.** This way the main manual's anchors (e.g., `containers.html#logs`) exist before reference guides cross-link to them.

### Pages to add

```
docs/manual/
├── backup-guide.html          ← from docs/BACKUP_GUIDE.md (751 lines, UI-heavy)
├── api-reference.html         ← from docs/API.md (2039 lines, reference tables)
├── notifications-setup.html   ← from docs/NOTIFICATIONS.md (823 lines, UI-heavy)
├── troubleshooting.html       ← from docs/TROUBLESHOOTING.md (950 lines, tables + code)
├── cloudflare-setup.html      ← from docs/CLOUDFLARE.md (701 lines, diagrams)
├── tailscale-setup.html       ← from docs/TAILSCALE.md (704 lines, diagrams)
├── certbot-ssl.html           ← from docs/CERTBOT.md (763 lines, diagrams + code)
└── migration-guide.html       ← from docs/MIGRATION.md (553 lines, procedures)
```

8 new pages. The Swagger UI / ReDoc / OpenAPI Schema links stay live (auto-generated). External Project Resources (GitHub, README) stay as external links.

### Site integration

- Add a new top-nav dropdown: **"Part 4: Reference Guides"** containing all 8 pages, grouped as the Help modal groups them (User Guides / Infrastructure Docs).
- Update `index.html` master TOC to add a Part 4 section.
- Update prev/next chains so Appendix → first reference guide → … → last reference guide → Home (and the other direction). Re-verify the chain.
- All shared header markup remains byte-identical across pages.

### Per-page conversion workflow

Each of the 8 pages follows the same recipe:

- [ ] **Step 1: Read the source markdown** verbatim into context.
- [ ] **Step 2: Plan the page**:
  - Map markdown headings to HTML `<section id>` anchors.
  - Identify info-box conversions (`> [!NOTE]`, `> [!WARNING]`, callout-block conventions) → our `.note` / `.tip` / `.warn` / `.danger` styles.
  - Identify embedded mermaid diagrams. Decide: render as SVG via mermaid CDN at runtime, or convert to a static screenshot. Recommend runtime mermaid for diagrams, since they're already in markdown form.
  - Identify which sections describe the management UI (these need fresh screenshots from the live test site).
  - Identify cross-links to other docs (`./CERTBOT.md`, etc.) → retarget to manual pages.
- [ ] **Step 3: Capture any UI screenshots** for the page using the established capture pipeline (html2canvas → upload server). Naming: `<slug>-<NN>-<descriptor>.png`, where slug is the doc filename without extension (e.g., `backup-guide-01-overview.png`).
- [ ] **Step 4: Write the HTML page** using the shell template from Task 1.3:
  - `{{PAGE_TITLE}}` = doc title
  - `{{PAGE_SLUG}}` = lowercase slug
  - `{{SIDEBAR_TOC}}` = page-level anchors from Step 2
  - `{{CONTENT}}` = converted markdown body
  - Code blocks gain copy-to-clipboard automatically via `manual.js`.
  - Mermaid diagrams render via `<pre class="mermaid">` blocks + a one-line CDN script include in this page.
  - Cross-link to relevant manual pages.
  - Wrap any sensitive figure with `class="has-security-flag"` per Q3 categories.
- [ ] **Step 5: Update top-nav** in this page AND in every other page's header (Part 4 dropdown must appear consistently across the site).
- [ ] **Step 6: Update prev/next chains** for this page and its neighbors.
- [ ] **Step 7: Verify in browser** at `http://localhost:8765/docs/manual/<slug>.html`:
  - All cross-links resolve.
  - Light/dark theme parity.
  - Mermaid diagrams render (if present).
  - Code blocks have working copy buttons.
  - Print preview clean.

### Content fidelity

- Source markdown is canonical for content. Conversion is byte-faithful where possible — don't paraphrase or trim; just re-style.
- Internal links (`./BACKUP_GUIDE.md`) get retargeted to the new HTML pages (`backup-guide.html`).
- "See [the X guide](#anchor)" cross-references inside one doc get preserved as anchor links within that page.
- Where a source-doc section duplicates manual UI coverage (e.g., the Backup Guide describing the Backups page UI), keep both — the reference guide gives the conceptual "why," the manual page gives the UI walkthrough. Cross-link them: each says "see the other for X."

### Suggested ordering inside Chunk 7

Smallest / least-UI first to validate the conversion approach quickly:
1. `migration-guide.html` (553 lines, no UI) — quickest win, validates the conversion pipeline.
2. `troubleshooting.html` (950 lines, mostly tables) — establishes table conversion patterns.
3. `certbot-ssl.html` (763 lines) — diagrams + code, no live UI.
4. `cloudflare-setup.html` (701 lines) — same shape as certbot.
5. `tailscale-setup.html` (704 lines) — same.
6. `notifications-setup.html` (823 lines) — UI-heavy, capture screenshots.
7. `backup-guide.html` (751 lines) — UI-heavy.
8. `api-reference.html` (2039 lines) — biggest, mostly reference tables. Last to land so cross-links from earlier pages resolve.

### Chunk 7 verification

- All 8 reference-guide pages exist under `docs/manual/`.
- Master TOC on `index.html` lists Part 4 with all 8 pages.
- Top nav has Part 4 dropdown on every page.
- Prev/next chain forms a complete loop: Home → … → Appendix → migration-guide → troubleshooting → … → api-reference → Home.
- Header markup byte-identical across all 17 pages (9 manual + 8 reference).
- All cross-links resolve.
- All mermaid diagrams render in both themes.
- All UI screenshots saved to `images/screenshots/` and referenced.
- Operator review: at this point the manual is "complete." Chunk 6 QA tasks (link integrity, image integrity, theme parity, print preview, manifest) are re-run against the expanded site.

### Post-Chunk-7 operator TODO

- Update the management console's Help & Documentation modal frontend to point each link at the new HTML page (e.g., `Backup Guide` → `/management/manual/backup-guide.html` if served via the app, or wherever the manual is hosted).
- Archive the legacy `docs/*.md` files.

---

## Done criteria

- 9 main manual HTML pages render correctly in light + dark themes.
- 8 reference-guide HTML pages (Chunk 7) render correctly in light + dark themes.
- Every UI section (Dashboard, Containers, Flows, Backups, Notifications, System, Settings) is documented page-by-page with annotated screenshots.
- Every modal, sub-tab, and significant input field has a corresponding screenshot.
- Every sensitive screenshot is flagged inline AND indexed in `appendix.html#security-index`.
- All 8 markdown reference docs are converted byte-faithfully to HTML and styled to match.
- `MANIFEST.txt` lists everything produced.
- Operator can open `docs/manual/index.html` and use the manual entirely offline.
- No git operations were performed by the implementer; operator handles git themselves.
- Operator's post-launch TODOs (Help-modal repoint, MD archive) are flagged in this plan and in project memory.
