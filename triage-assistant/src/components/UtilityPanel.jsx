/**
 * UtilityPanel Component
 * Admin/Utility panel for testing and managing CloudWatch alarms, logs, and incidents
 */

import { useState } from 'react';
import { manageSampleLogs, fetchIncidents } from '../services/api';

export default function UtilityPanel({ onClose }) {
  const [activeTab, setActiveTab] = useState('alarms'); // 'alarms', 'logs', 'incidents', 'lambda-logs'
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [password, setPassword] = useState('');
  const [showPasswordInput, setShowPasswordInput] = useState(false);
  const [pendingOperation, setPendingOperation] = useState(null);
  const [triggerTimeframe, setTriggerTimeframe] = useState('1h'); // Default: last 1 hour
  const [triggerScenario, setTriggerScenario] = useState('code_fix'); // Default: code_fix to test full workflow
  
  // Alarm creation state
  const [alarmConfig, setAlarmConfig] = useState({
    alarmName: 'payment-service-error-rate',
    metricName: 'Errors',
    namespace: 'AWS/Lambda',
    service: 'payment-service',
    threshold: 5.0,
    evaluationPeriods: 1,
    datapointsToAlarm: 1
  });

  // Incident viewing state
  const [incidents, setIncidents] = useState([]);
  const [incidentFilter, setIncidentFilter] = useState({ source: 'all', status: 'all' });

  const handlePasswordSubmit = async () => {
    if (!password) {
      setMessage({ type: 'error', text: 'Password is required' });
      return;
    }

    if (pendingOperation) {
      setIsLoading(true);
      setMessage({ type: '', text: '' });
      
      try {
        const result = await pendingOperation.fn(password);
        setMessage({ type: 'success', text: result.message || 'Operation completed successfully' });
        setShowPasswordInput(false);
        setPassword('');
        setPendingOperation(null);
      } catch (error) {
        setMessage({ type: 'error', text: error.message || 'Operation failed' });
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleLogOperation = async (operation) => {
    setPendingOperation({
      fn: async (pwd) => await manageSampleLogs(operation, pwd)
    });
    setShowPasswordInput(true);
  };

  const handleCreateAlarm = async () => {
    setIsLoading(true);
    setMessage({ type: '', text: '' });
    
    try {
      // Call Lambda to create CloudWatch alarm
      const response = await fetch(import.meta.env.VITE_API_ENDPOINT || 'https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'create_cloudwatch_alarm',
          alarm_name: alarmConfig.alarmName,
          metric_name: alarmConfig.metricName,
          namespace: alarmConfig.namespace,
          service: alarmConfig.service,
          threshold: alarmConfig.threshold,
          evaluation_periods: alarmConfig.evaluationPeriods,
          datapoints_to_alarm: alarmConfig.datapointsToAlarm
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to create alarm: ${response.statusText}`);
      }

      const result = await response.json();
      setMessage({ type: 'success', text: `Alarm "${alarmConfig.alarmName}" created successfully!` });
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to create alarm' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleTriggerAlarm = async (alarmName) => {
    setIsLoading(true);
    setMessage({ type: '', text: '' });
    
    try {
      const response = await fetch(import.meta.env.VITE_API_ENDPOINT || 'https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'trigger_cloudwatch_alarm',
          alarm_name: alarmName,
          timeframe: triggerTimeframe, // Pass timeframe to backend
          scenario: triggerScenario // Pass scenario: 'code_fix' or 'monitor'
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to trigger alarm: ${response.statusText}`);
      }

      const scenarioText = triggerScenario === 'code_fix' 
        ? 'Code fix scenario triggered! Error logs generated. Full workflow will run: Incident → Issue → Auto-Fix → PR → PR Review'
        : 'Monitor scenario triggered! Check the chat for the incident.';
      setMessage({ type: 'success', text: `Alarm "${alarmName}" triggered! ${scenarioText}` });
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to trigger alarm' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadIncidents = async () => {
    setIsLoading(true);
    setMessage({ type: '', text: '' });
    
    try {
      const result = await fetchIncidents({
        limit: 50,
        source: incidentFilter.source === 'all' ? 'all' : incidentFilter.source,
        status: incidentFilter.status === 'all' ? 'all' : incidentFilter.status
      });
      
      setIncidents(result);
      setMessage({ type: 'success', text: `Loaded ${result.length} incident(s)` });
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to load incidents' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Utility & Admin Panel</h2>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700"
        >
          ✕ Close
        </button>
      </div>

      {/* Tabs */}
      <div className="flex space-x-2 mb-6 border-b">
        <button
          onClick={() => setActiveTab('alarms')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'alarms'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          CloudWatch Alarms
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'logs'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          Log Management
        </button>
        <button
          onClick={() => setActiveTab('incidents')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'incidents'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          View Incidents
        </button>
        <button
          onClick={() => setActiveTab('lambda-logs')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'lambda-logs'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          Lambda Logs
        </button>
      </div>

      {/* Message Display */}
      {message.text && (
        <div className={`mb-4 p-3 rounded ${
          message.type === 'error' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
        }`}>
          {message.text}
        </div>
      )}

      {/* Password Input Dialog */}
      {showPasswordInput && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-lg max-w-md w-full">
            <h3 className="text-lg font-bold mb-4">Enter Password</h3>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter log management password"
              className="w-full px-3 py-2 border rounded mb-4"
              onKeyPress={(e) => e.key === 'Enter' && handlePasswordSubmit()}
              autoFocus
            />
            <div className="flex space-x-2">
              <button
                onClick={handlePasswordSubmit}
                disabled={isLoading}
                className="flex-1 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
              >
                Submit
              </button>
              <button
                onClick={() => {
                  setShowPasswordInput(false);
                  setPassword('');
                  setPendingOperation(null);
                }}
                className="flex-1 bg-gray-300 text-gray-700 px-4 py-2 rounded hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CloudWatch Alarms Tab */}
      {activeTab === 'alarms' && (
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold mb-4">Create CloudWatch Alarm</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Alarm Name</label>
                <input
                  type="text"
                  value={alarmConfig.alarmName}
                  onChange={(e) => setAlarmConfig({ ...alarmConfig, alarmName: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="payment-service-error-rate"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Service</label>
                <input
                  type="text"
                  value={alarmConfig.service}
                  onChange={(e) => setAlarmConfig({ ...alarmConfig, service: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="payment-service"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Metric Name</label>
                <input
                  type="text"
                  value={alarmConfig.metricName}
                  onChange={(e) => setAlarmConfig({ ...alarmConfig, metricName: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="Errors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Threshold</label>
                <input
                  type="number"
                  value={alarmConfig.threshold}
                  onChange={(e) => setAlarmConfig({ ...alarmConfig, threshold: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 border rounded"
                  step="0.1"
                />
              </div>
            </div>
            <button
              onClick={handleCreateAlarm}
              disabled={isLoading}
              className="mt-4 bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Creating...' : 'Create Alarm'}
            </button>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-4">Quick Test: Trigger Test Alarm</h3>
            <p className="text-sm text-gray-600 mb-4">
              This will create a test CloudWatch alarm event and trigger the incident workflow.
              The alarm will check for errors in the selected timeframe.
            </p>
            <div className="mb-4 space-y-4">
              <div>
                <label htmlFor="trigger-timeframe" className="block text-sm font-medium text-gray-700 mb-2">
                  Check for errors in:
                </label>
                <select
                  id="trigger-timeframe"
                  value={triggerTimeframe}
                  onChange={(e) => setTriggerTimeframe(e.target.value)}
                  className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  <option value="15m">Last 15 minutes</option>
                  <option value="1h">Last 1 hour</option>
                  <option value="6h">Last 6 hours</option>
                  <option value="24h">Last 24 hours</option>
                </select>
              </div>
              <div>
                <label htmlFor="trigger-scenario" className="block text-sm font-medium text-gray-700 mb-2">
                  Test Scenario:
                </label>
                <select
                  id="trigger-scenario"
                  value={triggerScenario}
                  onChange={(e) => setTriggerScenario(e.target.value)}
                  className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  <option value="code_fix">Code Fix (Full Workflow)</option>
                  <option value="monitor">Monitor Only</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  {triggerScenario === 'code_fix' 
                    ? 'Generates error logs and triggers full workflow: Incident → Issue → Auto-Fix → PR → PR Review'
                    : 'Creates incident for monitoring only (no code changes)'}
                </p>
              </div>
            </div>
            <button
              onClick={() => handleTriggerAlarm('test-payment-service-error-rate')}
              disabled={isLoading}
              className="bg-green-600 text-white px-6 py-2 rounded hover:bg-green-700 disabled:opacity-50"
            >
              {isLoading ? 'Triggering...' : 'Trigger Test Alarm'}
            </button>
          </div>
        </div>
      )}

      {/* Log Management Tab */}
      {activeTab === 'logs' && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Manage Sample Logs</h3>
          <div className="grid grid-cols-3 gap-4">
            <button
              onClick={() => handleLogOperation('regenerate')}
              disabled={isLoading}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              Regenerate Logs
            </button>
            <button
              onClick={() => handleLogOperation('clean')}
              disabled={isLoading}
              className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 disabled:opacity-50"
            >
              Clean Logs
            </button>
            <button
              onClick={() => handleLogOperation('clean_and_regenerate')}
              disabled={isLoading}
              className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50"
            >
              Clean & Regenerate
            </button>
          </div>
          <p className="text-sm text-gray-600 mt-4">
            These operations require a password for security. You'll be prompted when you click a button.
          </p>
        </div>
      )}

      {/* View Incidents Tab */}
      {activeTab === 'incidents' && (
        <div className="space-y-4">
          <div className="flex items-center space-x-4">
            <div>
              <label className="block text-sm font-medium mb-1">Source</label>
              <select
                value={incidentFilter.source}
                onChange={(e) => setIncidentFilter({ ...incidentFilter, source: e.target.value })}
                className="px-3 py-2 border rounded"
              >
                <option value="all">All</option>
                <option value="chat">Chat</option>
                <option value="cloudwatch_alarm">CloudWatch Alarm</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Status</label>
              <select
                value={incidentFilter.status}
                onChange={(e) => setIncidentFilter({ ...incidentFilter, status: e.target.value })}
                className="px-3 py-2 border rounded"
              >
                <option value="all">All</option>
                <option value="open">Open</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>
            <button
              onClick={handleLoadIncidents}
              disabled={isLoading}
              className="mt-6 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Loading...' : '🔄 Load Incidents'}
            </button>
          </div>

          {incidents.length > 0 ? (
            <div className="mt-4">
              <h4 className="font-semibold mb-2">Incidents ({incidents.length})</h4>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {incidents.map((incident) => {
                  // Parse incident data - it might be nested
                  // First try to parse the 'data' field if it's a string
                  let incidentData = incident.investigation_result || incident;
                  if (incident.data) {
                    try {
                      if (typeof incident.data === 'string') {
                        incidentData = JSON.parse(incident.data);
                      } else {
                        incidentData = incident.data;
                      }
                    } catch (e) {
                      console.warn('Failed to parse incident data:', e);
                    }
                  }
                  
                  // Extract fields with proper fallback chain
                  const incidentId = incident.incident_id || incidentData?.incident_id || incident.id || 'unknown';
                  // Source can be at top level of incident item OR in the parsed data
                  const source = incident.source || incidentData?.source || 
                                incidentData?.full_state?.incident?.source || 'chat';
                  const status = incident.status || incidentData?.status || 'unknown';
                  const service = incident.service || incidentData?.service || 
                                 incidentData?.full_state?.incident?.service || 'unknown';
                  const alertName = incident.alert_name || incidentData?.alert_name || 
                                   incidentData?.full_state?.incident?.alert_name || 
                                   incidentData?.alertName || 'N/A';
                  const timestamp = incident.timestamp || incident.created_at || 
                                   incidentData?.timestamp || 
                                   incidentData?.full_state?.incident?.timestamp || 'N/A';
                  
                  return (
                    <div key={incidentId} className="border rounded p-3 hover:bg-gray-50">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{incidentId}</span>
                            <span className={`text-xs px-2 py-1 rounded ${
                              source === 'cloudwatch_alarm' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
                            }`}>
                              {source === 'cloudwatch_alarm' ? '🔴 CloudWatch' : '💬 Chat'}
                            </span>
                            <span className={`text-xs px-2 py-1 rounded ${
                              status === 'open' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                            }`}>
                              {status}
                            </span>
                          </div>
                          <div className="mt-2 text-sm text-gray-600 space-y-1">
                            {service !== 'unknown' && <div>Service: <span className="font-medium">{service}</span></div>}
                            {alertName !== 'N/A' && <div>Alert: <span className="font-medium">{alertName}</span></div>}
                            {timestamp !== 'N/A' && (
                              <div>Created: <span className="font-medium">{new Date(timestamp).toLocaleString()}</span></div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="mt-4 p-4 bg-gray-100 rounded text-center text-gray-600">
              {isLoading ? 'Loading incidents...' : 'No incidents found. Try loading with different filters or trigger a test alarm.'}
            </div>
          )}
        </div>
      )}

      {/* Lambda Logs Tab */}
      {activeTab === 'lambda-logs' && (
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold mb-4">View Lambda Function Logs</h3>
            <p className="text-sm text-gray-600 mb-4">
              Check Lambda function logs to see alarm trigger events and incident creation logs.
              You can also use the chat interface to query CloudWatch logs.
            </p>
            
            <div className="bg-blue-50 border border-blue-200 rounded p-4 mb-4">
              <h4 className="font-semibold text-blue-900 mb-2">📋 How to Check Logs:</h4>
              <div className="text-sm text-blue-800 space-y-2">
                <div>
                  <strong>Option 1: Use Chat Interface (Recommended!)</strong>
                  <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                    <li>Go back to chat and ask: <code className="bg-blue-100 px-1 rounded">"Show me recent logs from /aws/lambda/sre-poc-incident-handler"</code></li>
                    <li>Or: <code className="bg-blue-100 px-1 rounded">"What errors occurred in the incident handler Lambda?"</code></li>
                    <li>Or: <code className="bg-blue-100 px-1 rounded">"Show me logs containing 'alarm' or 'trigger' from the last hour"</code></li>
                  </ul>
                </div>
                <div className="mt-3">
                  <strong>Option 2: AWS Console</strong>
                  <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                    <li>Go to CloudWatch → Log Groups</li>
                    <li>Find: <code className="bg-blue-100 px-1 rounded">/aws/lambda/sre-poc-incident-handler</code></li>
                    <li>Search for: <code className="bg-blue-100 px-1 rounded">"trigger"</code> or <code className="bg-blue-100 px-1 rounded">"alarm"</code></li>
                  </ul>
                </div>
                <div className="mt-3">
                  <strong>Option 3: AWS CLI</strong>
                  <div className="bg-gray-100 p-2 rounded mt-1 font-mono text-xs">
                    aws logs tail /aws/lambda/sre-poc-incident-handler --since 1h --filter-pattern "alarm"
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
              <h4 className="font-semibold text-yellow-900 mb-2">💡 Pro Tip:</h4>
              <p className="text-sm text-yellow-800">
                The chat interface is perfect for querying CloudWatch logs! Try asking:
                <br />
                <code className="bg-yellow-100 px-2 py-1 rounded mt-2 inline-block">
                  "Show me logs from sre-poc-incident-handler containing 'CloudWatch alarm' from the last 30 minutes"
                </code>
              </p>
            </div>

            <div className="mt-4">
              <h4 className="font-semibold mb-2">What to Look For in Logs:</h4>
              <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                <li><code className="bg-gray-100 px-1 rounded">"Generated test CloudWatch alarm event"</code> - Alarm trigger started</li>
                <li><code className="bg-gray-100 px-1 rounded">"Invoking incident handler"</code> - Incident handler called</li>
                <li><code className="bg-gray-100 px-1 rounded">"Incident created with ID"</code> - Incident successfully created</li>
                <li><code className="bg-gray-100 px-1 rounded">"Saving incident"</code> - Incident saved to DynamoDB</li>
                <li><code className="bg-gray-100 px-1 rounded">"source: cloudwatch_alarm"</code> - Source field set correctly</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
