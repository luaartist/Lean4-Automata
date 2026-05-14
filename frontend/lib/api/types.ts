// TypeScript types mirroring Phase 3 Pydantic models from app/query/router.py

export interface SymbolLookupResponse {
  id: number;
  file_id: number;
  project_id: number;
  name: string;
  full_name: string;
  kind: string;
  line_start: number;
  line_end: number;
  signature: string | null;
  docstring: string | null;
}

export interface SymbolSearchItem {
  id: number;
  file_id: number;
  project_id: number;
  name: string;
  full_name: string;
  kind: string;
  rank: number;
}

export interface SymbolSearchResponse {
  q: string;
  project_id: number;
  limit: number;
  offset: number;
  total: number;
  items: SymbolSearchItem[];
}

export interface DependencyNode {
  symbol_id: number;
  full_name: string;
  name: string;
  kind: string;
  depth: number;
  path: number[];
  dependency_type: string | null;
}

export interface DependencyGraphResponse {
  full_name: string;
  max_depth: number;
  transitive: DependencyNode[];
  reverse: DependencyNode[];
}

export interface ModuleMetricItem {
  file_id: number;
  module_name: string;
  total_symbols: number;
  theorem_count: number;
  def_count: number;
  instance_count: number;
  inductive_count: number;
  structure_count: number;
  class_count: number;
  avg_symbol_length_lines: number | null;
  max_symbol_length_lines: number | null;
  public_symbols: number;
  deprecated_symbols: number;
  documented_symbols: number;
  documentation_coverage_pct: number;
}

export interface ModuleMetricsResponse {
  project_id: number;
  order_by: string;
  items: ModuleMetricItem[];
}

// SSE invalidation event payload
export interface InvalidationPayload {
  path: string;
  file_id?: number;
  symbols?: string[];
}

// UI-specific types
export type SymbolKind =
  | 'theorem'
  | 'def'
  | 'lemma'
  | 'instance'
  | 'structure'
  | 'class'
  | 'axiom'
  | 'inductive';

export type Visibility = 'public' | 'private' | 'all';

export interface SearchFilters {
  kind: SymbolKind[];
  project_id: number | null;
  visibility: Visibility;
  deprecated: boolean;
  depth: number;
  query: string;
}
