import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';

export const SymbolNode = memo(({ data }: NodeProps) => {
  return (
    <div
      className="px-12 py-8 bg-bg-surface border-2 border-border rounded shadow-sm hover:shadow-md transition-shadow"
      style={{ width: 180, minHeight: 48 }}
    >
      <Handle type="target" position={Position.Top} className="opacity-0" />
      
      <div className="flex items-center justify-between gap-8">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium font-mono truncate" title={data.fullName}>
            {data.label}
          </div>
          <div className="flex items-center gap-4 mt-2">
            <span className="text-xs text-text-secondary">{data.kind}</span>
            {data.depth > 0 && (
              <span className="text-xs text-text-secondary">d{data.depth}</span>
            )}
          </div>
        </div>
        <div className="flex-shrink-0">
          <KindIcon kind={data.kind} />
        </div>
      </div>
      
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
});

SymbolNode.displayName = 'SymbolNode';

function KindIcon({ kind }: { kind: string }) {
  const iconClasses = 'w-16 h-16';
  
  switch (kind) {
    case 'theorem':
      return (
        <svg className={iconClasses} viewBox="0 0 16 16" fill="none" stroke="currentColor">
          <circle cx="8" cy="8" r="6" strokeWidth="2" />
          <path d="M8 5v6M5 8h6" strokeWidth="2" />
        </svg>
      );
    case 'def':
      return (
        <svg className={iconClasses} viewBox="0 0 16 16" fill="currentColor">
          <rect x="4" y="4" width="8" height="8" rx="1" />
        </svg>
      );
    case 'lemma':
      return (
        <svg className={iconClasses} viewBox="0 0 16 16" fill="none" stroke="currentColor">
          <polygon points="8,3 13,8 8,13 3,8" strokeWidth="2" />
        </svg>
      );
    default:
      return (
        <svg className={iconClasses} viewBox="0 0 16 16" fill="currentColor">
          <circle cx="8" cy="8" r="3" />
        </svg>
      );
  }
}
