'use client';

import Link from 'next/link';
import { SearchBar } from './SearchBar';
import { useUIPrefs } from '@/lib/store';

export function Header() {
  const { theme, setTheme, toggleSidebar } = useUIPrefs();

  const handleThemeToggle = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };

  return (
    <header className="h-[56px] bg-bg-surface border-b border-border flex items-center px-16 gap-16">
      <button
        onClick={toggleSidebar}
        className="p-8 hover:bg-bg-secondary rounded"
        aria-label="Toggle sidebar"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <line x1="3" y1="5" x2="17" y2="5" />
          <line x1="3" y1="10" x2="17" y2="10" />
          <line x1="3" y1="15" x2="17" y2="15" />
        </svg>
      </button>

      <Link href="/" className="flex items-center gap-8 font-semibold text-lg">
        <span className="text-accent-primary">Lean4</span>
        <span>Automata</span>
      </Link>

      <div className="flex-1 max-w-[600px]">
        <SearchBar />
      </div>

      <button
        onClick={handleThemeToggle}
        className="p-8 hover:bg-bg-secondary rounded"
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
      >
        {theme === 'light' ? (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 3a1 1 0 011 1v1a1 1 0 11-2 0V4a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" />
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
          </svg>
        )}
      </button>

      <SSEIndicator />
    </header>
  );
}

function SSEIndicator() {
  // Simple indicator using global state from InvalidationProvider
  if (typeof window === 'undefined') return null;

  const state = (window as any).__sseConnectionState || {
    connected: false,
    lastEvent: null,
  };

  return (
    <div className="flex items-center gap-8" title={state.connected ? 'SSE Connected' : 'SSE Reconnecting...'}>
      <div
        className={`w-8 h-8 rounded-full ${
          state.connected ? 'bg-status-success' : 'bg-status-warning'
        } ${!state.connected ? 'animate-pulse' : ''}`}
      />
    </div>
  );
}
