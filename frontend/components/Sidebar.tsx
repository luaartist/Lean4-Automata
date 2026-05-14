'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface SidebarProps {
  isOpen: boolean;
}

export function Sidebar({ isOpen }: SidebarProps) {
  const pathname = usePathname();

  if (!isOpen) {
    return null;
  }

  return (
    <aside className="w-[240px] bg-bg-surface border-r border-border overflow-y-auto">
      <nav className="p-16">
        <div className="mb-24">
          <h2 className="text-sm font-medium text-text-secondary mb-8">Projects</h2>
          <ul className="space-y-4">
            <li>
              <Link
                href="/projects/1"
                className={`block px-12 py-8 rounded hover:bg-bg-secondary ${
                  pathname?.startsWith('/projects/1') ? 'bg-accent-primary text-white' : ''
                }`}
              >
                Project 1
              </Link>
            </li>
          </ul>
        </div>

        <div>
          <h2 className="text-sm font-medium text-text-secondary mb-8">Navigation</h2>
          <ul className="space-y-4">
            <li>
              <Link
                href="/search"
                className={`block px-12 py-8 rounded hover:bg-bg-secondary ${
                  pathname === '/search' ? 'bg-accent-primary text-white' : ''
                }`}
              >
                Search
              </Link>
            </li>
            <li>
              <Link
                href="/settings"
                className={`block px-12 py-8 rounded hover:bg-bg-secondary ${
                  pathname === '/settings' ? 'bg-accent-primary text-white' : ''
                }`}
              >
                Settings
              </Link>
            </li>
          </ul>
        </div>
      </nav>
    </aside>
  );
}
