/**
 * CloudWatch Incidents Dialog Component
 * Allows users to view and load CloudWatch alarm-triggered incidents
 */

import { useState, useEffect } from 'react';
import { fetchIncidents, deleteIncident, reanalyzeIncident } from '../services/api';
import { incidentToMessage, parseIncidentData } from '../utils/incidentParser';

export default function CloudWatchIncidentsDialog({ 
  isOpen, 
  onClose, 
  onLoadIncident
}) {
  const [incidents, setIncidents] = useState([]);
  const [allIncidents, setAllIncidents] = useState([]); // Store all incidents for client-side filtering
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [timeframe, setTimeframe] = useState('24h'); // Default to last 24 hours
  const [expandedIncident, setExpandedIncident] = useState(null); // Track which incident card is expanded

  // Timeframe options
  const timeframeOptions = [
    { value: '1h', label: 'Last Hour' },
    { value: '6h', label: 'Last 6 Hours' },
    { value: '24h', label: 'Last 24 Hours' },
    { value: '7d', label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' },
    { value: 'all', label: 'All Time' }
  ];

  // Load incidents when dialog opens
  useEffect(() => {
    if (isOpen) {
      loadIncidents();
    }
  }, [isOpen]);

  // Filter incidents when timeframe changes
  useEffect(() => {
    filterIncidentsByTimeframe();
  }, [timeframe, allIncidents]);

  const loadIncidents = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchIncidents({
        limit: 100, // Fetch more to allow client-side filtering
        source: 'cloudwatch_alarm',
        status: 'all'
      });
      console.log('📋 Loaded CloudWatch incidents:', result);
      
      // Sort incidents by timestamp descending (newest first)
      const sorted = (result || []).sort((a, b) => {
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
        if (!timestampA) return 1; // Put items without timestamp at end
        if (!timestampB) return -1;
        
        try {
          const dateA = new Date(timestampA);
          const dateB = new Date(timestampB);
          return dateB.getTime() - dateA.getTime(); // Descending (newest first)
        } catch {
          return 0;
        }
      });
      
      setAllIncidents(sorted);
    } catch (err) {
      console.error('Error loading CloudWatch incidents:', err);
      setError('Failed to load CloudWatch incidents. Please try again.');
    } finally {
      setIsLoading(false);
    }
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
      // Convert incident to message format
      const incidentMessage = incidentToMessage(incidentItem);
      
      // Call parent callback to add incident to chat
      onLoadIncident(incidentMessage);
      
      // Close dialog
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-orange-600 to-orange-700 text-white px-6 py-4 rounded-t-lg">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">⚠️ CloudWatch Alarm Incidents</h2>
              <p className="text-xs text-orange-100 mt-1">Click an incident to load it into the chat for detailed analysis</p>
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
                  className="text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  {timeframeOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <button
              onClick={loadIncidents}
              disabled={isLoading}
              className="text-xs text-orange-600 hover:text-orange-800 font-medium disabled:opacity-50 flex items-center gap-1"
            >
              🔄 Refresh
            </button>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <svg className="animate-spin h-6 w-6 text-orange-600" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
          ) : incidents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p className="text-sm">No CloudWatch incidents found.</p>
              <p className="text-xs mt-2">Create and trigger a CloudWatch alarm to see incidents here.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {incidents.map((incident) => {
                // Parse incident data to extract fields correctly
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

                return (
                  <div
                    key={incidentId}
                    className={`border rounded-lg transition-colors ${isExpanded ? 'border-orange-400 bg-orange-50' : 'border-gray-200 hover:border-orange-300'}`}
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
                              {alertName && alertName !== 'Unknown Alert' ? alertName : incidentId}
                            </h4>
                            <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(severity)}`}>
                              {severity}
                            </span>
                          </div>
                          <div className="text-xs text-gray-600 flex flex-wrap gap-x-4 gap-y-1 ml-5">
                            <span><span className="font-medium">Service:</span> {service}</span>
                            <span><span className="font-medium">Confidence:</span> {confidence}%</span>
                            {timestamp && <span><span className="font-medium">Time:</span> {formatDate(timestamp)}</span>}
                          </div>
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
                            className="px-3 py-1.5 bg-orange-600 text-white text-xs rounded hover:bg-orange-700 transition-colors whitespace-nowrap"
                          >
                            Load
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Expanded detail section */}
                    {isExpanded && (
                      <div className="px-4 pb-4 border-t border-orange-200 pt-3 ml-5 space-y-3">
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
