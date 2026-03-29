/**
 * Incident summary (“What happened”) — structured sub-panels from full_state when available.
 */

import ChatMarkdown from './ChatMarkdown';
import { executiveSummaryIsFullNarrative, normalizeRemediationStepText } from '../utils/incidentParser';

function meaningfulRootCause(incident) {
  const rc = incident?.root_cause;
  if (typeof rc !== 'string' || !rc.trim()) return '';
  if (rc === 'Unknown' || rc === 'Analysis in progress') return '';
  return rc.trim();
}

/** Normalize Pydantic / JSON enum or plain string for display. */
function dispEnum(v) {
  if (v == null) return '';
  if (typeof v === 'object' && v !== null && 'value' in v) return String(v.value ?? '');
  return String(v);
}

function hasTriage(triage) {
  if (!triage || typeof triage !== 'object') return false;
  return Boolean(
    dispEnum(triage.severity) ||
      dispEnum(triage.decision) ||
      (typeof triage.reasoning === 'string' && triage.reasoning.trim())
  );
}

function hasAnalysis(analysis) {
  if (!analysis || typeof analysis !== 'object') return false;
  const patterns = analysis.error_patterns;
  const hasPatterns = Array.isArray(patterns) && patterns.length > 0;
  const count = analysis.error_count;
  const hasCount = typeof count === 'number' && count > 0;
  const summary = typeof analysis.summary === 'string' && analysis.summary.trim();
  const findings = Array.isArray(analysis.key_findings) && analysis.key_findings.length > 0;
  return Boolean(hasPatterns || hasCount || summary || findings);
}

function hasDiagnosis(diagnosis) {
  if (!diagnosis || typeof diagnosis !== 'object') return false;
  return Boolean(
    (typeof diagnosis.root_cause === 'string' && diagnosis.root_cause.trim()) ||
      diagnosis.confidence != null ||
      (typeof diagnosis.category === 'string' && diagnosis.category.trim()) ||
      (typeof diagnosis.component === 'string' && diagnosis.component.trim()) ||
      (typeof diagnosis.reasoning === 'string' && diagnosis.reasoning.trim())
  );
}

function hasRemediation(remediation, incident) {
  if (remediation && typeof remediation === 'object') {
    if (remediation.recommended_action && typeof remediation.recommended_action === 'object') return true;
    if (remediation.requires_approval != null) return true;
  }
  const ra = incident?.recommended_action;
  return !!(ra && typeof ra === 'object' && (ra.description || ra.action_type));
}

/** Prefer incident.full_state; some payloads only nest under investigation_result. */
function resolveFullState(incident) {
  const a = incident?.full_state;
  if (a && typeof a === 'object' && Object.keys(a).length > 0) return a;
  const b = incident?.investigation_result?.full_state;
  if (b && typeof b === 'object') return b;
  return {};
}

function useStructuredLayout(fullState, incident) {
  if (!fullState || typeof fullState !== 'object') return false;
  return (
    hasTriage(fullState.triage) ||
    hasAnalysis(fullState.analysis) ||
    hasDiagnosis(fullState.diagnosis) ||
    hasRemediation(fullState.remediation, incident)
  );
}

function SubPanel({ title, children }) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white px-3 py-3 mb-3 last:mb-0">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-2">{title}</div>
      <div className="text-sm text-gray-800 leading-relaxed">{children}</div>
    </section>
  );
}

function StructuredSummary({ incident, formatMarkdown }) {
  const fs = resolveFullState(incident);
  const triage = fs.triage;
  const analysis = fs.analysis;
  const diagnosis = fs.diagnosis;
  const remediation = fs.remediation;
  const action = remediation?.recommended_action || incident.recommended_action;

  const executive =
    typeof incident.executive_summary === 'string' ? incident.executive_summary.trim() : '';
  const analysisSummary = typeof analysis?.summary === 'string' ? analysis.summary.trim() : '';
  const showExecutiveFallback =
    Boolean(executive) &&
    (!hasAnalysis(analysis) || !analysisSummary);

  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50/90 p-3 sm:p-4">
      <SubPanel title="Metadata">
        <p className="m-0 font-semibold text-gray-900">
          INCIDENT INVESTIGATION: {incident.incident_id}
        </p>
        <p className="mt-2 mb-0">
          <span className="font-semibold text-gray-900">Service:</span>{' '}
          {incident.service || '—'}
        </p>
        {hasTriage(triage) && (
          <div className="mt-3 space-y-1.5">
            {dispEnum(triage.severity) && (
              <p className="m-0">
                <span className="font-semibold text-gray-900">SEVERITY:</span>{' '}
                {dispEnum(triage.severity)}
              </p>
            )}
            {dispEnum(triage.decision) && (
              <p className="m-0">
                <span className="font-semibold text-gray-900">Decision:</span>{' '}
                {dispEnum(triage.decision)}
              </p>
            )}
            {typeof triage.reasoning === 'string' && triage.reasoning.trim() && (
              <p className="m-0">
                <span className="font-semibold text-gray-900">Reasoning:</span>{' '}
                <span className="font-normal">{triage.reasoning.trim()}</span>
              </p>
            )}
          </div>
        )}
        {!hasTriage(triage) && incident.severity && (
          <p className="mt-2 m-0">
            <span className="font-semibold text-gray-900">SEVERITY:</span> {String(incident.severity)}
          </p>
        )}
      </SubPanel>

      {hasAnalysis(analysis) && (
        <SubPanel title="Log analysis">
          {analysis.error_count != null && analysis.error_count > 0 && (
            <p className="m-0 mb-2">
              <span className="font-semibold text-gray-900">Error count:</span> {analysis.error_count}
            </p>
          )}
          {Array.isArray(analysis.error_patterns) && analysis.error_patterns.length > 0 && (
            <div className="mb-2">
              <p className="m-0 mb-1 font-semibold text-gray-900">Patterns</p>
              <ul className="m-0 pl-5 list-disc space-y-0.5">
                {analysis.error_patterns.map((p, i) => (
                  <li key={i} className="font-mono text-xs sm:text-sm break-words">
                    {String(p)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {Array.isArray(analysis.key_findings) && analysis.key_findings.length > 0 && (
            <div className="mb-2">
              <p className="m-0 mb-1 font-semibold text-gray-900">Key findings</p>
              <ul className="m-0 pl-5 list-disc space-y-0.5">
                {analysis.key_findings.map((f, i) => (
                  <li key={i}>{String(f)}</li>
                ))}
              </ul>
            </div>
          )}
          {analysisSummary &&
            (formatMarkdown ? (
              <div className="mt-1">
                <p className="m-0 mb-1 font-semibold text-gray-900">Summary</p>
                <ChatMarkdown>{analysis.summary}</ChatMarkdown>
              </div>
            ) : (
              <p className="m-0 mt-1 whitespace-pre-wrap">
                <span className="font-semibold text-gray-900">Summary:</span> {analysisSummary}
              </p>
            ))}
        </SubPanel>
      )}

      {(hasDiagnosis(diagnosis) || meaningfulRootCause(incident)) && (
        <SubPanel title="Root cause">
          {hasDiagnosis(diagnosis) ? (
            <>
              <p className="m-0 mb-2">
                <span className="font-semibold text-gray-900">
                  ROOT CAUSE ({diagnosis.confidence != null ? `${diagnosis.confidence}%` : '—'} confidence):
                </span>
              </p>
              {diagnosis.root_cause && (
                <p className="m-0 mb-2 whitespace-pre-wrap">{diagnosis.root_cause}</p>
              )}
              {diagnosis.category && (
                <p className="m-0 mb-1">
                  <span className="font-semibold text-gray-900">Category:</span> {diagnosis.category}
                </p>
              )}
              {diagnosis.component && (
                <p className="m-0 mb-2">
                  <span className="font-semibold text-gray-900">Component:</span> {diagnosis.component}
                </p>
              )}
              {typeof diagnosis.reasoning === 'string' && diagnosis.reasoning.trim() && (
                <p className="m-0 mb-2 whitespace-pre-wrap">
                  <span className="font-semibold text-gray-900">Reasoning:</span> {diagnosis.reasoning.trim()}
                </p>
              )}
              {Array.isArray(diagnosis.supporting_evidence) && diagnosis.supporting_evidence.length > 0 && (
                <div>
                  <p className="m-0 mb-1 font-semibold text-gray-900">Supporting evidence</p>
                  <ul className="m-0 pl-5 list-disc space-y-0.5">
                    {diagnosis.supporting_evidence.map((e, i) => (
                      <li key={i}>{String(e)}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <p className="m-0 whitespace-pre-wrap">{meaningfulRootCause(incident)}</p>
          )}
        </SubPanel>
      )}

      {hasRemediation(remediation, incident) && action && (
        <SubPanel title="Recommended action">
          {action.description && <p className="m-0 mb-2 whitespace-pre-wrap">{action.description}</p>}
          {action.action_type && (
            <p className="m-0 mb-1">
              <span className="font-semibold text-gray-900">Type:</span> {String(action.action_type)}
            </p>
          )}
          {action.risk_level != null && (
            <p className="m-0 mb-1">
              <span className="font-semibold text-gray-900">Risk:</span> {dispEnum(action.risk_level)}
            </p>
          )}
          {remediation?.requires_approval != null && (
            <p className="m-0 mb-2">
              <span className="font-semibold text-gray-900">Requires approval:</span>{' '}
              {String(remediation.requires_approval)}
            </p>
          )}
          {Array.isArray(action.steps) && action.steps.length > 0 && (
            <div>
              <p className="m-0 mb-1 font-semibold text-gray-900">Steps</p>
              <ol className="m-0 pl-5 list-decimal space-y-1">
                {action.steps.map((step, i) => (
                  <li key={i} className="whitespace-pre-wrap">
                    {normalizeRemediationStepText(step)}
                  </li>
                ))}
              </ol>
            </div>
          )}
          {incident.execution_type === 'code_fix' &&
            action?.action_type &&
            String(action.action_type).toLowerCase().includes('rollback') && (
              <p className="text-xs text-amber-900 bg-amber-50 border border-amber-200/80 rounded-md px-2.5 py-2 mt-3 m-0 leading-snug">
                <span className="font-semibold">Note:</span> This incident is on a code-fix path (issue/PR in the lifecycle
                below). The recommended action above is from the initial investigation and may differ—for example rollback
                vs forward fix. Treat the active remediation workflow as the source of truth unless you explicitly choose
                a different operational response.
              </p>
            )}
        </SubPanel>
      )}

      {showExecutiveFallback && (
        <details className="rounded-lg border border-gray-200 bg-white px-3 py-2 mt-1 group">
          <summary className="text-xs font-semibold text-violet-700 cursor-pointer list-none flex items-center gap-2">
            <span className="group-open:rotate-90 transition-transform inline-block" aria-hidden>
              ▸
            </span>
            Full investigation report
          </summary>
          <div className="mt-2 pt-2 border-t border-gray-100 text-sm text-gray-800 leading-relaxed">
            {formatMarkdown && executiveSummaryIsFullNarrative(executive) ? (
              <ChatMarkdown>{executive}</ChatMarkdown>
            ) : (
              <p className="m-0 whitespace-pre-wrap">{executive}</p>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

export default function IncidentSummaryPanel({
  incident,
  messageText = '',
  formatMarkdown = false,
}) {
  if (!incident?.incident_id) return null;

  const fullState = resolveFullState(incident);
  const structured = useStructuredLayout(fullState, incident);

  const executive = typeof incident.executive_summary === 'string' ? incident.executive_summary.trim() : '';
  const root = meaningfulRootCause(incident);
  const fallback = typeof messageText === 'string' ? messageText.trim() : '';
  const blobBody = executive || root || fallback;

  const placeholder =
    'Investigation is in progress. A read-only summary will appear here when analysis completes.';

  return (
    <div className="mb-4">
      <div className="mb-3 min-w-0">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-violet-700 mb-1">
          Incident summary
        </div>
        <h2 className="text-lg font-bold text-gray-900 leading-snug m-0">What happened</h2>
      </div>

      {structured ? (
        <StructuredSummary incident={incident} formatMarkdown={formatMarkdown} />
      ) : (
        <div className="rounded-xl border border-gray-200 bg-gray-50/90 px-4 py-4 text-sm text-gray-800 leading-relaxed">
          {blobBody ? (
            formatMarkdown ? (
              <ChatMarkdown>{blobBody}</ChatMarkdown>
            ) : (
              <p className="m-0 whitespace-pre-wrap">{blobBody}</p>
            )
          ) : (
            <p className="m-0 text-gray-500">{placeholder}</p>
          )}
        </div>
      )}
    </div>
  );
}
