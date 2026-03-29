/**
 * IncidentDetailView — Structured incident detail page
 * Replaces chat area when an incident is active.
 * Layout: Header → Analysis → Root Cause → Recommended Action → Fix & Remediation → Footer
 */

import React, { useState } from 'react';
import DiagnosisView from './DiagnosisView';
import RemediationStatus from './RemediationStatus';

// ── Helpers ────────────────────────────────────────────────────────────────────

function severityColor(sev) {
  return (
    { P1: 'bg-red-100 text-red-700 border-red-200',
      P2: 'bg-orange-100 text-orange-700 border-orange-200',
      P3: 'bg-yellow-100 text-yellow-700 border-yellow-200',
      P4: 'bg-gray-100 text-gray-600 border-gray-200' }[sev] ||
    'bg-gray-100 text-gray-600 border-gray-200'
  );
}

function confidenceColor(conf) {
  if (conf >= 80) return 'bg-green-50 text-green-700 border-green-200';
  if (conf >= 50) return 'bg-yellow-50 text-yellow-700 border-yellow-200';
  return 'bg-gray-50 text-gray-600 border-gray-200';
}

// ── CollapsibleCard ────────────────────────────────────────────────────────────

function CollapsibleCard({ title, icon, defaultOpen = true, children, accent = 'border-l-violet-400' }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      <button
        onClick={() => setOpen(v => !v)}
        className={`w-full px-4 py-3 bg-gray-50 border-b border-gray-200 border-l-4 ${accent} flex items-center justify-between hover:bg-gray-100 transition-colors`}
      >
        <div className="flex items-center gap-2">
          {icon && <span className="text-base">{icon}</span>}
          <span className="text-sm font-semibold text-gray-700">{title}</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="p-4 bg-white">{children}</div>}
    </div>
  );
}

// ── PipelineStrip ──────────────────────────────────────────────────────────────

function PipelineStrip({ origin, remediationStatus }) {
  const hasFix = Boolean(remediationStatus?.pr?.number || remediationStatus?.issue?.number);
  const hasReview = Boolean(remediationStatus?.pr?.ai_pr_review_completed);

  const originStage = (() => {
    if (origin === 'cloudwatch_alarm') return { label: 'Alarm', icon: '🔔' };
    if (origin === 'trace') return { label: 'Trace', icon: '🔗' };
    return { label: 'Chat', icon: '💬' };
  })();

  const stages = [
    { id: 'origin', label: originStage.label, icon: originStage.icon, done: true },
    { id: 'investigation', label: 'Investigation', icon: '🔍', done: true },
    { id: 'fix', label: 'Fix', icon: '🔧', done: hasFix },
    { id: 'review', label: 'Review', icon: '👁', done: hasReview },
  ];

  return (
    <div className="flex items-center gap-1.5 mt-3 flex-wrap">
      {stages.map((stage, i) => (
        <React.Fragment key={stage.id}>
          {i > 0 && <span className="text-gray-300 text-xs">→</span>}
          <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border
            ${stage.done
              ? 'bg-green-50 text-green-700 border-green-200'
              : 'bg-gray-50 text-gray-400 border-gray-200'}`}
          >
            {stage.done ? '✅' : stage.icon} {stage.label}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}

// ── RecommendedAction ──────────────────────────────────────────────────────────

function RecommendedAction({ recommendedAction, executionType }) {
  if (!recommendedAction) return null;

  const steps = (() => {
    if (typeof recommendedAction === 'object' && recommendedAction.steps) {
      return recommendedAction.steps.map(s =>
        typeof s === 'string' ? s : (s.description || s.action || JSON.stringify(s))
      );
    }
    return [];
  })();

  const actionDesc = typeof recommendedAction === 'object'
    ? recommendedAction.description || ''
    : typeof recommendedAction === 'string' ? recommendedAction : '';

  const actionType = typeof recommendedAction === 'object'
    ? recommendedAction.action_type?.replace(/_/g, ' ')
    : executionType?.replace(/_/g, ' ') || null;

  const risk = typeof recommendedAction === 'object' ? recommendedAction.risk : null;

  if (!actionDesc && steps.length === 0) return null;

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 border-l-4 border-l-orange-400 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">🎯</span>
          <span className="text-sm font-semibold text-gray-700">Recommended Action</span>
        </div>
        <div className="flex items-center gap-2">
          {actionType && (
            <span className="text-xs font-medium px-2 py-0.5 rounded bg-orange-100 text-orange-700">
              {actionType}
            </span>
          )}
          {risk && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded ${
              risk === 'HIGH' ? 'bg-red-100 text-red-700' :
              risk === 'MEDIUM' ? 'bg-yellow-100 text-yellow-700' :
              'bg-green-100 text-green-700'
            }`}>
              {risk} risk
            </span>
          )}
        </div>
      </div>
      <div className="p-4 bg-white space-y-2">
        {actionDesc && <p className="text-sm text-gray-700 leading-relaxed">{actionDesc}</p>}
        {steps.length > 0 && (
          <ol className="space-y-1.5 mt-2">
            {steps.map((step, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-600">
                <span className="text-violet-500 font-semibold shrink-0 w-5 text-right">{i + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

// ── IncidentDetailView ─────────────────────────────────────────────────────────

export default function IncidentDetailView({
  incident,
  displayText,
  diagnosis,
  origin,
  remediationStatus,
  onRefreshRemediation,
  onPausePolling,
  onResumePolling,
  isPollingActive,
  isPollingPaused,
  onCheckPRStatus,
  onBack,
  onAcknowledge,
  onReanalyze,
  onDelete,
}) {
  const {
    incident_id,
    service,
    severity,
    confidence,
    alert_name,
    alert_description,
    execution_type,
    execution_results,
    full_state = {},
    root_cause,
  } = incident || {};

  const remediation = full_state.remediation || {};
  const recommendedAction = remediation.recommended_action || incident?.recommended_action;
  const diagCategory = diagnosis?.category || remediation.execution_type?.replace(/_/g, ' ');
  const executiveSummary = incident?.executive_summary || full_state.executive_summary;

  // Determine if we have structured diagnosis to show
  const hasDiagnosis = diagnosis && (diagnosis.root_cause || diagnosis.hypothesis);

  // Show Fix & Remediation section if execution type is code_fix and issue/PR exists or polling
  const showRemediation = execution_type === 'code_fix' && (
    execution_results?.github_issue?.status === 'success' ||
    remediationStatus ||
    isPollingActive
  );

  const [isDeleting, setIsDeleting] = useState(false);
  const [isAcknowledging, setIsAcknowledging] = useState(false);
  const [isReanalyzing, setIsReanalyzing] = useState(false);

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden bg-gray-50/60">
      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-4">

          {/* ── HEADER CARD ── */}
          <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
            <div className="px-5 py-4 bg-white border-l-4 border-l-violet-500">
              {/* Title row */}
              <div className="flex items-start gap-3">
                <span className="text-2xl mt-0.5 shrink-0">🔴</span>
                <div className="flex-1 min-w-0">
                  <h2 className="text-lg font-bold text-gray-900 leading-tight">
                    {alert_name || 'Incident'}
                  </h2>
                  {alert_description && (
                    <p className="text-sm text-gray-500 mt-1 leading-relaxed">{alert_description}</p>
                  )}
                </div>
                {incident_id && (
                  <span className="text-xs text-gray-400 shrink-0 font-mono mt-1">
                    {incident_id.slice(-8)}
                  </span>
                )}
              </div>

              {/* Metadata pills */}
              <div className="flex flex-wrap gap-2 mt-3">
                {service && service !== 'unknown' && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-violet-50 text-violet-700 border border-violet-200">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                    {service}
                  </span>
                )}
                {severity && (
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${severityColor(severity)}`}>
                    {severity}
                  </span>
                )}
                {confidence > 0 && (
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${confidenceColor(confidence)}`}>
                    {confidence}% confidence
                  </span>
                )}
                {diagCategory && (
                  <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-600 border border-gray-200">
                    {diagCategory}
                  </span>
                )}
              </div>

              {/* Pipeline strip */}
              <PipelineStrip origin={origin || incident?.source || 'chat'} remediationStatus={remediationStatus} />
            </div>
          </div>

          {/* ── ANALYSIS SUMMARY ── */}
          {displayText && (
            <CollapsibleCard title="Analysis Summary" icon="📊" defaultOpen={true} accent="border-l-blue-400">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                {displayText}
              </pre>
            </CollapsibleCard>
          )}

          {/* Executive summary fallback when no display_text */}
          {!displayText && executiveSummary && (
            <CollapsibleCard title="Analysis Summary" icon="📊" defaultOpen={true} accent="border-l-blue-400">
              <p className="text-sm text-gray-700 leading-relaxed">{executiveSummary}</p>
            </CollapsibleCard>
          )}

          {/* ── ROOT CAUSE ── */}
          {hasDiagnosis ? (
            <CollapsibleCard title="Root Cause Diagnosis" icon="🔍" defaultOpen={true} accent="border-l-violet-400">
              {/* DiagnosisView already has its own header — render inline content only */}
              <DiagnosisViewInline diagnosis={diagnosis} />
            </CollapsibleCard>
          ) : root_cause && root_cause !== 'Analysis in progress' && root_cause !== 'Unknown' ? (
            <CollapsibleCard title="Root Cause" icon="🔍" defaultOpen={true} accent="border-l-violet-400">
              <p className="text-sm text-gray-700 leading-relaxed">{root_cause}</p>
            </CollapsibleCard>
          ) : null}

          {/* ── RECOMMENDED ACTION ── */}
          <RecommendedAction
            recommendedAction={recommendedAction}
            executionType={execution_type}
          />

          {/* ── FIX & REMEDIATION ── */}
          {showRemediation && (
            <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 border-l-4 border-l-green-400">
                <div className="flex items-center gap-2">
                  <span className="text-base">🔧</span>
                  <span className="text-sm font-semibold text-gray-700">Fix & Remediation</span>
                </div>
              </div>
              <div className="p-4 bg-white">
                <RemediationStatus
                  incidentId={incident_id}
                  incidentSource={incident?.source}
                  remediationStatus={remediationStatus}
                  onRefresh={onRefreshRemediation}
                  onPausePolling={onPausePolling}
                  onResumePolling={onResumePolling}
                  isPollingActive={isPollingActive}
                  isPollingPaused={isPollingPaused}
                  onCheckPRStatus={onCheckPRStatus}
                  showTriggerStage={false}
                />
              </div>
            </div>
          )}

          {/* ── FOOTER ACTIONS ── */}
          <div className="flex items-center gap-3 pt-2 pb-6 border-t border-gray-200 mt-2">
            <button
              onClick={onBack}
              className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Back to Chat
            </button>
            <div className="flex-1" />
            <button
              onClick={async () => {
                setIsReanalyzing(true);
                try { await onReanalyze?.(incident_id); } finally { setIsReanalyzing(false); }
              }}
              disabled={isReanalyzing}
              className="text-sm px-3 py-1.5 rounded-lg bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100 disabled:opacity-50 transition-colors"
            >
              {isReanalyzing ? 'Re-analyzing...' : 'Re-analyze'}
            </button>
            <button
              onClick={async () => {
                setIsAcknowledging(true);
                try { await onAcknowledge?.(incident_id); } finally { setIsAcknowledging(false); }
              }}
              disabled={isAcknowledging}
              className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {isAcknowledging ? 'Acknowledging...' : 'Acknowledge'}
            </button>
            <button
              onClick={async () => {
                if (!window.confirm('Delete this incident?')) return;
                setIsDeleting(true);
                try { await onDelete?.(incident_id); } finally { setIsDeleting(false); }
              }}
              disabled={isDeleting}
              className="text-sm px-3 py-1.5 rounded-lg bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 disabled:opacity-50 transition-colors"
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── DiagnosisViewInline ───────────────────────────────────────────────────────
// Renders DiagnosisView content without the outer card wrapper
// (since CollapsibleCard already provides the wrapper)

function DiagnosisViewInline({ diagnosis }) {
  const [reasoningExpanded, setReasoningExpanded] = useState(false);

  const {
    confidence,
    category,
    component,
    supporting_evidence = [],
    alternative_causes = [],
    reasoning,
    timeline,
    next_steps = [],
  } = diagnosis;

  const hypothesis = diagnosis.hypothesis || diagnosis.root_cause;
  if (!hypothesis) return null;

  const getConfidenceColor = (conf) => {
    if (conf >= 90) return 'bg-green-100 text-green-700 border-green-200';
    if (conf >= 70) return 'bg-blue-100 text-blue-700 border-blue-200';
    if (conf >= 50) return 'bg-yellow-100 text-yellow-700 border-yellow-200';
    return 'bg-red-100 text-red-700 border-red-200';
  };

  const categoryColors = {
    DEPLOYMENT:    'bg-purple-100 text-purple-700',
    CONFIGURATION: 'bg-orange-100 text-orange-700',
    RESOURCE:      'bg-red-100 text-red-700',
    CODE:          'bg-pink-100 text-pink-700',
    DEPENDENCY:    'bg-indigo-100 text-indigo-700',
    LOAD:          'bg-cyan-100 text-cyan-700',
    TIMEOUT:       'bg-amber-100 text-amber-700',
    UNKNOWN:       'bg-gray-100 text-gray-600',
  };
  const categoryColor = categoryColors[category] || categoryColors.UNKNOWN;

  const timestampStr = diagnosis.diagnosed_at
    ? new Date(diagnosis.diagnosed_at).toLocaleString()
    : null;

  return (
    <div className="space-y-4">
      {/* Confidence badge */}
      {confidence > 0 && (
        <div className="flex justify-end">
          <span className={`px-2.5 py-1 rounded-full border text-xs font-semibold ${getConfidenceColor(confidence)}`}>
            {confidence}% Confidence
          </span>
        </div>
      )}

      {/* Hypothesis */}
      <div>
        <p className="text-base font-semibold text-gray-900 leading-snug">{hypothesis}</p>
        <div className="flex flex-wrap gap-1.5 mt-2">
          {category && category !== 'UNKNOWN' && (
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${categoryColor}`}>
              {category}
            </span>
          )}
          {component && (
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
              {component}
            </span>
          )}
        </div>
      </div>

      {/* Evidence */}
      {supporting_evidence.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Evidence</p>
          <ul className="space-y-1.5">
            {supporting_evidence.map((ev, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-700">
                <span className="text-violet-400 shrink-0 mt-0.5 font-bold">•</span>
                <span>{ev}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Reasoning (collapsible) */}
      {reasoning && (
        <div>
          <button
            onClick={() => setReasoningExpanded(r => !r)}
            className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider hover:text-violet-600 transition-colors"
          >
            <svg
              className={`w-3 h-3 transition-transform ${reasoningExpanded ? 'rotate-90' : ''}`}
              fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            Why this conclusion
          </button>
          {reasoningExpanded && (
            <p className="mt-2 text-sm text-gray-600 leading-relaxed border-l-2 border-gray-200 pl-3">
              {reasoning}
            </p>
          )}
        </div>
      )}

      {/* Alternative causes */}
      {alternative_causes.length > 0 && (
        <div className="pt-1 border-t border-gray-100">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
            Other possibilities
          </p>
          <ul className="space-y-1">
            {alternative_causes.map((cause, i) => (
              <li key={i} className="flex gap-2 text-xs text-gray-400">
                <span className="shrink-0">◦</span>
                <span>{cause}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Timeline */}
      {timeline && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Timeline</p>
          <p className="text-sm text-gray-600">{timeline}</p>
        </div>
      )}

      {/* Next Steps */}
      {next_steps.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Next Steps</p>
          <ol className="space-y-1">
            {next_steps.map((step, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-600">
                <span className="text-violet-500 font-semibold shrink-0 w-4 text-right">{i + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Footer timestamp */}
      {timestampStr && (
        <p className="text-xs text-gray-400 pt-1 border-t border-gray-100">
          Diagnosed {timestampStr}
        </p>
      )}
    </div>
  );
}
