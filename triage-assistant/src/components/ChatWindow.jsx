/**
 * ChatWindow Component
 * Main chat interface that combines all components
 */

import { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import InputBox from './InputBox';
import SuggestedQuestions from './SuggestedQuestions';
import { askQuestion, fetchLogGroups, requestDiagnosis, createIncident, manageSampleLogs } from '../services/api';

export default function ChatWindow({ isFullScreen = false, onToggleFullScreen }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      text: "Hi! I'm your Triage Assistant. I can help you analyze CloudWatch logs and identify issues in your services.\n\nAsk me questions like:\n- \"What errors occurred in payment-service?\"\n- \"Show me policy-service errors with policy_number\"\n- \"What rating calculations failed in rating-service?\"\n\nCross-Service Tracing:\n- \"Trace CORR-ABBFE258-2314-494A-B9BB-ADB33142404F across services\"\n- \"Follow request CORR-... through the system\"\n- \"Show me the request flow for correlation_id ...\"\n\nThe trace feature will search across all services to show you the complete request flow!",
      isUser: false,
      timestamp: new Date().toISOString(),
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [useMCP, setUseMCP] = useState(true); // Default to ON (true), user can toggle to OFF (false)
  const [searchMode, setSearchMode] = useState('quick'); // 'quick' = real-time, 'deep' = Logs Insights
  const [selectedService, setSelectedService] = useState(''); // Empty = auto-detect from question
  const [timeRange, setTimeRange] = useState('24h'); // Default 24 hours
  const [diagnosingMessageId, setDiagnosingMessageId] = useState(null); // Track which message is being diagnosed
  const [creatingIncidentMessageId, setCreatingIncidentMessageId] = useState(null); // Track which message is creating incident
  const [isManagingLogs, setIsManagingLogs] = useState(false); // Track log management operations
  const [showIncidentDialog, setShowIncidentDialog] = useState(false); // Show incident creation confirmation dialog
  const [pendingIncidentMessage, setPendingIncidentMessage] = useState(null); // Store message while waiting for confirmation
  const [showPasswordDialog, setShowPasswordDialog] = useState(false); // Show password input dialog
  const [passwordInput, setPasswordInput] = useState(''); // Password input value
  const [passwordError, setPasswordError] = useState(''); // Password validation error
  const [pendingOperation, setPendingOperation] = useState(null); // Store operation while waiting for password
  const passwordInputRef = useRef(null); // Ref for password input field
  const messagesEndRef = useRef(null);
  
  // Hardcoded password for log management (matches backend)
  const LOG_MANAGEMENT_PASSWORD = '13579';
  
  // Log groups state
  const [logGroups, setLogGroups] = useState([]);
  const [isLoadingLogGroups, setIsLoadingLogGroups] = useState(false);
  const [logGroupSearch, setLogGroupSearch] = useState('');
  const [logGroupsCache, setLogGroupsCache] = useState(null);
  const [logGroupsCacheTime, setLogGroupsCacheTime] = useState(0);
  const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

  // Available services for dropdown (fallback if log groups not loaded)
  const defaultServices = [
    { value: '', label: 'Auto-detect' },
    { value: 'payment-service', label: 'Payment Service' },
    { value: 'order-service', label: 'Order Service' },
    { value: 'api-gateway', label: 'API Gateway' },
    { value: 'user-service', label: 'User Service' },
    { value: 'inventory-service', label: 'Inventory Service' },
    { value: 'policy-service', label: 'Policy Service' },
    { value: 'rating-service', label: 'Rating Service' },
    { value: 'notification-service', label: 'Notification Service' },
    { value: 'sre-poc-incident-handler', label: 'Incident Handler (Lambda)' },
  ];

  // Time range options
  const timeRanges = [
    { value: '15m', label: '15 min' },
    { value: '1h', label: '1 hour' },
    { value: '2h', label: '2 hours' },
    { value: '6h', label: '6 hours' },
    { value: '24h', label: '24 hours' },
    { value: '48h', label: '48 hours' },
    { value: '7d', label: '7 days' },
  ];

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch log groups on mount (CloudWatch is always selected for now)
  useEffect(() => {
    const loadLogGroups = async () => {
      // Check cache
      const now = Date.now();
      if (logGroupsCache && (now - logGroupsCacheTime) < CACHE_DURATION) {
        setLogGroups(logGroupsCache);
        return;
      }

      setIsLoadingLogGroups(true);
      try {
        console.log('Fetching log groups...');
        const response = await fetchLogGroups('/aws/', 50);
        console.log('Log groups response:', response);
        
        const groups = response.logGroups || [];
        console.log(`Found ${groups.length} log groups`);
        
        // Add "Auto-detect" option at the beginning
        const groupsWithAuto = [
          { value: '', label: 'Auto-detect', fullName: '', category: 'Default' },
          ...groups
        ];
        
        console.log('Setting log groups:', groupsWithAuto.length);
        setLogGroups(groupsWithAuto);
        setLogGroupsCache(groupsWithAuto);
        setLogGroupsCacheTime(now);
      } catch (error) {
        console.error('Failed to fetch log groups:', error);
        console.error('Error details:', error.message, error.stack);
        // Fallback to default services on error
        setLogGroups(defaultServices);
      } finally {
        setIsLoadingLogGroups(false);
      }
    };

    loadLogGroups();
  }, []); // Run once on mount

  const handleDiagnose = async (message) => {
    setDiagnosingMessageId(message.id);
    try {
      // Build log_data from message
      const logData = {
        log_entries: message.logEntries || [],
        insights: message.insights || [],
        total_results: message.totalResults || 0,
        pattern_data: message.patternData || null,
        correlation_data: message.correlationData || null,
        recommendations: message.recommendations || [],
      };

      // Extract service name from message or use selected service
      const serviceName = selectedService || 'unknown-service';
      
      // Call diagnosis API
      const diagnosisResult = await requestDiagnosis(logData, serviceName);

      // Update the message with diagnosis data
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === message.id
            ? { ...msg, diagnosis: diagnosisResult }
            : msg
        )
      );
    } catch (error) {
      console.error('Diagnosis failed:', error);
      // You could add an error message here if needed
    } finally {
      setDiagnosingMessageId(null);
    }
  };

  const handleCreateIncident = (message) => {
    // Store the message and show confirmation dialog
    setPendingIncidentMessage(message);
    setShowIncidentDialog(true);
  };

  const handleIncidentConfirm = async () => {
    if (!pendingIncidentMessage) return;

    const message = pendingIncidentMessage;
    setCreatingIncidentMessageId(message.id);
    setShowIncidentDialog(false);

    try {
      // Build log_data from message
      const logData = {
        log_entries: message.logEntries || [],
        insights: message.insights || [],
        total_results: message.totalResults || 0,
        pattern_data: message.patternData || null,
        correlation_data: message.correlationData || null,
        recommendations: message.recommendations || [],
      };

      // Extract service name from message or use selected service
      // Priority: 1) selectedService, 2) correlation_data.services_found, 3) log entries, 4) default
      let serviceName = selectedService;
      if (!serviceName || serviceName === '') {
        // Try to extract from correlation data
        if (message.correlationData?.services_found?.length > 0) {
          serviceName = message.correlationData.services_found[0];
        } else if (message.logEntries?.length > 0) {
          // Extract from first log entry
          const firstEntry = message.logEntries[0];
          if (firstEntry.service) {
            serviceName = firstEntry.service;
          } else if (firstEntry.log_group) {
            // Extract service name from log group path (e.g., /aws/lambda/payment-service -> payment-service)
            const parts = firstEntry.log_group.split('/');
            serviceName = parts[parts.length - 1] || 'unknown-service';
          }
        }
      }
      // Fallback to unknown-service if still empty
      if (!serviceName || serviceName === '') {
        serviceName = 'unknown-service';
      }
      
      // Extract log group from message
      // Priority: 1) message.logGroup, 2) correlation_data.log_group, 3) first log entry, 4) construct from service
      let logGroup = message.logGroup;
      if (!logGroup) {
        if (message.correlationData?.log_group) {
          logGroup = message.correlationData.log_group;
        } else if (message.logEntries?.length > 0 && message.logEntries[0].log_group) {
          logGroup = message.logEntries[0].log_group;
        } else if (serviceName && serviceName !== 'unknown-service') {
          logGroup = `/aws/lambda/${serviceName}`;
        }
      }
      
      // Extract question from the user message that triggered this response
      const userMessage = messages.find(m => m.id < message.id && m.isUser);
      const question = userMessage?.text || 'Incident from chat analysis';

      // Call createIncident API
      // API signature: createIncident(logData, service, question, logGroup = null, alertName = null, context = null)
      const result = await createIncident(
        logData,
        serviceName,
        question,
        logGroup, // Pass extracted log group
        null, // alertName
        null  // context
      );

      // Debug: Log the full result to see what we're getting
      console.log('🔍 Full incident result:', JSON.stringify(result, null, 2));
      
      // Extract execution results from full_state
      const fullState = result.full_state || {};
      const executionResults = fullState.execution_results || result.execution_results;
      const remediation = fullState.remediation || {};
      const executionType = remediation.execution_type || result.execution_type;
      
      // Debug: Log extracted values
      console.log('🔍 Full state:', fullState);
      console.log('🔍 Execution results:', executionResults);
      console.log('🔍 Execution type:', executionType);

      // Update the message with incident creation result
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === message.id
            ? { 
                ...msg, 
                incident: {
                  incident_id: result.incident_id,
                  root_cause: result.root_cause,
                  confidence: result.confidence,
                  recommended_action: result.recommended_action,
                  executive_summary: result.executive_summary,
                  execution_results: executionResults,
                  execution_type: executionType,
                }
              }
            : msg
        )
      );

      // Build execution status message
      let executionStatus = '';
      const execResults = result.full_state?.execution_results || result.execution_results;
      const execType = result.full_state?.remediation?.execution_type || result.execution_type;
      
      if (execResults) {
        if (execResults.auto_execute) {
          const status = execResults.auto_execute.status;
          executionStatus = `\n\n⚡ EXECUTION: ${status === 'success' ? '✅ Auto-executed' : status === 'failed' ? '❌ Auto-execution failed' : '⏸️ Skipped'}`;
          if (execResults.auto_execute.action) {
            executionStatus += ` (${execResults.auto_execute.action})`;
          }
        } else if (execResults.github_issue) {
          const status = execResults.github_issue.status;
          if (status === 'success') {
            executionStatus = `\n\n🔗 EXECUTION: ✅ GitHub issue created: ${execResults.github_issue.issue_url || 'N/A'}`;
          } else {
            executionStatus = `\n\n🔗 EXECUTION: ❌ GitHub issue creation failed: ${execResults.github_issue.error || 'Unknown error'}`;
          }
        } else if (execResults.escalation) {
          executionStatus = `\n\n👤 EXECUTION: ⚠️ Escalated to human: ${execResults.escalation.reason || 'Complex remediation required'}`;
        }
      } else if (execType) {
        executionStatus = `\n\n⚡ EXECUTION TYPE: ${execType}`;
      }

      // Add a success message
      const successMessage = {
        id: `incident-created-${Date.now()}`,
        text: `✅ Incident created successfully!\n\nIncident ID: ${result.incident_id}\nRoot Cause: ${result.root_cause}\nConfidence: ${result.confidence}%${executionStatus}\n\n${result.executive_summary || ''}`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, successMessage]);
    } catch (error) {
      console.error('Incident creation failed:', error);
      const errorMessage = {
        id: `incident-error-${Date.now()}`,
        text: `❌ Failed to create incident: ${error.message}`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setCreatingIncidentMessageId(null);
      setPendingIncidentMessage(null);
    }
  };

  const handleIncidentCancel = () => {
    setShowIncidentDialog(false);
    setPendingIncidentMessage(null);
  };

  const handleManageLogs = async (operation) => {
    // Show password dialog instead of window.prompt
    setPendingOperation(operation);
    setPasswordInput('');
    setPasswordError('');
    setShowPasswordDialog(true);
  };

  const handlePasswordSubmit = async () => {
    if (!passwordInput.trim()) {
      setPasswordError('Password cannot be empty');
      return;
    }

    // Validate password on frontend
    if (passwordInput !== LOG_MANAGEMENT_PASSWORD) {
      setPasswordError('Incorrect password. Please try again.');
      setPasswordInput(''); // Clear password field
      passwordInputRef.current?.focus(); // Refocus input
      return;
    }

    // Password is correct - clear error and proceed
    setPasswordError('');
    const password = passwordInput;
    const operation = pendingOperation;
    
    // Close password dialog
    setShowPasswordDialog(false);
    setPasswordInput('');

    // Show confirmation dialog
    if (!window.confirm(`This will ${operation === 'clean' ? 'delete all sample log groups' : operation === 'regenerate' ? 'generate new sample logs' : 'delete existing logs and generate new ones'}. Continue?`)) {
      setPendingOperation(null);
      return;
    }

    setIsManagingLogs(true);
    try {
      const result = await manageSampleLogs(operation, password);
      
      // Add a system message showing the result
      const systemMessage = {
        id: `log-mgmt-${Date.now()}`,
        text: `✅ Log management completed: ${result.message}\n\n${result.log_groups ? `Affected log groups: ${result.log_groups.length}` : ''}${result.total_deleted ? `\nDeleted: ${result.total_deleted}` : ''}${result.total_created ? `\nCreated: ${result.total_created}` : ''}`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, systemMessage]);
    } catch (error) {
      console.error('Log management failed:', error);
      let errorText = `❌ Log management failed: ${error.message}`;
      if (error.status === 401 || error.message.includes('Unauthorized') || error.message.includes('Invalid password')) {
        errorText = '❌ Authentication failed: The password you entered is incorrect. Please try again.';
      }
      const errorMessage = {
        id: `log-mgmt-error-${Date.now()}`,
        text: errorText,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsManagingLogs(false);
      setPendingOperation(null);
    }
  };

  const handlePasswordCancel = () => {
    setShowPasswordDialog(false);
    setPasswordInput('');
    setPasswordError('');
    setPendingOperation(null);
  };

  const handlePasswordInputChange = (e) => {
    setPasswordInput(e.target.value);
    // Clear error when user starts typing
    if (passwordError) {
      setPasswordError('');
    }
  };

  // Focus password input when dialog opens
  useEffect(() => {
    if (showPasswordDialog && passwordInputRef.current) {
      passwordInputRef.current.focus();
    }
  }, [showPasswordDialog]);

  const handleSendMessage = async (question) => {
    // Add user message
    const userMessage = {
      id: `user-${Date.now()}`,
      text: question,
      isUser: true,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setSuggestions([]);

    try {
      // Call API with all options
      const response = await askQuestion(
        question,
        selectedService || null,  // null = auto-detect
        timeRange,
        useMCP,
        searchMode  // 'quick' or 'deep'
      );

      // Add assistant message
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        text: response.answer || 'I could not process your request. Please try again.',
        isUser: false,
        timestamp: response.timestamp || new Date().toISOString(),
        insights: response.insights || [],
        recommendations: response.recommendations || [],
        logEntries: response.log_entries || [],
        totalResults: response.total_results || 0,
        searchMode: response.search_mode || searchMode,  // Store search mode used for this query
        cloudwatchUrl: response.cloudwatch_url || null,  // CloudWatch Logs Console URL
        logGroup: response.log_group || null,  // Store log group for incident creation
        // Cross-service correlation data
        correlationData: response.correlation_data || null,
        requestFlow: response.request_flow || null,
        servicesFound: response.services_found || null,
        patternData: response.pattern_data || null,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Update suggestions
      if (response.follow_up_questions && response.follow_up_questions.length > 0) {
        setSuggestions(response.follow_up_questions);
      }
    } catch (error) {
      console.error('Error:', error);
      const errorMessage = {
        id: `error-${Date.now()}`,
        text: `❌ Sorry, I encountered an error: ${error.message}\n\nPlease try again or rephrase your question.`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
              <span className="text-xl">🔍</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold">Triage Hub</h1>
              <p className="text-sm text-blue-100">AI-powered log analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* MCP Toggle - Always visible, default ON */}
            <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5">
              <span className="text-xs text-blue-100">MCP:</span>
              <button
                onClick={() => setUseMCP(true)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  useMCP === true
                    ? 'bg-white text-blue-700 font-semibold'
                    : 'bg-white/20 text-white hover:bg-white/30'
                }`}
                title="Use MCP server for log queries"
              >
                ON
              </button>
              <button
                onClick={() => setUseMCP(false)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  useMCP === false
                    ? 'bg-white text-blue-700 font-semibold'
                    : 'bg-white/20 text-white hover:bg-white/30'
                }`}
                title="Use Direct API for log queries"
              >
                OFF
              </button>
            </div>
            <button
              onClick={onToggleFullScreen}
              className="bg-white/20 hover:bg-white/30 rounded-lg p-2 transition-colors"
              title={isFullScreen ? 'Exit full screen' : 'Enter full screen'}
            >
              {isFullScreen ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Log Source Selector */}
      <div className="bg-gray-50 border-b border-gray-200 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500 font-medium">Log Source:</span>
          <div className="flex gap-2">
            {/* CloudWatch - Enabled */}
            <button
              disabled={false}
              className="text-xs px-3 py-1.5 rounded-md bg-blue-600 text-white font-medium cursor-default"
              title="CloudWatch Logs (Active)"
            >
              CloudWatch
            </button>
            {/* Elasticsearch - Disabled */}
            <button
              disabled={true}
              className="text-xs px-3 py-1.5 rounded-md bg-gray-200 text-gray-400 cursor-not-allowed opacity-60"
              title="Elasticsearch (Coming soon)"
            >
              Elasticsearch
            </button>
            {/* Datadog - Disabled */}
            <button
              disabled={true}
              className="text-xs px-3 py-1.5 rounded-md bg-gray-200 text-gray-400 cursor-not-allowed opacity-60"
              title="Datadog (Coming soon)"
            >
              Datadog
            </button>
            {/* Dynatrace - Disabled */}
            <button
              disabled={true}
              className="text-xs px-3 py-1.5 rounded-md bg-gray-200 text-gray-400 cursor-not-allowed opacity-60"
              title="Dynatrace (Coming soon)"
            >
              Dynatrace
            </button>
          </div>
          <span className="text-xs text-gray-400 italic ml-auto">Multi-source support coming soon</span>
        </div>
      </div>

      {/* Search Controls */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="flex flex-wrap items-center gap-4">
          {/* Quick/Deep Search Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Search:</span>
            <div className="flex bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => setSearchMode('quick')}
                className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
                  searchMode === 'quick'
                    ? 'bg-white text-blue-700 font-semibold shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
                title="Real-time search using filter_log_events (no indexing delay)"
              >
                Quick
              </button>
              <button
                onClick={() => setSearchMode('deep')}
                className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
                  searchMode === 'deep'
                    ? 'bg-white text-blue-700 font-semibold shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
                title="CloudWatch Logs Insights (may have 5-15 min indexing delay for new logs)"
              >
                Deep
              </button>
            </div>
          </div>

          {/* Service/Log Group Dropdown */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Service:</span>
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              disabled={isLoadingLogGroups}
              className="text-xs bg-gray-100 border-0 rounded-lg px-2 py-1.5 text-gray-700 focus:ring-2 focus:ring-blue-500 disabled:opacity-50 min-w-[180px]"
              title={selectedService || 'Auto-detect'}
            >
              {isLoadingLogGroups ? (
                <option>Loading log groups...</option>
              ) : logGroups.length > 0 ? (
                logGroups.map((group) => (
                  <option key={group.value || group.fullName} value={group.fullName || group.value} title={group.fullName}>
                    {group.label}
                  </option>
                ))
              ) : (
                defaultServices.map((service) => (
                  <option key={service.value} value={service.value}>
                    {service.label}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Time Range Dropdown */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Time:</span>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="text-xs bg-gray-100 border-0 rounded-lg px-2 py-1.5 text-gray-700 focus:ring-2 focus:ring-blue-500"
            >
              {timeRanges.map((range) => (
                <option key={range.value} value={range.value}>
                  {range.label}
                </option>
              ))}
            </select>
          </div>

          {/* Log Management Button */}
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => handleManageLogs('clean_and_regenerate')}
              disabled={isManagingLogs}
              className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              title="Clean existing sample logs and regenerate new ones with enhanced patterns"
            >
              {isManagingLogs ? (
                <>
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
                  <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Generate Logs
                </>
              )}
            </button>
          </div>
        </div>

        {/* Always Visible Disclaimer */}
        <div className="mt-2 text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
          {searchMode === 'quick' ? (
            <span>
              <strong className="text-blue-600">Quick Search:</strong> Real-time results with no delay. Searches multiple log groups in parallel. Best for recent logs and immediate troubleshooting.
            </span>
          ) : (
            <span>
              <strong className="text-orange-600">Deep Search:</strong> Uses CloudWatch Logs Insights for complex queries and analytics. Note: New logs may take 5-15 minutes to be indexed.
            </span>
          )}
        </div>
      </div>

      {/* Main content area with sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Messages and Input area (main content) */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                isUser={message.isUser}
                onDiagnose={handleDiagnose}
                isDiagnosing={diagnosingMessageId === message.id}
                onCreateIncident={handleCreateIncident}
                isCreatingIncident={creatingIncidentMessageId === message.id}
              />
            ))}

            {/* Loading indicator */}
            {isLoading && (
              <div className="flex justify-start mb-4">
                <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex items-center gap-2 text-gray-500">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span className="text-sm">Analyzing logs...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input box */}
          <InputBox onSend={handleSendMessage} disabled={isLoading} />
        </div>

        {/* Right sidebar - Suggested questions */}
        <div className="w-96 border-l border-gray-200 bg-white flex flex-col">
          <SuggestedQuestions
            suggestions={suggestions}
            onQuestionClick={handleSendMessage}
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Password Dialog Modal */}
      {showPasswordDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-96 max-w-md">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Enter Password
            </h3>
            
            {/* Warning Message */}
            <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-start gap-2">
                <svg className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-yellow-800 mb-1">
                    Caution: This operation will modify AWS CloudWatch Logs
                  </p>
                  <p className="text-xs text-yellow-700">
                    This will delete existing sample log groups and regenerate new logs in AWS CloudWatch. Please proceed with caution.
                  </p>
                </div>
              </div>
            </div>

            <p className="text-sm text-gray-600 mb-2">
              Password required to proceed:
            </p>
            <input
              ref={passwordInputRef}
              type="password"
              value={passwordInput}
              onChange={handlePasswordInputChange}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handlePasswordSubmit();
                } else if (e.key === 'Escape') {
                  handlePasswordCancel();
                }
              }}
              placeholder="Enter password"
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 ${
                passwordError ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}
              autoComplete="off"
            />
            {passwordError && (
              <p className="mt-2 text-sm text-red-600">{passwordError}</p>
            )}
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={handlePasswordCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handlePasswordSubmit}
                disabled={!passwordInput.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Incident Creation Confirmation Dialog */}
      {showIncidentDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-96 max-w-md">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Create Incident & Run Full Investigation
            </h3>
            
            {/* Information Message */}
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-start gap-2">
                <svg className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-blue-800 mb-1">
                    This will create a formal incident record
                  </p>
                  <p className="text-xs text-blue-700">
                    This triggers a complete AgentCore investigation workflow (Triage → Analysis → Diagnosis → Remediation). The incident will be saved to DynamoDB and may send notifications. This process may take several minutes.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={handleIncidentCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleIncidentConfirm}
                disabled={creatingIncidentMessageId !== null}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {creatingIncidentMessageId !== null ? 'Creating...' : 'Create Incident'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
