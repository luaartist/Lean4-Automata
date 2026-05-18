import type { Metadata } from 'next';
import { QueryProvider } from '@/components/QueryProvider';
import { ThemeProvider } from '@/components/ThemeProvider';
import { InvalidationProvider } from '@/lib/sse/invalidation';
import { AppShell } from '@/components/AppShell';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'Lean4-Automata: Local Lean 4 Proof Observatory',
    template: '%s | Lean4-Automata',
  },
  description:
    'Inspect Lean 4 projects locally with import graphs, symbol search, proof completion views, audit tickets, optional Wolfram companion maps, and evidence badges.',
  applicationName: 'Lean4-Automata',
  keywords: [
    'Lean4-Automata',
    'Lean 4 proof observatory',
    'Lean import graph',
    'proof audit tickets',
    'proof completion tracking',
  ],
  openGraph: {
    title: 'Lean4-Automata',
    description:
      'Local proof observability for Lean 4 projects, audit tickets, and durable evidence records.',
    type: 'website',
  },
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
