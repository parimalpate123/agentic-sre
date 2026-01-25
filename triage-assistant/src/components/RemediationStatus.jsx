/**
 * Remediation Status Component
 * Shows the full lifecycle: Issue → PR → Review → Merge
 * With expandable timeline for detailed events
 */

import { useState } from 'react';

export default function RemediationStatus({ incidentId, remediationStatus, onRefresh }) {
  const [expandedTimeline, setExpandedTimeline] = useState(false);
  const [expandedDetails, setExpandedDetails] = useState({});

  if (!remediationStatus) {
    return (
      <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-sm text-gray-600">Loading remediation status...</p>
      </div>
    );
  }

  const { issue, pr, timeline, next_action } = remediationStatus;

  // Group timeline events by type for better organization
  const majorMilestones = timeline?.filter(event => 
    ['issue_created', 'pr_created', 'pr_reviewed', 'pr_merged'].includes(event.event)
  ) || [];

  const detailedEvents = timeline?.filter(event => 
    !['issue_created', 'pr_created', 'pr_reviewed', 'pr_merged'].includes(event.event)
  ) || [];

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
      case 'merged':
      case 'approved':
        return '✅';
      case 'open':
      case 'created':
        return '🔄';
      case 'failed':
      case 'changes_requested':
        return '⚠️';
      case 'pending':
        return '⏳';
      default:
        return '📋';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'success':
      case 'merged':
      case 'approved':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'open':
      case 'created':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'failed':
      case 'changes_requested':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'pending':
        return 'text-gray-600 bg-gray-50 border-gray-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const toggleDetail = (eventIndex) => {
    setExpandedDetails(prev => ({
      ...prev,
      [eventIndex]: !prev[eventIndex]
    }));
  };

  return (
    <div className="mt-4 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-800">🔄 Remediation Lifecycle</h3>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            Refresh
          </button>
        )}
      </div>

      {/* Current Status */}
      <div className="mb-4">
        <div className="flex items-center gap-3 mb-3">
          {/* Issue Status */}
          {issue && (
            <div className={`flex-1 p-3 rounded-lg border ${getStatusColor('open')}`}>
              <div className="flex items-center gap-2 mb-1">
                <span>{getStatusIcon('open')}</span>
                <span className="text-xs font-semibold">Issue #{issue.number}</span>
              </div>
              {issue.url && (
                <a
                  href={issue.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline"
                >
                  View Issue →
                </a>
              )}
            </div>
          )}
          
          {/* PR Status */}
          {pr ? (
            <div className={`flex-1 p-3 rounded-lg border ${getStatusColor(pr.status)}`}>
              <div className="flex items-center gap-2 mb-1">
                <span>{getStatusIcon(pr.status)}</span>
                <span className="text-xs font-semibold">PR #{pr.number}</span>
              </div>
              <div className="space-y-1">
                {pr.url && (
                  <a
                    href={pr.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline block"
                  >
                    View PR →
                  </a>
                )}
                {pr.review_status && (
                  <p className="text-xs text-gray-600">
                    Review: <span className="font-medium">{pr.review_status}</span>
                  </p>
                )}
                {pr.merge_status && (
                  <p className="text-xs text-gray-600">
                    Merge: <span className="font-medium">{pr.merge_status}</span>
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex-1 p-3 rounded-lg border border-gray-200 bg-gray-50">
              <div className="flex items-center gap-2">
                <span>⏳</span>
                <span className="text-xs text-gray-600">Waiting for PR...</span>
              </div>
            </div>
          )}
        </div>

        {/* Next Action */}
        {next_action && (
          <div className="p-2 bg-blue-50 border border-blue-200 rounded">
            <p className="text-xs text-blue-800">
              <span className="font-semibold">Next:</span> {next_action}
            </p>
          </div>
        )}
      </div>

      {/* Timeline - Collapsible */}
      {timeline && timeline.length > 0 && (
        <div className="border-t border-gray-200 pt-4">
          <button
            onClick={() => setExpandedTimeline(!expandedTimeline)}
            className="flex items-center justify-between w-full text-sm font-medium text-gray-700 hover:text-gray-900 mb-2"
          >
            <span>Timeline ({timeline.length} events)</span>
            <span className="text-gray-400">
              {expandedTimeline ? '▼' : '▶'}
            </span>
          </button>

          {expandedTimeline && (
            <div className="space-y-2 mt-2">
              {/* Major Milestones - Always Visible */}
              {majorMilestones.map((event, index) => (
                <div key={index} className="flex items-start gap-3 p-2 bg-gray-50 rounded">
                  <div className="flex-shrink-0 w-2 h-2 rounded-full bg-blue-500 mt-1.5"></div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-gray-800 capitalize">
                        {event.event.replace(/_/g, ' ')}
                      </p>
                      <span className="text-xs text-gray-500">
                        {formatTimestamp(event.timestamp)}
                      </span>
                    </div>
                    {event.issue_url && (
                      <a
                        href={event.issue_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline mt-1 block"
                      >
                        Issue #{event.issue_number} →
                      </a>
                    )}
                    {event.pr_url && (
                      <a
                        href={event.pr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline mt-1 block"
                      >
                        PR #{event.pr_number} →
                      </a>
                    )}
                    {event.reviewer && (
                      <p className="text-xs text-gray-600 mt-1">
                        Reviewed by: <span className="font-medium">{event.reviewer}</span>
                      </p>
                    )}
                    {event.merger && (
                      <p className="text-xs text-gray-600 mt-1">
                        Merged by: <span className="font-medium">{event.merger}</span>
                      </p>
                    )}
                  </div>
                </div>
              ))}

              {/* Detailed Events - Collapsible */}
              {detailedEvents.length > 0 && (
                <div className="mt-3">
                  <button
                    onClick={() => setExpandedDetails(prev => ({ ...prev, details: !prev.details }))}
                    className="text-xs text-gray-600 hover:text-gray-800 font-medium mb-2"
                  >
                    {expandedDetails.details ? '▼' : '▶'} Detailed Events ({detailedEvents.length})
                  </button>
                  {expandedDetails.details && (
                    <div className="space-y-1 ml-4 border-l-2 border-gray-200 pl-3">
                      {detailedEvents.map((event, index) => (
                        <div key={index} className="text-xs text-gray-600 py-1">
                          <span className="font-medium">{event.event.replace(/_/g, ' ')}</span>
                          {' '}
                          <span className="text-gray-500">
                            {formatTimestamp(event.timestamp)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
