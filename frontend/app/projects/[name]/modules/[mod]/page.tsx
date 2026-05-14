'use client';

import Link from 'next/link';
import { useModuleMetrics, useSymbolSearch } from '@/lib/api/queries';
import { Breadcrumbs } from '@/components/Breadcrumbs';
import { Loading } from '@/components/states/Loading';
import { ErrorState } from '@/components/states/Error';

export default function ModulePage({
  params,
}: {
  params: { name: string; mod: string };
}) {
  const projectId = parseInt(params.name, 10);
  const moduleName = decodeURIComponent(params.mod);

  const { data: metrics } = useModuleMetrics(projectId);
  const {
    data: symbols,
    isLoading: symbolsLoading,
    error,
    refetch,
  } = useSymbolSearch(moduleName, projectId, 100);

  const moduleMetric = metrics?.items.find((m) => m.module_name === moduleName);

  return (
    <div>
      <Breadcrumbs
        segments={[
          { label: 'Home', href: '/' },
          { label: `Project ${projectId}`, href: `/projects/${projectId}` },
          { label: moduleName, href: `/projects/${projectId}/modules/${encodeURIComponent(moduleName)}` },
        ]}
      />

      <h1 className="text-2xl font-bold mt-24 mb-16">{moduleName}</h1>

      {moduleMetric && (
        <div className="bg-bg-surface p-16 rounded border border-border mb-24">
          <div className="grid grid-cols-4 gap-16">
            <div>
              <div className="text-sm text-text-secondary">Total Symbols</div>
              <div className="text-xl font-semibold">{moduleMetric.total_symbols}</div>
            </div>
            <div>
              <div className="text-sm text-text-secondary">Theorems</div>
              <div className="text-xl font-semibold">{moduleMetric.theorem_count}</div>
            </div>
            <div>
              <div className="text-sm text-text-secondary">Definitions</div>
              <div className="text-xl font-semibold">{moduleMetric.def_count}</div>
            </div>
            <div>
              <div className="text-sm text-text-secondary">Documentation</div>
              <div className="text-xl font-semibold">
                {moduleMetric.documentation_coverage_pct.toFixed(1)}%
              </div>
            </div>
          </div>
        </div>
      )}

      <h2 className="text-lg font-semibold mb-16">Symbols</h2>

      {symbolsLoading && <Loading />}
      {error && (
        <ErrorState
          message="Failed to load symbols"
          error={error}
          onRetry={() => refetch()}
        />
      )}
      {symbols && (
        <div className="space-y-8">
          {symbols.items.map((symbol) => (
            <Link
              key={symbol.id}
              href={`/projects/${projectId}/modules/${encodeURIComponent(moduleName)}/symbols/${encodeURIComponent(symbol.full_name)}`}
              className="block p-16 bg-bg-surface border border-border rounded hover:border-accent-primary transition-colors"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium font-mono">{symbol.name}</div>
                  <div className="text-sm text-text-secondary mt-4">
                    {symbol.full_name}
                  </div>
                </div>
                <span className="px-8 py-4 bg-accent-primary text-white text-xs rounded">
                  {symbol.kind}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
