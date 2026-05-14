import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';

export const ClusterNode = memo(({ data }: NodeProps) => {
  return (
    <div
      className="px-16 py-12 bg-bg-secondary border-2 border-border rounded shadow-sm cursor-pointer hover:bg-bg-surface transition-colors"
      style={{ width: 200, minHeight: 64 }}
    >
      <Handle type="target" position={Position.Top} className="opacity-0" />
      
      <div className="flex flex-col items-center justify-center gap-4">
        <div className="text-sm font-medium text-text-secondary">
          {data.label}
        </div>
        <div className="text-xs text-text-secondary flex items-center gap-4">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
            <circle cx="3" cy="3" r="2" />
            <circle cx="9" cy="3" r="2" />
            <circle cx="6" cy="9" r="2" />
          </svg>
          Double-click to expand
        </div>
      </div>
      
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
});

ClusterNode.displayName = 'ClusterNode';
