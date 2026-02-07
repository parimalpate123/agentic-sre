/**
 * CorrelationView Component
 * Displays cross-service correlation results with timeline and request flow visualization
 */

import { useState } from 'react';
import TraceGraphModal from './TraceGraphModal';

export default function CorrelationView({ correlationData }) {
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

  // Calculate duration if we have first and last seen
  const getDuration = () => {
    if (!first_seen || !last_seen) return null;
    const start = new Date(first_seen.timestamp);
    const end = new Date(last_seen.timestamp);
    const diffMs = end - start;
    if (diffMs < 1000) return `${diffMs}ms`;
    if (diffMs < 60000) return `${(diffMs / 1000).toFixed(1)}s`;
    return `${(diffMs / 60000).toFixed(1)}min`;
  };

  const duration = getDuration();

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
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                {duration}
              </span>
            )}
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
              {total_events} events
            </span>
            {request_flow.length > 0 && (
              <button
                onClick={() => setShowGraphModal(true)}
                className="text-xs text-blue-600 hover:text-blue-800 hover:underline font-medium flex items-center gap-1"
                title="View Datadog-style topology"
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

      {/* Request Flow Visualization */}
      {request_flow.length > 0 && (
        <div className="px-4 py-3 bg-white border-b border-blue-100">
          <p className="text-xs text-gray-500 mb-2 font-medium">Request Flow:</p>
          <div className="flex items-center gap-2 flex-wrap">
            {request_flow.map((step, index) => (
              <div key={step.service} className="flex items-center">
                <div className="flex items-center gap-1">
                  <span className="text-xs text-gray-400 font-mono">{step.order}</span>
                  <span className="bg-blue-100 text-blue-800 px-3 py-1.5 rounded-full text-sm font-medium">
                    {step.service}
                  </span>
                </div>
                {index < request_flow.length - 1 && (
                  <svg className="w-5 h-5 text-gray-400 mx-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Services Summary */}
      <div className="px-4 py-2 bg-gray-50 border-b border-blue-100">
        <p className="text-xs text-gray-500">
          Found in {services_found.length} of {services_searched} services searched:
          {services_found.length > 0 && (
            <span className="ml-1 text-gray-700 font-medium">
              {services_found.join(', ')}
            </span>
          )}
        </p>
      </div>

      {/* Event Timeline */}
      {timeline.length > 0 && (
        <div className="px-4 py-3 max-h-64 overflow-y-auto">
          <p className="text-xs text-gray-500 mb-2 font-medium">Event Timeline:</p>
          <div className="space-y-2">
            {timeline.slice(0, 15).map((event, index) => {
              // Detect error/warning patterns in message
              const isError = /error|fail|exception/i.test(event.message);
              const isWarning = /warn|timeout|retry/i.test(event.message);

              return (
                <div
                  key={index}
                  className={`flex gap-3 text-xs p-2 rounded ${
                    isError
                      ? 'bg-red-50'
                      : isWarning
                      ? 'bg-yellow-50'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  <span className="text-gray-400 whitespace-nowrap font-mono">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                  <span
                    className={`font-medium whitespace-nowrap px-2 py-0.5 rounded ${
                      isError
                        ? 'bg-red-100 text-red-700'
                        : isWarning
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {event.service}
                  </span>
                  <span className={`truncate ${isError ? 'text-red-600' : 'text-gray-600'}`}>
                    {event.message.substring(0, 150)}
                    {event.message.length > 150 && '...'}
                  </span>
                  {event.cloudwatch_url && (
                    <a
                      href={event.cloudwatch_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto flex-shrink-0 text-blue-600 hover:text-blue-800"
                      title="Open in CloudWatch Logs"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  )}
                </div>
              );
            })}
            {timeline.length > 15 && (
              <p className="text-xs text-gray-400 italic text-center py-2">
                ... and {timeline.length - 15} more events
              </p>
            )}
          </div>
        </div>
      )}

      {/* No events message */}
      {timeline.length === 0 && (
        <div className="px-4 py-6 text-center">
          <p className="text-gray-500 text-sm">No events found for this correlation ID</p>
          <p className="text-gray-400 text-xs mt-1">
            Try extending the time range or verify the correlation ID format
          </p>
        </div>
      )}

      {/* Trace Graph Modal (Datadog-style topology) */}
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
