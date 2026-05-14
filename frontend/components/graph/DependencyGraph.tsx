'use client';

import { useCallback, useEffect, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  Panel,
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';
import type { DependencyGraphResponse } from '@/lib/api/types';
import { useGraphView, useUIPrefs } from '@/lib/store';
import { SymbolNode } from './nodes/SymbolNode';
import { ModuleNode } from './nodes/ModuleNode';
import { ClusterNode } from './nodes/ClusterNode';

interface DependencyGraphProps {
  data: DependencyGraphResponse;
  projectId?: number;
  moduleName?: string;
}

const nodeTypes = {
  symbol: SymbolNode,
  module: ModuleNode,
  cluster: ClusterNode,
};

// Dagre layout
function getLayoutedElements(nodes: Node[], edges: Edge[], direction = 'TB') {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, ranksep: 80, nodesep: 60 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 180, height: 48 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 90,
        y: nodeWithPosition.y - 24,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

export function DependencyGraph({ data, projectId, moduleName }: DependencyGraphProps) {
  const { layout } = useGraphView();
  const { clusterThreshold } = useUIPrefs();

  // Convert API data to React Flow nodes and edges
  const { initialNodes, initialEdges } = useMemo(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const nodeMap = new Map<string, boolean>();

    // Add transitive dependencies (outgoing)
    data.transitive.forEach((dep) => {
      if (!nodeMap.has(dep.full_name)) {
        nodes.push({
          id: dep.full_name,
          type: 'symbol',
          data: {
            label: dep.name,
            fullName: dep.full_name,
            kind: dep.kind,
            depth: dep.depth,
          },
          position: { x: 0, y: 0 },
        });
        nodeMap.set(dep.full_name, true);
      }

      edges.push({
        id: `${data.full_name}-${dep.full_name}`,
        source: data.full_name,
        target: dep.full_name,
        type: 'default',
        animated: dep.dependency_type === 'direct',
        style: getEdgeStyle(dep.dependency_type || 'indirect'),
        label: dep.dependency_type || '',
      });
    });

    // Add reverse dependencies (incoming)
    data.reverse.forEach((dep) => {
      if (!nodeMap.has(dep.full_name)) {
        nodes.push({
          id: dep.full_name,
          type: 'symbol',
          data: {
            label: dep.name,
            fullName: dep.full_name,
            kind: dep.kind,
            depth: dep.depth,
          },
          position: { x: 0, y: 0 },
        });
        nodeMap.set(dep.full_name, true);
      }

      edges.push({
        id: `${dep.full_name}-${data.full_name}`,
        source: dep.full_name,
        target: data.full_name,
        type: 'default',
        animated: dep.dependency_type === 'direct',
        style: getEdgeStyle(dep.dependency_type || 'indirect'),
        label: dep.dependency_type || '',
      });
    });

    // Add center node if not present
    if (!nodeMap.has(data.full_name)) {
      nodes.push({
        id: data.full_name,
        type: 'symbol',
        data: {
          label: data.full_name.split('.').pop() || data.full_name,
          fullName: data.full_name,
          kind: 'unknown',
          depth: 0,
        },
        position: { x: 0, y: 0 },
      });
    }

    return { initialNodes: nodes, initialEdges: edges };
  }, [data]);

  const layouted = useMemo(() => {
    if (layout === 'dagre') {
      return getLayoutedElements(initialNodes, initialEdges);
    }
    return { nodes: initialNodes, edges: initialEdges };
  }, [initialNodes, initialEdges, layout]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layouted.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layouted.edges);

  useEffect(() => {
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
  }, [layouted, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      // Navigate to symbol detail using provided context or fallback
      const project = projectId || 1;
      const module = moduleName || 'unknown';
      window.location.href = `/projects/${project}/modules/${encodeURIComponent(module)}/symbols/${encodeURIComponent(node.data.fullName)}`;
    },
    [projectId, moduleName]
  );

  // Clustering logic
  const shouldCluster = useMemo(() => {
    if (clusterThreshold === 'unlimited') return false;
    return nodes.length > clusterThreshold;
  }, [nodes.length, clusterThreshold]);

  return (
    <div className="h-[600px] bg-bg-surface border border-border rounded">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
        attributionPosition="bottom-right"
      >
        <Controls />
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
          style={{ width: 160, height: 100 }}
        />
        <Background />
        <Panel position="top-right" className="bg-bg-surface p-8 rounded border border-border">
          <div className="text-xs text-text-secondary">
            {shouldCluster && <div>Clustering enabled ({nodes.length} nodes)</div>}
            <div>{edges.length} dependencies</div>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}

function getEdgeStyle(type: string) {
  const colors = {
    direct: 'var(--edge-direct)',
    import: 'var(--edge-import)',
    implicit: 'var(--edge-implicit)',
    indirect: 'var(--edge-indirect)',
  };

  const color = colors[type as keyof typeof colors] || colors.indirect;

  if (type === 'implicit' || type === 'indirect') {
    return {
      stroke: color,
      strokeWidth: type === 'implicit' ? 1.5 : 1,
      strokeDasharray: type === 'implicit' ? '4 2' : '6 3',
    };
  }

  return {
    stroke: color,
    strokeWidth: 2,
  };
}
