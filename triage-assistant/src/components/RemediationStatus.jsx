/**
 * Remediation Status Component
 * Shows the automated lifecycle: Issue → Analysis → AI-Powered Fix Generation → PR Creation → AI-Powered PR Review
 * After PR creation, AI-powered PR Review is automatically triggered
 */

import { useState, useEffect, useRef } from 'react';

// Stage definitions - only automated stages
const STAGES = [
  {
    id: 'issue',
    name: 'Issue Created',
    icon: '📋',
    description: 'GitHub issue created for remediation',
    event: 'issue_created'
  },
  {
    id: 'analysis',
    name: 'Analysis',
    icon: '🔍',
    description: 'Analyzing code patterns and root cause',
    event: 'analysis_started'
  },
  {
    id: 'fix_generation',
    name: 'AI-Powered Fix Generation',
    icon: '✏️',
    description: 'AI generating fix based on analysis',
    event: 'fix_generation_started'
  },
  {
    id: 'pr_creation',
    name: 'PR Creation',
    icon: '📝',
    description: 'Creating pull request with fix',
    event: 'pr_creation_started'
  },
  {
    id: 'pr_review',
    name: 'AI-Powered PR Review',
    icon: '🤖',
    description: 'AI reviewing pull request via PR Review Agent',
    event: 'pr_reviewed'
  }
];

export default function RemediationStatus({ 
  incidentId, 
  remediationStatus, 
  onRefresh,
  onPausePolling,
  onResumePolling,
  isPollingActive,
  isPollingPaused,
  onCheckPRStatus
}) {
  const [expandedTimeline, setExpandedTimeline] = useState(false);
  const [expandedDetails, setExpandedDetails] = useState({});
  const [isCheckingPRStatus, setIsCheckingPRStatus] = useState(false);
  
  // All hooks must be called before any early returns
  const prevStatusRef = useRef(null);
  
  // Debug logging - only log when status actually changes
  useEffect(() => {
    if (remediationStatus) {
      // Only log if status actually changed (compare by incident_id and key fields)
      const statusKey = JSON.stringify({
        incident_id: remediationStatus.incident_id,
        pr_number: remediationStatus.pr?.number,
        issue_number: remediationStatus.issue?.number,
        timeline_length: remediationStatus.timeline?.length,
        timeline_events: remediationStatus.timeline?.map(e => e.event).join(',') || ''
      });
      
      if (prevStatusRef.current !== statusKey) {
        console.log('🔍 RemediationStatus component received status:', {
          incident_id: remediationStatus.incident_id,
          has_issue: !!remediationStatus.issue,
          issue_number: remediationStatus.issue?.number,
          has_pr: !!remediationStatus.pr,
          pr_number: remediationStatus.pr?.number,
          pr_status: remediationStatus.pr?.status,
          timeline_length: remediationStatus.timeline?.length,
          timeline_events: remediationStatus.timeline?.map(e => e.event) || [],
          next_action: remediationStatus.next_action
        });
        prevStatusRef.current = statusKey;
      }
    }
    // Only depend on remediationStatus object itself
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remediationStatus]);

  // Only show loading state if polling is active (meaning we're actively fetching)
  // Don't show loading if polling hasn't started yet (before GitHub issue is created)
  if (!remediationStatus) {
    // Only show loading if polling is active (issue was created and we're fetching status)
    if (isPollingActive) {
      return (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="flex items-center gap-2">
            <svg className={`h-4 w-4 text-gray-500 ${!isPollingPaused ? 'animate-spin' : ''}`} viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <p className="text-sm text-gray-600">
              {isPollingPaused ? 'Status updates paused' : 'Loading remediation status...'}
            </p>
          </div>
        </div>
      );
    }
    // If polling hasn't started yet, don't show anything (component shouldn't be rendered)
    return null;
  }

  const { issue, pr, timeline, next_action, repo, similar_incidents_count } = remediationStatus || {};

  // Determine stage statuses
  const getStageStatus = (stage) => {
    const timelineEvents = timeline || [];
    
    // Check if stage is completed
    const isCompleted = timelineEvents.some(event => {
      if (stage.event === 'issue_created') {
        return event.event === 'issue_created' || issue?.number;
      }
      if (stage.event === 'pr_creation_started') {
        // PR creation is complete if PR exists or pr_created event exists
        return pr?.number || event.event === 'pr_created';
      }
      if (stage.event === 'pr_reviewed') {
        // PR review is complete if review_status exists and is not 'pending'
        return pr?.review_status && pr.review_status !== 'pending';
      }
      return event.event === stage.event;
    }) || (stage.event === 'pr_creation_started' && pr?.number) || // Also check if PR exists directly
         (stage.event === 'pr_reviewed' && pr?.review_status && pr.review_status !== 'pending'); // Also check review_status directly

    // Check if stage is in progress
    const isInProgress = timelineEvents.some(event => {
      const eventType = typeof event === 'object' ? event.event : event;
      if (stage.event === 'analysis_started') {
        return eventType === 'analysis_started' && !timelineEvents.some(e => (typeof e === 'object' ? e.event : e) === 'fix_generation_started');
      }
      if (stage.event === 'fix_generation_started') {
        return eventType === 'fix_generation_started' && !timelineEvents.some(e => (typeof e === 'object' ? e.event : e) === 'pr_creation_started');
      }
      if (stage.event === 'pr_creation_started') {
        return eventType === 'pr_creation_started' && !pr?.number;
      }
      if (stage.event === 'pr_created') {
        return eventType === 'pr_created' || pr?.number;
      }
      if (stage.event === 'pr_reviewed') {
        // PR review is in progress if:
        // 1. PR exists
        // 2. Review has started (pr_review_started event exists) OR review_status is not set
        // 3. BUT review is NOT yet complete (review_status is null, undefined, or 'pending')
        // If review_status is 'approved' or 'changes_requested', it's complete, not in progress
        if (pr?.review_status && pr.review_status !== 'pending') {
          // Review is complete, not in progress
          return false;
        }
        const reviewStarted = timelineEvents.some(e => {
          const eType = typeof e === 'object' ? e.event : e;
          return eType === 'pr_review_started';
        });
        return pr?.number && (reviewStarted || !pr?.review_status || pr.review_status === 'pending');
      }
      return false;
    });

    if (isCompleted) return 'completed';
    if (isInProgress) return 'in_progress';
    return 'pending';
  };

  // Get current stage explanation
  const getCurrentStageExplanation = () => {
    const timelineEvents = timeline || [];
    
    // Check for in-progress stages
    if (timelineEvents.some(e => e.event === 'analysis_started') && 
        !timelineEvents.some(e => e.event === 'fix_generation_started')) {
      return 'Analyzing code patterns...';
    }
    if (timelineEvents.some(e => e.event === 'fix_generation_started') && 
        !timelineEvents.some(e => e.event === 'pr_creation_started')) {
      return 'AI is generating fix...';
    }
    if (timelineEvents.some(e => e.event === 'pr_creation_started') && !pr?.number) {
      return 'Creating pull request...';
    }
    if (pr?.review_status === 'approved' && !pr?.merge_status) {
      return 'AI review complete. Please review and approve before merging.';
    }
    if (pr?.review_status === 'changes_requested') {
      return 'PR review requested changes. Check PR comments for details.';
    }
    if (timelineEvents.some(e => e.event === 'pr_review_started') && !pr?.review_status) {
      return 'AI-powered PR Review Agent is analyzing the pull request...';
    }
    if (pr?.number && !pr?.review_status) {
      return 'PR created successfully. AI-powered PR Review Agent is being triggered automatically...';
    }
    if (pr?.merge_status === 'merged') {
      return 'PR merged successfully.';
    }
    
    return null;
  };

  // Build GitHub Actions link
  const getGitHubActionsLink = () => {
    if (!repo) return null;
    
    // Extract owner and repo name from repo string (format: "owner/repo" or full URL)
    let owner, repoName;
    if (repo.includes('/')) {
      const parts = repo.split('/');
      if (repo.startsWith('http')) {
        // Full URL: https://github.com/owner/repo
        const urlParts = repo.split('/');
        owner = urlParts[urlParts.length - 2];
        repoName = urlParts[urlParts.length - 1];
      } else {
        // owner/repo format
        owner = parts[0];
        repoName = parts[1];
      }
    } else {
      return null; // Can't parse
    }
    
    return `https://github.com/${owner}/${repoName}/actions`;
  };

  const githubActionsLink = getGitHubActionsLink();
  const currentExplanation = getCurrentStageExplanation();

  // Group timeline events by type for better organization
  const majorMilestones = timeline?.filter(event => 
    ['issue_created', 'pr_created'].includes(event.event)
  ) || [];

  const progressEvents = timeline?.filter(event => 
    ['analysis_started', 'fix_generation_started', 'pr_creation_started'].includes(event.event)
  ) || [];

  const detailedEvents = timeline?.filter(event => 
    !['issue_created', 'pr_created', 'analysis_started', 'fix_generation_started', 'pr_creation_started'].includes(event.event)
  ) || [];

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  return (
    <div className="mt-4 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-800">🔄 Remediation Lifecycle</h3>
        <div className="flex items-center gap-2">
          {/* Pause/Resume Polling Controls */}
          {isPollingActive && onPausePolling && (
            <button
              onClick={onPausePolling}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-yellow-50 text-yellow-700 hover:bg-yellow-100 rounded border border-yellow-300 transition-colors"
              title="Pause automatic status updates"
            >
              <span>⏸️</span>
              Pause
            </button>
          )}
          {isPollingPaused && onResumePolling && (
            <button
              onClick={onResumePolling}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-green-50 text-green-700 hover:bg-green-100 rounded border border-green-300 transition-colors"
              title="Resume automatic status updates"
            >
              <span>▶️</span>
              Resume
            </button>
          )}
          {githubActionsLink && (
            <a
              href={githubActionsLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              View Actions →
            </a>
          )}
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          )}
        </div>
      </div>
      
      {/* Paused polling indicator */}
      {isPollingPaused && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-blue-600">⏸️</span>
              <p className="text-sm text-blue-800">
                <strong>Polling paused.</strong> Status updates are not being fetched automatically. Click "Resume" to continue.
              </p>
            </div>
            {onResumePolling && (
              <button
                onClick={onResumePolling}
                className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                Resume
              </button>
            )}
          </div>
        </div>
      )}

      {/* Similar Incidents */}
      {similar_incidents_count !== undefined && similar_incidents_count > 0 && (
        <div className="mb-4 p-2 bg-blue-50 border border-blue-200 rounded">
          <p className="text-xs text-blue-800">
            <span className="font-semibold">Similar incidents:</span> {similar_incidents_count} resolved this week
          </p>
        </div>
      )}

      {/* Stage Indicators */}
      <div className="mb-4">
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {STAGES.map((stage, index) => {
            const status = getStageStatus(stage);
            const isCompleted = status === 'completed';
            const isInProgress = status === 'in_progress';
            const isPending = status === 'pending';
            
            // Check if we're waiting for Issue Agent - show animation on relevant pending stages
            const isWaitingForIssueAgent = next_action?.includes('Issue Agent') || 
                                           next_action?.includes('Issue agent') ||
                                           (timeline && timeline.length > 0 && !pr?.number);
            
            // Determine which pending stages should pulse (Analysis, Fix Generation, PR Creation)
            const shouldPulse = isPending && isWaitingForIssueAgent && 
                               (stage.id === 'analysis' || 
                                stage.id === 'fix_generation' || 
                                stage.id === 'pr_creation');
            
            // Only animate if polling is active and not paused
            const shouldAnimate = (isPollingActive && !isPollingPaused) || (!isPollingActive && !isPollingPaused);

            return (
              <div key={stage.id} className="flex items-center flex-shrink-0">
                {/* Stage Circle */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all ${
                      isCompleted
                        ? 'bg-green-50 border-green-500 text-green-600'
                        : isInProgress
                        ? `bg-blue-50 border-blue-500 text-blue-600 ${shouldAnimate ? 'animate-pulse' : ''} shadow-lg shadow-blue-300`
                        : shouldPulse
                        ? 'bg-blue-100 border-blue-500 text-blue-700 shadow-lg shadow-blue-300'
                        : 'bg-gray-50 border-gray-300 text-gray-400'
                    }`}
                    style={shouldPulse && shouldAnimate ? {
                      animation: 'pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                      boxShadow: '0 0 0 0 rgba(59, 130, 246, 0.7), 0 0 0 0 rgba(59, 130, 246, 0.7), 0 0 0 0 rgba(59, 130, 246, 0.7)'
                    } : shouldPulse ? {
                      boxShadow: '0 0 0 0 rgba(59, 130, 246, 0.3)'
                    } : {}}
                  >
                    {isCompleted ? (
                      <span className="text-lg">✓</span>
                    ) : isInProgress ? (
                      <svg className={`h-5 w-5 ${shouldAnimate ? 'animate-spin' : ''}`} viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      <span 
                        className="text-lg"
                        style={shouldPulse && shouldAnimate ? {
                          animation: 'pulse-scale 1.5s ease-in-out infinite',
                          display: 'inline-block'
                        } : { display: 'inline-block' }}
                      >
                        {stage.icon}
                      </span>
                    )}
                  </div>
                  <p className={`text-xs mt-1 text-center max-w-[60px] ${
                    isCompleted ? 'text-green-600 font-medium' : 
                    isInProgress ? 'text-blue-600 font-medium' : 
                    shouldPulse ? 'text-blue-600 font-medium' :
                    'text-gray-400'
                  }`}>
                    {stage.name}
                  </p>
                </div>
                {/* Connector Line */}
                {index < STAGES.length - 1 && (
                  <div className={`w-8 h-0.5 mx-1 ${
                    isCompleted ? 'bg-green-500' : 'bg-gray-300'
                  }`} />
                )}
              </div>
            );
          })}
        </div>

        {/* Current Stage Explanation */}
        {currentExplanation && (
          <div className="mt-3 p-2 bg-blue-50 border border-blue-200 rounded">
            <div className="flex items-center gap-2">
              <svg className={`h-3 w-3 text-blue-600 ${(isPollingActive && !isPollingPaused) ? 'animate-spin' : ''}`} viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <p className="text-xs text-blue-800">
                <span className="font-semibold">In Progress:</span> {currentExplanation}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Issue and PR Status Cards */}
      <div className="mb-4">
        <div className="flex items-center gap-3 mb-3">
          {/* Issue Status */}
          {issue && (
            <div className="flex-1 p-3 rounded-lg border border-green-200 bg-green-50">
              <div className="flex items-center gap-2 mb-1">
                <span>📋</span>
                <span className="text-xs font-semibold text-green-700">Issue #{issue.number}</span>
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
          {pr && pr.number ? (
            <div className={`flex-1 p-3 rounded-lg border ${
              pr.merge_status === 'merged' 
                ? 'border-green-200 bg-green-50'
                : pr.review_status === 'approved'
                ? 'border-blue-200 bg-blue-50'
                : 'border-gray-200 bg-gray-50'
            }`}>
              <div className="flex items-center gap-2 mb-1">
                <span>📝</span>
                <span className={`text-xs font-semibold ${
                  pr.merge_status === 'merged' ? 'text-green-700' :
                  pr.review_status === 'approved' ? 'text-blue-700' :
                  'text-gray-700'
                }`}>
                  PR #{pr.number}
                </span>
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
                {pr.review_status && pr.review_status !== 'approved' && (
                  <p className="text-xs text-gray-600">
                    Review: <span className="font-medium">{pr.review_status}</span>
                  </p>
                )}
                {pr.review_status === 'approved' && (
                  <p className="text-xs text-gray-600">
                    Review: <span className="font-medium">complete</span>
                  </p>
                )}
                {pr.merge_status && (
                  <p className="text-xs text-gray-600">
                    Merge: <span className="font-medium">{pr.merge_status}</span>
                  </p>
                )}
                {!pr.review_status && !pr.merge_status && (
                  <p className="text-xs text-gray-500 italic">
                    Status not tracked automatically
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

        {/* PR Review Section (AI-based review - automatically triggered) */}
        {pr && pr.number && (
          <div className="space-y-3">
            {/* AI-Based PR Review Status */}
            <div className={`p-3 rounded-lg border ${
              pr.review_status === 'approved'
                ? 'bg-green-50 border-green-200'
                : pr.review_status === 'changes_requested'
                ? 'bg-yellow-50 border-yellow-200'
                : pr.review_status
                ? 'bg-blue-50 border-blue-200'
                : 'bg-gray-50 border-gray-200'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🤖</span>
                  <div>
                    <p className="text-xs font-semibold text-gray-800">
                      AI-Based PR Review {pr.review_status === 'approved' ? '(complete)' : pr.review_status ? `(${pr.review_status})` : '(In Progress)'}
                    </p>
                    <p className="text-xs text-gray-600">
                      PR Review Agent automatically reviews the PR
                    </p>
                  </div>
                </div>
                {pr.review_status && (
                  <span className={`px-2 py-1 text-xs rounded font-medium ${
                    pr.review_status === 'approved'
                      ? 'bg-green-100 text-green-700'
                      : pr.review_status === 'changes_requested'
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-blue-100 text-blue-700'
                  }`}>
                    {pr.review_status === 'approved' ? '✓ Complete' :
                     pr.review_status === 'changes_requested' ? '⚠ Changes Requested' :
                     pr.review_status}
                  </span>
                )}
              </div>
              {!pr.review_status && (
                <div className="text-xs text-gray-600 space-y-1">
                  <p>• PR Review Agent workflow is automatically triggered after PR creation</p>
                  <p>• Review happens via GitHub Actions workflow (pr-review.yml)</p>
                  <p>• Status will update automatically when review completes</p>
                </div>
              )}
              {pr.review_status && (
                <div className="text-xs text-gray-600 mt-2">
                  {pr.review_status === 'approved' && (
                    <p className="text-green-700">✓ AI review complete. <strong>Please review before merging.</strong></p>
                  )}
                  {pr.review_status === 'changes_requested' && (
                    <p className="text-yellow-700">⚠ AI reviewer requested changes. Check PR comments for details.</p>
                  )}
                </div>
              )}
            </div>

            {/* Important Disclaimer */}
            <div className="p-3 rounded-lg border-2 border-yellow-300 bg-yellow-50">
              <div className="flex items-start gap-2">
                <span className="text-lg flex-shrink-0">⚠️</span>
                <div className="flex-1">
                  <p className="text-xs font-semibold text-yellow-900 mb-1">
                    Important: Please Review Before Merging
                  </p>
                  <p className="text-xs text-yellow-800">
                    This fix was generated by AI. Please carefully review the code changes, test the fix, and ensure it meets your requirements before merging the PR.
                  </p>
                </div>
              </div>
            </div>

            {/* Manual Check & Merge Section */}
            <div className="p-3 rounded border bg-blue-50 border-blue-200">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-blue-800">
                  <span className="font-semibold">Next Steps:</span> Review and merge in GitHub
                </p>
                {onCheckPRStatus && (
                  <button
                    onClick={async () => {
                      setIsCheckingPRStatus(true);
                      try {
                        await onCheckPRStatus(incidentId);
                      } finally {
                        setIsCheckingPRStatus(false);
                      }
                    }}
                    disabled={isCheckingPRStatus}
                    className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                  >
                    {isCheckingPRStatus ? (
                      <>
                        <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Checking...
                      </>
                    ) : (
                      <>
                        🔍 Check PR Status
                      </>
                    )}
                  </button>
                )}
              </div>
              <div className="text-xs text-blue-700 space-y-1">
                <p>• PR review can be done by AI (PR Review Agent) or manually</p>
                <p>• Use "Check PR Status" to see current review/merge status</p>
                <p>• <strong>Always review AI-generated code before merging</strong></p>
                <p>• Merge the PR manually in GitHub when ready</p>
                {pr.merge_status === 'merged' && (
                  <p className="text-green-700 font-medium">✓ PR has been merged successfully!</p>
                )}
              </div>
            </div>
          </div>
        )}
        {next_action && !pr?.number && (
          <div className={`p-2 rounded border ${
            next_action.includes('⚠️') || next_action.includes('may not be configured')
              ? 'bg-yellow-50 border-yellow-300'
              : 'bg-blue-50 border-blue-200'
          }`}>
            <p className={`text-xs ${
              next_action.includes('⚠️') || next_action.includes('may not be configured')
                ? 'text-yellow-800'
                : 'text-blue-800'
            }`}>
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
              {/* Progress Events - Show with messages */}
              {progressEvents.map((event, index) => (
                <div key={`progress-${index}`} className="flex items-start gap-3 p-2 bg-blue-50 rounded border border-blue-200">
                  <div className={`flex-shrink-0 w-2 h-2 rounded-full bg-blue-500 mt-1.5 ${(isPollingActive && !isPollingPaused) ? 'animate-pulse' : ''}`}></div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-blue-800 capitalize">
                        {event.event.replace(/_/g, ' ')}
                      </p>
                      <span className="text-xs text-blue-600">
                        {formatTimestamp(event.timestamp)}
                      </span>
                    </div>
                    {event.message && (
                      <p className="text-xs text-blue-700 mt-1 italic">
                        {event.message}
                      </p>
                    )}
                  </div>
                </div>
              ))}

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
