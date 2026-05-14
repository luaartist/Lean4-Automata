'use client';

import { useFilters } from '@/lib/store';
import type { SymbolKind, Visibility } from '@/lib/api/types';

export function FilterPanel() {
  const { filters, setKind, setVisibility, setDeprecated, setDepth, resetFilters } = useFilters();

  const symbolKinds: SymbolKind[] = [
    'theorem',
    'def',
    'lemma',
    'instance',
    'structure',
    'class',
    'axiom',
    'inductive',
  ];

  const handleKindToggle = (kind: SymbolKind) => {
    const newKinds = filters.kind.includes(kind)
      ? filters.kind.filter((k) => k !== kind)
      : [...filters.kind, kind];
    setKind(newKinds);
  };

  return (
    <div className="bg-bg-surface border border-border rounded p-16 space-y-16">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Filters</h3>
        <button
          onClick={resetFilters}
          className="text-sm text-accent-primary hover:underline"
        >
          Reset
        </button>
      </div>

      {/* Kind filter */}
      <div>
        <h4 className="text-sm font-medium mb-8">Kind</h4>
        <div className="flex flex-wrap gap-8">
          {symbolKinds.map((kind) => (
            <button
              key={kind}
              onClick={() => handleKindToggle(kind)}
              className={`px-8 py-4 text-xs rounded border transition-colors ${
                filters.kind.includes(kind)
                  ? 'bg-accent-primary text-white border-accent-primary'
                  : 'bg-bg-primary border-border hover:border-accent-primary'
              }`}
            >
              {kind}
            </button>
          ))}
        </div>
      </div>

      {/* Visibility filter */}
      <div>
        <h4 className="text-sm font-medium mb-8">Visibility</h4>
        <div className="flex gap-8">
          {(['all', 'public', 'private'] as Visibility[]).map((vis) => (
            <button
              key={vis}
              onClick={() => setVisibility(vis)}
              className={`px-12 py-8 text-sm rounded border transition-colors ${
                filters.visibility === vis
                  ? 'bg-accent-primary text-white border-accent-primary'
                  : 'bg-bg-primary border-border hover:border-accent-primary'
              }`}
            >
              {vis}
            </button>
          ))}
        </div>
      </div>

      {/* Deprecated filter */}
      <div>
        <label className="flex items-center gap-8 cursor-pointer">
          <input
            type="checkbox"
            checked={filters.deprecated}
            onChange={(e) => setDeprecated(e.target.checked)}
            className="w-16 h-16 accent-accent-primary"
          />
          <span className="text-sm">Include deprecated</span>
        </label>
      </div>

      {/* Depth slider */}
      <div>
        <h4 className="text-sm font-medium mb-8">
          Dependency Depth: {filters.depth}
        </h4>
        <input
          type="range"
          min="1"
          max="5"
          value={filters.depth}
          onChange={(e) => setDepth(parseInt(e.target.value, 10))}
          className="w-full accent-accent-primary"
        />
      </div>
    </div>
  );
}
