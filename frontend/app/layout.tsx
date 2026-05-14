import type { Metadata } from 'next';
import { QueryProvider } from '@/components/QueryProvider';
import { ThemeProvider } from '@/components/ThemeProvider';
import { InvalidationProvider } from '@/lib/sse/invalidation';
import { AppShell } from '@/components/AppShell';
import './globals.css';

export const metadata: Metadata = {
  title: 'Lean4-Automata',
  description: 'Dependency analysis and visualization for Lean4 projects',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <a href="#main-content" className="skip-to-content">
          Skip to content
        </a>
        <QueryProvider>
          <InvalidationProvider>
            <ThemeProvider>
              <AppShell>{children}</AppShell>
            </ThemeProvider>
          </InvalidationProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
