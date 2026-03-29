/**
 * IncidentFormPanel — loads an incident by ID from DynamoDB and renders IncidentFormView.
 * Mounts inside ChatLayout alongside the hidden (not unmounted) ChatWindow.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import IncidentFormView from './IncidentFormView';
import { fetchIncidents, getRemediationStatus } from '../services/api';
import { parseIncidentData } from '../utils/incidentParser';

const POLL_INTERVAL = 8000;
const POLL_TIMEOUT = 10 * 60 * 1000;

export default function IncidentFormPanel({ incidentId, onBack }) {
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
    if (!incidentId) return;
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      setIncident(null);
      setRemediationStatus(null);
      stopPolling();

      try {
        // Fetch all incidents and find by ID (same approach as IncidentPanel)
        const incidents = await fetchIncidents({ limit: 100, source: 'all', status: 'all' });
        const found = incidents.find(item => {
          const raw = item.data
            ? (typeof item.data === 'string' ? JSON.parse(item.data) : item.data)
            : item;
          return raw.incident_id === incidentId;
        });

        if (!found || cancelled) {
          if (!cancelled) setError('Incident not found: ' + incidentId);
          return;
        }

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

        if (cancelled) return;

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
          timestamp: parsed.timestamp,
        });
        setDisplayText(raw.display_text || null);
        setDiagnosis(fullState.diagnosis || null);
        setOrigin(raw.origin || parsed.source || 'chat');
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [incidentId]);

  // Start remediation polling for code_fix incidents
  useEffect(() => {
    if (!incident?.incident_id || incident.execution_type !== 'code_fix') return;
    startPolling(incident.incident_id);
    return () => stopPolling();
  }, [incident?.incident_id, incident?.execution_type]);

  const startPolling = useCallback((id) => {
    if (pollingIntervalRef.current) return;
    setIsPollingActive(true);
    pausedRef.current = false;
    setIsPollingPaused(false);
    pollingStartRef.current = Date.now();

    const poll = async () => {
      if (pausedRef.current) return;
      if (Date.now() - pollingStartRef.current > POLL_TIMEOUT) { stopPolling(); return; }
      try {
        const status = await getRemediationStatus(id);
        if (status) setRemediationStatus(status);
      } catch (e) { console.error('Poll error:', e); }
    };

    poll();
    pollingIntervalRef.current = setInterval(poll, POLL_INTERVAL);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPollingActive(false);
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <svg className="animate-spin h-6 w-6" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm">Loading incident form...</p>
        </div>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 bg-gray-50">
        <p className="text-red-600 text-sm">{error || 'Incident not found'}</p>
        <button onClick={onBack} className="text-sm text-violet-600 hover:underline">← Back to Chat</button>
      </div>
    );
  }

  return (
    <IncidentFormView
      incident={incident}
      displayText={displayText}
      diagnosis={diagnosis}
      origin={origin}
      remediationStatus={remediationStatus}
      onRefreshRemediation={async () => {
        try {
          const s = await getRemediationStatus(incident.incident_id);
          if (s) setRemediationStatus(s);
        } catch (e) { console.error(e); }
      }}
      onPausePolling={() => { pausedRef.current = true; setIsPollingPaused(true); }}
      onResumePolling={() => { pausedRef.current = false; setIsPollingPaused(false); }}
      isPollingActive={isPollingActive}
      isPollingPaused={isPollingPaused}
      onCheckPRStatus={async () => {
        try {
          const s = await getRemediationStatus(incident.incident_id);
          if (s) setRemediationStatus(s);
        } catch (e) { console.error(e); }
      }}
      onBack={onBack}
    />
  );
}
