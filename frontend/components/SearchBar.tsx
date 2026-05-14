'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function SearchBarContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams?.get('q') || '');

  // Debounced search
  useEffect(() => {
    if (query.length === 0) return;

    const timer = setTimeout(() => {
      const params = new URLSearchParams(searchParams?.toString() || '');
      params.set('q', query);
      router.push(`/search?${params.toString()}`);
    }, 250);

    return () => clearTimeout(timer);
  }, [query, searchParams, router]);

  // ⌘K / Ctrl+K keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('global-search')?.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (query.trim()) {
        router.push(`/search?q=${encodeURIComponent(query.trim())}`);
      }
    },
    [query, router]
  );

  return (
    <form onSubmit={handleSubmit} className="relative">
      <input
        id="global-search"
        type="search"
        placeholder="Search symbols... (⌘K)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full px-12 py-8 pr-32 bg-bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-accent-primary"
        role="combobox"
        aria-autocomplete="list"
      />
      <kbd className="absolute right-12 top-1/2 -translate-y-1/2 px-8 py-4 bg-bg-primary border border-border rounded text-xs font-mono text-text-secondary">
        ⌘K
      </kbd>
    </form>
  );
}

export function SearchBar() {
  return (
    <Suspense fallback={
      <div className="w-full px-12 py-8 bg-bg-secondary border border-border rounded">
        <span className="text-text-secondary">Search...</span>
      </div>
    }>
      <SearchBarContent />
    </Suspense>
  );
}
