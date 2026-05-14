// React Query hooks for API endpoints

import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { apiFetch, buildQueryString } from './client';
import type {
  SymbolLookupResponse,
  SymbolSearchResponse,
  DependencyGraphResponse,
  ModuleMetricsResponse,
  SearchFilters,
} from './types';

// Query key factory
export const queryKeys = {
  symbol: (fullName: string) => ['symbols', fullName] as const,
  symbolSearch: (filters: Partial<SearchFilters>) => ['symbols', 'search', filters] as const,
  dependencyGraph: (fullName: string, maxDepth: number) => ['deps', 'graph', { fullName, maxDepth }] as const,
  moduleMetrics: (projectId: number, orderBy: string) => ['modules', 'metrics', { projectId, orderBy }] as const,
};

// Default React Query options per UX spec
const defaultQueryOptions = {
  staleTime: 60_000, // 1 minute
  refetchOnWindowFocus: false,
};

export function useSymbol(
  fullName: string,
  options?: Omit<UseQueryOptions<SymbolLookupResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.symbol(fullName),
    queryFn: () => apiFetch<SymbolLookupResponse>(`/api/v1/symbols/${encodeURIComponent(fullName)}`),
    ...defaultQueryOptions,
    staleTime: 300_000, // 5 minutes per spec
    ...options,
  });
}

export function useSymbolSearch(
  query: string,
  projectId: number,
  limit: number = 20,
  offset: number = 0,
  options?: Omit<UseQueryOptions<SymbolSearchResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.symbolSearch({ query, project_id: projectId, depth: limit }),
    queryFn: () => {
      const qs = buildQueryString({ q: query, project_id: projectId, limit, offset });
      return apiFetch<SymbolSearchResponse>(`/api/v1/symbols/search${qs}`);
    },
    ...defaultQueryOptions,
    staleTime: 120_000, // 2 minutes per spec
    enabled: query.length > 0,
    ...options,
  });
}

export function useDependencyGraph(
  fullName: string,
  maxDepth: number = 5,
  options?: Omit<UseQueryOptions<DependencyGraphResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.dependencyGraph(fullName, maxDepth),
    queryFn: () => {
      const qs = buildQueryString({ full_name: fullName, max_depth: maxDepth });
      return apiFetch<DependencyGraphResponse>(`/api/v1/dependencies/graph${qs}`);
    },
    ...defaultQueryOptions,
    staleTime: 300_000, // 5 minutes per spec
    enabled: fullName.length > 0,
    ...options,
  });
}

export function useModuleMetrics(
  projectId: number,
  orderBy: string = 'total_symbols',
  options?: Omit<UseQueryOptions<ModuleMetricsResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: queryKeys.moduleMetrics(projectId, orderBy),
    queryFn: () => {
      const qs = buildQueryString({ project_id: projectId, order_by: orderBy });
      return apiFetch<ModuleMetricsResponse>(`/api/v1/modules/metrics${qs}`);
    },
    ...defaultQueryOptions,
    staleTime: 300_000, // 5 minutes per spec
    enabled: projectId > 0,
    ...options,
  });
}
