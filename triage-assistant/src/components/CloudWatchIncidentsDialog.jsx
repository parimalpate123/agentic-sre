/**
 * CloudWatch Incidents Dialog Component
 * Allows users to view and load CloudWatch alarm-triggered incidents,
 * and optionally ServiceNow / Jira when Incident MCP is enabled.
 */

import { useState, useEffect } from 'react';
import { fetchIncidents, deleteIncident, reanalyzeIncident, getRemediationStatus } from '../services/api';
import { incidentToMessage, parseIncidentData } from '../utils/incidentParser';
import { normalizeCloudWatchIncident, normalizeServiceNowTicket, normalizeJiraIssue } from '../utils/incidentNormalizer';
import { MOCK_SERVICENOW_TICKETS, MOCK_JIRA_ISSUES } from '../data/mockIncidents';

export default function CloudWatchIncidentsDialog({
  isOpen,
  onClose,
  onLoadIncident,
  initialSource = 'cloudwatch_alarm'
}) {
  const [incidents, setIncidents] = useState([]);
  const [allIncidents, setAllIncidents] = useState([]); // Store all incidents for client-side filtering
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [timeframe, setTimeframe] = useState('24h'); // Default to last 24 hours
  const [expandedIncident, setExpandedIncident] = useState(null); // Track which incident card is expanded
  const [remediationStatuses, setRemediationStatuses] = useState({}); // Track remediation status for each incident
  const [incidentSource, setIncidentSource] = useState(initialSource); // cloudwatch_alarm | servicenow | jira

  // Timeframe options
  const timeframeOptions = [
    { value: '1h', label: 'Last Hour' },
    { value: '6h', label: 'Last 6 Hours' },
    { value: '24h', label: 'Last 24 Hours' },
    { value: '7d', label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' },
    { value: 'all', label: 'All Time' }
  ];

  // When dialog opens, sync incident source from parent (main dashboard "Incident source" dropdown)
  useEffect(() => {
    if (isOpen && initialSource) {
      setIncidentSource(initialSource);
    }
  }, [isOpen, initialSource]);

  // Load incidents when dialog opens or when timeframe / incident source changes
  useEffect(() => {
    if (isOpen) {
      loadIncidents();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, timeframe, incidentSource]);

  // Fetch remediation status when incident is expanded (always refetch so expanded card is up to date)
  useEffect(() => {
    if (expandedIncident) {
      fetchRemediationStatusForIncident(expandedIncident, true);
    }
  }, [expandedIncident]);

  // Filter incidents when timeframe changes
  useEffect(() => {
    filterIncidentsByTimeframe();
  }, [timeframe, allIncidents]);

  const loadIncidents = async (forceRefresh = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchIncidents({
        limit: 100,
        source: incidentSource,
        status: 'all'
      });
      let list = result || [];

      if (incidentSource === 'servicenow' || incidentSource === 'jira') {
        // Use mock data when API returns empty (e.g. Incident MCP not deployed)
        if (list.length === 0) {
          list = incidentSource === 'servicenow' ? MOCK_SERVICENOW_TICKETS : MOCK_JIRA_ISSUES;
        }
        const normalizer = incidentSource === 'servicenow' ? normalizeServiceNowTicket : normalizeJiraIssue;
        const normalized = list.map((item) => normalizer(item));
        const sorted = normalized.sort((a, b) => {
          const tsA = a.timestamp || '';
          const tsB = b.timestamp || '';
          if (!tsA && !tsB) return 0;
          if (!tsA) return 1;
          if (!tsB) return -1;
          try {
            return new Date(tsB).getTime() - new Date(tsA).getTime();
          } catch {
            return 0;
          }
        });
        setAllIncidents(sorted);
        setRemediationStatuses({});
        return;
      }

      // CloudWatch path (unchanged behavior)
      const sorted = list.sort((a, b) => {
        const getTimestamp = (incident) => {
          const rawData = incident.data
            ? (typeof incident.data === 'string' ? JSON.parse(incident.data) : incident.data)
            : (incident.investigation_result || incident);
          const parsed = parseIncidentData(rawData);
          return parsed.timestamp || incident.timestamp || incident.created_at || '';
        };
        const timestampA = getTimestamp(a);
        const timestampB = getTimestamp(b);
        if (!timestampA && !timestampB) return 0;
        if (!timestampA) return 1;
        if (!timestampB) return -1;
        try {
          const dateA = new Date(timestampA);
          const dateB = new Date(timestampB);
          return dateB.getTime() - dateA.getTime();
        } catch {
          return 0;
        }
      });
      setAllIncidents(sorted);
      fetchRemediationStatusesForAll(sorted, forceRefresh);
    } catch (err) {
      console.error('Error loading incidents:', err);
      setError('Failed to load incidents. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchRemediationStatusesForAll = async (incidentsList, forceRefresh = false) => {
    // Fetch remediation status for all incidents in parallel.
    // When forceRefresh is true (e.g. user clicked Refresh), refetch for every incident
    // so the list shows up-to-date state without reopening the page.
    const statusPromises = incidentsList.map(async (incident) => {
      try {
        const rawData = incident.data
          ? (typeof incident.data === 'string' ? JSON.parse(incident.data) : incident.data)
          : (incident.investigation_result || incident);
        const parsed = parseIncidentData(rawData);
        const incidentId = parsed.incident_id;

        if (!incidentId) return null;
        if (!forceRefresh && remediationStatuses[incidentId]) return null;

        const status = await getRemediationStatus(incidentId);
        if (status) {
          return { incidentId, status };
        }
        return null;
      } catch (err) {
        console.error(`Error fetching remediation status for incident:`, err);
        return null;
      }
    });
    
    // Wait for all requests to complete (don't block UI)
    Promise.all(statusPromises).then(results => {
      const newStatuses = {};
      results.forEach(result => {
        if (result) {
          newStatuses[result.incidentId] = result.status;
        }
      });
      
      if (Object.keys(newStatuses).length > 0) {
        setRemediationStatuses(prev => ({
          ...prev,
          ...newStatuses
        }));
      }
    });
  };

  const filterIncidentsByTimeframe = () => {
    if (timeframe === 'all') {
      setIncidents(allIncidents);
      return;
    }

    const now = new Date();
    let cutoffTime;

    switch (timeframe) {
      case '1h':
        cutoffTime = new Date(now - 60 * 60 * 1000);
        break;
      case '6h':
        cutoffTime = new Date(now - 6 * 60 * 60 * 1000);
        break;
      case '24h':
        cutoffTime = new Date(now - 24 * 60 * 60 * 1000);
        break;
      case '7d':
        cutoffTime = new Date(now - 7 * 24 * 60 * 60 * 1000);
        break;
      case '30d':
        cutoffTime = new Date(now - 30 * 24 * 60 * 60 * 1000);
        break;
      default:
        setIncidents(allIncidents);
        return;
    }

    const filtered = allIncidents.filter(incident => {
      const timestamp = incident.timestamp || incident.created_at || incident.investigation_result?.timestamp;
      if (!timestamp) return true; // Include incidents without timestamp
      
      try {
        const incidentDate = new Date(timestamp);
        return incidentDate >= cutoffTime;
      } catch {
        return true; // Include incidents with invalid timestamp
      }
    });

    setIncidents(filtered);
  };

  const handleLoadIncident = (incidentItem) => {
    try {
      let incidentMessage;
      if (incidentItem.source === 'servicenow' || incidentItem.source === 'jira') {
        const label = incidentItem.source === 'servicenow' ? 'ServiceNow' : 'Jira';
        const incidentNumberLabel = incidentItem.source === 'servicenow' ? 'Ticket' : 'Issue';
        let text = `**${label} ${incidentNumberLabel} #${incidentItem.id}:** ${incidentItem.title}\n\n**Service:** ${incidentItem.service}\n**Status:** ${incidentItem.status}\n**Priority:** ${incidentItem.priority || '—'}`;
        if (incidentItem.timestamp) {
          try {
            const d = new Date(incidentItem.timestamp);
            text += `\n**Date/Time:** ${d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}`;
          } catch (_) {}
        }
        if (incidentItem.app_name || incidentItem.system_name) {
          text += `\n**App/System:** ${incidentItem.app_name || incidentItem.system_name}`;
        }
        if (incidentItem.created_by) {
          text += `\n**Created by:** ${incidentItem.created_by}`;
        }
        if (incidentItem.description) {
          text += `\n\n**Description:**\n${incidentItem.description}`;
        }
        if (incidentItem.steps_to_reproduce) {
          text += `\n\n**Steps to reproduce:**\n${incidentItem.steps_to_reproduce}`;
        }
        incidentMessage = {
          id: `incident-${incidentItem.id}`,
          role: 'system',
          text,
          timestamp: incidentItem.timestamp ? new Date(incidentItem.timestamp) : new Date(),
          incident: {
            incident_id: incidentItem.id,
            source: incidentItem.source,
            service: incidentItem.service,
            severity: incidentItem.priority || '—',
            root_cause: incidentItem.title,
            alert_name: incidentItem.title,
            execution_type: null,
            execution_results: null
          }
        };
      } else {
        incidentMessage = incidentToMessage(incidentItem);
      }
      onLoadIncident(incidentMessage);
      onClose();
    } catch (err) {
      console.error('Error loading incident:', err);
      setError('Failed to load incident. Please try again.');
    }
  };

  const handleDeleteIncident = async (incidentId, e) => {
    e.stopPropagation(); // Prevent loading the incident when clicking delete
    
    if (!window.confirm(`Are you sure you want to delete incident ${incidentId}? This action cannot be undone.`)) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await deleteIncident(incidentId);
      
      // Remove from local state
      setAllIncidents(prev => prev.filter(inc => {
        const id = inc.incident_id || inc.investigation_result?.incident_id;
        return id !== incidentId;
      }));
      
      // Reload incidents to refresh the list
      await loadIncidents();
    } catch (err) {
      console.error('Error deleting incident:', err);
      setError(`Failed to delete incident: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReanalyzeIncident = async (incidentId, e) => {
    if (e) {
      e.stopPropagation(); // Prevent loading the incident when clicking re-analyze
    }
    
    setIsLoading(true);
    setError(null);

    try {
      console.log(`🔄 Re-analyzing incident: ${incidentId}`);
      const result = await reanalyzeIncident(incidentId);
      
      console.log('✅ Re-analysis complete:', result);
      
      // Reload incidents to refresh the list with updated data
      await loadIncidents();
      
      // Show success message
      setError(null);
      // Optionally show a success notification
      alert(`Incident ${incidentId} has been re-analyzed successfully. The results have been updated.`);
    } catch (err) {
      console.error('Error re-analyzing incident:', err);
      setError(`Failed to re-analyze incident: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteAllUnknown = async () => {
    const unknownIncidents = incidents.filter(incident => {
      const rawData = incident.data
        ? (typeof incident.data === 'string' ? JSON.parse(incident.data) : incident.data)
        : (incident.investigation_result || incident);
      const parsed = parseIncidentData(rawData);
      return parsed.service === 'unknown';
    });

    if (unknownIncidents.length === 0) {
      alert('No incidents with "unknown" service found.');
      return;
    }

    if (!window.confirm(
      `Are you sure you want to delete ${unknownIncidents.length} incident(s) with "unknown" service? This action cannot be undone.`
    )) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      let deletedCount = 0;
      let failedCount = 0;

      for (const incident of unknownIncidents) {
        const rawData = incident.data
          ? (typeof incident.data === 'string' ? JSON.parse(incident.data) : incident.data)
          : (incident.investigation_result || incident);
        const parsed = parseIncidentData(rawData);
        const incidentId = parsed.incident_id || incident.incident_id;

        try {
          await deleteIncident(incidentId);
          deletedCount++;
        } catch (err) {
          console.error(`Failed to delete incident ${incidentId}:`, err);
          failedCount++;
        }
      }

      // Reload incidents
      await loadIncidents();

      if (failedCount > 0) {
        alert(`Deleted ${deletedCount} incident(s). ${failedCount} failed to delete.`);
      } else {
        alert(`Successfully deleted ${deletedCount} incident(s) with "unknown" service.`);
      }
    } catch (err) {
      console.error('Error deleting unknown incidents:', err);
      setError(`Failed to delete incidents: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchRemediationStatusForIncident = async (incidentId, forceRefresh = false) => {
    if (!forceRefresh && remediationStatuses[incidentId]) {
      return;
    }

    try {
      const status = await getRemediationStatus(incidentId);
      if (status) {
        setRemediationStatuses(prev => ({
          ...prev,
          [incidentId]: status
        }));
      }
    } catch (err) {
      console.error(`Error fetching remediation status for ${incidentId}:`, err);
    }
  };

  const getCurrentStage = (parsed, remediationStatus) => {
    // Check execution_results first (from incident data)
    const githubIssue = parsed.execution_results?.github_issue;
    
    // Check remediation status (from DynamoDB remediation_state table)
    const issue = remediationStatus?.issue;
    const pr = remediationStatus?.pr;
    const timeline = remediationStatus?.timeline || [];

    // Determine current stage based on timeline and status
    // API returns issue.url / pr.url; support both for backwards compatibility
    const hasIssue = issue?.issue_url || issue?.url || githubIssue?.issue_url;
    const hasPR = pr?.pr_url || pr?.url || pr?.number;
    const reviewStatus = pr?.review_status;

    // Check timeline events to determine stage
    const timelineEvents = timeline.map(e => typeof e === 'object' ? e.event : e);
    
    // PR Review complete
    if (reviewStatus && reviewStatus !== 'pending') {
      return { 
        stage: 'pr_review', 
        text: 'AI PR Review Complete', 
        color: 'bg-green-100 text-green-800 border-green-300', 
        icon: '✅',
        currentStage: 5
      };
    }
    
    // PR Review in progress
    if (hasPR && (timelineEvents.includes('pr_review_started') || !reviewStatus || reviewStatus === 'pending')) {
      return { 
        stage: 'pr_review', 
        text: 'AI PR Review', 
        color: 'bg-blue-100 text-blue-800 border-blue-300', 
        icon: '🤖',
        currentStage: 5
      };
    }
    
    // PR Created
    if (hasPR) {
      return { 
        stage: 'pr_creation', 
        text: 'PR Created', 
        color: 'bg-blue-100 text-blue-800 border-blue-300', 
        icon: '📝',
        currentStage: 4
      };
    }
    
    // PR Creation in progress
    if (timelineEvents.includes('pr_creation_started')) {
      return { 
        stage: 'pr_creation', 
        text: 'Creating PR', 
        color: 'bg-yellow-100 text-yellow-800 border-yellow-300', 
        icon: '⏳',
        currentStage: 4
      };
    }
    
    // Fix Generation in progress
    if (timelineEvents.includes('fix_generation_started')) {
      return { 
        stage: 'fix_generation', 
        text: 'Generating Fix', 
        color: 'bg-purple-100 text-purple-800 border-purple-300', 
        icon: '✏️',
        currentStage: 3
      };
    }
    
    // Analysis in progress
    if (timelineEvents.includes('analysis_started')) {
      return { 
        stage: 'analysis', 
        text: 'Analyzing', 
        color: 'bg-blue-100 text-blue-800 border-blue-300', 
        icon: '🔍',
        currentStage: 2
      };
    }
    
    // Issue Created
    if (hasIssue) {
      return { 
        stage: 'issue', 
        text: 'Issue Created', 
        color: 'bg-yellow-100 text-yellow-800 border-yellow-300', 
        icon: '📋',
        currentStage: 1
      };
    }
    
    // Auto-executing (code_fix but no issue yet)
    if (parsed.execution_type === 'code_fix') {
      return { 
        stage: 'pending', 
        text: 'Auto-executing', 
        color: 'bg-purple-100 text-purple-800 border-purple-300', 
        icon: '⚡',
        currentStage: 0
      };
    }
    
    // New - AI Analysis
    return { 
      stage: 'new', 
      text: 'AI Analysis', 
      color: 'bg-gray-100 text-gray-800 border-gray-300', 
      icon: '🤖',
      currentStage: 0
    };
  };

  const getStageStatus = (stageId, currentStageInfo, remediationStatus) => {
    const timeline = remediationStatus?.timeline || [];
    const timelineEvents = timeline.map(e => typeof e === 'object' ? e.event : e);
    const issue = remediationStatus?.issue;
    const pr = remediationStatus?.pr;
    
    // Check if stage is completed based on timeline events and status
    let isCompleted = false;
    let isInProgress = false;
    
    switch (stageId) {
      case 'issue':
        isCompleted = !!(issue?.issue_url || issue?.url) || timelineEvents.includes('issue_created');
        break;
      case 'analysis':
        isCompleted = timelineEvents.includes('fix_generation_started') || timelineEvents.includes('pr_creation_started');
        isInProgress = timelineEvents.includes('analysis_started') && !isCompleted;
        break;
      case 'fix_generation':
        isCompleted = timelineEvents.includes('pr_creation_started') || !!(pr?.pr_url || pr?.url);
        isInProgress = timelineEvents.includes('fix_generation_started') && !isCompleted;
        break;
      case 'pr_creation':
        isCompleted = !!(pr?.pr_url || pr?.url) || timelineEvents.includes('pr_created');
        isInProgress = timelineEvents.includes('pr_creation_started') && !isCompleted;
        break;
      case 'pr_review':
        isCompleted = pr?.review_status && pr.review_status !== 'pending';
        isInProgress = (timelineEvents.includes('pr_review_started') || !!(pr?.pr_url || pr?.url)) && !isCompleted;
        break;
    }
    
    if (isCompleted) return 'completed';
    if (isInProgress) return 'in_progress';
    return 'pending';
  };

  const handleDeleteAll = async () => {
    if (incidents.length === 0) {
      alert('No incidents to delete.');
      return;
    }

    if (!window.confirm(
      `Are you sure you want to delete ALL ${incidents.length} CloudWatch incident(s)? This action cannot be undone.`
    )) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      let deletedCount = 0;
      let failedCount = 0;

      for (const incident of incidents) {
        const rawData = incident.data
          ? (typeof incident.data === 'string' ? JSON.parse(incident.data) : incident.data)
          : (incident.investigation_result || incident);
        const parsed = parseIncidentData(rawData);
        const incidentId = parsed.incident_id || incident.incident_id;

        try {
          await deleteIncident(incidentId);
          deletedCount++;
        } catch (err) {
          console.error(`Failed to delete incident ${incidentId}:`, err);
          failedCount++;
        }
      }

      // Reload incidents
      await loadIncidents();

      if (failedCount > 0) {
        alert(`Deleted ${deletedCount} incident(s). ${failedCount} failed to delete.`);
      } else {
        alert(`Successfully deleted ${deletedCount} incident(s).`);
      }
    } catch (err) {
      console.error('Error deleting all incidents:', err);
      setError(`Failed to delete incidents: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    try {
      let dateStr = dateString.toString().trim();
      
      // Handle various timestamp formats
      // 1. ISO format with milliseconds: "2026-01-26T20:43:32.658803"
      // 2. ISO format with Z: "2026-01-26T20:43:32Z"
      // 3. ISO format with timezone: "2026-01-26T20:43:32+00:00"
      // 4. Already formatted date string
      
      // If it's already a formatted date (contains commas, slashes, or "AM/PM"), return as-is
      if (dateStr.includes(',') || dateStr.includes('/') || dateStr.match(/\d{1,2}:\d{2}\s*(AM|PM)/i)) {
        return dateStr;
      }
      
      // If it's ISO format (contains 'T')
      if (dateStr.includes('T')) {
        // Remove any trailing milliseconds if present
        if (dateStr.includes('.') && !dateStr.includes('Z') && !dateStr.includes('+') && !dateStr.match(/[+-]\d{2}:?\d{2}$/)) {
          // Has milliseconds but no timezone - assume UTC
          const parts = dateStr.split('.');
          dateStr = parts[0] + 'Z'; // Remove milliseconds and add Z for UTC
        } else if (!dateStr.includes('Z') && !dateStr.includes('+') && !dateStr.match(/[+-]\d{2}:?\d{2}$/)) {
          // No timezone info at all - add Z for UTC
          dateStr = dateStr + 'Z';
        }
      } else {
        // Not ISO format - try to parse as-is, but if it fails, assume it's UTC
        const testDate = new Date(dateStr);
        if (isNaN(testDate.getTime())) {
          // If parsing fails, try appending 'Z' to force UTC
          dateStr = dateStr + 'Z';
        }
      }
      
      const date = new Date(dateStr);
      
      // Check if date is valid
      if (isNaN(date.getTime())) {
        console.warn('Invalid date string:', dateString, 'parsed as:', dateStr);
        return dateString; // Return original if invalid
      }
      
      // Convert to EST/EDT timezone (America/New_York)
      // This ensures UTC times are properly converted to Eastern Time
      const formatted = date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
        timeZone: 'America/New_York', // Force EST/EDT timezone
        timeZoneName: 'short' // Shows timezone abbreviation (EST, EDT)
      });
      
      return formatted;
    } catch (error) {
      console.error('Error formatting date:', dateString, error);
      return dateString;
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'P1':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'P2':
        return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'P3':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'P4':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-7xl max-h-[95vh] flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-4 rounded-t-lg">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">⚠️ Incidents</h2>
              <p className="text-xs text-purple-100 mt-1">Click an incident to load it into the chat for detailed analysis</p>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 text-xl font-bold"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-800 text-sm">
              {error}
            </div>
          )}

          {/* Filters and Controls */}
          <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200">
            <div className="flex items-center gap-4">
              <h3 className="text-sm font-semibold text-gray-700">
                Incidents ({incidents.length})
              </h3>
              <div className="flex items-center gap-2">
                <label htmlFor="timeframe" className="text-xs text-gray-600 font-medium">
                  Timeframe:
                </label>
                <select
                  id="timeframe"
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  {timeframeOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label htmlFor="incident-source" className="text-xs text-gray-600 font-medium">
                  Source:
                </label>
                <select
                  id="incident-source"
                  value={incidentSource}
                  onChange={(e) => setIncidentSource(e.target.value)}
                  className="text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="cloudwatch_alarm">CloudWatch</option>
                  <option value="servicenow">ServiceNow</option>
                  <option value="jira">Jira</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* Bulk Delete Options - CloudWatch only */}
              {incidentSource === 'cloudwatch_alarm' && incidents.length > 0 && (
                <div className="flex items-center gap-2 border-r border-gray-300 pr-2 mr-2">
                  <button
                    onClick={handleDeleteAllUnknown}
                    disabled={isLoading}
                    className="text-xs bg-yellow-100 hover:bg-yellow-200 text-yellow-800 font-medium px-2 py-1 rounded disabled:opacity-50 flex items-center gap-1"
                    title="Delete all incidents with 'unknown' service"
                  >
                    🗑️ Delete Unknown
                  </button>
                  <button
                    onClick={handleDeleteAll}
                    disabled={isLoading}
                    className="text-xs bg-red-100 hover:bg-red-200 text-red-800 font-medium px-2 py-1 rounded disabled:opacity-50 flex items-center gap-1"
                    title="Delete all CloudWatch incidents"
                  >
                    🗑️ Delete All
                  </button>
                </div>
              )}
              <button
                onClick={() => loadIncidents(true)}
                disabled={isLoading}
                className="text-xs text-purple-600 hover:text-purple-800 font-medium disabled:opacity-50 flex items-center gap-1"
              >
                🔄 Refresh
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <svg className="animate-spin h-6 w-6 text-purple-600" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
          ) : incidents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p className="text-sm">No {incidentSource === 'cloudwatch_alarm' ? 'CloudWatch' : incidentSource === 'servicenow' ? 'ServiceNow' : 'Jira'} incidents found.</p>
              {incidentSource === 'cloudwatch_alarm' && (
                <p className="text-xs mt-2">Create and trigger a CloudWatch alarm to see incidents here.</p>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {incidents.map((incident) => {
                // ServiceNow / Jira: normalized item (id, source, title, service, timestamp, status)
                if (incident.source === 'servicenow' || incident.source === 'jira') {
                  const sourceLabel = incident.source === 'servicenow' ? 'ServiceNow' : 'Jira';
                  const desc = (incident.description || '').slice(0, 120);
                  const steps = (incident.steps_to_reproduce || '').slice(0, 100);
                  return (
                    <div
                      key={incident.id}
                      className="border rounded-lg border-gray-200 hover:border-purple-300 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="px-2 py-0.5 text-xs font-medium rounded border bg-gray-100 text-gray-700">
                              {sourceLabel}
                            </span>
                            <span className="text-xs text-gray-500">{formatDate(incident.timestamp)}</span>
                            {(incident.app_name || incident.system_name) && (
                              <span className="text-xs text-gray-500">
                                App: {incident.app_name || incident.system_name}
                              </span>
                            )}
                            {incident.created_by && (
                              <span className="text-xs text-gray-500">By: {incident.created_by}</span>
                            )}
                          </div>
                          <h4 className="font-semibold text-gray-800 text-sm">{incident.title}</h4>
                          <p className="text-xs text-gray-600 mt-1">Service: {incident.service} · Status: {incident.status} · Priority: {incident.priority || '—'}</p>
                          {desc && (
                            <p className="text-xs text-gray-500 mt-2 leading-relaxed">{desc}{incident.description?.length > 120 ? '…' : ''}</p>
                          )}
                          {steps && (
                            <p className="text-xs text-gray-500 mt-1"><strong>Steps to reproduce:</strong> {steps}{incident.steps_to_reproduce?.length > 100 ? '…' : ''}</p>
                          )}
                        </div>
                        <button
                          onClick={() => handleLoadIncident(incident)}
                          className="text-xs bg-purple-100 hover:bg-purple-200 text-purple-800 font-medium px-3 py-1.5 rounded shrink-0"
                        >
                          Load
                        </button>
                      </div>
                    </div>
                  );
                }

                // CloudWatch: parse and show full card with remediation lifecycle
                const rawData = incident.data
                  ? (typeof incident.data === 'string' ? JSON.parse(incident.data) : incident.data)
                  : (incident.investigation_result || incident);

                const parsed = parseIncidentData(rawData);

                const incidentId = parsed.incident_id;
                const service = parsed.service;
                const severity = parsed.severity;
                const rootCause = parsed.root_cause;
                const timestamp = parsed.timestamp;
                const confidence = parsed.confidence;
                const alertName = parsed.alert_name;
                const alertDescription = parsed.alert_description;
                const executiveSummary = parsed.executive_summary;
                const recommendedAction = parsed.recommended_action;
                const executionType = parsed.execution_type;
                const isExpanded = expandedIncident === incidentId;
                const remediationStatus = remediationStatuses[incidentId];
                const currentStageInfo = getCurrentStage(parsed, remediationStatus);
                
                // Get issue and PR URLs
                const githubIssue = parsed.execution_results?.github_issue || remediationStatus?.issue;
                const issue = remediationStatus?.issue;
                const pr = remediationStatus?.pr;
                const issueUrl = githubIssue?.issue_url || issue?.issue_url || issue?.url;
                const prUrl = pr?.pr_url || pr?.url;
                
                // Define stages for lifecycle display
                const stages = [
                  { id: 'issue', name: 'Issue', icon: '📋' },
                  { id: 'analysis', name: 'Analysis', icon: '🔍' },
                  { id: 'fix_generation', name: 'Fix', icon: '✏️' },
                  { id: 'pr_creation', name: 'PR', icon: '📝' },
                  { id: 'pr_review', name: 'AI Review', icon: '🤖' }
                ];

                return (
                  <div
                    key={incidentId}
                    className={`border rounded-lg transition-colors ${isExpanded ? 'border-purple-400 bg-purple-50' : 'border-gray-200 hover:border-purple-300'}`}
                  >
                    {/* Compact header — click to expand/collapse */}
                    <div
                      className="p-4 cursor-pointer"
                      onClick={() => setExpandedIncident(isExpanded ? null : incidentId)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs text-gray-400">{isExpanded ? '▼' : '▶'}</span>
                            <h4 className="font-semibold text-gray-800 text-sm">
                              {alertName && alertName !== 'Unknown Alert' ? `${alertName} (${incidentId})` : incidentId}
                            </h4>
                            <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(severity)}`}>
                              {severity}
                            </span>
                            <span className={`px-2 py-0.5 text-xs font-medium rounded border ${currentStageInfo.color}`}>
                              {currentStageInfo.icon} {currentStageInfo.text}
                            </span>
                            {timestamp && (
                              <span className="text-xs font-semibold text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
                                🕐 {formatDate(timestamp)}
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-gray-600 flex flex-wrap gap-x-4 gap-y-1 ml-5">
                            <span><span className="font-medium">Service:</span> {service}</span>
                            <span><span className="font-medium">Confidence:</span> {confidence}%</span>
                            {issueUrl && (
                              <a
                                href={issueUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="text-blue-600 hover:text-blue-800 underline"
                              >
                                📝 Issue #{githubIssue?.issue_number || issue?.issue_number || 'View'}
                              </a>
                            )}
                            {prUrl && (
                              <a
                                href={prUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="text-blue-600 hover:text-blue-800 underline"
                              >
                                🔵 PR #{pr?.pr_number || 'View'}
                              </a>
                            )}
                          </div>
                          
                          {/* Remediation Lifecycle Status - Show in collapsed view */}
                          {(remediationStatus || githubIssue || executionType === 'code_fix') && (
                            <div className="mt-2 ml-5">
                              <div className="flex items-center gap-1">
                                {stages.map((stage, index) => {
                                  const stageStatus = getStageStatus(stage.id, currentStageInfo, remediationStatus);
                                  const isCompleted = stageStatus === 'completed';
                                  const isInProgress = stageStatus === 'in_progress';
                                  
                                  return (
                                    <div key={stage.id} className="flex items-center">
                                      <div className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs ${
                                        isCompleted 
                                          ? 'bg-green-100 text-green-800' 
                                          : isInProgress 
                                          ? 'bg-blue-100 text-blue-800 animate-pulse' 
                                          : 'bg-gray-100 text-gray-400'
                                      }`}>
                                        <span>{isCompleted ? '✅' : isInProgress ? '⏳' : '○'}</span>
                                        <span className="hidden sm:inline">{stage.name}</span>
                                      </div>
                                      {index < stages.length - 1 && (
                                        <div className={`w-2 h-0.5 mx-0.5 ${
                                          isCompleted ? 'bg-green-300' : 'bg-gray-200'
                                        }`} />
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => handleReanalyzeIncident(incidentId, e)}
                            disabled={isLoading}
                            className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors whitespace-nowrap disabled:opacity-50"
                            title="Re-analyze incident"
                          >
                            🔄 Re-analyze
                          </button>
                          <button
                            onClick={(e) => handleDeleteIncident(incidentId, e)}
                            disabled={isLoading}
                            className="px-3 py-1.5 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition-colors whitespace-nowrap disabled:opacity-50"
                            title="Delete incident"
                          >
                            🗑️ Delete
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleLoadIncident(incident);
                            }}
                            className="px-3 py-1.5 bg-purple-600 text-white text-xs rounded hover:bg-purple-700 transition-colors whitespace-nowrap"
                          >
                            Load
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Expanded detail section */}
                    {isExpanded && (
                      <div className="px-4 pb-4 border-t border-purple-200 pt-3 ml-5 space-y-3">
                        {/* Alert description */}
                        {alertDescription && (
                          <div>
                            <p className="text-xs font-semibold text-gray-700 mb-1">Alert Description</p>
                            <p className="text-xs text-gray-600 bg-white p-2 rounded border border-gray-100">{alertDescription}</p>
                          </div>
                        )}

                        {/* Root cause / Executive summary */}
                        {rootCause && rootCause !== 'Unknown' ? (
                          <div>
                            <p className="text-xs font-semibold text-gray-700 mb-1">Root Cause Analysis</p>
                            <p className="text-xs text-gray-600 bg-white p-2 rounded border border-gray-100 whitespace-pre-wrap">{rootCause}</p>
                          </div>
                        ) : executiveSummary ? (
                          <div>
                            <p className="text-xs font-semibold text-gray-700 mb-1">Executive Summary</p>
                            <p className="text-xs text-gray-600 bg-white p-2 rounded border border-gray-100 whitespace-pre-wrap">{executiveSummary}</p>
                          </div>
                        ) : null}

                        {/* Confidence */}
                        {confidence > 0 && (
                          <div>
                            <p className="text-xs font-semibold text-gray-700 mb-1">Confidence Level</p>
                            <div className="flex items-center gap-2">
                              <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-xs">
                                <div
                                  className={`h-2 rounded-full ${confidence >= 70 ? 'bg-green-500' : confidence >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                  style={{ width: `${Math.min(confidence, 100)}%` }}
                                />
                              </div>
                              <span className="text-xs font-medium text-gray-700">{confidence}%</span>
                            </div>
                          </div>
                        )}

                        {/* Recommended action */}
                        {recommendedAction && (
                          <div>
                            <p className="text-xs font-semibold text-gray-700 mb-1">Recommended Action</p>
                            <div className="text-xs text-gray-600 bg-white p-2 rounded border border-gray-100">
                              {typeof recommendedAction === 'object' ? (
                                <>
                                  {recommendedAction.action_type && (
                                    <span className="inline-block font-medium text-orange-700 bg-orange-50 px-1.5 py-0.5 rounded mb-1">
                                      {recommendedAction.action_type.replace(/_/g, ' ')}
                                    </span>
                                  )}
                                  {recommendedAction.description && (
                                    <p className="mt-1">{recommendedAction.description}</p>
                                  )}
                                  {recommendedAction.steps && recommendedAction.steps.length > 0 && (
                                    <ol className="mt-1 ml-4 list-decimal space-y-0.5">
                                      {recommendedAction.steps.map((step, i) => (
                                        <li key={i}>{typeof step === 'string' ? step : step.description || step.action || JSON.stringify(step)}</li>
                                      ))}
                                    </ol>
                                  )}
                                </>
                              ) : (
                                <p className="whitespace-pre-wrap">{recommendedAction}</p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Remediation Lifecycle Status - Detailed view */}
                        {(remediationStatus || githubIssue || executionType === 'code_fix') && (
                          <div>
                            <p className="text-xs font-semibold text-gray-700 mb-2">Remediation Lifecycle</p>
                            <div className="bg-white p-3 rounded border border-gray-200">
                              <div className="flex items-center gap-1">
                                {stages.map((stage, index) => {
                                  const stageStatus = getStageStatus(stage.id, currentStageInfo, remediationStatus);
                                  const isCompleted = stageStatus === 'completed';
                                  const isInProgress = stageStatus === 'in_progress';
                                  
                                  return (
                                    <div key={stage.id} className="flex items-center">
                                      <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
                                        isCompleted 
                                          ? 'bg-green-100 text-green-800' 
                                          : isInProgress 
                                          ? 'bg-blue-100 text-blue-800 animate-pulse' 
                                          : 'bg-gray-100 text-gray-400'
                                      }`}>
                                        <span>{isCompleted ? '✅' : isInProgress ? '⏳' : '○'}</span>
                                        <span>{stage.name}</span>
                                        {stage.id === 'issue' && issueUrl && (
                                          <a
                                            href={issueUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="ml-1 underline hover:text-green-900"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            #{githubIssue?.issue_number || issue?.issue_number}
                                          </a>
                                        )}
                                        {stage.id === 'pr_creation' && prUrl && (
                                          <a
                                            href={prUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="ml-1 underline hover:text-green-900"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            #{pr?.pr_number}
                                          </a>
                                        )}
                                      </div>
                                      {index < stages.length - 1 && (
                                        <div className={`w-3 h-0.5 mx-1 ${
                                          isCompleted ? 'bg-green-300' : 'bg-gray-200'
                                        }`} />
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                              
                              {/* Status message */}
                              {currentStageInfo.text !== 'New' && (
                                <p className="text-xs text-gray-600 mt-2">
                                  {currentStageInfo.text === 'AI PR Review Complete' && '✅ AI review complete. Please review and approve before merging.'}
                                  {currentStageInfo.text === 'AI PR Review' && '🤖 AI-powered PR Review Agent is analyzing the pull request...'}
                                  {currentStageInfo.text === 'PR Created' && '🔵 Pull request created. AI-powered review will start automatically...'}
                                  {currentStageInfo.text === 'Creating PR' && '⏳ Creating pull request with AI-generated fix...'}
                                  {currentStageInfo.text === 'Generating Fix' && '✏️ AI is generating fix based on analysis...'}
                                  {currentStageInfo.text === 'Analyzing' && '🔍 Analyzing code patterns and root cause...'}
                                  {currentStageInfo.text === 'Issue Created' && '📝 GitHub issue created. Auto-fix workflow in progress...'}
                                  {currentStageInfo.text === 'Auto-executing' && '⚡ Auto-execution in progress. Issue will be created automatically.'}
                                </p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Incident ID */}
                        <div>
                          <p className="text-xs font-semibold text-gray-700 mb-1">Incident ID</p>
                          <p className="text-xs text-gray-500 font-mono">{incidentId}</p>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
