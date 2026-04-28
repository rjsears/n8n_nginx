# Visual User Manual — Build & Capture Methodology

Reusable playbook for building a polished, screenshot-driven HTML user manual for any web app. Hand this file to a fresh agent (or me in a fresh session) and they should be able to build the same style of manual for a different site without further instruction.

---

## What this produces

A multi-page static HTML manual under `docs/manual/`:

- 1 cover page (`index.html`)
- N section pages, one per top-level area of the target app's UI
- 1 appendix page
- Shared `styles.css` + `manual.js` (no build step)
- Light/dark theme toggle, top-nav with section dropdowns, per-page sidebar TOC
- Annotated screenshots stored in `images/screenshots/`, referenced from `docs/manual/<page>.html` via `<figure class="screenshot">`
- Security flags (red badge) inline on any screenshot containing sensitive data, plus a master index in the appendix

The methodology assumes the operator (you) is logged into the live target app in a Chrome tab attached to a Claude Chrome extension MCP session. Everything else is automated by the agent.

---

## Operating environment

### What the agent needs running

| Service | Port | Purpose |
|---|---|---|
| Python `http.server` | 8765 | Serves the manual + screenshots for live preview during the build |
| Custom Python upload server | 8766 | Receives `POST /upload?filename=X` with image bytes; saves into `images/screenshots/` |
| Chrome with Claude MCP extension | — | Hosts both the live target-app tab AND the manual preview tab, so the agent can navigate and capture |

### Preview server

Start once, leave running for the whole build:

```
cd <project root>
python3 -m http.server 8765
```

The manual is then served at `http://localhost:8765/docs/manual/index.html`.

### Upload server

This script must exist on disk; create it once:

**`/tmp/screenshot_uploader.py`**

```python
#!/usr/bin/env python3
"""Tiny POST receiver for screenshot uploads from html2canvas."""
import http.server, os, re, sys, urllib.parse

UPLOAD_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8766
SAFE = re.compile(r"^[A-Za-z0-9._-]+$")

class Handler(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/upload":
            self.send_response(404); self._cors(); self.end_headers()
            self.wfile.write(b"not found"); return
        qs = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        filename = (qs.get("filename") or [""])[0]
        if not filename or not SAFE.match(filename) or not filename.endswith(".png"):
            self.send_response(400); self._cors(); self.end_headers()
            self.wfile.write(b"bad filename"); return
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length)
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, "wb") as f: f.write(data)
        self.send_response(200); self._cors()
        self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(b'{"ok":true,"path":"%s","bytes":%d}' % (path.encode(), len(data)))

    def log_message(self, fmt, *args):
        sys.stderr.write("[upload] " + fmt % args + "\n")

if __name__ == "__main__":
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    print(f"Upload server: dir={UPLOAD_DIR} port={PORT}", flush=True)
    http.server.HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
```

Start once per build:

```
python3 /tmp/screenshot_uploader.py "<absolute path to images/screenshots>" 8766
```

Run in the background. Leave running.

### Chrome MCP attachment

Operator opens the target site in a Chrome tab and attaches it to the Claude MCP session via the Claude Chrome extension. Operator stays logged in. Agent uses `mcp__claude-in-chrome__navigate` to switch the tab between sub-pages of the target app, and `mcp__claude-in-chrome__javascript_tool` to inject capture logic.

A second tab in the same MCP group is created by the agent (`mcp__claude-in-chrome__tabs_create_mcp`) and pointed at `http://localhost:8765/docs/manual/<page>.html` as the live preview.

---

## The capture helper

This JavaScript helper is injected into the live target-app tab via `javascript_tool`. It captures a region of the page and uploads it to the local upload server.

**The settings below are non-negotiable** — they are the result of trial-and-error against text-cutoff bugs and rendering inconsistencies. Don't change them without understanding why each one is there.

```javascript
window.__cap = (sel, filename) => new Promise((resolve, reject) => {
  const target = sel ? document.querySelector(sel) : null;
  if (sel && !target) return reject('selector not found: ' + sel);

  const opts = {
    backgroundColor: '#ffffff',     // explicit; foreignObject default is sometimes transparent
    scale: 2,                        // 2x device pixels — fixes subpixel text clipping
    logging: false,
    useCORS: true,
    foreignObjectRendering: true,    // SVG-based render; fixes text cutoff at scale: 1
    letterRendering: true,           // glyph alignment
    onclone: (doc) => {
      // Override Tailwind's truncate utilities so html2canvas never clips text
      const styleEl = doc.createElement('style');
      styleEl.textContent = `
        * { text-overflow: clip !important; }
        .truncate {
          text-overflow: clip !important;
          white-space: normal !important;
          overflow: visible !important;
        }
      `;
      doc.head.appendChild(styleEl);
    }
  };

  const PAD = 16; // CSS pixels of breathing room around element captures (16 → 32 device px after scale)

  const go = () => Promise.resolve(document.fonts && document.fonts.ready)
    .then(() => new Promise(r => setTimeout(r, 300)))
    .then(() => {
      if (target) target.scrollIntoView({block: 'start'});
      return new Promise(r => setTimeout(r, 200));
    })
    .then(() => html2canvas(document.body, opts))   // ALWAYS render the body
    .then(canvas => {
      const s = 2;
      if (!target) return canvas;                    // full-body capture: return as-is
      // Element capture: crop the target's region from the body canvas
      const rect = target.getBoundingClientRect();
      const sx = Math.max(0, (rect.left + window.scrollX - PAD) * s);
      const sy = Math.max(0, (rect.top + window.scrollY - PAD) * s);
      const sw = Math.min(canvas.width - sx, (rect.width + PAD * 2) * s);
      const sh = Math.min(canvas.height - sy, (rect.height + PAD * 2) * s);
      const out = document.createElement('canvas');
      out.width = Math.round(sw);
      out.height = Math.round(sh);
      out.getContext('2d').drawImage(canvas, sx, sy, sw, sh, 0, 0, sw, sh);
      return out;
    })
    .then(c => new Promise(r => c.toBlob(r, 'image/png')))
    .then(blob => fetch('http://localhost:8766/upload?filename=' + filename, {
      method: 'POST', body: blob, headers: {'Content-Type': 'image/png'}
    }))
    .then(r => r.json()).then(resolve, reject);

  if (window.html2canvas) return go();
  const s = document.createElement('script');
  s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
  s.onload = go;
  s.onerror = () => reject('html2canvas load failed');
  document.head.appendChild(s);
});
```

### Why these settings

| Setting | Why it's there |
|---|---|
| `scale: 2` | At `scale: 1`, html2canvas measures box height in CSS pixels but rendered text uses subpixel positioning, so glyphs at the bottom of boxes get clipped. 2x rendering eliminates the rounding error. |
| `foreignObjectRendering: true` | The default DOM-cloning renderer reflows the cloned tree, which causes text-overflow / line-height differences vs. the live page. The SVG `<foreignObject>` renderer preserves the live page's exact layout. **Caveat: only works reliably on `document.body`. Element-direct captures with this flag produce wrong content.** That's why we always render the body and then crop. |
| `letterRendering: true` | Forces per-glyph positioning instead of run-batching. Helps with custom fonts (Inter) where small kerning tweaks matter. |
| `onclone` style override | Tailwind's `.truncate` utility class hides overflow with ellipsis. In a live page that's fine. In a capture you want the full text. Override it in the clone. |
| `document.fonts.ready` wait | Web fonts (Google Fonts Inter) load asynchronously. Capturing before they're ready produces a render with system fallback fonts — wrong widths, broken layouts. Wait. |
| `200–300ms settle delay` | Even after fonts.ready, complex layouts can still be reflowing. A short delay before capture eliminates flicker artifacts. |
| Body-render-then-crop | Element-direct captures with foreignObjectRendering produce wrong content. Body render works perfectly, so render the body then crop the target's bounding rect from the resulting canvas. |
| `PAD: 16` | `getBoundingClientRect()` doesn't include shadows or sub-pixel anti-aliased edges. 16 CSS px (32 device px at scale 2) of margin guarantees no clipping at the edges of the cropped image. |
| **Canvas pre-rasterization** | `foreignObjectRendering: true` cannot capture content drawn into a `<canvas>` element (the SVG foreignObject doesn't transfer canvas pixel data). Charts (Recharts, Chart.js, D3) and any other canvas-rendered UI come out as blank white boxes. **Fix:** before calling `html2canvas`, walk all live `<canvas>` elements, call `canvas.toDataURL('image/png')` on each, store the result, then in `onclone` replace each cloned `<canvas>` with an `<img>` whose `src` is the captured data URL. |
| **Force chart redraw via `resize` event** | Many chart libraries (Recharts, Chart.js) lazy-render and only redraw their canvases when the window is resized or new data arrives. After a theme toggle (light↔dark) or any visual state change, the chart canvas may still hold the OLD theme's pixels — capturing immediately gives blank/stale charts. **Fix:** dispatch `window.dispatchEvent(new Event('resize'))` and wait 1–2 seconds before capturing. This is also a good defensive trick for full-body captures of any page with charts, even when no theme change has happened, because it guarantees the canvas pixels reflect the current visual state. Symptom of needing this: `canvas.toDataURL('image/png')` returns a tiny string (3–5 KB) when the chart is visibly populated on screen — that means the canvas bitmap is mostly empty even though the user sees lines. |
| **Modal capture: standard renderer + crop to modal element** | `foreignObjectRendering: true` does NOT correctly render `position: fixed` elements (the SVG foreignObject sandboxes layout). For modals, switch to `foreignObjectRendering: false` (the standard cloning renderer), which DOES capture position-fixed correctly. Then crop the resulting canvas to the modal's inner content rect (NOT the backdrop, NOT the entire body) using PAD=24 — generous padding so the modal feels like a focused crop with breathing room, not crammed into corners. The modal content rect is typically a child div of the `[role="dialog"]` element with sub-window dimensions (300–1100 wide, 100–1000 tall). |
| **Trim body whitespace** | Full-body captures often include large amounts of empty viewport space below AND on the sides of the actual content. Compute (a) the bottom of the last meaningful element and (b) the leftmost/rightmost extent of centered content wrappers (header content, `main`, Tailwind `.max-w-7xl`-style containers), and crop the canvas to that region + padding. Otherwise overview images end up wide and tall with whitespace borders, which renders as small images in a fixed-width content column — text becomes hard to read. The rule of thumb: every CSS pixel of whitespace baked into the PNG is a CSS pixel that the manual's figure container can't use to display actual content. |

### Calling the helper

```javascript
// Full body
window.__cap(null, 'dashboard-01-overview.png');

// Specific element (after tagging it with data-cap-id for a clean selector)
window.__cap('[data-cap-id="dashboard-stats"]', 'dashboard-02-stats-row.png');
```

The helper returns `{ok: true, path: "...", bytes: N}` on success.

### Reinstalling after navigation

`window.__cap` lives in the page's JS context. When you navigate the tab to a different URL, it gets cleared. Reinstall it (paste the helper code again) at the start of every section.

---

## Capture rules of thumb

These are the operator's preferences, baked in from feedback during the n8n_management build:

1. **One overview per page, not many close-ups.** Don't capture every individual card, chart, or sub-panel as its own image. Capture ONE comprehensive overview of the whole section, then describe each area in prose, referencing the overview. Individual close-ups make the manual cluttered and produce HUGE individual figures next to small overview figures — visual inconsistency. Reserve close-ups for genuinely different states: modals, expanded rows, edit dialogs, post-action result screens.
2. **Don't make screenshots unnecessarily long.** If a panel has 88 rows of data, set the per-page filter to 5 before expanding, OR capture only the top portion. The reader needs to understand the layout, not see every row.
3. **Consistent padding.** Always use the body-crop approach with PAD=16. Don't switch to element-direct captures even if they "look good enough" — they'll have inconsistencies.
4. **Tag with `data-cap-id`.** Don't try to write fragile CSS selectors using auto-generated Tailwind classes. Set `data-cap-id="thing-name"` on the target element via JS, then capture with `[data-cap-id="thing-name"]`.
5. **Square corners are fine.** The manual's `figure.screenshot` CSS has `border-radius: 8px` + `overflow: hidden`. Captured PNGs are square but appear rounded in context. No need to bake rounding into the PNG itself.
6. **No security blur in the PNG.** Capture sensitive content as-is; flag it with `class="has-security-flag"` in HTML so the operator can blur in their own tool before publishing.
7. **Capture rough budget.** A typical section page should have 1–6 figures: 1 overview, optionally 1 dark-theme variant, plus a handful for genuinely-different states (modals, dialogs, expanded panels). Pages with sub-tabs (e.g., a settings area with 7 tabs) get one figure per tab, no more granular than that.

---

## File and directory layout

```
<project root>/
├── docs/
│   └── manual/
│       ├── index.html         # Cover + master TOC
│       ├── <section>.html     # One per top-level UI area
│       ├── appendix.html      # Troubleshooting + master security index
│       ├── styles.css         # Shared theme
│       └── manual.js          # Theme toggle, copy-buttons, sidebar toggle
└── images/
    └── screenshots/
        └── <section>-<NN>-<descriptor>.png
```

### Naming convention

```
<section-slug>-<two-digit-sequence>-<short-descriptor>.png
```

Examples:
- `dashboard-01-overview.png`
- `dashboard-02-header.png`
- `settings-09-environment-required-expanded.png`

The two-digit sequence puts files in reading order alphabetically.

---

## Style system

### CSS

Use design tokens (CSS custom properties) for theming. Define light + dark in two `:root` blocks:

```css
:root {
  --bg: #fafafa; --surface: #ffffff; --text: #1f2937;
  --accent: #2563eb; --border: #e5e7eb;
  --note-bg: #dbeafe; --note-border: #1e40af; /* etc. */
  --radius: 8px; --topnav-h: 56px; --sidebar-w: 260px;
}
:root[data-theme="dark"] {
  --bg: #0d1117; --surface: #161b22; --text: #e5e7eb;
  /* ... */
}
```

JavaScript persists the chosen theme to `localStorage` and sets `data-theme` on `<html>`.

### Layout

- **Top nav**: `position: sticky; top: 0; z-index: 100;` — visible on every page, byte-identical markup across pages.
- **App grid**: `grid-template-columns: 260px 1fr` for sidebar + content. Collapses to single column at `< 900px`.
- **Sidebar**: `position: sticky; top: var(--topnav-h);` with its own scroll.
- **Content**: `max-width: 900px` for comfortable line length.

### Components

- **`figure.screenshot`** — wraps every captured PNG. `border-radius: 8px; overflow: hidden;` rounds corners. `figcaption` provides the caption.
- **Info boxes** — `.info-box.note` / `.tip` / `.warn` / `.danger` / `.security`. Border-left 4px solid the variant color. Leading emoji.
- **Code blocks** — `<pre>` with copy-to-clipboard button injected by `manual.js`.
- **Tables** — zebra-striped via `tbody tr:nth-child(even)`.
- **Step lists** — `<ol class="steps">` with circular numbered badges via `::before`.

### Fonts

- Body: **Inter** (Google Fonts), system fallback
- Code: **JetBrains Mono**, monospace fallback

---

## HTML page template

Every section page uses this skeleton. Substitute four variables: `{{PAGE_TITLE}}`, `{{PAGE_SLUG}}`, `{{SIDEBAR_TOC}}`, `{{CONTENT}}`, plus prev/next links.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{PAGE_TITLE}} — <Site> Manual</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body data-page="{{PAGE_SLUG}}">
  <header class="topnav">
    <a class="brand" href="index.html"><Site> Manual</a>
    <nav class="topnav-links">
      <a href="index.html">Home</a>
      <details class="topnav-dropdown">
        <summary>Part 1: User Guide</summary>
        <div class="dropdown-menu">
          <!-- one <a> per Part 1 page -->
        </div>
      </details>
      <details class="topnav-dropdown">
        <summary>Part 2: Administration</summary>
        <div class="dropdown-menu">
          <!-- one <a> per Part 2 page -->
        </div>
      </details>
      <a href="appendix.html">Appendix</a>
    </nav>
    <button id="themeToggle" class="theme-toggle" type="button">🌙 Dark</button>
    <button id="sidebarToggle" class="sidebar-toggle" type="button" aria-label="Toggle sidebar">☰</button>
  </header>
  <div class="app">
    <aside class="sidebar">
      <h2 class="sidebar-title">On this page</h2>
      <ul class="sidebar-toc">
        {{SIDEBAR_TOC}}
      </ul>
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

**The `<header class="topnav">` block must be byte-identical across every page.** Future updates (e.g., adding a new section) must apply uniformly to every page's header.

---

## Per-page workflow

For each section of the target app:

1. **Navigate** the live tab: `mcp__claude-in-chrome__navigate(tabId, url)`
2. **Wait** for the page to load and fonts to settle
3. **Reinstall** `window.__cap` via `javascript_tool`
4. **Tour** the page — `read_page` with `filter: "interactive"` to inventory buttons/links/inputs; click through tabs and modals to discover IA
5. **Tag** elements you want to capture: `el.setAttribute('data-cap-id', 'thing-name')`
6. **Capture** in batches via `window.__cap`. Always do full-body for overview, then individual element crops for sub-sections
7. **Capture states** — light theme, dark theme, modals open, etc.
8. **Write** the HTML page using the template above. Embed each figure with `<figure class="screenshot"><img src="../../images/screenshots/{filename}" alt="..."><figcaption>Figure N: ...</figcaption></figure>`
9. **Cross-link** to other pages where appropriate
10. **Flag security-sensitive figures** with `class="has-security-flag"` and a `<div class="security-flag">SECURITY: blur X before publishing</div>` inside the figure

---

## Security flagging

When a screenshot exposes any of the following, wrap the figure with `class="has-security-flag"`:

- API tokens, OAuth tokens, JWT secrets
- Database passwords or connection strings
- SSL private key paths or contents
- Internal IP addresses, MAC addresses, subnets, hostnames
- User email addresses (when not the operator's own / test accounts)
- Webhook URLs that include auth tokens
- Tunnel IDs (Cloudflare, Tailscale)
- Anything visibly displaying secrets (`.env` contents, credentials lists)

Format:

```html
<figure class="screenshot has-security-flag">
  <img src="../../images/screenshots/foo.png" alt="...">
  <figcaption>Figure N: ...</figcaption>
  <div class="security-flag">SECURITY: Blur the API token field before publishing.</div>
</figure>
```

The appendix page has a master Security Flag Index — a table generated by walking every page for `class="has-security-flag"` and listing each flagged screenshot with its location and what to blur.

---

## Information architecture

Default structure for a typical operator-facing app:

- **Cover (`index.html`)** — intro, master TOC, legend (info-box variants), how to read the manual
- **Part 1: User Guide** — everyday operations the user does most often (in observed-usage order)
- **Part 2: Administration** — system-level configuration and integrations
- **Part 3: Appendix** — troubleshooting tables + Security Flag Index

Each Part has a top-nav dropdown listing its pages.

For each page, the sidebar TOC lists in-page anchors (`<h2>` and `<h3>` IDs). Anchor IDs use kebab-case nouns (e.g., `#row-actions`, `#config-storage`).

---

## Known issues & fixes

| Symptom | Cause | Fix |
|---|---|---|
| Text cut off at bottom of cards | `scale: 1` subpixel rendering | Use `scale: 2` |
| Text horizontally clipped (e.g., "Sort by Date" cut to "Sort b") | Tailwind `.truncate` ellipsis | Use `onclone` to override `text-overflow: ellipsis` |
| Element capture renders wrong content | `foreignObjectRendering: true` + element-direct doesn't work | Always render body, then crop |
| Both sides of cropped element clipped | `getBoundingClientRect` doesn't include shadow/anti-aliased edges | Add `PAD: 16` CSS px of margin |
| Renderer timeouts during capture | Heavy DOM, many DOM mutations in flight | Wait 300–500ms after fonts.ready before calling html2canvas; retry on timeout |
| `data:image/png;base64,...` returned by JS gets blocked in tool response | Base64 strings hit a tool guard | Don't return image data inline; POST to local upload server instead |
| `chrome-error://chromewebdata/` unable to reach the test site | Internal-DNS / Cloudflare ECH issue (temporary) | Wait 5 minutes, retry |
| `docker run` from inside Python in the management container fails with AppArmor in LXC | Backend bug — needs `--security-opt apparmor=unconfined` on every `docker run` shell call | Search `grep -rn '"docker", "run"' <api dir> --include="*.py"` and add the flag. Symptom: API returns HTTP 200 with body `{"status":"failed","error":"Failed to start <X> container"}` |

---

## Workflow / process

1. **Brainstorm** the manual scope with the operator — what target app, what pages, what level of detail (per-modal, per-button?), what counts as sensitive
2. **Write a design doc** at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` with the full IA + visual design + screenshot policy
3. **Write a plan** at `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` with the page-by-page checklist
4. **Build the foundation** (Chunk 1): `styles.css`, `manual.js`, cover page, stub pages, theme toggle, navigation working end-to-end. Operator reviews look-and-feel before content
5. **Build one reference page** (Chunk 2): pick the most representative section, capture and write it fully. Operator reviews format
6. **Build the rest** of the section pages mechanically, following the format
7. **Build the appendix** (troubleshooting + security index)
8. **Final QA**: link integrity, image integrity (no orphans, no broken refs), theme parity, print preview, manifest

Use TaskCreate / TaskUpdate to track each chunk's progress. Save chunk completion notes to project memory so future sessions can resume.

---

## Operator preferences (project-portable)

These came up during the n8n_management build and are worth carrying forward:

- **No git operations from the agent.** Edit local files only. The operator handles all branches, commits, pushes, and PRs themselves. Adding an agent's name to a commit message (e.g., `Co-Authored-By: Claude`) is not acceptable.
- **No PRs created by the agent**, even if the project's CLAUDE.md says otherwise — operator preference overrides.
- **Capture from a real running deployment**, not from mockups. Screenshots reflect actual data, then the operator blurs sensitive parts post-build using the security flags.
- **Don't make screenshots unnecessarily long.** Collapse panels, paginate, narrow filters before capturing. If 5 rows convey the layout, don't capture 88.
- **Don't add individual close-ups for items that look the same.** A row of 4 stat cards captured once as a row is enough — don't separately capture each stat card.
- **Square PNGs are fine**; the figure wrapper rounds them via CSS.

---

## Quick-start checklist (for a new project)

When starting a manual for a different site:

- [ ] Confirm what target app you're documenting and the operator's URL
- [ ] Operator opens the target app in a Chrome MCP-attached tab and stays logged in
- [ ] Start the preview server (`python3 -m http.server 8765`) from the new project root
- [ ] Confirm `/tmp/screenshot_uploader.py` exists, or recreate from this doc
- [ ] Start the upload server pointing at the new project's `images/screenshots/` dir
- [ ] Read this doc end-to-end if not already familiar
- [ ] Brainstorm + design + plan with the operator (don't skip even if the project seems simple)
- [ ] Build the foundation, get review, build first reference page, get review
- [ ] Mechanically build remaining pages
- [ ] Build appendix
- [ ] Final QA
