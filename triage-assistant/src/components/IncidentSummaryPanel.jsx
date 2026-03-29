/**
 * Incident summary (“What happened”) panel.
 */

import ChatMarkdown from './ChatMarkdown';

function meaningfulRootCause(incident) {
  const rc = incident?.root_cause;
  if (typeof rc !== 'string' || !rc.trim()) return '';
  if (rc === 'Unknown' || rc === 'Analysis in progress') return '';
  return rc.trim();
}

export default function IncidentSummaryPanel({
  incident,
  messageText = '',
  formatMarkdown = false,
}) {
  if (!incident?.incident_id) return null;

  const executive = typeof incident.executive_summary === 'string' ? incident.executive_summary.trim() : '';
  const root = meaningfulRootCause(incident);
  const fallback = typeof messageText === 'string' ? messageText.trim() : '';
  const body = executive || root || fallback;

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

      <div className="rounded-xl border border-gray-200 bg-gray-50/90 px-4 py-4 text-sm text-gray-800 leading-relaxed">
        {body ? (
          formatMarkdown ? (
            <ChatMarkdown>{body}</ChatMarkdown>
          ) : (
            <p className="m-0 whitespace-pre-wrap">{body}</p>
          )
        ) : (
          <p className="m-0 text-gray-500">{placeholder}</p>
        )}
      </div>
    </div>
  );
}
