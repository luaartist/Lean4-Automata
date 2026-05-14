'use client';

import Link from 'next/link';
import type { ModuleMetricsResponse } from '@/lib/api/types';

interface ModuleMetricsTableProps {
  metrics: ModuleMetricsResponse;
  projectId: number;
}

export function ModuleMetricsTable({ metrics, projectId }: ModuleMetricsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-bg-secondary border-b border-border">
            <th className="text-left p-12 text-sm font-medium">Module</th>
            <th className="text-right p-12 text-sm font-medium">Symbols</th>
            <th className="text-right p-12 text-sm font-medium">Theorems</th>
            <th className="text-right p-12 text-sm font-medium">Defs</th>
            <th className="text-right p-12 text-sm font-medium">Avg Lines</th>
            <th className="text-right p-12 text-sm font-medium">Docs %</th>
          </tr>
        </thead>
        <tbody>
          {metrics.items.map((module) => (
            <tr
              key={module.file_id}
              className="border-b border-border hover:bg-bg-secondary transition-colors"
            >
              <td className="p-12">
                <Link
                  href={`/projects/${projectId}/modules/${encodeURIComponent(module.module_name)}`}
                  className="text-accent-primary hover:underline font-mono text-sm"
                >
                  {module.module_name}
                </Link>
              </td>
              <td className="text-right p-12 text-sm">{module.total_symbols}</td>
              <td className="text-right p-12 text-sm">{module.theorem_count}</td>
              <td className="text-right p-12 text-sm">{module.def_count}</td>
              <td className="text-right p-12 text-sm">
                {module.avg_symbol_length_lines?.toFixed(1) || 'N/A'}
              </td>
              <td className="text-right p-12 text-sm">
                <span
                  className={`inline-block px-8 py-4 rounded text-xs ${
                    module.documentation_coverage_pct >= 80
                      ? 'bg-status-success text-white'
                      : module.documentation_coverage_pct >= 50
                      ? 'bg-status-warning text-white'
                      : 'bg-status-error text-white'
                  }`}
                >
                  {module.documentation_coverage_pct.toFixed(1)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
