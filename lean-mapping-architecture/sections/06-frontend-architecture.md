# Frontend Architecture

## Technology Choice

| Concern | Decision |
|---------|----------|
| Framework | Next.js 15 (App Router) + React 19 |
| Rendering | Server Components for data-heavy views; Client Components for interactivity |
| State | Zustand (global), React Query (server state) |
| Styling | Tailwind CSS 3.4 + CSS variables for theming |
| Graph | React Flow 11 (custom nodes, minimap) |
| Charts | Recharts 2.12 |
| Testing | Vitest (unit), Playwright (E2E) |

## Directory Layout

```
frontend/
├── app/                        # Next.js App Router pages
│   ├── layout.tsx
│   ├── page.tsx                # Landing / project selector
│   ├── projects/[name]/
│   │   ├── page.tsx            # Project overview  (Layer 1)
│   │   └── modules/[mod]/
│   │       ├── page.tsx        # Module detail     (Layer 2)
│   │       └── symbols/[sym]/
│   │           └── page.tsx    # Symbol detail     (Layer 3)
│   ├── search/page.tsx
│   └── api/proxy/[...path]/route.ts
├── components/
│   ├── visualizations/         # DependencyGraph, SymbolChart, MiniMap
│   ├── exploration/            # BreadcrumbNav, SymbolList, ModuleExplorer
│   ├── search/                 # SearchBar, FilterPanel
│   └── ui/                     # Button, Dialog, Tooltip, ErrorBoundary
├── lib/
│   ├── api/                    # Typed fetch client + endpoint map
│   ├── graph/                  # Layout algorithms, transformers
│   └── hooks/                  # useSymbol, useDependencies, useSearch
├── state/                      # Zustand store + slices
└── styles/                     # Tailwind globals, themes
```

## Server vs Client Components

| Component | Rendered on | Reason |
|-----------|------------|--------|
| Project overview data table | Server | Large JSON, no interactivity |
| Dependency graph canvas | Client | Pan/zoom/click |
| Search results list | Client | Real-time filtering |
| Symbol metadata card | Server | Static read |
| Breadcrumb nav | Server | Pure HTML links |

## API Client

A singleton `APIClient` class wraps `fetch` with:
- Typed generics for every endpoint (`api.getSymbol(name): Promise<SymbolResponse>`)
- Client-side LRU cache (5-min TTL, invalidated via SSE)
- Automatic `X-Request-ID` header for correlation (§12)
- `ETag` / `If-None-Match` support for conditional GETs

## React Query Integration

```typescript
export function useSymbol(fullName: string) {
  return useQuery({
    queryKey: ['symbol', fullName],
    queryFn: () => api.getSymbol(fullName),
    staleTime: 5 * 60_000,
    retry: 2,
  })
}
```

| Data type | staleTime | gcTime |
|-----------|-----------|--------|
| Symbol metadata | 5 min | 10 min |
| Dependency graphs | 10 min | 20 min |
| Search results | 2 min | 5 min |
| Graph layouts | `Infinity` (localStorage) | – |

## Error Handling

- Global `ErrorBoundary` catches render errors with a friendly fallback.
- API errors surface via React Query's `error` state, displayed as toasts
  for transient failures and inline messages for 404s.
- Network errors trigger an automatic retry (exponential back-off, max 3).
