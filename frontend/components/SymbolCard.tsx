'use client';

import type { SymbolLookupResponse } from '@/lib/api/types';

interface SymbolCardProps {
  symbol: SymbolLookupResponse;
}

export function SymbolCard({ symbol }: SymbolCardProps) {
  return (
    <div className="bg-bg-surface border border-border rounded p-16 space-y-16">
      <div>
        <span className="inline-block px-8 py-4 bg-accent-primary text-white text-xs rounded mb-8">
          {symbol.kind}
        </span>
        <h3 className="font-mono font-medium">{symbol.name}</h3>
        <p className="text-sm text-text-secondary">{symbol.full_name}</p>
      </div>

      {symbol.signature && (
        <div>
          <h4 className="text-sm font-medium mb-8">Signature</h4>
          <pre className="bg-bg-primary p-12 rounded text-sm font-mono overflow-x-auto">
            {symbol.signature}
          </pre>
        </div>
      )}

      {symbol.docstring && (
        <div>
          <h4 className="text-sm font-medium mb-8">Documentation</h4>
          <div className="text-sm text-text-secondary whitespace-pre-wrap">
            {symbol.docstring}
          </div>
        </div>
      )}

      <div className="text-xs text-text-secondary space-y-4">
        <div>
          Lines: {symbol.line_start}–{symbol.line_end}
        </div>
        <div>File ID: {symbol.file_id}</div>
        <div>Symbol ID: {symbol.id}</div>
      </div>
    </div>
  );
}
