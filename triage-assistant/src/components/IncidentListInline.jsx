/**
 * IncidentListInline — incident list rendered inside the TARS layout.
 * Appears when user clicks the "Incidents" tab. Clicking a row opens IncidentPanel.
 */

import { useState, useEffect } from 'react';
import { fetchIncidents } from '../services/api';

const SOURCE_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'cloudwatch_alarm', label: 'Alarm' },
  { value: 'chat', label: 'Chat' },
  { value: 'trace', label: 'Trace' },
];

function sevColor(sev) {
  return ({
    P1: 'bg-red-100 text-red-700 border-red-200',
    P2: 'bg-orange-100 text-orange-700 border-orange-200',
    P3: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    P4: 'bg-gray-100 text-gray-600 border-gray-200',
  }[sev] || 'bg-gray-100 text-gray-600 border-gray-200');
}

function parseItem(item) {
  let raw = item;
  if (item.data) raw = typeof item.data === 'string' ? JSON.parse(item.data) : item.data;
  else if (item.investigation_result) raw = typeof item.investigation_result === 'string' ? JSON.parse(item.investigation_result) : item.investigation_result;

  const fs = raw.full_state || {};
  const diag = fs.diagnosis || {};
  const triage = fs.triage || {};
  const id = raw.incident_id || item.incident_id;
  const service = raw.service || fs.incident?.service || 'unknown';
  const severity = raw.severity || triage.severity?.value || triage.severity || 'P3';
  let confidence = raw.confidence || diag.confidence || 0;
  if (confidence > 0 && confidence <= 1) confidence = Math.round(confidence * 100);
  const alertName = raw.alert_name || fs.incident?.alert_name || 'Incident';
  const rootCause = diag.hypothesis || diag.root_cause || raw.root_cause || '';
  const origin = raw.origin || raw.source || 'chat';
  const timestamp = raw.timestamp || raw.created_at || item.created_at;

  const originIcon = origin === 'cloudwatch_alarm' ? '🔔' : origin === 'trace' ? '🔗' : '💬';
  const originLabel = origin === 'cloudwatch_alarm' ? 'Alarm' : origin === 'trace' ? 'Trace' : 'Chat';

  return { id, service, severity, confidence, alertName, rootCause, originIcon, originLabel, timestamp };
}

export default function IncidentListInline({ onViewIncident, onBack }) {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    setLoading(true);
    fetchIncidents({ limit: 50, source: filter, status: 'all' })
      .then(data => setIncidents(data))
      .catch(() => setIncidents([]))
      .finally(() => setLoading(false));
  }, [filter]);

  const parsed = incidents.map(parseItem);

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden bg-gray-50/60">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-200 shrink-0">
        <button onClick={onBack} className="text-gray-400 hover:text-gray-600 transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <span className="text-sm font-semibold text-gray-800 flex-1">
          Incidents <span className="text-gray-400 font-normal text-xs ml-1">{parsed.length} total</span>
        </span>
        {/* Filter pills */}
        <div className="flex items-center gap-1">
          {SOURCE_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`text-xs font-medium px-2.5 py-1 rounded-full border transition-colors ${
                filter === f.value
                  ? 'bg-violet-600 text-white border-violet-600'
                  : 'bg-white text-gray-500 border-gray-200 hover:border-violet-300 hover:text-violet-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-3">
        {loading && (
          <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
            <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading...
          </div>
        )}

        {!loading && parsed.length === 0 && (
          <div className="text-center py-16 text-gray-400 text-sm">No incidents found</div>
        )}

        {!loading && parsed.length > 0 && (
          <div className="space-y-2 max-w-3xl mx-auto">
            {parsed.map(inc => (
              <button
                key={inc.id}
                onClick={() => onViewIncident(inc.id)}
                className="w-full text-left bg-white border border-gray-200 rounded-xl px-4 py-3.5 hover:border-violet-300 hover:shadow-sm transition-all group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-xs">{inc.originIcon}</span>
                      <span className="text-[10px] text-gray-400 font-medium uppercase tracking-wide">{inc.originLabel}</span>
                      {inc.timestamp && (
                        <span className="text-[10px] text-gray-400">
                          · {new Date(inc.timestamp).toLocaleString()}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-violet-700 transition-colors">
                      {inc.alertName}
                    </p>
                    {inc.rootCause && (
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{inc.rootCause}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {inc.service && inc.service !== 'unknown' && (
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 border border-violet-200">
                        {inc.service}
                      </span>
                    )}
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${sevColor(inc.severity)}`}>
                      {inc.severity}
                    </span>
                    {inc.confidence > 0 && (
                      <span className="text-xs text-gray-500">{inc.confidence}%</span>
                    )}
                    <svg className="w-3.5 h-3.5 text-gray-300 group-hover:text-violet-400 transition-colors" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
