/**
 * IncidentDetailPage — /incidents/:id
 * Dedicated page for a single incident. Loads data, polls remediation, renders IncidentDetailView.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import IncidentDetailView from '../components/IncidentDetailView';
import { fetchIncidents, getRemediationStatus, acknowledgeIncident, deleteIncident, reanalyzeIncident } from '../services/api';
import { parseIncidentData } from '../utils/incidentParser';

const POLL_INTERVAL = 8000;
const POLL_TIMEOUT = 10 * 60 * 1000; // 10 min

export default function IncidentDetailPage() {
  const { incidentId } = useParams();
  const navigate = useNavigate();

  const [incident, setIncident] = useState(null);
  const [displayText, setDisplayText] = useState(null);
  const [diagnosis, setDiagnosis] = useState(null);
  const [origin, setOrigin] = useState('chat');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [remediationStatus, setRemediationStatus] = useState(null);
  const [isPollingActive, setIsPollingActive] = useState(false);
  const [isPollingPaused, setIsPollingPaused] = useState(false);
  const pollingIntervalRef = useRef(null);
  const pollingStartRef = useRef(null);
  const pausedRef = useRef(false);

  // Load incident data
  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        // Fetch all recent incidents and find by ID
        const incidents = await fetchIncidents({ limit: 100, source: 'all', status: 'all' });
        const found = incidents.find(item => {
          const raw = item.data
            ? (typeof item.data === 'string' ? JSON.parse(item.data) : item.data)
            : item;
          return raw.incident_id === incidentId;
        });

        if (!found) {
          setError(`Incident ${incidentId} not found`);
          return;
        }

        // Parse raw data
        let raw = found;
        if (found.data) {
          raw = typeof found.data === 'string' ? JSON.parse(found.data) : found.data;
        } else if (found.investigation_result) {
          raw = typeof found.investigation_result === 'string'
            ? JSON.parse(found.investigation_result)
            : found.investigation_result;
        }

        const parsed = parseIncidentData(raw);
        const fullState = raw.full_state || {};

        setIncident({
          incident_id: parsed.incident_id,
          source: parsed.source,
          service: parsed.service,
          severity: parsed.severity,
          confidence: parsed.confidence,
          alert_name: parsed.alert_name,
          alert_description: parsed.alert_description,
          execution_type: parsed.execution_type,
          execution_results: parsed.execution_results,
          full_state: fullState,
          root_cause: parsed.root_cause,
          executive_summary: raw.executive_summary || fullState.executive_summary,
          recommended_action: parsed.recommended_action,
        });

        setDisplayText(raw.display_text || null);
        setDiagnosis(fullState.diagnosis || null);
        setOrigin(raw.origin || parsed.source || 'chat');

      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [incidentId]);

  // Start remediation polling when incident loads and has code_fix
  useEffect(() => {
    if (!incident?.incident_id) return;
    if (incident.execution_type !== 'code_fix') return;
    startPolling(incident.incident_id);
    return () => stopPolling();
  }, [incident?.incident_id, incident?.execution_type]);

  const startPolling = useCallback((id) => {
    if (pollingIntervalRef.current) return;
    setIsPollingActive(true);
    setIsPollingPaused(false);
    pollingStartRef.current = Date.now();

    const poll = async () => {
      if (pausedRef.current) return;
      if (Date.now() - pollingStartRef.current > POLL_TIMEOUT) {
        stopPolling();
        return;
      }
      try {
        const status = await getRemediationStatus(id);
        if (status) setRemediationStatus(status);
      } catch (e) {
        console.error('Remediation poll error:', e);
      }
    };

    poll(); // immediate first fetch
    pollingIntervalRef.current = setInterval(poll, POLL_INTERVAL);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPollingActive(false);
    setIsPollingPaused(false);
  }, []);

  const pausePolling = useCallback(() => {
    pausedRef.current = true;
    setIsPollingPaused(true);
  }, []);

  const resumePolling = useCallback(() => {
    pausedRef.current = false;
    setIsPollingPaused(false);
  }, []);

  const refreshRemediation = useCallback(async () => {
    if (!incident?.incident_id) return;
    try {
      const status = await getRemediationStatus(incident.incident_id);
      if (status) setRemediationStatus(status);
    } catch (e) {
      console.error('Refresh error:', e);
    }
  }, [incident?.incident_id]);

  const checkPRStatus = useCallback(async () => {
    await refreshRemediation();
  }, [refreshRemediation]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-400 text-sm">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading incident...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
        <p className="text-red-600 text-sm">{error}</p>
        <Link to="/incidents" className="text-sm text-violet-600 hover:underline">← All Incidents</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50 overflow-hidden">
      {/* Top nav bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3 shrink-0">
        <Link
          to="/incidents"
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          All Incidents
        </Link>
        <span className="text-gray-300">/</span>
        <span className="text-sm text-gray-700 font-medium truncate">
          {incident?.alert_name || incidentId}
        </span>
      </div>

      {/* IncidentDetailView fills remaining height */}
      <div className="flex-1 overflow-hidden">
        <IncidentDetailView
          incident={incident}
          displayText={displayText}
          diagnosis={diagnosis}
          origin={origin}
          remediationStatus={remediationStatus}
          onRefreshRemediation={refreshRemediation}
          onPausePolling={pausePolling}
          onResumePolling={resumePolling}
          isPollingActive={isPollingActive}
          isPollingPaused={isPollingPaused}
          onCheckPRStatus={checkPRStatus}
          onBack={() => navigate('/incidents')}
          onAcknowledge={async (id) => {
            await acknowledgeIncident(id);
          }}
          onReanalyze={async (id) => {
            await reanalyzeIncident(id);
            // Reload page to show updated data
            window.location.reload();
          }}
          onDelete={async (id) => {
            await deleteIncident(id);
            navigate('/incidents');
          }}
        />
      </div>
    </div>
  );
}
