# Frontend Engineer — Role Anchor

> 10 most likely questions a Frontend Engineer will ask, answered with file paths and code examples.

---

## Q1. Where is the forum UI and how is it structured?

**File:** `ui/lean4a_forum.html` — a **single self-contained HTML file** (~900 lines) with no build step.

Structure:
- **Lines 1–448:** `<style>` block — CSS custom properties (dark theme), responsive 3-column grid, Bootstrap 5.3 overrides, JSON syntax highlighting classes.
- **Lines 449–650 (approx):** HTML body — Bootstrap grid with three panels:
  1. **Left sidebar** — flow buttons generated from `flow_definitions.json`
  2. **Center panel** — live log output with SSE streaming
  3. **Right panel** — ticket history (expand/collapse)
- **Lines 650+ :** `<script>` block — vanilla JavaScript, SSE EventSource, DOM manipulation, auto-refresh toggle.

External dependencies (loaded from CDN):
- Bootstrap 5.3.3 (CSS + JS)
- Font Awesome 6.4.2 (icons)
- No React, no bundler, no framework.

---

## Q2. How does the UI discover and render flow buttons?

The UI fetches flow definitions from the Go backend on page load:

```javascript
async function loadFlows() {
    const resp = await fetch(`${API_BASE}/flows`);
    const flows = await resp.json();
    flows.forEach(flow => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline-primary w-100 mb-2';
        btn.textContent = flow.description || flow.name;
        btn.onclick = () => runFlow(flow.name, {});
        sidebar.appendChild(btn);
    });
}
```

The static definitions are stored in **`ui/flow_definitions.json`** (12 flows). Each entry has:

```json
{
  "name": "lean_sorry_scan",
  "description": "Scan all indexed files for sorry/admit usage",
  "params_schema": { "type": "object", "properties": {} },
  "tags": ["lean", "quality"],
  "handler_type": "builtin"
}
```

Tags are used for badge coloring (lean = blue, gpu = orange, system = green).

---

## Q3. How does `API_BASE` get resolved? Can I point it elsewhere?

```javascript
const API_BASE = window.location.hostname === 'localhost'
    ? 'http://localhost:8443'
    : `${window.location.protocol}//${window.location.host}`;
```

- **Local development:** Hardcoded to `http://localhost:8443` (the Go forum's default port).
- **Production / remote:** Uses the same origin the page was served from.

To override for a custom environment, either:
1. Edit the constant directly in `lean4a_forum.html`, or
2. Set `window.LEAN4A_API_BASE` before the script block and change the detection to `window.LEAN4A_API_BASE || ...`.

---

## Q4. How does the SSE flow-execution stream work?

When a user clicks a flow button, the UI calls `runFlow(name, params)`:

```javascript
async function runFlow(name, params) {
    const resp = await fetch(`${API_BASE}/run/flow/${name}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        // Parse SSE lines: "event: log\ndata: {...}\n\n"
        parseSSE(text);
    }
}
```

The Go backend emits three event types:
1. **`event: log`** — Intermediate log messages during execution
2. **`event: result`** — Final structured JSON result
3. **`event: done`** — Flow completed (includes ticket ID, duration_ms, status)

The center panel renders `log` events in real-time. On `done`, the ticket is added to the right panel.

---

## Q5. How does JSON syntax highlighting work?

**File:** `ui/lean4a_forum.html` — CSS classes + a custom `highlightJSON()` function.

CSS classes:
```css
.json-key     { color: #82aaff; }
.json-string  { color: #c3e88d; }
.json-number  { color: #f78c6c; }
.json-boolean { color: #c792ea; }
.json-null    { color: #ff5370; font-style: italic; }
```

The JavaScript function walks the JSON string and wraps tokens in `<span>` tags:

```javascript
function highlightJSON(obj) {
    const json = JSON.stringify(obj, null, 2);
    return json
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/: "([^"]*)"/g, ': <span class="json-string">"$1"</span>')
        .replace(/: (\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
        .replace(/: (true|false)/g, ': <span class="json-boolean">$1</span>')
        .replace(/: (null)/g, ': <span class="json-null">$1</span>');
}
```

Highlighted JSON is rendered inside a `<pre><code>` block in the log panel.

---

## Q6. How does the dark theme work and how can I customize it?

The theme uses CSS custom properties defined at the `:root` level:

```css
:root {
    --bg-primary:    #1a1a2e;
    --bg-secondary:  #16213e;
    --bg-tertiary:   #0f3460;
    --text-primary:  #e0e0e0;
    --text-secondary:#a0a0b0;
    --accent-primary:#00d4ff;
    --accent-success:#00e676;
    --accent-warning:#ffab40;
    --accent-danger: #ff5252;
    --border-color:  #2a2a4a;
    --card-shadow:   0 4px 6px rgba(0,0,0,0.3);
}
```

All components reference these variables. To create a light theme, override the variables:

```css
[data-theme="light"] {
    --bg-primary:    #ffffff;
    --bg-secondary:  #f5f5f5;
    --text-primary:  #212121;
    /* ... */
}
```

The Bootstrap theme is forced to dark via `data-bs-theme="dark"` on `<html>`.

---

## Q7. How does the ticket panel work?

Tickets are stored server-side in SQLite (`tickets` table) and fetched by the UI:

```javascript
async function loadTickets() {
    const resp = await fetch(`${API_BASE}/tickets`);
    const tickets = await resp.json();
    renderTicketList(tickets);
}
```

Each ticket card shows:
- **Flow name** + **status badge** (success = green, error = red, timeout = orange)
- **Duration** in milliseconds
- **Expand/collapse** toggle to show full input and output JSON
- **Ticket ID** (format: `tk_<ULID>`)

The panel auto-refreshes when:
1. A new flow completes (the `done` SSE event triggers `loadTickets()`)
2. The user toggles the auto-refresh switch (polls every 10 seconds)

---

## Q8. How does the UI handle connection status badges?

Three status badges appear in the header:

| Badge | Checks | Method |
|---|---|---|
| **Python API** | `GET ${LEAN_DB_URL}/health/ready` (proxied through Go) | Fetch with 3s timeout |
| **Lean DB** | Included in health response (`db: true/false`) | Same response |
| **TPH GPU** | `GET ${TPH_SERVER_URL}/status` | Fetch with 3s timeout |

```javascript
async function checkStatus() {
    try {
        const resp = await fetch(`${API_BASE}/status`, { signal: AbortSignal.timeout(3000) });
        const data = await resp.json();
        updateBadge('python-api', data.api_ok);
        updateBadge('lean-db', data.db_ok);
        updateBadge('tph-gpu', data.tph_ok);
    } catch {
        ['python-api', 'lean-db', 'tph-gpu'].forEach(id => updateBadge(id, false));
    }
}
```

Badges use Font Awesome icons: `fa-circle-check` (green) or `fa-circle-xmark` (red).

---

## Q9. What XSS protections are in place and what should I maintain?

From the security audit (commit `4a3c84a`):

**Server-side (Go):**
- SSE output is JSON-encoded — no raw HTML is emitted in event data.
- Request body limited to 1 MB to prevent memory-based attacks.
- Flow names are validated against the compile-time `flowRegistry` map — no arbitrary strings reach shell execution.

**Client-side (HTML):**
- The `highlightJSON()` function operates on `JSON.stringify()` output, which escapes `<`, `>`, `&` in strings.
- Log messages are rendered via `textContent` (not `innerHTML`) for plain text; JSON is rendered via `innerHTML` after `highlightJSON()` sanitizes through `JSON.stringify()`.

**What to maintain:**
- Never use `innerHTML` with unsanitized user input.
- Always pass user-facing text through `textContent`.
- When displaying flow output JSON, always route through `JSON.stringify()` → `highlightJSON()`.
- If adding markdown rendering, use a sanitizing library (e.g., DOMPurify).

---

## Q10. How do I add a new panel or section to the 3-column layout?

The layout uses a CSS Grid with named areas:

```css
.forum-grid {
    display: grid;
    grid-template-columns: 280px 1fr 350px;
    grid-template-areas: "sidebar main tickets";
    gap: 1rem;
    height: calc(100vh - 80px);  /* below header */
}
```

To add a fourth column (e.g., a metrics panel):

```css
.forum-grid {
    grid-template-columns: 250px 1fr 300px 300px;
    grid-template-areas: "sidebar main tickets metrics";
}
```

```html
<div class="metrics-panel" style="grid-area: metrics;">
    <!-- new content -->
</div>
```

For responsive behavior, the CSS includes a media query:

```css
@media (max-width: 992px) {
    .forum-grid {
        grid-template-columns: 1fr;
        grid-template-areas: "sidebar" "main" "tickets";
    }
}
```

Update this too to include your new area or consider collapsing it on mobile.
