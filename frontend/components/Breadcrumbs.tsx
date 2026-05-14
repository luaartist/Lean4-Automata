'use client';

import Link from 'next/link';

interface BreadcrumbSegment {
  label: string;
  href: string;
}

interface BreadcrumbsProps {
  segments: BreadcrumbSegment[];
}

export function Breadcrumbs({ segments }: BreadcrumbsProps) {
  return (
    <nav aria-label="Breadcrumb" className="mb-16">
      <ol className="flex items-center gap-8 text-sm">
        {segments.map((segment, index) => (
          <li key={segment.href} className="flex items-center gap-8">
            {index > 0 && (
              <span className="text-text-secondary" aria-hidden="true">
                /
              </span>
            )}
            {index === segments.length - 1 ? (
              <span className="text-text-primary font-medium" aria-current="page">
                {segment.label}
              </span>
            ) : (
              <Link
                href={segment.href}
                className="text-text-secondary hover:text-accent-primary"
              >
                {segment.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
