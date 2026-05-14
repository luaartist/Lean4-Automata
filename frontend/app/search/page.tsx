'use client';

import { useState } from 'react';
import { useSymbolSearch } from '@/lib/api/queries';
import { Loading } from '@/components/states/Loading';
import { ErrorState } from '@/components/states/Error';
import { EmptyState } from '@/components/states/Empty';
import type { SymbolSearchItem } from '@/lib/api/types';
import Link from 'next/link';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const projectId = 1; // Default project ID - can be made dynamic later

  const {
    data,
    isLoading,
    error,
    refetch,
  } = useSymbolSearch(query, projectId, 50, 0);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setQuery(searchInput);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      setQuery(searchInput);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-24 py-24">
      <h1 className="text-2xl font-bold mb-24">Search Symbols</h1>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="mb-32">
        <div className="flex gap-12">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search for symbols (e.g., List.map, theorem, def...)"
            className="flex-1 px-16 py-12 border border-border rounded bg-bg-surface focus:outline-none focus:ring-2 focus:ring-accent-primary"
            autoFocus
          />
          <button
            type="submit"
            className="px-24 py-12 bg-accent-primary text-white rounded hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={searchInput.trim().length === 0}
          >
            Search
          </button>
        </div>
      </form>

      {/* Results Section */}
      {isLoading && <Loading />}

      {error && (
        <ErrorState
          message="Failed to search symbols"
          error={error}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !error && query.length === 0 && (
        <EmptyState
          icon={
            <svg
              className="w-64 h-64 text-text-secondary mx-auto"
              viewBox="0 0 64 64"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="28" cy="28" r="18" />
              <line x1="42" y1="42" x2="54" y2="54" />
            </svg>
          }
          title="Search Lean4 Symbols"
          description="Enter a search query to find symbols across the project. You can search by name, full name, or partial matches."
        />
      )}

      {!isLoading && !error && query.length > 0 && data && data.items.length === 0 && (
        <EmptyState
          icon={
            <svg
              className="w-64 h-64 text-text-secondary mx-auto"
              viewBox="0 0 64 64"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="28" cy="28" r="18" />
              <line x1="42" y1="42" x2="54" y2="54" />
              <line x1="22" y1="28" x2="34" y2="28" />
            </svg>
          }
          title="No results found"
          description={`No symbols found matching "${query}". Try a different search term.`}
        />
      )}

      {!isLoading && !error && data && data.items.length > 0 && (
        <div>
          <div className="mb-16 text-sm text-text-secondary">
            Found {data.total} result{data.total !== 1 ? 's' : ''} for "{data.q}"
            {data.total > data.items.length && ` (showing first ${data.items.length})`}
          </div>

          <div className="space-y-12">
            {data.items.map((item) => (
              <SymbolSearchResult key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface SymbolSearchResultProps {
  item: SymbolSearchItem;
}

function SymbolSearchResult({ item }: SymbolSearchResultProps) {
  // Construct route from symbol data
  const href = `/projects/${item.project_id}/modules/unknown/symbols/${encodeURIComponent(item.full_name)}`;

  return (
    <Link
      href={href}
      className="block bg-bg-surface border border-border rounded p-16 hover:border-accent-primary transition-colors"
    >
      <div className="flex items-start justify-between gap-16">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-12 mb-8">
            <span className="inline-block px-8 py-4 bg-accent-primary text-white text-xs rounded">
              {item.kind}
            </span>
            <h3 className="font-mono font-medium truncate">{item.name}</h3>
          </div>
          <p className="text-sm text-text-secondary font-mono truncate">
            {item.full_name}
          </p>
        </div>
        <div className="text-xs text-text-secondary">
          rank: {item.rank.toFixed(2)}
        </div>
      </div>
    </Link>
  );
}
