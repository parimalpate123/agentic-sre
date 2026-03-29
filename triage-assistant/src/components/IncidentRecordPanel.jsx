/**
 * Summary header for an incident message — matches product “Incident record” layout.
 * No blast-radius column (per product request).
 */

/** Date + time for incident panel (e.g. Mar 28, 2026, 1:45 AM). */
function formatDateTime(value) {
  if (value == null) return '—';
  try {
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

function pickDetectedAt(incident, messageTimestamp) {
  const inv = incident?.investigation_result;
  return (
    messageTimestamp ||
    incident?.timestamp ||
    incident?.detected_at ||
    (inv && typeof inv === 'object' ? inv.created_at || inv.timestamp : null) ||
    null
  );
}

function sourceLabel(incident) {
  switch (incident?.source) {
    case 'cloudwatch_alarm':
      return 'CloudWatch';
    case 'servicenow':
      return 'ServiceNow';
    case 'jira':
      return 'Jira';
    default:
      return 'Chat';
  }
}

function timelineEvents(remediationStatus) {
  const t = remediationStatus?.timeline || [];
  return t.map((e) => (typeof e === 'object' && e?.event ? e.event : e));
}

export default function IncidentRecordPanel({ incident, remediationStatus = null, messageTimestamp = null }) {
  if (!incident?.incident_id) return null;

  const title =
    incident.alert_name ||
    incident.service ||
    `Incident ${incident.incident_id}`;

  const service = incident.service || '—';
  const severity = incident.severity || '—';
  const confidence =
    incident.confidence != null && incident.confidence !== ''
      ? `${Number(incident.confidence)}% confidence`
      : null;

  const isCodeRelated =
    incident.execution_type === 'code_fix' ||
    (typeof incident.root_cause === 'string' &&
      /code|bug|deploy|rollback|repository/i.test(incident.root_cause));

  const pr = remediationStatus?.pr;
  const issue = remediationStatus?.issue;
  const events = timelineEvents(remediationStatus);
  const merged = pr?.merge_status === 'merged';

  const investigationComplete =
    (incident.root_cause &&
      incident.root_cause !== 'Unknown' &&
      incident.root_cause !== 'Analysis in progress') ||
    Boolean(incident.executive_summary) ||
    Boolean(remediationStatus);

  const fixGenerated =
    events.includes('fix_generation_started') ||
    events.includes('pr_creation_started') ||
    events.includes('pr_created') ||
    Boolean(pr?.number) ||
    Boolean(issue?.number);

  const reviewComplete =
    pr?.ai_pr_review_completed === true ||
    (pr?.review_status && pr.review_status !== 'pending' && pr.review_status != null);

  const workflowSteps = [
    { key: 'src', label: `Source: ${sourceLabel(incident)}`, done: true },
    { key: 'inv', label: 'Investigation complete', done: investigationComplete },
    { key: 'fix', label: 'Fix generated', done: fixGenerated },
    { key: 'rev', label: 'Review complete', done: reviewComplete },
  ];

  let statusHeadline = 'In progress';
  if (merged) {
    statusHeadline = 'Resolved';
  } else if (reviewComplete) {
    statusHeadline = 'Awaiting human review';
  } else if (fixGenerated && pr?.number) {
    statusHeadline = 'Remediation in progress';
  } else if (issue?.number && !pr?.number) {
    statusHeadline = 'Awaiting fix / PR';
  } else if (investigationComplete) {
    statusHeadline = 'Investigation complete';
  }

  const caseLabel = merged ? 'Closed' : 'Active case';
  const caseClass = merged
    ? 'bg-slate-100 text-slate-700 border border-slate-200'
    : 'bg-emerald-50 text-emerald-800 border border-emerald-200';

  /** Always show concrete PR # when remediation has a PR; API next_action only as tooltip context. */
  const prUrl = pr?.url || pr?.pr_url;
  let nextStepDisplay;
  if (pr?.number != null && pr.number !== '') {
    nextStepDisplay = `Review PR #${pr.number}`;
  } else if (issue?.number != null && issue.number !== '') {
    nextStepDisplay = `Track issue #${issue.number}`;
  } else {
    nextStepDisplay = 'Approve GitHub issue creation';
  }
  const nextStepDetail = remediationStatus?.next_action
    ? String(remediationStatus.next_action)
    : nextStepDisplay;

  const detectedAt = pickDetectedAt(incident, messageTimestamp);
  const updatedAt =
    remediationStatus?.updated_at ||
    incident?.updated_at ||
    incident?.investigation_result?.updated_at ||
    messageTimestamp ||
    detectedAt;

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-4 mb-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-violet-700">
          Incident record
        </span>
        <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full shrink-0 ${caseClass}`}>
          {caseLabel}
        </span>
      </div>

      <h3 className="text-lg font-bold text-gray-900 leading-snug mb-3">{title}</h3>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span
          className="text-xs font-medium px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-800 border border-zinc-200/80 font-mono max-w-[min(100%,18rem)] truncate"
          title={incident.incident_id}
        >
          ID {incident.incident_id}
        </span>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-sky-100 text-sky-900 border border-sky-200/80">
          {service}
        </span>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-rose-50 text-rose-800 border border-rose-200/80">
          {severity}
        </span>
        {confidence && (
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-violet-50 text-violet-900 border border-violet-200/80">
            {confidence}
          </span>
        )}
        {isCodeRelated && (
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-amber-50 text-amber-900 border border-amber-200/80">
            Code-related
          </span>
        )}
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-700 border border-gray-200">
          Updated {formatDateTime(updatedAt)}
        </span>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-slate-50 text-slate-700 border border-slate-200">
          First detected {formatDateTime(detectedAt)}
        </span>
      </div>

      <div className="rounded-lg border border-gray-200 bg-gray-50/80 px-3 py-2.5 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs text-gray-700">
        {workflowSteps.map((step, i) => (
          <div key={step.key} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-gray-300 mx-0.5" aria-hidden>→</span>}
            <span
              className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 ${
                step.done ? 'text-green-800 bg-green-50 border border-green-200/80' : 'text-gray-400 bg-white border border-gray-200'
              }`}
            >
              <span aria-hidden>{step.done ? '✅' : '⬜'}</span>
              <span className="font-medium">{step.label}</span>
            </span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-100">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">Status</div>
          <div className="text-sm font-semibold text-gray-900 leading-tight">{statusHeadline}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">Owner</div>
          <div className="text-sm font-semibold text-gray-900 leading-tight">Unassigned</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">First detected</div>
          <div className="text-sm font-semibold text-gray-900 leading-tight">
            {formatDateTime(detectedAt)}
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">Next step</div>
          {pr?.number != null && pr.number !== '' && prUrl ? (
            <a
              href={prUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-semibold text-violet-700 hover:text-violet-900 hover:underline leading-tight break-words inline-block"
              title={nextStepDetail}
            >
              {nextStepDisplay}
            </a>
          ) : (
            <div className="text-sm font-semibold text-gray-900 leading-tight break-words" title={nextStepDetail}>
              {nextStepDisplay}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
