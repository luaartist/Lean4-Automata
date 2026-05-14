import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';

export const ModuleNode = memo(({ data }: NodeProps) => {
  return (
    <div
      className="px-12 py-8 bg-bg-surface border-2 border-dashed border-accent-primary rounded shadow-sm"
      style={{ width: 220, minHeight: 56 }}
    >
      <Handle type="target" position={Position.Top} className="opacity-0" />
      
      <div className="flex items-center justify-between gap-8">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium font-mono truncate" title={data.modulePath}>
            {data.label}
          </div>
          <div className="text-xs text-text-secondary mt-2">
            {data.symbolCount} symbols
          </div>
        </div>
      </div>
      
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
});

ModuleNode.displayName = 'ModuleNode';
