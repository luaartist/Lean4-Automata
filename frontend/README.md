# Lean4-Automata Frontend

Next.js 16 LTS frontend for Lean4-Automata dependency analysis and visualization.

## Features

- 🚀 **Next.js 16** with App Router and React Server Components
- ⚛️ **React 19** with modern hooks and concurrent features
- 📊 **React Flow** for interactive dependency graph visualization
- 🔍 **Real-time search** with 250ms debounce and URL state sync
- 🔄 **SSE invalidation** for automatic cache updates
- 🎨 **Tailwind CSS 4** with design tokens for light/dark themes
- 🗂️ **Zustand** for client-side state management
- 🌐 **React Query** for server state with smart caching
- 🔐 **TypeScript strict mode** for type safety
- ♿ **WCAG 2.1 AA compliant** with keyboard navigation and screen reader support

## Quick Start

### Prerequisites

- Node.js 22+ 
- npm 10+ or pnpm 9+

### Development

```bash
# Install dependencies
npm install
# or
pnpm install

# Run development server
npm run dev

# Open http://localhost:3000
```

### Build

```bash
# Type check
npm run type-check

# Production build
npm run build

# Start production server
npm start
```

### Docker

```bash
# Build image
docker build -t lean4-automata-frontend .

# Run container
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
  lean4-automata-frontend
```

## Environment Variables

Create `.env.local` for local development:

```env
# API base URL (default: http://localhost:8000)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Architecture

### Directory Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx         # Root layout with providers
│   ├── page.tsx           # Landing page (redirects to project)
│   ├── projects/[name]/   # Project pages
│   ├── search/            # Global search
│   └── settings/          # User settings
├── components/            # React components
│   ├── graph/            # React Flow graph components
│   ├── states/           # Loading, Error, Empty states
│   ├── AppShell.tsx      # Main app layout
│   ├── Header.tsx        # Top navigation
│   ├── Sidebar.tsx       # Left navigation
│   └── ...
├── lib/                   # Core utilities
│   ├── api/              # API client and types
│   │   ├── types.ts      # TypeScript types mirroring Pydantic
│   │   ├── client.ts     # Fetch wrapper with error handling
│   │   └── queries.ts    # React Query hooks
│   ├── store/            # Zustand state management
│   │   └── index.ts      # UI prefs, graph view, filters
│   └── sse/              # Server-Sent Events
│       └── invalidation.tsx  # SSE invalidation provider
└── public/               # Static assets
```

### State Management

- **React Query**: Server state (symbols, dependencies, metrics)
- **Zustand**: Client state (UI preferences, graph view, filters)
- **URL params**: Search and filter state (shareable links)
- **SSE**: Real-time cache invalidation

### API Integration

All endpoints use `/api/v1` prefix, proxied through Next.js rewrites:

- `GET /api/v1/symbols/{full_name}` - Symbol lookup
- `GET /api/v1/symbols/search` - Full-text search
- `GET /api/v1/dependencies/graph` - Dependency graph
- `GET /api/v1/modules/metrics` - Module metrics
- `GET /api/v1/events/invalidation` - SSE invalidation stream

### Accessibility

- Keyboard shortcuts (⌘K for search, Tab navigation, Escape to close)
- Screen reader support with ARIA labels
- Focus management and visible focus indicators
- Color contrast WCAG AA compliant
- Dependency graph accessible table fallback

## Scripts

- `dev` - Start development server
- `build` - Build for production
- `start` - Start production server
- `lint` - Run ESLint
- `type-check` - Run TypeScript type checking

## Performance Targets

- **LCP**: ≤ 1.2s
- **INP**: ≤ 100ms
- **CLS**: ≤ 0.05
- **Bundle size**: ≤ 120kB gzipped (initial)
- **Graph render**: ≤ 500ms for ≤150 nodes

## Contributing

See the main [CONTRIBUTING.md](../CONTRIBUTING.md) in the repository root.

## License

See [LICENSE](../LICENSE) in the repository root.
