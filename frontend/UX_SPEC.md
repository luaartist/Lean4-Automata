# Lean4-Automata Frontend — UX Design Spec

> Next.js 15 App Router · React Flow · React Query + Zustand · API at `localhost:8000/api/v1`

---

## 1. Information Architecture

### Page Tree

| Route | Purpose | Primary Tasks |
|---|---|---|
| `/` | Dashboard / project list | Pick project, view global search, see recent activity |
| `/projects/[name]` | Project overview | Browse modules, view project-level dep graph, metrics summary |
| `/projects/[name]/modules/[mod]` | Module detail | Inspect module metrics, list symbols, view module-scoped dep graph |
| `/projects/[name]/modules/[mod]/symbols/[sym]` | Symbol detail | Read signature/docstring, trace dependencies in/out, view usages |
| `/search` | Global search results | Full-text search across all symbols, filter & drill down |
| `/settings` | User preferences | Theme toggle, graph defaults, keyboard shortcut reference |

### Navigation Model
- **Breadcrumb trail** always visible: Home → Project → Module → Symbol
- **Sidebar** drives primary nav (project tree + module list)
- **Deep links** — every view fully represented in URL (shareable)

---

## 2. Layout

### App Shell (desktop)

```
┌─────────────────────────────────────────────────┐
│  Header  (56px)  [logo] [search] [theme] [user] │
├────────┬────────────────────────┬───────────────┤
│Sidebar │       Main Content     │  Right Rail   │
│ 240px  │       flex-1           │   320px       │
│        │                        │  (collapsible)│
└────────┴────────────────────────┴───────────────┘
```

- **Header**: global search (⌘K), theme toggle, breadcrumbs on mobile
- **Sidebar**: project picker → module tree; collapsible
- **Main**: page content, dep graph canvas
- **Right Rail**: contextual detail (symbol card, filters); collapses on ≤ tablet

### Breakpoints

| Token | Range | Layout changes |
|---|---|---|
| `mobile` | < 640px | Sidebar → hamburger drawer; right rail hidden; single-column |
| `tablet` | 640–1024px | Sidebar collapsed (icons only, 64px); right rail overlay |
| `desktop` | > 1024px | Full 3-column layout |

---

## 3. Component Inventory

| Component | Key Props | Notes |
|---|---|---|
| **ProjectPicker** | `projects[]`, `selected`, `onSelect` | Dropdown + search; sticky top of sidebar |
| **SearchBar** | `query`, `onChange`, `onSubmit`, `hotkey` | ⌘K activation; 250ms debounce; combobox pattern |
| **ModuleList** | `modules[]`, `activeModule`, `onSelect`, `sortBy` | Virtualized for > 200 items; sort by name/metric |
| **SymbolDetailCard** | `symbol`, `isLoading`, `onNavigateDep` | Signature, docstring, kind badge, dep links |
| **DepGraph** | `nodes[]`, `edges[]`, `layout`, `onNodeClick`, `maxNodes` | React Flow canvas; see §4 |
| **FilterPanel** | `filters`, `onChange`, `onReset` | Collapsible accordion sections; see §5 |
| **Breadcrumbs** | `segments[]` | Auto-generated from route params |
| **MetricsSummary** | `metrics{}` | Sparkline bars for loc, complexity, dep count |
| **EmptyState** | `icon`, `title`, `description`, `action?` | Reusable across all surfaces |
| **ErrorBanner** | `error`, `onRetry` | Inline or toast; retry action |
| **SSEIndicator** | `connected`, `lastEvent` | Subtle pulse dot in header |

---

## 4. Dependency Graph (React Flow)

### Node Types

| Type | Shape | Content | Badge |
|---|---|---|---|
| **SymbolNode** | Rounded rect 180×48 | `name` + kind icon | In/out degree |
| **ModuleNode** | Rounded rect 220×56, dashed border | `module_path` | Symbol count |
| **ClusterNode** | Rounded rect, muted fill | `"N nodes"` label | Expand affordance |

### Edge Styles

| `dependency_type` | Stroke | Dash | Color token |
|---|---|---|---|
| `direct` | 2px solid | — | `--edge-direct` (blue-500) |
| `import` | 2px solid | — | `--edge-import` (green-500) |
| `implicit` | 1.5px | 4-2 dash | `--edge-implicit` (amber-500) |
| `indirect` | 1px | 6-3 dash | `--edge-indirect` (gray-400) |

### Interaction
- **Pan/zoom**: scroll + drag; pinch on touch
- **Minimap**: bottom-right, 160×100; toggle-able
- **Controls**: zoom in/out, fit-view, lock-toggle (top-right overlay)
- **Node click** → navigate to symbol/module detail; highlight connected edges
- **Hover** → tooltip with full name, kind, metric summary
- **Multi-select**: Shift+click → batch highlight / filter

### Clustering
- **Threshold**: > 150 visible nodes → auto-cluster by module
- Cluster expand on double-click; breadcrumb shows cluster context
- User can adjust threshold in settings (50 / 150 / 300 / unlimited)

### Layout
- Default: `dagre` top-to-bottom for dependency direction
- Toggle: force-directed layout for exploration
- Persist layout choice per project in Zustand `graphView` slice

---

## 5. Search & Filter Panel

### Filter Dimensions

| Dimension | Control | Values |
|---|---|---|
| `kind` | Multi-select chips | `theorem`, `def`, `lemma`, `instance`, `structure`, `class`, `axiom`, `inductive` |
| `project` | Dropdown (single) | Dynamic from API |
| `visibility` | Toggle group | `public` / `private` / `all` |
| `deprecated` | Checkbox | Include deprecated (default: off) |
| `depth` | Slider (1–5) | Dependency traversal depth for graph |

### Behavior
- **Debounce**: 250ms on text input; immediate on select/toggle
- **URL sync**: all filters serialized to search params (`?kind=def,lemma&vis=public&depth=2`)
- On page load, initialize filters from URL params → Zustand → React Query keys
- **Reset** button clears all filters and URL params
- Result count badge updates reactively

---

## 6. State Model

### Zustand Slices

| Slice | Keys | Persistence |
|---|---|---|
| `uiPrefs` | `theme`, `sidebarOpen`, `rightRailOpen`, `clusterThreshold` | `localStorage` |
| `graphView` | `layout`, `zoomLevel`, `selectedNodes[]`, `hoveredNode` | Session only |
| `filters` | `kind[]`, `project`, `visibility`, `deprecated`, `depth`, `query` | URL search params |

### React Query Key Map

| Key | Endpoint | Stale time |
|---|---|---|
| `['symbols', fullName]` | `GET /symbols/{full_name}` | 5 min |
| `['symbols', 'search', filters]` | `GET /symbols/search?…` | 2 min |
| `['deps', 'graph', params]` | `GET /dependencies/graph?…` | 5 min |
| `['modules', 'metrics', mod]` | `GET /modules/metrics?module=…` | 5 min |

### SSE Invalidation (`/events/invalidation`)
- On message `{ path, file_id, symbols }`:
  - Invalidate `['symbols', sym]` for each `sym` in `symbols`
  - Invalidate `['deps', 'graph', *]` if any affected symbol is in current graph
  - Invalidate `['modules', 'metrics', mod]` where `mod` matches `path`
- Reconnect with exponential backoff: 1s → 2s → 4s → max 30s
- Show `SSEIndicator` disconnect state after 5s without heartbeat

---

## 7. Design Tokens

### Color Palette

| Token | Light | Dark |
|---|---|---|
| `--bg-primary` | `#ffffff` | `#0f1117` |
| `--bg-secondary` | `#f4f5f7` | `#1a1d27` |
| `--bg-surface` | `#ffffff` | `#232631` |
| `--text-primary` | `#1a1a2e` | `#e4e5e9` |
| `--text-secondary` | `#5c5f6e` | `#9395a1` |
| `--border-default` | `#d1d5db` | `#3a3d4a` |
| `--accent-primary` | `#2563eb` | `#3b82f6` |
| `--accent-hover` | `#1d4ed8` | `#60a5fa` |
| `--status-error` | `#dc2626` | `#f87171` |
| `--status-warning` | `#d97706` | `#fbbf24` |
| `--status-success` | `#16a34a` | `#4ade80` |
| `--edge-direct` | `#2563eb` | `#60a5fa` |
| `--edge-import` | `#16a34a` | `#4ade80` |
| `--edge-implicit` | `#d97706` | `#fbbf24` |
| `--edge-indirect` | `#9ca3af` | `#6b7280` |

### Spacing Scale
- `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96` px (base unit = 4px)

### Type Scale
| Token | Size | Weight | Use |
|---|---|---|---|
| `--text-xs` | 12/16 | 400 | Badges, captions |
| `--text-sm` | 14/20 | 400 | Secondary text, table cells |
| `--text-base` | 16/24 | 400 | Body, inputs |
| `--text-lg` | 18/28 | 500 | Section headings |
| `--text-xl` | 24/32 | 600 | Page titles |
| `--text-2xl` | 30/36 | 700 | Dashboard hero |
| `--text-mono` | 14/20 | 400 | Code, signatures (monospace) |

### Focus Ring
- `2px solid var(--accent-primary)` with `2px offset`
- High-contrast mode: `3px solid #000` / `#fff` (auto by theme)

---

## 8. Accessibility

### Keyboard Navigation
- **⌘K** / **Ctrl+K**: Focus global search
- **Tab**: Standard focus order — header → sidebar → main → right rail
- **Arrow keys**: Navigate within module list, filter chips, graph nodes
- **Enter/Space**: Activate focused element
- **Escape**: Close overlays, deselect graph, clear search
- **?**: Open keyboard shortcut reference overlay

### Graph Accessibility
- `role="application"` on graph canvas with `aria-label="Dependency graph"`
- Each node: `role="button"`, `aria-label="{name} ({kind}), {N} dependencies"`
- **Roving tabindex** across nodes; arrow keys to traverse connected edges
- Screen-reader-only table fallback listing all nodes + edges (toggle-able)
- Announcements via `aria-live="polite"` on node focus/selection changes

### Focus Order
1. Skip-to-content link
2. Header (search → theme → user)
3. Sidebar (project picker → module list)
4. Main content (breadcrumbs → primary surface → graph)
5. Right rail (detail card → filters)

### Color Contrast
- All text: minimum **4.5:1** against background (WCAG AA)
- UI controls / graph edges: minimum **3:1**
- Edge colors verified in both themes; edge dash pattern provides non-color differentiator
- Dependency types distinguished by stroke style (solid/dash) + color (redundant encoding)

---

## 9. Empty / Loading / Error States

| Surface | Empty | Loading | Error |
|---|---|---|---|
| **Project list** | Illustration + "No projects found" + import CTA | Skeleton cards (3) | Inline banner + retry |
| **Module list** | "No modules in project" | Skeleton lines (8) | Toast + retry |
| **Symbol detail** | — (404 → redirect to module) | Skeleton card with shimmer | "Symbol not found" + back link |
| **Dep graph** | "Select a node or search to explore" | Canvas spinner + "Loading graph…" | "Failed to load graph" + retry |
| **Search results** | "No results for '{query}'" + filter suggestions | Skeleton rows (5) | Inline error + retry |
| **Filter panel** | All defaults shown | Disabled + skeleton | Silent fallback to defaults |
| **SSE connection** | — | Pulsing dot (connecting) | Orange dot + "Reconnecting…" tooltip |

### Patterns
- Skeleton placeholders match component dimensions to avoid layout shift
- Loading states appear after **150ms** delay (avoid flash for fast responses)
- Error states always include a retry action where applicable
- Empty states suggest next action to guide user

---

## 10. Performance & UX Budgets

| Metric | Target | Measurement |
|---|---|---|
| **LCP** | ≤ 1.2s | Dashboard / project page |
| **INP** | ≤ 100ms | Any interaction |
| **CLS** | ≤ 0.05 | All pages |
| **TTFB** | ≤ 200ms | App shell (SSR streaming) |
| **Search response** | ≤ 300ms | Debounce (250ms) + API round-trip |
| **Graph initial render** | ≤ 500ms | ≤ 150 nodes |
| **Graph render (large)** | ≤ 1.5s | 150–500 nodes (clustered) |
| **Graph max nodes** | 500 | Hard cap; prompt user to filter |
| **SSE reconnect** | ≤ 30s | Max backoff ceiling |
| **Bundle size (initial)** | ≤ 120kB gzip | JS; React Flow lazy-loaded |

### Strategies
- React Flow + graph layout engine: dynamic `import()` (route-level split)
- Module list virtualized via `react-window` at > 100 items
- React Query `staleTime` prevents redundant fetches; SSE provides freshness
- Image/icon assets: SVG sprites, no raster images
- Prefetch adjacent routes on hover (Next.js `<Link prefetch>`)

---

*Spec version: 1.0 · Last updated: 2025*
