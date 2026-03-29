/**
 * IncidentListPage — /incidents
 * Full-page list of all incidents. Click any row to open IncidentDetailPage.
 */

import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { fetchIncidents } from '../services/api';

const SOURCE_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'cloudwatch_alarm', label: 'CloudWatch' },
  { value: 'chat', label: 'Chat' },
  { value: 'trace', label: 'Trace' },
];

function severityColor(sev) {
  return ({
    P1: 'bg-red-100 text-red-700 border-red-200',
    P2: 'bg-orange-100 text-orange-700 border-orange-200',
    P3: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    P4: 'bg-gray-100 text-gray-600 border-gray-200',
  }[sev] || 'bg-gray-100 text-gray-600 border-gray-200');
}

function originIcon(source, origin) {
  const o = origin || source;
  if (o === 'cloudwatch_alarm') return { icon: '🔔', label: 'Alarm' };
  if (o === 'trace') return { icon: '🔗', label: 'Trace' };
  return { icon: '💬', label: 'Chat' };
}

function parseIncidentItem(item) {
  let raw = item;
  if (item.data) {
    raw = typeof item.data === 'string' ? JSON.parse(item.data) : item.data;
  } else if (item.investigation_result) {
    raw = typeof item.investigation_result === 'string'
      ? JSON.parse(item.investigation_result)
      : item.investigation_result;
  }

  const fullState = raw.full_state || {};
  const diagnosis = fullState.diagnosis || {};
  const triage = fullState.triage || {};

  const id = raw.incident_id || item.incident_id;
  const service = raw.service || fullState.incident?.service || 'unknown';
  const severity = raw.severity || triage.severity?.value || triage.severity || 'P3';
  const confidence = raw.confidence || diagnosis.confidence || 0;
  const alertName = raw.alert_name || fullState.incident?.alert_name || raw.executive_summary?.slice(0, 60) || 'Incident';
  const rootCause = diagnosis.hypothesis || diagnosis.root_cause || raw.root_cause || '';
  const origin = raw.origin || raw.source || 'chat';
  const timestamp = raw.timestamp || raw.created_at || item.created_at;
  const executionType = raw.execution_type || fullState.remediation?.execution_type;

  return { id, service, severity, confidence, alertName, rootCause, origin, timestamp, executionType };
}

export default function IncidentListPage() {
  const navigate = useNavigate();
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sourceFilter, setSourceFilter] = useState('all');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchIncidents({ limit: 50, source: sourceFilter, status: 'all' });
        setIncidents(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [sourceFilter]);

  const parsed = incidents.map(parseIncidentItem);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/chat')}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div>
              <h1 className="text-lg font-semibold text-gray-900">Incidents</h1>
              <p className="text-xs text-gray-500">{parsed.length} incident{parsed.length !== 1 ? 's' : ''}</p>
            </div>
          </div>

          {/* Source filter pills */}
          <div className="flex items-center gap-1.5">
            {SOURCE_FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => setSourceFilter(f.value)}
                className={`text-xs font-medium px-3 py-1.5 rounded-full border transition-colors ${
                  sourceFilter === f.value
                    ? 'bg-violet-600 text-white border-violet-600'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-violet-300 hover:text-violet-700'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        {loading && (
          <div className="flex items-center justify-center py-20 text-gray-400">
            <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading incidents...
          </div>
        )}

        {error && (
          <div className="text-center py-20 text-red-600 text-sm">
            Failed to load incidents: {error}
          </div>
        )}

        {!loading && !error && parsed.length === 0 && (
          <div className="text-center py-20 text-gray-400">
            <p className="text-4xl mb-3">📋</p>
            <p className="text-sm">No incidents found</p>
          </div>
        )}

        {!loading && !error && parsed.length > 0 && (
          <div className="space-y-2">
            {parsed.map((inc) => {
              const { icon, label } = originIcon(inc.origin);
              const conf = typeof inc.confidence === 'number' && inc.confidence > 0 && inc.confidence <= 1
                ? Math.round(inc.confidence * 100)
                : inc.confidence;
              const timeStr = inc.timestamp
                ? new Date(inc.timestamp).toLocaleString()
                : '';

              return (
                <Link
                  key={inc.id}
                  to={`/incidents/${inc.id}`}
                  className="block bg-white border border-gray-200 rounded-xl px-5 py-4 hover:border-violet-300 hover:shadow-sm transition-all group"
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: title + metadata */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-sm">{icon}</span>
                        <span className="text-xs text-gray-400 font-medium">{label}</span>
                        {timeStr && (
                          <span className="text-xs text-gray-400">· {timeStr}</span>
                        )}
                      </div>
                      <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-violet-700 transition-colors">
                        {inc.alertName}
                      </p>
                      {inc.rootCause && (
                        <p className="text-xs text-gray-500 mt-1 line-clamp-1">{inc.rootCause}</p>
                      )}
                    </div>

                    {/* Right: badges */}
                    <div className="flex items-center gap-2 shrink-0">
                      {inc.service && inc.service !== 'unknown' && (
                        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 border border-violet-200">
                          {inc.service}
                        </span>
                      )}
                      {inc.severity && (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${severityColor(inc.severity)}`}>
                          {inc.severity}
                        </span>
                      )}
                      {conf > 0 && (
                        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-50 text-gray-600 border border-gray-200">
                          {conf}%
                        </span>
                      )}
                      <svg className="w-4 h-4 text-gray-300 group-hover:text-violet-400 transition-colors" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
