/**
 * TraceGraphModal - Datadog-style topology view for cross-service trace
 * Uses React Flow for interactive graph (pan, zoom, Datadog-style visualization)
 */

import { useCallback, useMemo, useEffect, useRef, useState } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Background,
  Controls,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';

function getStatusStyles(status) {
  switch (status) {
    case 'error':
      return 'bg-red-100 border-red-300 text-red-800';
    case 'warn':
      return 'bg-yellow-100 border-yellow-300 text-yellow-800';
    default:
      return 'bg-green-100 border-green-300 text-green-800';
  }
}

function formatLatency(ms) {
  if (ms == null || ms < 0) return null;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function deriveRequestFlowFromTimeline(timeline) {
  if (!Array.isArray(timeline) || timeline.length === 0) return [];
  const seen = [];
  const flow = [];
  for (const event of timeline) {
    const svc = event?.service;
    if (svc && !seen.includes(svc)) {
      seen.push(svc);
      const ts = event?.timestamp_ms ?? (event?.timestamp ? new Date(event.timestamp).getTime() : 0);
      flow.push({ order: flow.length + 1, service: svc, first_timestamp_ms: ts, status: 'ok', event_count: 0 });
    }
  }
  for (const step of flow) {
    step.event_count = timeline.filter((e) => e?.service === step.service).length;
    const msgs = timeline.filter((e) => e?.service === step.service).map((e) => e?.message || '');
    if (msgs.some((m) => /error|fail|exception|Status=[45]\d{2}/i.test(m))) step.status = 'error';
    else if (msgs.some((m) => /warn|timeout|retry/i.test(m))) step.status = 'warn';
  }
  for (let i = 0; i < flow.length - 1; i++) {
    const curr = flow[i].first_timestamp_ms;
    const next = flow[i + 1].first_timestamp_ms;
    flow[i].latency_to_next_ms = curr && next ? Math.max(0, next - curr) : null;
  }
  return flow;
}

function getRequestFlow(correlationData) {
  let requestFlow = correlationData?.request_flow || [];
  if (requestFlow.length === 0 && correlationData?.timeline?.length > 0) {
    requestFlow = deriveRequestFlowFromTimeline(correlationData.timeline);
  }
  return requestFlow;
}

// Custom node for styled service boxes with sequence number
// Handles are required for edges to connect and render
function TraceNode({ data }) {
  const status = data?.status || 'ok';
  const service = data?.service || 'unknown';
  const eventCount = data?.eventCount ?? 0;
  const order = data?.order ?? 0;
  return (
    <div
      className={`px-4 py-2 rounded-lg border-2 font-medium text-sm relative ${getStatusStyles(status)}`}
      style={{ minWidth: 100 }}
    >
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !border-2 !bg-white !border-gray-400" />
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !border-2 !bg-white !border-gray-400" />
      <div className="flex items-center gap-2">
        {order > 0 && (
          <span className="flex-shrink-0 w-5 h-5 rounded-full bg-gray-200 text-gray-700 flex items-center justify-center text-xs font-bold">
            {order}
          </span>
        )}
        <div className="font-semibold whitespace-nowrap">{service}</div>
      </div>
      <div className="text-xs opacity-80 mt-0.5">
        {eventCount} event{eventCount !== 1 ? 's' : ''}
      </div>
    </div>
  );
}

const NODE_WIDTH = 150;
const NODE_HEIGHT = 60;
const HORIZONTAL_GAP = 80;
const VERTICAL_GAP = 60;
const MAX_ROW_WIDTH = 680; // Wrap to next row when exceeding
const START_X = 50;
const START_Y = 50;

const nodeTypes = { traceNode: TraceNode };

// Compute positions with wrap layout - nodes go to next row when exceeding max width
function computeNodePositions(count) {
  const positions = [];
  let x = START_X;
  let y = START_Y;
  for (let i = 0; i < count; i++) {
    positions.push({ x, y });
    x += NODE_WIDTH + HORIZONTAL_GAP;
    if (x + NODE_WIDTH > MAX_ROW_WIDTH && i < count - 1) {
      x = START_X;
      y += NODE_HEIGHT + VERTICAL_GAP;
    }
  }
  return positions;
}

function buildGraphData(correlationData) {
  const requestFlow = getRequestFlow(correlationData);
  if (requestFlow.length === 0) return { nodes: [], edges: [] };

  const nodes = [];
  const edges = [];
  const positions = computeNodePositions(requestFlow.length);

  requestFlow.forEach((step, index) => {
    const id = `node-${step.service}`;
    const status = step.status || 'ok';
    const eventCount = step.event_count ?? 0;
    const order = step.order ?? index + 1;
    const { x, y } = positions[index];

    nodes.push({
      id,
      type: 'traceNode',
      position: { x, y },
      data: {
        service: step.service,
        status,
        eventCount,
        order,
      },
      sourcePosition: 'right',
      targetPosition: 'left',
    });

    if (index < requestFlow.length - 1) {
      const latencyLabel = formatLatency(step.latency_to_next_ms);
      edges.push({
        id: `edge-${step.service}-${requestFlow[index + 1].service}`,
        source: id,
        target: `node-${requestFlow[index + 1].service}`,
        type: 'smoothstep',
        markerEnd: { type: MarkerType.ArrowClosed },
        label: latencyLabel || '—',
        labelStyle: { fill: '#1f2937', fontWeight: 600, fontSize: 12 },
        labelBgStyle: { fill: '#f3f4f6' },
        labelBgBorderRadius: 6,
        labelBgPadding: [6, 8],
      });
    }
  });

  return { nodes, edges };
}

function TraceGraphFlowInner({ correlationData }) {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => buildGraphData(correlationData),
    [correlationData]
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const { fitView } = useReactFlow();

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [correlationData, initialNodes, initialEdges, setNodes, setEdges]);

  const onInit = useCallback(() => {
    fitView({ padding: 0.2, duration: 100 });
  }, [fitView]);

  if (initialNodes.length === 0) return null;

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      defaultEdgeOptions={{
        type: 'smoothstep',
        style: { stroke: '#6b7280', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed },
      }}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      onInit={onInit}
      minZoom={0.2}
      maxZoom={2}
      defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      nodesDraggable={true}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={true}
      zoomOnScroll={true}
      zoomOnPinch={true}
      proOptions={{ hideAttribution: true }}
    >
      <Background color="#e5e7eb" gap={16} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

function TraceGraphFlow({ correlationData }) {
  const { nodes: initialNodes } = useMemo(
    () => buildGraphData(correlationData),
    [correlationData]
  );

  if (initialNodes.length === 0) return null;

  return (
    <ReactFlowProvider>
      <TraceGraphFlowInner correlationData={correlationData} />
    </ReactFlowProvider>
  );
}

function getTotalDuration(correlationData) {
  const first = correlationData?.first_seen;
  const last = correlationData?.last_seen;
  if (!first?.timestamp || !last?.timestamp) return null;
  const diffMs = new Date(last.timestamp) - new Date(first.timestamp);
  if (diffMs < 1000) return `${diffMs}ms`;
  if (diffMs < 60000) return `${(diffMs / 1000).toFixed(1)}s`;
  return `${(diffMs / 60000).toFixed(1)}min`;
}

export default function TraceGraphModal({ isOpen, onClose, correlationData }) {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isExpanded, setIsExpanded] = useState(false);
  const dragRef = useRef({ startX: 0, startY: 0, startPosX: 0, startPosY: 0 });

  const handleHeaderMouseDown = useCallback((e) => {
    if (e.target.closest('button')) return;
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startPosX: position.x,
      startPosY: position.y,
    };
    const onMove = (ev) => {
      setPosition({
        x: dragRef.current.startPosX + (ev.clientX - dragRef.current.startX),
        y: dragRef.current.startPosY + (ev.clientY - dragRef.current.startY),
      });
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [position]);

  if (!isOpen) return null;

  const requestFlow = getRequestFlow(correlationData);
  const correlationId = correlationData?.correlation_id || '';
  const totalEvents = correlationData?.total_events ?? 0;
  const totalDuration = getTotalDuration(correlationData);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="trace-graph-title"
    >
      <div
        className={`bg-white shadow-2xl flex flex-col overflow-hidden transition-all duration-200 ${
          isExpanded
            ? 'fixed inset-4 rounded-lg'
            : 'fixed max-w-5xl w-[calc(100%-2rem)] max-h-[90vh] rounded-xl'
        }`}
        style={
          isExpanded
            ? undefined
            : {
                left: '50%',
                top: '50%',
                transform: `translate(calc(-50% + ${position.x}px), calc(-50% + ${position.y}px))`,
              }
        }
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header - draggable when not expanded */}
        <div
          className={`flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-purple-50 ${
            !isExpanded ? 'cursor-move select-none' : ''
          }`}
          onMouseDown={!isExpanded ? handleHeaderMouseDown : undefined}
        >
          <div className="flex items-center gap-2">
            <span className="text-lg">🔗</span>
            <h2 id="trace-graph-title" className="font-semibold text-purple-900">
              Trace Topology
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-purple-700 font-mono truncate max-w-[200px]" title={correlationId}>
              {correlationId}
            </span>
            <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded-full">
              {totalEvents} events
            </span>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-2 rounded-lg hover:bg-purple-100 text-purple-700 transition-colors"
              aria-label={isExpanded ? 'Restore' : 'Expand'}
              title={isExpanded ? 'Restore size' : 'Expand'}
            >
              {isExpanded ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="Restore">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9H4v5M9 9v5H4M15 9h5v5M15 9v5h5M9 15H4v-5M9 15v-5H4M15 15h5v-5M15 15v-5h5" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="Expand">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                </svg>
              )}
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-purple-100 text-purple-700 transition-colors"
              aria-label="Close"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Graph area - explicit dimensions, grows when expanded */}
        <div
          className="flex-1 w-full relative"
          style={{
            minHeight: 420,
            height: isExpanded ? '100%' : 420,
          }}
        >
          {requestFlow.length > 0 ? (
            <div
              style={{
                width: '100%',
                height: '100%',
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
              }}
            >
              <TraceGraphFlow correlationData={correlationData} />
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              No flow data to display
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="flex-shrink-0 px-4 py-2 border-t border-gray-200 bg-gray-50 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-green-200 border border-green-300" />
            OK
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-yellow-200 border border-yellow-300" />
            Warn
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-red-200 border border-red-300" />
            Error
          </span>
          <span className="flex items-center gap-1.5">
            <span className="font-medium text-gray-500">Edge labels:</span>
            Time between consecutive services (first event to first event)
          </span>
          {totalDuration && (
            <span className="flex items-center gap-1.5">
              <span className="font-medium text-gray-500">Total trace:</span>
              {totalDuration}
            </span>
          )}
          <span className="ml-auto">Pan & zoom</span>
        </div>
      </div>
    </div>
  );
}
