// Zustand store with uiPrefs, graphView, and filters slices

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SearchFilters, Visibility, SymbolKind } from '../api/types';

// UI Preferences slice (persisted to localStorage)
interface UIPrefsState {
  theme: 'light' | 'dark';
  sidebarOpen: boolean;
  rightRailOpen: boolean;
  clusterThreshold: 50 | 150 | 300 | 'unlimited';
  setTheme: (theme: 'light' | 'dark') => void;
  toggleSidebar: () => void;
  toggleRightRail: () => void;
  setClusterThreshold: (threshold: 50 | 150 | 300 | 'unlimited') => void;
}

export const useUIPrefs = create<UIPrefsState>()(
  persist(
    (set) => ({
      theme: 'light',
      sidebarOpen: true,
      rightRailOpen: true,
      clusterThreshold: 150,
      setTheme: (theme) => set({ theme }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      toggleRightRail: () => set((state) => ({ rightRailOpen: !state.rightRailOpen })),
      setClusterThreshold: (clusterThreshold) => set({ clusterThreshold }),
    }),
    {
      name: 'lean4-ui-prefs',
    }
  )
);

// Graph View slice (session only, not persisted)
interface GraphViewState {
  layout: 'dagre' | 'force';
  zoomLevel: number;
  selectedNodes: string[];
  hoveredNode: string | null;
  setLayout: (layout: 'dagre' | 'force') => void;
  setZoomLevel: (zoomLevel: number) => void;
  setSelectedNodes: (selectedNodes: string[]) => void;
  addSelectedNode: (nodeId: string) => void;
  removeSelectedNode: (nodeId: string) => void;
  clearSelectedNodes: () => void;
  setHoveredNode: (nodeId: string | null) => void;
}

export const useGraphView = create<GraphViewState>((set) => ({
  layout: 'dagre',
  zoomLevel: 1,
  selectedNodes: [],
  hoveredNode: null,
  setLayout: (layout) => set({ layout }),
  setZoomLevel: (zoomLevel) => set({ zoomLevel }),
  setSelectedNodes: (selectedNodes) => set({ selectedNodes }),
  addSelectedNode: (nodeId) =>
    set((state) => ({
      selectedNodes: [...state.selectedNodes, nodeId],
    })),
  removeSelectedNode: (nodeId) =>
    set((state) => ({
      selectedNodes: state.selectedNodes.filter((id) => id !== nodeId),
    })),
  clearSelectedNodes: () => set({ selectedNodes: [] }),
  setHoveredNode: (hoveredNode) => set({ hoveredNode }),
}));

// Filters slice (synced with URL search params, managed by components)
interface FiltersState {
  filters: SearchFilters;
  setFilters: (filters: Partial<SearchFilters>) => void;
  resetFilters: () => void;
  setQuery: (query: string) => void;
  setKind: (kind: SymbolKind[]) => void;
  setProjectId: (projectId: number | null) => void;
  setVisibility: (visibility: Visibility) => void;
  setDeprecated: (deprecated: boolean) => void;
  setDepth: (depth: number) => void;
}

const defaultFilters: SearchFilters = {
  kind: [],
  project_id: null,
  visibility: 'all',
  deprecated: false,
  depth: 5,
  query: '',
};

export const useFilters = create<FiltersState>((set) => ({
  filters: defaultFilters,
  setFilters: (newFilters) =>
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
    })),
  resetFilters: () => set({ filters: defaultFilters }),
  setQuery: (query) =>
    set((state) => ({
      filters: { ...state.filters, query },
    })),
  setKind: (kind) =>
    set((state) => ({
      filters: { ...state.filters, kind },
    })),
  setProjectId: (project_id) =>
    set((state) => ({
      filters: { ...state.filters, project_id },
    })),
  setVisibility: (visibility) =>
    set((state) => ({
      filters: { ...state.filters, visibility },
    })),
  setDeprecated: (deprecated) =>
    set((state) => ({
      filters: { ...state.filters, deprecated },
    })),
  setDepth: (depth) =>
    set((state) => ({
      filters: { ...state.filters, depth },
    })),
}));
