/**
 * MessageBubble Component
 * Displays a single chat message (user or assistant)
 */

import CorrelationView from './CorrelationView';
import ErrorPatternsView from './ErrorPatternsView';
import DiagnosisView from './DiagnosisView';

export default function MessageBubble({ message, isUser, onDiagnose, isDiagnosing = false, onCreateIncident, isCreatingIncident = false }) {
  // Get search mode badge text and styles
  const getSearchModeBadge = () => {
    switch (message.searchMode) {
      case 'quick':
        return {
          text: 'Quick',
          icon: '\u26A1',
          className: 'bg-blue-100 text-blue-700',
          title: 'Quick Search: Real-time results using filter_log_events'
        };
      case 'deep':
        return {
          text: 'Deep',
          icon: '\uD83D\uDD0D',
          className: 'bg-orange-100 text-orange-700',
          title: 'Deep Search: CloudWatch Logs Insights (may have indexing delay)'
        };
      case 'correlation':
        return {
          text: 'Trace',
          icon: '\uD83D\uDD17',
          className: 'bg-purple-100 text-purple-700',
          title: 'Cross-Service Correlation: Tracing request across multiple services'
        };
      case 'patterns':
        return {
          text: 'Patterns',
          icon: '\uD83D\uDCCA',
          className: 'bg-orange-100 text-orange-700',
          title: 'Error Pattern Analysis: Aggregated error statistics'
        };
      default:
        return null;
    }
  };

  const badge = getSearchModeBadge();

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-md'
            : 'bg-gray-100 text-gray-800 rounded-bl-md'
        }`}
      >
        {/* Search Mode Badge (for assistant messages) */}
        {!isUser && badge && (
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`text-xs font-semibold px-2 py-0.5 rounded-full ${badge.className}`}
              title={badge.title}
            >
              {badge.icon} {badge.text}
            </span>
            {/* Show services found count for correlation mode */}
            {message.searchMode === 'correlation' && message.servicesFound && (
              <span className="text-xs text-gray-500">
                {message.servicesFound.length} services
              </span>
            )}
          </div>
        )}

        {/* Message text */}
        <p className="text-sm whitespace-pre-wrap">{message.text}</p>

        {/* Insights (for assistant messages) */}
        {!isUser && message.insights && message.insights.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <p className="text-xs font-semibold text-gray-500 mb-2">💡 Insights:</p>
            <ul className="space-y-1">
              {message.insights.map((insight, index) => (
                <li key={index} className="text-xs text-gray-600 flex items-start">
                  <span className="mr-2">•</span>
                  <span>{insight}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Log entries preview (for assistant messages) - only for non-correlation mode */}
        {!isUser && message.searchMode !== 'correlation' && message.logEntries && message.logEntries.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-gray-500">
                Log Entries ({message.totalResults} total):
              </p>
              {message.cloudwatchUrl && (
                <a
                  href={message.cloudwatchUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1 transition-colors"
                  title="Open in CloudWatch Logs Console"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  View in CloudWatch
                </a>
              )}
            </div>
            <div className="bg-gray-800 rounded-lg p-2 max-h-32 overflow-y-auto">
              {message.logEntries.slice(0, 3).map((entry, index) => (
                <p key={index} className="text-xs text-green-400 font-mono truncate">
                  {entry['@message'] || JSON.stringify(entry)}
                </p>
              ))}
              {message.logEntries.length > 3 && (
                <p className="text-xs text-gray-400 mt-1">
                  ... and {message.logEntries.length - 3} more
                </p>
              )}
            </div>
          </div>
        )}

        {/* Correlation View (for cross-service trace mode) */}
        {!isUser && message.searchMode === 'correlation' && message.correlationData && (
          <CorrelationView correlationData={message.correlationData} />
        )}

        {/* Recommendations (for assistant messages) */}
        {!isUser && message.recommendations && message.recommendations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <p className="text-xs font-semibold text-gray-500 mb-2">🎯 Recommendations:</p>
            <ul className="space-y-1">
              {message.recommendations.map((recommendation, index) => (
                <li key={index} className="text-xs text-gray-600 flex items-start">
                  <span className="mr-2">→</span>
                  <span>{recommendation}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action Buttons (for assistant messages with log data) */}
        {!isUser && (message.logEntries?.length > 0 || message.patternData || message.correlationData) && !message.diagnosis && (
          <div className="mt-3 pt-3 border-t border-gray-200 flex flex-col sm:flex-row gap-2">
            {/* Diagnose Button */}
            {onDiagnose && (
              <button
                onClick={() => onDiagnose(message)}
                disabled={isDiagnosing || isCreatingIncident}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isDiagnosing ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Analyzing...
                  </>
                ) : (
                  <>
                    <span>🔍</span>
                    Diagnose Root Cause
                  </>
                )}
              </button>
            )}
            
            {/* Create Incident Button */}
            {onCreateIncident && (
              <button
                onClick={() => onCreateIncident(message)}
                disabled={isDiagnosing || isCreatingIncident}
                className="flex-1 bg-blue-800 hover:bg-blue-900 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isCreatingIncident ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Creating Incident...
                  </>
                ) : (
                  <>
                    <span>🚨</span>
                    Create Incident & Run Full Investigation
                  </>
                )}
              </button>
            )}
          </div>
        )}

        {/* Diagnosis View (if diagnosis is available) */}
        {!isUser && message.diagnosis && (
          <DiagnosisView diagnosis={message.diagnosis} />
        )}

        {/* Execution Results (if available) */}
        {!isUser && message.incident && (message.incident.execution_results || message.incident.execution_type) && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <p className="text-xs font-semibold text-gray-500 mb-2">⚡ Execution Results:</p>
            {message.incident.execution_results?.auto_execute && (
              <div className={`mb-2 p-2 rounded border ${
                message.incident.execution_results.auto_execute.status === 'success' 
                  ? 'bg-green-50 border-green-200' 
                  : message.incident.execution_results.auto_execute.status === 'failed'
                  ? 'bg-red-50 border-red-200'
                  : message.incident.execution_results.auto_execute.status === 'not_implemented'
                  ? 'bg-gray-50 border-gray-300'
                  : 'bg-blue-50 border-blue-200'
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={
                    message.incident.execution_results.auto_execute.status === 'success' 
                      ? 'text-green-600' 
                      : message.incident.execution_results.auto_execute.status === 'failed'
                      ? 'text-red-600'
                      : message.incident.execution_results.auto_execute.status === 'not_implemented'
                      ? 'text-gray-500'
                      : 'text-blue-600'
                  }>
                    {message.incident.execution_results.auto_execute.status === 'success' 
                      ? '✅' 
                      : message.incident.execution_results.auto_execute.status === 'failed'
                      ? '❌'
                      : message.incident.execution_results.auto_execute.status === 'not_implemented'
                      ? '🚧'
                      : '⏸️'}
                  </span>
                  <span className="text-xs font-medium text-gray-700">
                    {message.incident.execution_results.auto_execute.status === 'not_implemented'
                      ? 'Auto-Execute: Coming Soon'
                      : `Auto-Execute: ${message.incident.execution_results.auto_execute.status}`}
                  </span>
                </div>
                {message.incident.execution_results.auto_execute.action && (
                  <p className="text-xs text-gray-600">
                    Action: {message.incident.execution_results.auto_execute.action}
                  </p>
                )}
                {message.incident.execution_results.auto_execute.service && (
                  <p className="text-xs text-gray-600">
                    Service: {message.incident.execution_results.auto_execute.service}
                  </p>
                )}
                {message.incident.execution_results.auto_execute.message && (
                  <div className="mt-2 p-2 bg-white rounded border border-gray-200">
                    <p className="text-xs font-semibold text-gray-700 mb-1">
                      📋 Planned Implementation:
                    </p>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      {message.incident.execution_results.auto_execute.message}
                    </p>
                  </div>
                )}
                {message.incident.execution_results.auto_execute.error && (
                  <p className="text-xs text-red-600 mt-1 font-medium">
                    Error: {message.incident.execution_results.auto_execute.error}
                  </p>
                )}
              </div>
            )}
            {message.incident.execution_results?.github_issue && (
              <div className="mb-2 p-2 bg-green-50 rounded border border-green-200">
                <div className="flex items-center gap-2 mb-1">
                  <span className={message.incident.execution_results.github_issue.status === 'success' ? 'text-green-600' : 'text-red-600'}>
                    {message.incident.execution_results.github_issue.status === 'success' ? '✅' : '❌'}
                  </span>
                  <span className="text-xs font-medium text-gray-700">
                    GitHub Issue: {message.incident.execution_results.github_issue.status}
                  </span>
                </div>
                {message.incident.execution_results.github_issue.issue_url && (
                  <a
                    href={message.incident.execution_results.github_issue.issue_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    View Issue →
                  </a>
                )}
                {message.incident.execution_results.github_issue.error && (
                  <p className="text-xs text-red-600 mt-1">
                    Error: {message.incident.execution_results.github_issue.error}
                  </p>
                )}
              </div>
            )}
            {message.incident.execution_results?.escalation && (
              <div className="mb-2 p-2 bg-yellow-50 rounded border border-yellow-200">
                <div className="flex items-center gap-2 mb-1">
                  <span>⚠️</span>
                  <span className="text-xs font-medium text-gray-700">
                    Escalated to Human
                  </span>
                </div>
                {message.incident.execution_results.escalation.reason && (
                  <p className="text-xs text-gray-600">
                    Reason: {message.incident.execution_results.escalation.reason}
                  </p>
                )}
              </div>
            )}
            {message.incident.execution_type && !message.incident.execution_results && (
              <div className="mb-2 p-2 bg-gray-50 rounded border border-gray-200">
                <p className="text-xs text-gray-600">
                  Execution Type: <span className="font-medium">{message.incident.execution_type}</span>
                </p>
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <p className={`text-xs mt-2 ${isUser ? 'text-blue-200' : 'text-gray-400'}`}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}
