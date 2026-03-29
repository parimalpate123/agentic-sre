/**
 * IncidentFormView — Read-only structured incident record (Figma-style form view).
 * Sections: Header → Pipeline → Status Grid → Incident Summary → Analysis →
 *           Root Cause → Decision → Resolution → Fix & Remediation → Footer
 */

import React, { useState } from 'react';
import RemediationStatus from './RemediationStatus';

// ── Helpers ─────────────────────────────────────────────────────────────────

function pill(label, className) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

function sevColor(sev) {
  return (
    { P1: 'bg-red-100 text-red-700', P2: 'bg-orange-100 text-orange-700',
      P3: 'bg-yellow-100 text-yellow-700', P4: 'bg-gray-100 text-gray-600' }[sev] ||
    'bg-gray-100 text-gray-600'
  );
}

function confColor(c) {
  if (c >= 80) return 'bg-green-100 text-green-700';
  if (c >= 50) return 'bg-yellow-100 text-yellow-700';
  return 'bg-gray-100 text-gray-600';
}

function SectionHeader({ label, labelColor = 'text-violet-600', badge, badgeClass = 'bg-violet-50 text-violet-700', title }) {
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-0.5">
        <span className={`text-xs font-semibold uppercase tracking-widest ${labelColor}`}>{label}</span>
        {badge && (
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badgeClass}`}>{badge}</span>
        )}
      </div>
      {title && <h3 className="text-base font-bold text-gray-900">{title}</h3>}
    </div>
  );
}

function GridRow({ cells }) {
  return (
    <div className={`grid gap-px bg-gray-200 rounded-lg overflow-hidden`}
         style={{ gridTemplateColumns: `repeat(${cells.length}, 1fr)` }}>
      {cells.map((cell, i) => (
        <div key={i} className="bg-white px-4 py-3">
          <p className="text-xs text-gray-400 uppercase tracking-wider font-medium mb-1">{cell.label}</p>
          <p className="text-sm font-semibold text-gray-900">{cell.value || '—'}</p>
        </div>
      ))}
    </div>
  );
}

// ── Pipeline strip ────────────────────────────────────────────────────────────

function PipelineStrip({ origin, remediationStatus }) {
  const hasFix = Boolean(remediationStatus?.pr?.number || remediationStatus?.issue?.number);
  const hasReview = Boolean(
    remediationStatus?.pr?.ai_pr_review_completed ||
    (remediationStatus?.pr?.review_status && remediationStatus?.pr?.review_status !== 'pending')
  );

  const originLabel = origin === 'cloudwatch_alarm' ? 'Alarm' : origin === 'trace' ? 'Trace' : 'Chat';
  const originIcon = origin === 'cloudwatch_alarm' ? '🔔' : origin === 'trace' ? '🔗' : '💬';

  const stages = [
    { label: `Source: ${originLabel}`, icon: originIcon, done: true },
    { label: 'Investigation complete', done: true },
    { label: 'Fix generated', done: hasFix },
    { label: 'Review complete', done: hasReview },
  ];

  return (
    <div className="flex items-center gap-1.5 flex-wrap mt-3">
      {stages.map((s, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="text-gray-300 text-xs select-none">→</span>}
          <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border
            ${s.done ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-50 text-gray-400 border-gray-200'}`}>
            {s.done ? '✅' : (s.icon || '')} {s.label}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Analysis section with dark terminal ──────────────────────────────────────

function AnalysisSection({ analysis, diagnosis }) {
  const errorPatterns = analysis?.error_patterns || [];
  const analysisSum = analysis?.summary || analysis?.error_summary || '';
  const logQueries = analysis?.log_queries || [];

  // Build signal rows
  const signals = [];

  if (errorPatterns.length > 0) {
    signals.push({
      label: 'Log pattern',
      text: Array.isArray(errorPatterns)
        ? errorPatterns.slice(0, 3).map(p => typeof p === 'string' ? p : JSON.stringify(p)).join('; ')
        : String(errorPatterns),
    });
  }

  const evidenceList = diagnosis?.supporting_evidence || [];
  if (evidenceList.length > 0) {
    signals.push({
      label: 'Service symptom',
      text: evidenceList[0],
    });
    if (evidenceList.length > 1) {
      signals.push({
        label: 'Downstream effect',
        text: evidenceList[1],
      });
    }
  }

  if (analysisSum && signals.length < 2) {
    signals.push({ label: 'Analysis summary', text: analysisSum });
  }

  // Build dark terminal lines from log queries or error patterns
  const terminalLines = [];
  if (errorPatterns.length > 0) {
    errorPatterns.slice(0, 8).forEach(p => {
      terminalLines.push(typeof p === 'string' ? p : JSON.stringify(p));
    });
  }
  logQueries.forEach(q => {
    if (q.sample_entries?.length > 0) {
      q.sample_entries.slice(0, 3).forEach(e => {
        const msg = e.message || e.msg || JSON.stringify(e);
        if (msg && !terminalLines.includes(msg)) terminalLines.push(msg);
      });
    }
  });

  if (signals.length === 0 && terminalLines.length === 0) return null;

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 bg-white border-b border-gray-100">
        <SectionHeader
          label="Analysis Summary"
          labelColor="text-blue-600"
          badge="Top evidence only"
          badgeClass="bg-blue-50 text-blue-700"
          title="Signals and patterns observed"
        />
        <div className="flex gap-4">
          {/* Left: signal cards */}
          <div className="flex-1 space-y-3">
            {signals.map((sig, i) => (
              <div key={i} className="border-b border-gray-100 last:border-0 pb-3 last:pb-0">
                <p className="text-xs font-semibold text-gray-700 mb-0.5">{sig.label}</p>
                <p className="text-sm text-blue-700 leading-relaxed">{sig.text}</p>
              </div>
            ))}
          </div>
          {/* Right: dark terminal */}
          {terminalLines.length > 0 && (
            <div className="w-80 shrink-0 bg-gray-900 rounded-lg p-3 overflow-hidden">
              <p className="text-xs text-gray-500 mb-2 font-mono">Representative analysis findings:</p>
              <div className="space-y-1 font-mono text-xs text-gray-300 leading-relaxed">
                {terminalLines.slice(0, 6).map((line, i) => (
                  <p key={i} className="truncate">– {line}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Root Cause section ────────────────────────────────────────────────────────

function RootCauseSection({ diagnosis, rootCause }) {
  const hypothesis = diagnosis?.hypothesis || diagnosis?.root_cause || rootCause;
  if (!hypothesis || hypothesis === 'Analysis in progress' || hypothesis === 'Unknown') return null;

  const unknown = diagnosis?.alternative_causes?.length > 0
    ? diagnosis.alternative_causes.slice(0, 2).join('; ')
    : 'The exact upstream cause and deployment correlation have not yet been fully verified.';

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 bg-white">
        <SectionHeader
          label="Root Cause Analysis"
          labelColor="text-orange-600"
          badge="Primary hypothesis"
          badgeClass="bg-green-50 text-green-700"
          title="Most likely explanation"
        />
        <div className="grid grid-cols-2 gap-4 mt-2">
          <div className="border border-gray-100 rounded-lg p-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Primary RCA</p>
            <p className="text-sm text-gray-800 leading-relaxed">{hypothesis}</p>
            {diagnosis?.supporting_evidence?.length > 0 && (
              <ul className="mt-2 space-y-1">
                {diagnosis.supporting_evidence.slice(0, 3).map((ev, i) => (
                  <li key={i} className="text-xs text-gray-500 flex gap-1.5">
                    <span className="text-violet-400 shrink-0 mt-0.5">•</span>
                    <span>{ev}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="border border-gray-100 rounded-lg p-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">What remains unknown</p>
            <p className="text-sm text-gray-600 leading-relaxed">{unknown}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Decision section ──────────────────────────────────────────────────────────

function DecisionSection({ triage, executionType, recommendedAction }) {
  const decisionText = triage?.reasoning ||
    'TARS analyzed the incident and determined the most appropriate remediation action based on the observed patterns and severity.';

  const execTypeLabel = executionType
    ? executionType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    : '—';

  const risk = (typeof recommendedAction === 'object' ? recommendedAction?.risk : null) || '—';
  const reason = triage?.decision || (typeof recommendedAction === 'object' ? recommendedAction?.action_type?.replace(/_/g, ' ') : null) || '—';
  const needsApproval = executionType === 'code_fix' ? 'Yes' : 'No';

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 bg-white">
        <SectionHeader
          label="Decision"
          labelColor="text-gray-500"
          badge="Separates RCA from action"
          badgeClass="bg-orange-50 text-orange-700"
          title="Operational conclusion"
        />
        <p className="text-sm text-gray-700 leading-relaxed mb-4">{decisionText}</p>
        <div className="grid grid-cols-4 gap-px bg-gray-200 rounded-lg overflow-hidden">
          {[
            { label: 'Decision Type', value: execTypeLabel },
            { label: 'Risk', value: risk },
            { label: 'Approval Required', value: needsApproval },
            { label: 'Reason', value: reason },
          ].map((cell, i) => (
            <div key={i} className="bg-white px-4 py-3">
              <p className="text-xs text-gray-400 uppercase tracking-wider font-medium mb-1">{cell.label}</p>
              <p className="text-sm font-semibold text-gray-900">{cell.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Resolution Recommendation ─────────────────────────────────────────────────

function ResolutionSection({ recommendedAction }) {
  if (!recommendedAction) return null;

  const desc = typeof recommendedAction === 'object'
    ? recommendedAction.description || ''
    : typeof recommendedAction === 'string' ? recommendedAction : '';

  const steps = typeof recommendedAction === 'object' && Array.isArray(recommendedAction.steps)
    ? recommendedAction.steps.map(s => typeof s === 'string' ? s : (s.description || s.action || JSON.stringify(s)))
    : [];

  if (!desc && steps.length === 0) return null;

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 bg-white">
        <SectionHeader
          label="Resolution Recommendation"
          labelColor="text-gray-500"
          badge="Immediate guidance"
          badgeClass="bg-orange-50 text-orange-700"
          title="What should happen next"
        />
        {desc && <p className="text-sm text-gray-700 leading-relaxed mb-3">{desc}</p>}
        {steps.length > 0 && (
          <ol className="space-y-2">
            {steps.map((step, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-600">
                <span className="text-violet-500 font-semibold shrink-0 w-5 text-right">{i + 1}.</span>
                <span className="leading-relaxed">{step}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

// ── Human Review Banner (footer of remediation) ───────────────────────────────

function HumanReviewBanner({ remediationStatus, onBack }) {
  const prNumber = remediationStatus?.pr?.number;
  const prUrl = remediationStatus?.pr?.url;
  const issueNumber = remediationStatus?.issue?.number;
  const issueUrl = remediationStatus?.issue?.url;
  const reviewDone = remediationStatus?.pr?.ai_pr_review_completed;

  if (!reviewDone && !prNumber) return null;

  return (
    <div className="border border-amber-200 bg-amber-50 rounded-xl px-5 py-4 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 mb-1">Human Review Required</p>
        <p className="text-sm font-bold text-gray-900">
          Automated remediation is complete. Human confirmation is required before merge.
        </p>
        <p className="text-sm text-gray-600 mt-1 leading-relaxed">
          Issue creation, fix generation, PR creation, and automated review have completed successfully.
          TARS is intentionally paused here because this is an AI-generated code change.
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {prNumber && (
          <a href={prUrl} target="_blank" rel="noopener noreferrer"
             className="text-sm px-3 py-1.5 rounded-lg bg-violet-600 text-white hover:bg-violet-700 font-medium whitespace-nowrap transition-colors">
            Review PR #{prNumber}
          </a>
        )}
        {issueNumber && (
          <a href={issueUrl} target="_blank" rel="noopener noreferrer"
             className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 font-medium whitespace-nowrap transition-colors">
            Open Issue #{issueNumber}
          </a>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function IncidentFormView({
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
    executive_summary,
    recommended_action,
    timestamp,
  } = incident || {};

  const triage = full_state.triage || {};
  const analysis = full_state.analysis || {};
  const fullDiagnosis = diagnosis || full_state.diagnosis || {};
  const fullRemediation = full_state.remediation || {};
  const resolvedRecommendedAction = fullRemediation.recommended_action || recommended_action;

  // Derive status for the status grid
  const prNumber = remediationStatus?.pr?.number;
  const issueNumber = remediationStatus?.issue?.number;
  const reviewDone = remediationStatus?.pr?.ai_pr_review_completed;

  let status = 'Under investigation';
  if (issueNumber && !prNumber) status = 'Fix in progress';
  if (prNumber && !reviewDone) status = 'Awaiting AI review';
  if (reviewDone) status = 'Awaiting human review';

  const nextStep = remediationStatus?.next_action ||
    (reviewDone && prNumber ? `Review PR #${prNumber}` : issueNumber ? 'Fix generation in progress' : 'Investigation complete');

  const detectedAt = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—';

  const updatedAt = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  const showRemediation = execution_type === 'code_fix' && (
    execution_results?.github_issue?.status === 'success' ||
    remediationStatus ||
    isPollingActive
  );

  const category =
    (fullDiagnosis?.category && fullDiagnosis.category !== 'UNKNOWN' ? fullDiagnosis.category : null) ||
    (execution_type ? execution_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + '-related' : null);

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden bg-gray-50">
      {/* Back bar */}
      <div className="px-4 py-2 border-b border-gray-200 bg-white flex items-center gap-3 shrink-0">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Chat
        </button>
        <span className="text-gray-300">|</span>
        <span className="text-sm text-gray-400 font-mono">{incident_id}</span>
      </div>

      {/* Scrollable form */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6 space-y-4">

          {/* ── HEADER CARD ── */}
          <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
            <div className="px-5 pt-3 pb-1 flex items-center justify-between border-b border-gray-100">
              <span className="text-xs font-semibold uppercase tracking-widest text-gray-400">Incident Record</span>
              <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Active case</span>
            </div>
            <div className="px-5 py-4">
              <h2 className="text-xl font-bold text-gray-900 leading-tight">{alert_name || 'Incident'}</h2>
              {alert_description && (
                <p className="text-sm text-gray-500 mt-1">{alert_description}</p>
              )}
              {/* Metadata pills */}
              <div className="flex flex-wrap items-center gap-2 mt-3">
                {service && service !== 'unknown' && pill(service, 'bg-violet-100 text-violet-700')}
                {severity && pill(severity, sevColor(severity))}
                {confidence > 0 && pill(`${confidence}% confidence`, confColor(confidence))}
                {category && pill(category, 'bg-gray-100 text-gray-600')}
                {updatedAt && (
                  <span className="text-xs text-gray-400">Updated {updatedAt}</span>
                )}
              </div>
              {/* Pipeline strip */}
              <PipelineStrip
                origin={origin || incident?.source || 'chat'}
                remediationStatus={remediationStatus}
              />
            </div>
          </div>

          {/* ── STATUS GRID ── */}
          <GridRow cells={[
            { label: 'Status', value: status },
            { label: 'Blast Radius', value: triage.blast_radius || '—' },
            { label: 'Owner', value: 'Unassigned' },
            { label: 'First Detected', value: detectedAt },
            { label: 'Next Step', value: nextStep },
          ]} />

          {/* ── INCIDENT SUMMARY ── */}
          {(executive_summary || displayText) && (
            <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
              <div className="px-5 py-4">
                <SectionHeader
                  label="Incident Summary"
                  labelColor="text-gray-500"
                  badge="Read-only case brief"
                  badgeClass="bg-teal-50 text-teal-700"
                  title="What happened"
                />
                <p className="text-sm text-gray-700 leading-relaxed">
                  {executive_summary || displayText}
                </p>
              </div>
            </div>
          )}

          {/* ── ANALYSIS SUMMARY ── */}
          <AnalysisSection analysis={analysis} diagnosis={fullDiagnosis} />

          {/* ── ROOT CAUSE ANALYSIS ── */}
          <RootCauseSection diagnosis={fullDiagnosis} rootCause={root_cause} />

          {/* ── DECISION ── */}
          <DecisionSection
            triage={triage}
            executionType={execution_type}
            recommendedAction={resolvedRecommendedAction}
          />

          {/* ── RESOLUTION RECOMMENDATION ── */}
          <ResolutionSection recommendedAction={resolvedRecommendedAction} />

          {/* ── FIX & REMEDIATION LIFECYCLE ── */}
          {showRemediation && (
            <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100">
                <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
                  Incident &amp; Remediation Lifecycle
                </p>
              </div>
              <div className="p-5">
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
                />
              </div>
            </div>
          )}

          {/* ── HUMAN REVIEW BANNER ── */}
          <HumanReviewBanner remediationStatus={remediationStatus} onBack={onBack} />

          {/* Bottom padding */}
          <div className="h-4" />
        </div>
      </div>
    </div>
  );
}
