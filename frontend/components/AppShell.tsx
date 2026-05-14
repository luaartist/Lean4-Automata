'use client';

import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useUIPrefs } from '@/lib/store';

export function AppShell({ children }: { children: React.ReactNode }) {
  const sidebarOpen = useUIPrefs((state) => state.sidebarOpen);

  return (
    <div className="flex flex-col h-screen">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar isOpen={sidebarOpen} />
        <main
          id="main-content"
          className="flex-1 overflow-auto bg-bg-primary p-24"
        >
          {children}
        </main>
        {/* Right rail will be implemented in pages that need it */}
      </div>
    </div>
  );
}
