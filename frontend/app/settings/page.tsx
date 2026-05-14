'use client';

import { useUIPrefs } from '@/lib/store';

export default function SettingsPage() {
  const { theme, clusterThreshold, setTheme, setClusterThreshold } = useUIPrefs();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-24">Settings</h1>

      <div className="max-w-2xl space-y-24">
        <div>
          <h2 className="text-lg font-semibold mb-16">Appearance</h2>
          <div className="bg-bg-surface p-16 rounded border border-border">
            <label htmlFor="theme" className="block text-sm font-medium mb-8">
              Theme
            </label>
            <select
              id="theme"
              value={theme}
              onChange={(e) => setTheme(e.target.value as 'light' | 'dark')}
              className="w-full px-12 py-8 bg-bg-primary border border-border rounded"
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-16">Graph Settings</h2>
          <div className="bg-bg-surface p-16 rounded border border-border">
            <label htmlFor="cluster" className="block text-sm font-medium mb-8">
              Cluster Threshold
            </label>
            <select
              id="cluster"
              value={clusterThreshold}
              onChange={(e) =>
                setClusterThreshold(
                  e.target.value === 'unlimited'
                    ? 'unlimited'
                    : (parseInt(e.target.value, 10) as 50 | 150 | 300)
                )
              }
              className="w-full px-12 py-8 bg-bg-primary border border-border rounded"
            >
              <option value="50">50 nodes</option>
              <option value="150">150 nodes (default)</option>
              <option value="300">300 nodes</option>
              <option value="unlimited">Unlimited</option>
            </select>
            <p className="text-sm text-text-secondary mt-8">
              Nodes will be clustered by module when count exceeds this threshold
            </p>
          </div>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-16">Keyboard Shortcuts</h2>
          <div className="bg-bg-surface p-16 rounded border border-border space-y-8">
            <div className="flex justify-between">
              <span className="text-sm">Focus search</span>
              <kbd className="px-8 py-4 bg-bg-primary border border-border rounded text-xs font-mono">
                ⌘K / Ctrl+K
              </kbd>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">Close overlays</span>
              <kbd className="px-8 py-4 bg-bg-primary border border-border rounded text-xs font-mono">
                Esc
              </kbd>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">Show shortcuts</span>
              <kbd className="px-8 py-4 bg-bg-primary border border-border rounded text-xs font-mono">
                ?
              </kbd>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
