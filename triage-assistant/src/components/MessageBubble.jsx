/**
 * MessageBubble Component
 * Displays a single chat message (user or assistant)
 */

import CorrelationView from './CorrelationView';
import ErrorPatternsView from './ErrorPatternsView';
import DiagnosisView from './DiagnosisView';
import RemediationStatus from './RemediationStatus';
import KBSourceIndicator from './KBSourceIndicator';

export default function MessageBubble({ 
  message, 
  isUser, 
  onQuestionClick = null,
  onDiagnose, 
  isDiagnosing = false, 
  onCreateIncident, 
  isCreatingIncident = false,
  remediationStatus = null,
  onRefreshRemediation = null,
  onCreateGitHubIssue = null,
  onPausePolling = null,
  onResumePolling = null,
  isPollingActive = false,
  isPollingPaused = false,
  onCheckPRStatus = null,
  onReanalyzeIncident = null,
  isReanalyzing = false
}) {
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
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 w-full`}>
      <div className={`flex flex-col w-full max-w-full ${isUser ? 'items-end' : ''}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-violet-100 text-gray-900 rounded-br-md shadow-sm border-l-4 border-violet-600'
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

        {/* Message text - but if it's an incident, we'll show it after Execution Results */}
        {!message.incident && <p className="text-sm whitespace-pre-wrap">{message.text}</p>}

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
                  className="text-xs text-violet-600 hover:text-violet-800 hover:underline flex items-center gap-1 transition-colors"
                  title="Open in CloudWatch Logs Console"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  View in CloudWatch
                </a>
              )}
            </div>
            <div className="bg-gray-800 rounded-lg p-3 max-h-96 overflow-y-auto space-y-2">
              {message.logEntries.map((entry, index) => (
                <div key={index} className="border-l-2 border-yellow-500 pl-2">
                  <p className="text-xs text-gray-400 font-mono mb-1">
                    🕐 {entry['@timestamp'] || 'No timestamp'}
                  </p>
                  <p className="text-xs text-green-400 font-mono whitespace-pre-wrap break-words">
                    {entry['@message'] || JSON.stringify(entry)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Correlation View (for cross-service trace mode) */}
        {!isUser && message.searchMode === 'correlation' && message.correlationData && (
          <CorrelationView correlationData={message.correlationData} />
        )}

        {/* Recommendations (for assistant messages) - clickable as follow-up questions */}
        {!isUser && message.recommendations && message.recommendations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <p className="text-xs font-semibold text-gray-900 mb-2">🎯 Recommendations:</p>
            <ul className="space-y-1.5">
              {message.recommendations.map((recommendation, index) => (
                <li key={index} className="text-xs text-gray-900 flex items-start">
                  <span className="mr-2">→</span>
                  {onQuestionClick ? (
                    <button
                      type="button"
                      onClick={() => onQuestionClick(recommendation)}
                      className="text-left text-gray-900 hover:text-black hover:underline focus:outline-none focus:underline"
                    >
                      {recommendation}
                    </button>
                  ) : (
                    <span>{recommendation}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* KB Source Indicator (shown when KB context was used) */}
        {!isUser && message.kbSources?.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <KBSourceIndicator sources={message.kbSources} />
          </div>
        )}

        {/* Action links (for assistant messages with log data) – link-style, content-first UX */}
        {!isUser && (message.logEntries?.length > 0 || message.patternData || message.correlationData) && !message.diagnosis && (
          <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap items-center gap-x-4 gap-y-2">
            {onCreateIncident && 
             !(message.incident?.source === 'cloudwatch_alarm' && message.incident?.execution_type === 'code_fix') && (
              <button
                  onClick={() => onCreateIncident(message)}
                  disabled={isDiagnosing || isCreatingIncident}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-violet-600 hover:text-violet-800 hover:underline disabled:opacity-50 disabled:cursor-not-allowed disabled:no-underline"
                >
                  {isCreatingIncident ? (
                    <>
                      <svg className="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Running investigation...
                    </>
                  ) : (
                    <>
                      <span className="text-base" aria-hidden>🚨</span>
                      Run full investigation
                    </>
                  )}
                </button>
            )}
            
            {/* Auto-execution status for CloudWatch incidents with code_fix */}
            {(() => {
              const isCloudWatch = message.incident?.source === 'cloudwatch_alarm';
              const isCodeFix = message.incident?.execution_type === 'code_fix';
              const hasExecutionResults = !!message.incident?.execution_results?.github_issue;
              
              // Debug logging
              if (isCloudWatch && isCodeFix) {
                console.log('🔍 Auto-execution status check:', {
                  source: message.incident?.source,
                  execution_type: message.incident?.execution_type,
                  has_execution_results: hasExecutionResults,
                  github_issue_status: message.incident?.execution_results?.github_issue?.status,
                  full_execution_results: message.incident?.execution_results
                });
              }
              
              return isCloudWatch && isCodeFix;
            })() && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                {message.incident?.execution_results?.github_issue?.status === 'success' ? (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-green-800">
                      <span>✅</span>
                      <span className="font-medium">Auto-execution Complete</span>
                    </div>
                    <p className="text-sm text-green-700 mt-1">
                      GitHub issue created automatically. Issue #{message.incident.execution_results.github_issue.issue_number} -{' '}
                      <a
                        href={message.incident.execution_results.github_issue.issue_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline hover:text-green-900"
                      >
                        View Issue
                      </a>
                    </p>
                  </div>
                ) : message.incident?.execution_results?.github_issue?.status === 'pending_approval' ? (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-yellow-800">
                      <span>⏳</span>
                      <span className="font-medium">Auto-execution Pending</span>
                    </div>
                    <p className="text-sm text-yellow-700 mt-1">
                      GitHub issue creation is pending approval.
                    </p>
                  </div>
                ) : message.incident?.execution_results?.github_issue?.status === 'error' ? (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-red-800">
                      <span>❌</span>
                      <span className="font-medium">Auto-execution Failed</span>
                    </div>
                    <p className="text-sm text-red-700 mt-1">
                      GitHub issue auto-creation failed: {message.incident.execution_results.github_issue.error || 'Unknown error'}
                    </p>
                  </div>
                ) : (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-blue-800">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      <span className="font-medium">Auto-creating GitHub Issue...</span>
                    </div>
                    <p className="text-sm text-blue-700 mt-1">
                      This CloudWatch incident requires code changes. GitHub issue is being created automatically.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Diagnosis View (if diagnosis is available) */}
        {!isUser && message.diagnosis && (
          <>
            {(message.incident?.source === 'servicenow' || message.incident?.source === 'jira') && message.incident?.incident_id && (
              <p className="text-sm font-medium text-gray-700 mb-2">
                {message.incident.source === 'servicenow' ? 'ServiceNow' : 'Jira'} {message.incident.source === 'servicenow' ? 'ticket' : 'issue'}: <strong>#{message.incident.incident_id}</strong>
              </p>
            )}
            <DiagnosisView diagnosis={message.diagnosis} />
          </>
        )}

        {/* Show incident analysis text BEFORE Execution Results */}
        {!isUser && message.incident && message.text && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <p className="text-sm whitespace-pre-wrap">{message.text}</p>
          </div>
        )}

        {/* Remediation Status (only for code_fix actions with GitHub issue created) */}
        {!isUser && 
         message.incident?.incident_id && 
         message.incident?.execution_type === 'code_fix' &&
         // Only show if GitHub issue was successfully created OR we have remediation status
         ((message.incident?.execution_results?.github_issue?.status === 'success') || remediationStatus) && (
          <RemediationStatus
            incidentId={message.incident.incident_id}
            remediationStatus={remediationStatus}
            onRefresh={onRefreshRemediation}
            onPausePolling={onPausePolling}
            onResumePolling={onResumePolling}
            isPollingActive={isPollingActive}
            isPollingPaused={isPollingPaused}
            onCheckPRStatus={onCheckPRStatus}
          />
        )}

        {/* Action Buttons for ServiceNow/Jira incidents loaded from Incidents dialog (exclusive: do not show if this message has log/pattern data - that uses the block above) */}
        {!isUser &&
         message.incident &&
         (message.incident.source === 'servicenow' || message.incident.source === 'jira') &&
         !(message.logEntries?.length > 0 || message.patternData || message.correlationData) &&
         !message.diagnosis &&
         !message.investigationStarted && (
          <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap items-center gap-x-4 gap-y-2">
            {onCreateIncident && (
              <button
                onClick={() => onCreateIncident(message)}
                disabled={isDiagnosing || isCreatingIncident}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-violet-600 hover:text-violet-800 hover:underline disabled:opacity-50 disabled:cursor-not-allowed disabled:no-underline"
              >
                {isCreatingIncident ? (
                  <>
                    <svg className="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Running investigation...
                  </>
                ) : (
                  <>
                    <span className="text-base" aria-hidden>🚨</span>
                    Run full investigation
                  </>
                )}
              </button>
            )}
          </div>
        )}

        {/* Action links for CloudWatch incidents loaded from Incidents dialog */}
        {!isUser &&
         message.incident &&
         message.incident.source === 'cloudwatch_alarm' &&
         !(message.logEntries?.length > 0 || message.patternData || message.correlationData) &&
         !message.incident.execution_results?.github_issue &&
         !message.diagnosis &&
         !message.investigationStarted && (
          <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap items-center gap-x-4 gap-y-2">
            {onCreateIncident && 
             !(message.incident?.source === 'cloudwatch_alarm' && message.incident?.execution_type === 'code_fix') && (
              <button
                onClick={() => onCreateIncident(message)}
                disabled={isDiagnosing || isCreatingIncident}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-violet-600 hover:text-violet-800 hover:underline disabled:opacity-50 disabled:cursor-not-allowed disabled:no-underline"
              >
                {isCreatingIncident ? (
                  <>
                    <svg className="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Running investigation...
                  </>
                ) : (
                  <>
                    <span className="text-base" aria-hidden>🚨</span>
                    Run full investigation
                  </>
                )}
              </button>
            )}
            
            {/* Auto-execution status for CloudWatch incidents with code_fix */}
            {message.incident?.source === 'cloudwatch_alarm' && 
             message.incident?.execution_type === 'code_fix' && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                {message.incident?.execution_results?.github_issue?.status === 'success' ? (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-green-800">
                      <span>✅</span>
                      <span className="font-medium">Auto-execution Complete</span>
                    </div>
                    <p className="text-sm text-green-700 mt-1">
                      GitHub issue created automatically. Issue #{message.incident.execution_results.github_issue.issue_number} -{' '}
                      <a
                        href={message.incident.execution_results.github_issue.issue_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline hover:text-green-900"
                      >
                        View Issue
                      </a>
                    </p>
                  </div>
                ) : message.incident?.execution_results?.github_issue?.status === 'pending_approval' ? (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-yellow-800">
                      <span>⏳</span>
                      <span className="font-medium">Auto-execution Pending</span>
                    </div>
                    <p className="text-sm text-yellow-700 mt-1">
                      GitHub issue creation is pending approval.
                    </p>
                  </div>
                ) : message.incident?.execution_results?.github_issue?.status === 'error' ? (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-red-800">
                      <span>❌</span>
                      <span className="font-medium">Auto-execution Failed</span>
                    </div>
                    <p className="text-sm text-red-700 mt-1">
                      GitHub issue auto-creation failed: {message.incident.execution_results.github_issue.error || 'Unknown error'}
                    </p>
                  </div>
                ) : (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-blue-800">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      <span className="font-medium">Auto-creating GitHub Issue...</span>
                    </div>
                    <p className="text-sm text-blue-700 mt-1">
                      This CloudWatch incident requires code changes. GitHub issue is being created automatically.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Execution Results (shown AFTER incident analysis) */}
        {!isUser && 
         message.incident && 
         (message.incident.execution_results || message.incident.execution_type) && 
         message.incident.source !== 'cloudwatch_alarm' && (
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
              <div className={`mb-2 p-3 rounded border ${
                message.incident.execution_results.github_issue.status === 'success' 
                  ? 'bg-green-50 border-green-200' 
                  : message.incident.execution_results.github_issue.status === 'pending_approval'
                  ? 'bg-amber-50 border-amber-200'
                  : 'bg-red-50 border-red-200'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={
                    message.incident.execution_results.github_issue.status === 'success' 
                      ? 'text-green-600' 
                      : message.incident.execution_results.github_issue.status === 'pending_approval'
                      ? 'text-amber-600'
                      : 'text-red-600'
                  }>
                    {message.incident.execution_results.github_issue.status === 'success' 
                      ? '✅' 
                      : message.incident.execution_results.github_issue.status === 'pending_approval'
                      ? '⏳'
                      : '❌'}
                  </span>
                  <span className="text-xs font-medium text-gray-700">
                    GitHub Issue: {message.incident.execution_results.github_issue.status === 'pending_approval' ? 'Pending Approval' : message.incident.execution_results.github_issue.status}
                  </span>
                </div>
                {message.incident.execution_results.github_issue.status === 'pending_approval' && 
                 onCreateGitHubIssue && 
                 message.incident.source !== 'cloudwatch_alarm' && (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-600 mb-2">
                      💡 <strong>Code changes required:</strong> This incident requires code modifications. Click the button below to create a GitHub issue in the <strong>{message.incident.service || 'service'}</strong> repository. The Issue Agent will automatically analyze and create a fix.
                    </p>
                    <button
                      onClick={() => onCreateGitHubIssue(message.incident)}
                      className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium py-2 px-4 rounded transition-colors inline-flex items-center justify-center gap-2"
                    >
                      <span>🔗</span>
                      Create GitHub Issue
                    </button>
                  </div>
                )}
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
          </div>
        )}

        {/* Re-analyze Button - CloudWatch only (not for ServiceNow/Jira) */}
        {!isUser &&
         message.incident &&
         message.incident.source === 'cloudwatch_alarm' &&
         message.incident.incident_id &&
         onReanalyzeIncident && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            {/* Show Re-analyze button if:
                1. execution_type is NOT code_fix (e.g., escalate, monitor)
                2. OR root_cause is Unknown/empty
                3. OR error_count is 0 or missing
            */}
            {(
              (message.incident.execution_type && 
               message.incident.execution_type !== 'code_fix') ||
              (message.incident.root_cause === 'Unknown' || 
               !message.incident.root_cause ||
               message.incident.root_cause === 'Analysis in progress') ||
              (message.incident.error_count === 0 || !message.incident.error_count)
            ) && (
              <div className="space-y-2">
                <p className="text-xs text-gray-600 mb-2">
                  🔄 <strong>Re-analyze Incident:</strong> Re-run the investigation to check for new errors or updated analysis.
                </p>
                <button
                  onClick={() => onReanalyzeIncident(message.incident.incident_id)}
                  disabled={isReanalyzing}
                  className={`${
                    isReanalyzing 
                      ? 'bg-gray-400 cursor-not-allowed' 
                      : 'bg-violet-600 hover:bg-violet-700'
                  } text-white text-xs font-medium py-2 px-4 rounded transition-colors inline-flex items-center justify-center gap-2`}
                >
                  {isReanalyzing ? (
                    <>
                      <span className="animate-spin">⏳</span>
                      Re-analyzing...
                    </>
                  ) : (
                    <>
                      <span>🔄</span>
                      Re-analyze Incident
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <p className={`text-xs mt-2 ${isUser ? 'text-violet-600' : 'text-gray-400'}`}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>

      {/* Suggested questions - outside response block, below in a single line that wraps */}
      {!isUser && message.followUpQuestions && message.followUpQuestions.length > 0 && (
        <div className="mt-2 w-full flex flex-wrap gap-2 items-center">
          <span className="text-xs font-semibold text-gray-500 shrink-0">💡 Suggested questions:</span>
          {message.followUpQuestions.map((question, index) => (
            <button
              key={index}
              type="button"
              onClick={() => onQuestionClick?.(question)}
              className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-gray-50 text-gray-500 hover:bg-gray-100 hover:border-gray-400 hover:text-gray-600 text-left shrink-0"
            >
              {question}
            </button>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}
