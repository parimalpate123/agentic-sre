/**
 * CorrelationView Component
 * Displays cross-service correlation results with a UNIFIED timeline that
 * merges CloudWatch log events and Elasticsearch APM trace spans by
 * correlation / trace ID, sorted chronologically.
 */

import { useState, useMemo } from 'react';
import TraceGraphModal from './TraceGraphModal';

// ---------------------------------------------------------------------------
// Shared status helpers (same regex as TraceGraphModal — keeps colors in sync)
// ---------------------------------------------------------------------------
function msgStatus(text) {
  if (/error|fail|exception|Status=[45]\d{2}/i.test(text)) return 'error';
  if (/warn|timeout|retry/i.test(text)) return 'warn';
  return 'ok';
}

const STATUS_PILL = {
  error: 'bg-red-100 text-red-800 border border-red-300',
  warn:  'bg-yellow-100 text-yellow-800 border border-yellow-300',
  ok:    'bg-green-100 text-green-800 border border-green-300',
};

const STATUS_ROW = {
  error: { row: 'bg-red-50',     badge: 'bg-red-100 text-red-700',       text: 'text-red-600' },
  warn:  { row: 'bg-yellow-50',  badge: 'bg-yellow-100 text-yellow-700', text: 'text-gray-600' },
  ok:    { row: 'hover:bg-gray-50', badge: 'bg-blue-100 text-blue-700',  text: 'text-gray-600' },
};

/** Source tag colors */
const SOURCE_TAG = {
  cloudwatch:    { cls: 'bg-orange-100 text-orange-700 border-orange-200', label: 'CW' },
  elasticsearch: { cls: 'bg-violet-100 text-violet-700 border-violet-200', label: 'APM' },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function CorrelationView({ correlationData, esContext = null }) {
  const [showGraphModal, setShowGraphModal] = useState(false);

  if (!correlationData) return null;

  const {
    correlation_id,
    services_found = [],
    services_searched = 0,
    total_events = 0,
    request_flow = [],
    timeline = [],
    first_seen,
    last_seen
  } = correlationData;

  // -----------------------------------------------------------------------
  // Build UNIFIED timeline merging CW log events + ES APM spans
  // -----------------------------------------------------------------------
  const unifiedTimeline = useMemo(() => {
    const entries = [];

    // 1. CloudWatch log events
    for (const ev of timeline) {
      const status = msgStatus(ev.message || '');
      entries.push({
        ts: ev.timestamp ? new Date(ev.timestamp).getTime() : 0,
        timestamp: ev.timestamp,
        service: ev.service || 'unknown',
        message: ev.message || '',
        status,
        source: 'cloudwatch',
        cloudwatch_url: ev.cloudwatch_url || null,
        duration_ms: null,
        operation: null,
      });
    }

    // 2. Elasticsearch APM trace spans
    if (esContext?.available && esContext?.traces?.length) {
      for (const trace of esContext.traces) {
        const spans = trace.spans || [];
        const traceStatus = trace.trace?.status || 'ok';

        for (const span of spans) {
          const spanTs = span.timestamp || trace['@timestamp'] || '';
          const spanStatus = span.status === 'error' ? 'error'
            : span.status === 'warn' || span.status === 'degraded' ? 'warn' : 'ok';
          const op = span.operation || span.name || 'span';
          const dur = span.duration_ms;
          entries.push({
            ts: spanTs ? new Date(spanTs).getTime() : 0,
            timestamp: spanTs,
            service: span.service || 'unknown',
            message: `${op}${dur != null ? ` — ${dur}ms` : ''}${spanStatus === 'error' ? ' [ERROR]' : ''}`,
            status: spanStatus,
            source: 'elasticsearch',
            cloudwatch_url: null,
            duration_ms: dur,
            operation: op,
          });
        }

        // Trace-level entry when no individual spans
        if (spans.length === 0) {
          const tTs = trace['@timestamp'] || '';
          const dur = trace.duration_ms || trace.trace?.duration_ms;
          entries.push({
            ts: tTs ? new Date(tTs).getTime() : 0,
            timestamp: tTs,
            service: trace.service || 'unknown',
            message: `trace — ${dur != null ? dur + 'ms' : 'N/A'} (status: ${traceStatus})`,
            status: traceStatus === 'error' ? 'error' : 'ok',
            source: 'elasticsearch',
            cloudwatch_url: null,
            duration_ms: dur,
            operation: 'trace',
          });
        }
      }
    }

    // Sort chronologically (oldest first)
    entries.sort((a, b) => a.ts - b.ts);
    return entries;
  }, [timeline, esContext]);

  // -----------------------------------------------------------------------
  // Per-service status map — merges evidence from BOTH sources
  // -----------------------------------------------------------------------
  const serviceStatusMap = useMemo(() => {
    const map = {};
    for (const step of request_flow) {
      const svcEntries = unifiedTimeline.filter(e => e.service === step.service);
      if (svcEntries.some(e => e.status === 'error')) map[step.service] = 'error';
      else if (svcEntries.some(e => e.status === 'warn')) map[step.service] = 'warn';
      else map[step.service] = 'ok';
    }
    return map;
  }, [request_flow, unifiedTimeline]);

  // Stats
  const cwCount = unifiedTimeline.filter(e => e.source === 'cloudwatch').length;
  const apmCount = unifiedTimeline.filter(e => e.source === 'elasticsearch').length;

  // Duration
  const getDuration = () => {
    if (!first_seen || !last_seen) return null;
    const diffMs = new Date(last_seen.timestamp) - new Date(first_seen.timestamp);
    if (diffMs < 1000) return `${diffMs}ms`;
    if (diffMs < 60000) return `${(diffMs / 1000).toFixed(1)}s`;
    return `${(diffMs / 60000).toFixed(1)}min`;
  };
  const duration = getDuration();

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="mt-4 border border-blue-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="bg-blue-50 px-4 py-3 border-b border-blue-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">🔗</span>
            <span className="font-semibold text-blue-800">Cross-Service Trace</span>
          </div>
          <div className="flex items-center gap-3">
            {duration && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">{duration}</span>
            )}
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
              {total_events} events
            </span>
            {request_flow.length > 0 && (
              <button
                onClick={() => setShowGraphModal(true)}
                className="text-xs text-blue-600 hover:text-blue-800 hover:underline font-medium flex items-center gap-1"
                title="View topology"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
                View topology
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-blue-600 mt-1 font-mono break-all">{correlation_id}</p>
      </div>

      {/* Request Flow Visualization — colors from both CW + APM */}
      {request_flow.length > 0 && (
        <div className="px-4 py-3 bg-white border-b border-blue-100">
          <p className="text-xs text-gray-500 mb-2 font-medium">Request Flow:</p>
          <div className="flex items-center gap-2 flex-wrap">
            {request_flow.map((step, index) => {
              const status = serviceStatusMap[step.service] || 'ok';
              return (
                <div key={step.service} className="flex items-center">
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-400 font-mono">{step.order}</span>
                    <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${STATUS_PILL[status]}`}>
                      {step.service}
                    </span>
                  </div>
                  {index < request_flow.length - 1 && (
                    <svg className="w-5 h-5 text-gray-400 mx-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Services Summary */}
      <div className="px-4 py-2 bg-gray-50 border-b border-blue-100">
        <p className="text-xs text-gray-500">
          Found in {services_found.length} of {services_searched} services searched:
          {services_found.length > 0 && (
            <span className="ml-1 text-gray-700 font-medium">{services_found.join(', ')}</span>
          )}
          {apmCount > 0 && (
            <span className="ml-2 text-violet-600">
              | APM: {apmCount} span{apmCount !== 1 ? 's' : ''}
            </span>
          )}
        </p>
      </div>

      {/* UNIFIED Event Timeline — CW logs + APM spans interleaved */}
      {unifiedTimeline.length > 0 && (
        <div className="px-4 py-3 max-h-80 overflow-y-auto">
          <p className="text-xs text-gray-500 mb-2 font-medium flex items-center gap-2">
            Correlated Timeline
            <span className="flex items-center gap-1.5 ml-1">
              <span className="inline-flex items-center gap-1 text-[10px] text-orange-600">
                <span className="w-2 h-2 rounded-full bg-orange-400 inline-block"></span> CW {cwCount}
              </span>
              {apmCount > 0 && (
                <span className="inline-flex items-center gap-1 text-[10px] text-violet-600">
                  <span className="w-2 h-2 rounded-full bg-violet-500 inline-block"></span> APM {apmCount}
                </span>
              )}
            </span>
          </p>
          <div className="space-y-1.5">
            {unifiedTimeline.slice(0, 30).map((entry, index) => {
              const s = STATUS_ROW[entry.status] || STATUS_ROW.ok;
              const src = SOURCE_TAG[entry.source] || SOURCE_TAG.cloudwatch;
              const durColor = entry.duration_ms > 1000 ? 'text-amber-600 font-semibold'
                : entry.duration_ms > 200 ? 'text-amber-500' : 'text-gray-400';

              return (
                <div key={index} className={`flex gap-2 text-xs p-2 rounded items-center ${s.row}`}>
                  {/* Source tag */}
                  <span className={`shrink-0 px-1.5 py-0.5 rounded border text-[9px] font-bold leading-none ${src.cls}`}>
                    {src.label}
                  </span>
                  {/* Timestamp */}
                  {entry.timestamp && (
                    <span className="text-gray-400 whitespace-nowrap font-mono shrink-0">
                      {new Date(entry.timestamp).toLocaleString('en-US', { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true })}
                    </span>
                  )}
                  {/* Service badge */}
                  <span className={`font-medium whitespace-nowrap px-2 py-0.5 rounded shrink-0 ${s.badge}`}>
                    {entry.service}
                  </span>
                  {/* Message */}
                  <span className={`truncate min-w-0 ${s.text}`}>
                    {entry.message.substring(0, 150)}
                    {entry.message.length > 150 && '...'}
                  </span>
                  {/* Duration (APM spans) */}
                  {entry.duration_ms != null && (
                    <span className={`ml-auto whitespace-nowrap font-mono shrink-0 ${durColor}`}>
                      {entry.duration_ms}ms
                    </span>
                  )}
                  {/* Error indicator */}
                  {entry.status === 'error' && entry.source === 'elasticsearch' && (
                    <span className="text-red-500 text-[9px] font-bold px-1 py-0.5 bg-red-100 rounded shrink-0">ERR</span>
                  )}
                  {/* CW external link */}
                  {entry.cloudwatch_url && (
                    <a
                      href={entry.cloudwatch_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto flex-shrink-0 text-blue-600 hover:text-blue-800"
                      title="Open in CloudWatch Logs"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  )}
                </div>
              );
            })}
            {unifiedTimeline.length > 30 && (
              <p className="text-xs text-gray-400 italic text-center py-2">
                ... and {unifiedTimeline.length - 30} more events
              </p>
            )}
          </div>
        </div>
      )}

      {/* No events message */}
      {unifiedTimeline.length === 0 && (
        <div className="px-4 py-6 text-center">
          <p className="text-gray-500 text-sm">No events found for this correlation ID</p>
          <p className="text-gray-400 text-xs mt-1">
            Try extending the time range or verify the correlation ID format
          </p>
        </div>
      )}

      {/* Trace Graph Modal */}
      <TraceGraphModal
        isOpen={showGraphModal}
        onClose={() => setShowGraphModal(false)}
        correlationData={correlationData}
      />

      {/* Footer with timing info */}
      {first_seen && last_seen && (
        <div className="px-4 py-2 bg-gray-50 border-t border-blue-100 text-xs text-gray-500 flex justify-between">
          <span>
            First: {new Date(first_seen.timestamp).toLocaleString()} ({first_seen.service})
          </span>
          <span>
            Last: {new Date(last_seen.timestamp).toLocaleString()} ({last_seen.service})
          </span>
        </div>
      )}
    </div>
  );
}
