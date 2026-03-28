/**
 * ESMetricsIndicator - Expandable panel showing APM metrics, traces, and infra data
 * from Elasticsearch in a dark terminal-style box matching the CW log entries look.
 */

import { useState } from 'react';

export default function ESMetricsIndicator({ esContext }) {
  const [expanded, setExpanded] = useState(false);

  if (!esContext || !esContext.available) return null;

  const summary = esContext.summary || {};
  const errorTraces = esContext.error_traces_sample || [];
  const errorCount = esContext.error_traces_count || 0;

  // Count available metric categories
  const categories = [];
  if (summary.latency_p95 != null) categories.push('APM');
  if (summary.cpu_pct != null) categories.push('Infra');
  if (errorCount > 0) categories.push(`${errorCount} error trace${errorCount !== 1 ? 's' : ''}`);
  if (summary.health_status) categories.push(summary.health_status);

  if (categories.length === 0) return null;

  const label = categories.join(' \u00b7 ');

  // Health status color for terminal
  const healthTermColor = {
    healthy: 'text-green-400',
    warning: 'text-yellow-400',
    degraded: 'text-red-400',
  }[summary.health_status] || 'text-gray-400';

  return (
    <div className="mt-2 w-full">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-amber-600 hover:text-amber-800 font-medium"
      >
        <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        APM Telemetry ({label})
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-2 bg-gray-800 rounded-lg p-3 max-h-96 overflow-y-auto space-y-3">
          {/* Performance Metrics */}
          {summary.latency_p95 != null && (
            <div className="border-l-2 border-amber-500 pl-2">
              <p className="text-xs text-amber-400 font-mono font-semibold mb-1">Performance Metrics</p>
              <div className="text-xs font-mono space-y-0.5">
                <p className="text-gray-300">
                  Latency p50: <span className="text-cyan-400">{summary.latency_p50}ms</span>
                  {' | '}p95: <span className="text-amber-400 font-semibold">{summary.latency_p95}ms</span>
                  {' | '}p99: <span className="text-cyan-400">{summary.latency_p99}ms</span>
                </p>
                {summary.throughput_rpm != null && (
                  <p className="text-gray-300">
                    Throughput: <span className="text-cyan-400">{summary.throughput_rpm} req/min</span>
                  </p>
                )}
                {summary.error_rate_pct != null && (
                  <p className="text-gray-300">
                    Error Rate: <span className={`font-semibold ${summary.error_rate_pct > 5 ? 'text-red-400' : 'text-cyan-400'}`}>
                      {summary.error_rate_pct}%
                    </span>
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Infrastructure */}
          {summary.cpu_pct != null && (
            <div className="border-l-2 border-blue-500 pl-2">
              <p className="text-xs text-blue-400 font-mono font-semibold mb-1">Infrastructure</p>
              <p className="text-xs font-mono text-gray-300">
                CPU: <span className={`font-semibold ${summary.cpu_pct > 80 ? 'text-red-400' : 'text-cyan-400'}`}>{summary.cpu_pct}%</span>
                {' | '}Memory: <span className={`font-semibold ${summary.memory_pct > 85 ? 'text-red-400' : 'text-cyan-400'}`}>{summary.memory_pct}%</span>
                {' | '}Disk: <span className="text-cyan-400">{summary.disk_pct}%</span>
              </p>
            </div>
          )}

          {/* Service Health */}
          {summary.health_status && (
            <div className="border-l-2 border-gray-500 pl-2">
              <p className="text-xs font-mono text-gray-300">
                Service Health: <span className={`font-semibold ${healthTermColor}`}>{summary.health_status}</span>
                {' | '}{summary.instances} instance{summary.instances !== 1 ? 's' : ''}
                {summary.dependencies?.length > 0 && (
                  <span className="text-gray-400"> | Deps: {summary.dependencies.join(', ')}</span>
                )}
              </p>
            </div>
          )}

          {/* Error Traces */}
          {errorCount > 0 && (
            <div className="border-l-2 border-red-500 pl-2">
              <p className="text-xs text-red-400 font-mono font-semibold mb-1">Error Traces ({errorCount})</p>
              <div className="space-y-1">
                {errorTraces.map((trace, idx) => (
                  <p key={idx} className="text-xs font-mono text-green-400 whitespace-pre-wrap break-words">
                    <span className="text-red-400">x</span>{' '}
                    {trace.trace?.name || 'Unknown'} — {trace.trace?.duration_ms}ms
                    {trace.correlation_id && (
                      <span className="text-gray-500"> ({trace.correlation_id.slice(0, 24)}...)</span>
                    )}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
