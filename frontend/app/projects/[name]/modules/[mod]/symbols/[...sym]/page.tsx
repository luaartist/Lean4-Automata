'use client';

import { useSymbol, useDependencyGraph } from '@/lib/api/queries';
import { Breadcrumbs } from '@/components/Breadcrumbs';
import { SymbolCard } from '@/components/SymbolCard';
import { DependencyGraph } from '@/components/graph/DependencyGraph';
import { Loading } from '@/components/states/Loading';
import { ErrorState } from '@/components/states/Error';
import { useState } from 'react';

export default function SymbolPage({
  params,
}: {
  params: { name: string; mod: string; sym: string[] };
}) {
  const projectId = parseInt(params.name, 10);
  const moduleName = decodeURIComponent(params.mod);
  const fullName = params.sym.join('.');
  const [depth, setDepth] = useState(5);

  const {
    data: symbol,
    isLoading: symbolLoading,
    error: symbolError,
    refetch: refetchSymbol,
  } = useSymbol(fullName);

  const {
    data: graph,
    isLoading: graphLoading,
    error: graphError,
    refetch: refetchGraph,
  } = useDependencyGraph(fullName, depth);

  return (
    <div>
      <Breadcrumbs
        segments={[
          { label: 'Home', href: '/' },
          { label: `Project ${projectId}`, href: `/projects/${projectId}` },
          {
            label: moduleName,
            href: `/projects/${projectId}/modules/${encodeURIComponent(moduleName)}`,
          },
          {
            label: fullName,
            href: `/projects/${projectId}/modules/${encodeURIComponent(moduleName)}/symbols/${encodeURIComponent(fullName)}`,
          },
        ]}
      />

      <div className="grid grid-cols-3 gap-24 mt-24">
        <div className="col-span-2">
          <h1 className="text-2xl font-bold mb-16">Dependency Graph</h1>

          <div className="mb-16 flex items-center gap-16">
            <label htmlFor="depth" className="text-sm font-medium">
              Max Depth:
            </label>
            <input
              id="depth"
              type="range"
              min="1"
              max="5"
              value={depth}
              onChange={(e) => setDepth(parseInt(e.target.value, 10))}
              className="flex-1"
            />
            <span className="text-sm text-text-secondary">{depth}</span>
          </div>

          {graphLoading && <Loading />}
          {graphError && (
            <ErrorState
              message="Failed to load dependency graph"
              error={graphError}
              onRetry={() => refetchGraph()}
            />
          )}
          {graph && <DependencyGraph data={graph} projectId={projectId} moduleName={moduleName} />}
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-16">Symbol Details</h2>
          {symbolLoading && <Loading />}
          {symbolError && (
            <ErrorState
              message="Failed to load symbol"
              error={symbolError}
              onRetry={() => refetchSymbol()}
            />
          )}
          {symbol && <SymbolCard symbol={symbol} />}
        </div>
      </div>
    </div>
  );
}
