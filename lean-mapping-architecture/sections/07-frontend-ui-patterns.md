# Frontend UI Patterns

## Three-Layer Exploration Model

```
Layer 1 – Project Overview     /projects/{name}
  │  Module-level dependency graph + project metrics
  ▼
Layer 2 – Module Detail        /projects/{name}/modules/{mod}
  │  Symbol list (filterable) + symbol-level graph
  ▼
Layer 3 – Symbol Detail        /…/symbols/{sym}
     Metadata card · dependency subgraph · code preview
```

Each layer deepens context; breadcrumbs allow instant back-navigation.

## Graph Interaction

| Action | Behaviour |
|--------|----------|
| Click node | Navigate to next layer |
| Hover node | Tooltip with kind + signature |
| Scroll wheel | Zoom |
| Drag canvas | Pan |
| Ctrl + click | Multi-select for subgraph export |
| Escape | Deselect |

Custom node component renders a coloured badge per `symbol.kind`:

| Kind | Colour | Hex |
|------|--------|-----|
| theorem | Blue | `#2563eb` |
| def | Purple | `#7c3aed` |
| axiom | Red | `#dc2626` |
| instance | Green | `#059669` |

All colours meet WCAG 2.1 AA contrast (≥ 4.5:1 on white).

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + K` | Open command palette / search |
| `Cmd/Ctrl + B` | Toggle sidebar |
| `Escape` | Close modals / deselect graph |
| Arrow keys (when graph focused) | Navigate between nodes |
| `Enter` | Select focused node |

## Accessibility

- **Skip links** at page top: "Skip to content", "Skip to graph".
- **ARIA live region** announces focused-node changes for screen readers.
- **Table alternative** – every graph has a toggle to show raw data as an
  accessible `<table>` with `<caption>` and `scope="col"` headers.
- **Focus indicators** – 2 px ring on all interactive elements.

## Search UX

- Debounced input (300 ms).
- Results appear below input with highlighted match reason.
- Facet filters: kind, project, attributes.
- `useSearch` hook skips fetch until ≥ 3 characters.

## Export

Users can export the current graph via toolbar buttons:

| Format | MIME | Use case |
|--------|------|----------|
| Cytoscape JSON | `application/json` | Re-import into Cytoscape desktop |
| GraphML | `application/xml` | Gephi |
| SVG | `image/svg+xml` | Embed in papers / presentations |

## Performance Budget

| Metric | Target |
|--------|--------|
| Time to Interactive | < 3 s |
| Largest Contentful Paint | < 2.5 s |
| Graph render (1 000 nodes) | < 1 s |
| Bundle size (gzipped) | < 250 KB (initial route) |

Graph layout computation offloaded to a Web Worker when node count > 500.
