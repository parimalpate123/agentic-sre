/**
 * ChatWindow Component
 * Main chat interface that combines all components
 */

import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import MessageBubble from './MessageBubble';
import InputBox from './InputBox';
import SuggestedQuestions from './SuggestedQuestions';
import IncidentApprovalDialog from './IncidentApprovalDialog';
import ChatSessionDialog from './ChatSessionDialog';
import CloudWatchIncidentsDialog from './CloudWatchIncidentsDialog';
import { askQuestion, fetchLogGroups, requestDiagnosis, createIncident, manageSampleLogs, createGitHubIssueAfterApproval, getRemediationStatus, saveChatSession, reanalyzeIncident } from '../services/api';

const ChatWindow = forwardRef(function ChatWindow({ isFullScreen = false, onToggleFullScreen, onShowUtilityPanel }, ref) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [useMCP, setUseMCP] = useState(true); // Default to ON (true), user can toggle to OFF (false)
  const [searchMode, setSearchMode] = useState('quick'); // 'quick' = real-time, 'deep' = Logs Insights
  const [selectedService, setSelectedService] = useState(''); // Empty = auto-detect from question
  const [timeRange, setTimeRange] = useState('24h'); // Default 24 hours
  const [diagnosingMessageId, setDiagnosingMessageId] = useState(null); // Track which message is being diagnosed
  const [creatingIncidentMessageId, setCreatingIncidentMessageId] = useState(null); // Track which message is creating incident
  const [reanalyzingIncidentId, setReanalyzingIncidentId] = useState(null); // Track which incident is being re-analyzed
  const [isManagingLogs, setIsManagingLogs] = useState(false); // Track log management operations
  const [showIncidentDialog, setShowIncidentDialog] = useState(false); // Show approval dialog for code fix (after investigation)
  const [pendingIncidentData, setPendingIncidentData] = useState(null); // Store incident data while waiting for approval
  const [remediationStatuses, setRemediationStatuses] = useState({}); // Store remediation status by incident_id
  const [pollingStatus, setPollingStatus] = useState({}); // Track polling status per incident: { incidentId: 'active' | 'paused' | null }
  const pollingIntervalsRef = useRef({}); // Store polling intervals (useRef to persist across renders)
  const pollingStartTimeRef = useRef({}); // Track polling start time for timeout
  const lastStatusHashRef = useRef({}); // Store hash of last status to detect when it stops changing
  const stableStatusCountRef = useRef({}); // Count how many times status hasn't changed
  const pausedPollingRef = useRef({}); // Track which incidents have paused polling
  const [showPasswordDialog, setShowPasswordDialog] = useState(false); // Show password input dialog
  const [passwordInput, setPasswordInput] = useState(''); // Password input value
  const [passwordError, setPasswordError] = useState(''); // Password validation error
  const [pendingOperation, setPendingOperation] = useState(null); // Store operation while waiting for password
  const passwordInputRef = useRef(null); // Ref for password input field
  const messagesEndRef = useRef(null);
  const [showSessionDialog, setShowSessionDialog] = useState(false); // Show chat session dialog
  const [showCloudWatchIncidentsDialog, setShowCloudWatchIncidentsDialog] = useState(false); // Show CloudWatch incidents dialog
  const [defaultIncidentSource, setDefaultIncidentSource] = useState('cloudwatch_alarm'); // Default source for Incidents dialog: cloudwatch_alarm | servicenow | jira
  const currentSessionIdRef = useRef(null); // Track current session ID for auto-save
  const lastAutoSaveRef = useRef(null); // Track last auto-save time
  
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

  // CloudWatch incidents are now loaded on-demand via the "CW Incidents" dialog
  // No auto-loading or external reload function needed

  // Note: CloudWatch incidents are loaded on-demand via the "CW Incidents" dialog
  // They are no longer auto-loaded to avoid cluttering the chat

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

      // For CloudWatch incidents, add incident analysis as context
      if (message.incident && !logData.insights.length) {
        const incident = message.incident;
        if (incident.alert_name) logData.insights.push(`Alert: ${incident.alert_name}`);
        if (incident.alert_description) logData.insights.push(`Description: ${incident.alert_description}`);
        if (incident.root_cause) logData.insights.push(`Initial Analysis: ${incident.root_cause}`);
      }

      // Extract service name from message or use selected service
      const serviceName = selectedService || message.incident?.service || 'unknown-service';
      
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

  const handleCreateIncident = async (message) => {
    // Create incident immediately (no approval needed at this stage)
    setCreatingIncidentMessageId(message.id);

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

      // For CloudWatch incidents, add incident analysis as context
      if (message.incident && !logData.insights.length) {
        const incident = message.incident;
        if (incident.alert_name) logData.insights.push(`Alert: ${incident.alert_name}`);
        if (incident.alert_description) logData.insights.push(`Description: ${incident.alert_description}`);
        if (incident.root_cause) logData.insights.push(`Initial Analysis: ${incident.root_cause}`);
      }

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
      // Fallback to incident service if available (for CW incidents)
      if (!serviceName || serviceName === '') {
        serviceName = message.incident?.service || 'unknown-service';
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
      const question = userMessage?.text || message.incident?.alert_name || 'Incident from chat analysis';

      // Extract alert name from incident if available (for CW incidents)
      const alertName = message.incident?.alert_name || null;

      // Call createIncident API
      // API signature: createIncident(logData, service, question, logGroup = null, alertName = null, context = null)
      const result = await createIncident(
        logData,
        serviceName,
        question,
        logGroup, // Pass extracted log group
        alertName, // Pass alert name from CW incident
        null  // context
      );

      // Debug: Log the full result to see what we're getting
      console.log('🔍 Full incident result:', JSON.stringify(result, null, 2));
      
      // Extract execution results from full_state
      const fullState = result.full_state || {};
      const executionResults = fullState.execution_results || result.execution_results;
      const remediation = fullState.remediation || {};
      const incident = fullState.incident || {};
      
      // Get service name from incident result (most accurate)
      // Priority: 1) incident.service, 2) remediation.execution_metadata.service, 3) original serviceName
      let actualServiceName = incident.service || 
                             remediation.execution_metadata?.service || 
                             serviceName;
      
      // Fallback to unknown-service if still empty
      if (!actualServiceName || actualServiceName === '') {
        actualServiceName = 'unknown-service';
      }
      
      // Get execution_type - handle both enum values and strings
      let executionType = remediation.execution_type || result.execution_type;
      // Convert enum to string if needed (e.g., "ExecutionType.CODE_FIX" -> "code_fix")
      if (executionType && typeof executionType === 'object' && executionType.value) {
        executionType = executionType.value.toLowerCase();
      } else if (executionType && typeof executionType === 'string') {
        // Already a string, but might be uppercase like "CODE_FIX"
        executionType = executionType.toLowerCase().replace('_', '_');
      }
      
      // Debug: Log extracted values
      console.log('🔍 Full state:', fullState);
      console.log('🔍 Execution results:', executionResults);
      console.log('🔍 Execution type (raw):', remediation.execution_type || result.execution_type);
      console.log('🔍 Execution type (normalized):', executionType);
      console.log('🔍 Service name (original):', serviceName);
      console.log('🔍 Service name (from incident):', actualServiceName);
      console.log('🔍 Incident:', incident);
      console.log('🔍 Remediation:', remediation);

      // Build execution status message first (needed for the text)
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
          } else if (status === 'pending_approval') {
            // Show that approval is needed, but don't show as error
            executionStatus = `\n\n🔗 EXECUTION: ⏳ Approval required to create GitHub issue`;
          } else {
            executionStatus = `\n\n🔗 EXECUTION: ❌ GitHub issue creation failed: ${execResults.github_issue.error || 'Unknown error'}`;
          }
        } else if (execResults.escalation) {
          executionStatus = `\n\n👤 EXECUTION: ⚠️ Escalated to human: ${execResults.escalation.reason || 'Complex remediation required'}`;
        }
      } else if (execType) {
        executionStatus = `\n\n⚡ EXECUTION TYPE: ${execType}`;
      }

      // Build the incident analysis text (this will appear BEFORE Execution Results)
      const incidentAnalysisText = `✅ Incident created successfully!\n\nIncident ID: ${result.incident_id}\nRoot Cause: ${result.root_cause}\nConfidence: ${result.confidence}%${executionStatus}\n\n${result.executive_summary || ''}`;
      
      // Include service name from full_state.incident.service for accurate service identification
      // Priority: full_state.incident.service > actualServiceName (from incident) > serviceName (from message) > 'unknown-service'
      const incidentService = fullState?.incident?.service || 
                             actualServiceName || 
                             serviceName || 
                             result.service ||  // Also check result.service
                             'unknown-service';
      
      console.log('🔍 Setting incident service name:', {
        incidentService,
        fullState_incident_service: fullState?.incident?.service,
        actualServiceName,
        serviceName,
        result_service: result.service,
        fullState_keys: fullState ? Object.keys(fullState) : 'no fullState'
      });
      
      // Build the incident object for the result message
      const incidentObj = {
        incident_id: result.incident_id,
        service: incidentService,  // Add service field for GitHub issue creation - CRITICAL!
        root_cause: result.root_cause,
        confidence: result.confidence,
        recommended_action: result.recommended_action,
        executive_summary: result.executive_summary,
        execution_results: executionResults,
        execution_type: executionType,
        full_state: fullState,  // Store full_state for GitHub issue creation
      };

      // For incidents loaded from Incidents dialog (CloudWatch, ServiceNow, Jira), add investigation
      // as a NEW message so the original incident detail stays visible
      const isLoadedIncident = message.incident?.source === 'cloudwatch_alarm' ||
        message.incident?.source === 'servicenow' ||
        message.incident?.source === 'jira';

      if (isLoadedIncident) {
        const investigationMessage = {
          id: `investigation-${Date.now()}`,
          text: incidentAnalysisText,
          isUser: false,
          timestamp: new Date().toISOString(),
          incident: { ...incidentObj, source: message.incident?.source || 'chat' },
        };
        setMessages((prev) => {
          // Mark original message to hide action buttons, then append new message
          const updated = prev.map((msg) =>
            msg.id === message.id
              ? { ...msg, investigationStarted: true }
              : msg
          );
          return [...updated, investigationMessage];
        });
      } else {
        // Normal flow (e.g. chat search result): update the existing message with incident creation result
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === message.id
              ? {
                  ...msg,
                  text: incidentAnalysisText,
                  incident: incidentObj,
                }
              : msg
          )
        );
      }
      
      // Check if approval is needed (code_fix and service known)
      // Show approval if:
      // 1. execution_type is code_fix (handle various formats)
      // 2. service is known (use actualServiceName from incident)
      // 3. github_issue doesn't exist OR status is 'pending_approval'
      const githubIssueStatus = executionResults?.github_issue?.status;
      
      // Normalize executionType for comparison (handle CODE_FIX, code_fix, ExecutionType.CODE_FIX, etc.)
      const normalizedExecutionType = executionType?.toString().toLowerCase().replace(/_/g, '_');
      const isCodeFix = normalizedExecutionType === 'code_fix' || 
                       normalizedExecutionType === 'codefix' ||
                       (executionType && executionType.toString().includes('CODE_FIX'));
      
      const needsApproval = isCodeFix && 
                           actualServiceName && 
                           actualServiceName !== 'unknown-service' &&
                           (!executionResults?.github_issue || githubIssueStatus === 'pending_approval');
      
      console.log('🔍 Approval check:', {
        executionType,
        normalizedExecutionType,
        isCodeFix,
        serviceName_original: serviceName,
        serviceName_actual: actualServiceName,
        githubIssueStatus,
        hasGithubIssue: !!executionResults?.github_issue,
        needsApproval
      });
      
      // Start polling for remediation status if GitHub issue was created
      if (executionResults?.github_issue?.status === 'success') {
        startRemediationPolling(result.incident_id);
      }

      // Don't show approval dialog automatically - let user review analysis first
      // User can click "Create GitHub Issue" button in the incident display to trigger approval
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
    }
  };

  // Build incident preview for approval dialog (after investigation)
  const getIncidentPreview = () => {
    if (!pendingIncidentData) return null;
    
    return {
      service: pendingIncidentData.service || 'Unknown',
      rootCause: pendingIncidentData.root_cause || 'Analysis pending',
      confidence: pendingIncidentData.confidence,
      repo: pendingIncidentData.service ? `poc-${pendingIncidentData.service}` : null
    };
  };

  // Handle approval for code fix (create GitHub issue after approval)
  const handleApprovalConfirm = async () => {
    if (!pendingIncidentData) {
      console.error('handleApprovalConfirm: pendingIncidentData is null');
      return;
    }

    setShowIncidentDialog(false);
    const incidentData = pendingIncidentData;
    setPendingIncidentData(null);

    console.log('🔍 handleApprovalConfirm: Creating GitHub issue with:', {
      incident_id: incidentData.incident_id,
      service: incidentData.service,
      full_data: incidentData
    });

    // Validate service before making API call
    if (!incidentData.service || incidentData.service === 'unknown-service') {
      console.error('❌ Cannot create GitHub issue: service is invalid', incidentData);
      alert(`Cannot create GitHub issue: Invalid service name "${incidentData.service}". Please try again.`);
      return;
    }

    try {
      // Get full_state from the message if available (for chat-created incidents)
      // Find the message that contains this incident
      const incidentMessage = messages.find(msg => 
        msg.incident?.incident_id === incidentData.incident_id
      );
      const fullState = incidentMessage?.incident?.full_state || null;
      
      console.log('🔍 Creating GitHub issue with full_state:', fullState ? 'provided' : 'not provided');
      
      // Call API to create GitHub issue after approval
      const result = await createGitHubIssueAfterApproval(
        incidentData.incident_id,
        incidentData.service,
        fullState
      );
      
      console.log('✅ GitHub issue created successfully:', result);

      // Update the message with issue creation result
      // Find message by incident_id (works for both chat and CloudWatch incidents)
      setMessages((prev) =>
        prev.map((msg) =>
          msg.incident?.incident_id === incidentData.incident_id
            ? {
                ...msg,
                incident: {
                  ...msg.incident,
                  execution_results: {
                    ...msg.incident.execution_results,
                    github_issue: result.github_issue
                  },
                  execution_type: 'code_fix' // Set execution type for CloudWatch incidents
                }
              }
            : msg
        )
      );

      // Start polling for remediation status
      if (result.github_issue?.status === 'success') {
        console.log(`🔄 Starting remediation polling for incident: ${incidentData.incident_id}`);
        startRemediationPolling(incidentData.incident_id);
      } else {
        console.warn(`⚠️ GitHub issue creation status: ${result.github_issue?.status}, not starting polling`);
      }

      // Show success message
      const successMessage = {
        id: `issue-created-${Date.now()}`,
        text: `✅ GitHub issue created successfully!\n\nIssue: ${result.github_issue?.issue_url || 'N/A'}\n\nRemediation workflow has started. The Issue Agent will analyze and create a PR automatically.`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, successMessage]);
      
      // Auto-save after GitHub issue creation
      setTimeout(() => {
        autoSaveSession();
      }, 1000);

    } catch (error) {
      console.error('GitHub issue creation failed:', error);
      const errorMessage = {
        id: `issue-error-${Date.now()}`,
        text: `❌ Failed to create GitHub issue: ${error.message}`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    }
  };

  const handleApprovalCancel = () => {
    setShowIncidentDialog(false);
    setPendingIncidentData(null);
    
    // Show message that issue creation was cancelled
    if (pendingIncidentData) {
      const cancelMessage = {
        id: `issue-cancelled-${Date.now()}`,
        text: `⚠️ GitHub issue creation cancelled. The incident has been created but no automated fix will be generated.`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, cancelMessage]);
    }
  };

  // Handle loading a saved chat session
  const handleLoadSession = (session) => {
    console.log('📥 Loading chat session:', session);
    
    // Restore messages
    if (session.messages && session.messages.length > 0) {
      setMessages(session.messages);
    }
    
    // Restore incident data
    if (session.incident_data) {
      setPendingIncidentData(session.incident_data);
    }
    
    // Restore remediation statuses
    if (session.remediation_statuses) {
      setRemediationStatuses(session.remediation_statuses);
      
      // Resume polling for any incidents that have remediation status
      Object.keys(session.remediation_statuses).forEach(incidentId => {
        const status = session.remediation_statuses[incidentId];
        // Resume polling if there's an issue (continue polling to track PR review status)
        if (status.issue && (!status.pr?.merge_status || status.pr?.merge_status !== 'merged')) {
          console.log(`🔄 Resuming polling for incident: ${incidentId}`);
          startRemediationPolling(incidentId);
        }
      });
    }
    
    // Set current session ID for auto-save
    currentSessionIdRef.current = session.session_id;
    
    console.log('✅ Chat session loaded successfully');
  };

  const handleLoadCloudWatchIncident = (incidentMessage) => {
    console.log('📥 Loading CloudWatch incident:', incidentMessage);
    console.log('🔍 Incident data check:', {
      source: incidentMessage.incident?.source,
      execution_type: incidentMessage.incident?.execution_type,
      execution_results: incidentMessage.incident?.execution_results,
      has_github_issue: !!incidentMessage.incident?.execution_results?.github_issue,
      github_issue_status: incidentMessage.incident?.execution_results?.github_issue?.status
    });
    
    // Add incident message to chat, avoiding duplicates
    setMessages(prev => {
      const existingIncidentIds = new Set(
        prev
          .filter(m => m.incident?.incident_id)
          .map(m => m.incident.incident_id)
      );
      
      // If incident already exists, don't add duplicate
      if (incidentMessage.incident?.incident_id && 
          existingIncidentIds.has(incidentMessage.incident.incident_id)) {
        console.log('⚠️ Incident already in chat, skipping duplicate');
        return prev;
      }
      
      // Append at end of chat
      return [...prev, incidentMessage];
    });
    
    // Start remediation polling only for CloudWatch incidents (not ServiceNow/Jira)
    if (incidentMessage.incident?.incident_id && incidentMessage.incident?.source === 'cloudwatch_alarm') {
      const incidentId = incidentMessage.incident.incident_id;
      console.log(`🔄 Starting remediation polling for incident: ${incidentId}`);
      startRemediationPolling(incidentId);
    }

    console.log('✅ Incident loaded successfully');
  };

  // Store refs for auto-save to access current values
  const messagesRef = useRef(messages);
  const pendingIncidentDataRef = useRef(pendingIncidentData);
  const remediationStatusesRef = useRef(remediationStatuses);
  
  // Update refs when values change
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  
  useEffect(() => {
    pendingIncidentDataRef.current = pendingIncidentData;
  }, [pendingIncidentData]);
  
  useEffect(() => {
    remediationStatusesRef.current = remediationStatuses;
  }, [remediationStatuses]);

  // Auto-save function
  const autoSaveSession = async () => {
    const currentMessages = messagesRef.current;
    const currentIncidentData = pendingIncidentDataRef.current;
    const currentRemediationStatuses = remediationStatusesRef.current;
    
    // Don't auto-save if no messages or too soon since last save
    if (currentMessages.length === 0) return; // No messages to save
    
    const now = Date.now();
    if (lastAutoSaveRef.current && (now - lastAutoSaveRef.current) < 5 * 60 * 1000) {
      return; // Don't save more than once every 5 minutes
    }
    
    try {
      // Extract incident data from messages
      const incidentData = currentIncidentData || 
        (currentMessages.find(m => m.incident)?.incident || null);
      
      // Generate session name from first user question or use default
      const firstUserMessage = currentMessages.find(m => m.isUser);
      const sessionName = firstUserMessage 
        ? `Auto-saved: ${firstUserMessage.text.substring(0, 50)}...`
        : `Chat Session ${new Date().toLocaleString()}`;
      
      const result = await saveChatSession(
        currentSessionIdRef.current, // Use existing session ID if available
        sessionName,
        currentMessages,
        incidentData,
        currentRemediationStatuses
      );
      
      currentSessionIdRef.current = result.session_id;
      lastAutoSaveRef.current = now;
      console.log('💾 Auto-saved chat session:', result.session_id);
    } catch (error) {
      console.error('Error auto-saving session:', error);
      // Don't show error to user - auto-save failures are silent
    }
  };

  // Auto-save on key events
  const remediationStatusesCount = Object.keys(remediationStatuses).length;
  const hasIncident = messages.some(m => m.incident);
  
  useEffect(() => {
    // Auto-save after incident creation or significant message changes
    if (hasIncident && messages.length > 1) {
      const timer = setTimeout(() => {
        autoSaveSession();
      }, 2000); // Debounce: wait 2 seconds after change
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, hasIncident]);

  useEffect(() => {
    // Auto-save after GitHub issue creation (remediation status added)
    if (remediationStatusesCount > 0) {
      const timer = setTimeout(() => {
        autoSaveSession();
      }, 2000); // Debounce: wait 2 seconds after change
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remediationStatusesCount]);

  // Handle "Create GitHub Issue" button click from incident display
  const handleCreateGitHubIssue = (incident) => {
    if (!incident) {
      console.error('handleCreateGitHubIssue: incident is null/undefined');
      return;
    }
    
    console.log('🔍 handleCreateGitHubIssue called with incident:', {
      incident_id: incident.incident_id,
      service: incident.service,
      execution_results: incident.execution_results,
      execution_metadata: incident.execution_metadata,
      full_incident: incident
    });
    
    // Extract service name from incident - prioritize incident.service field
    const service = incident.service || 
                   incident.execution_results?.github_issue?.service ||
                   incident.execution_metadata?.service ||
                   'unknown-service';
    
    console.log('🔍 Extracted service name:', service);
    
    // Validate service name
    if (!service || service === 'unknown-service') {
      console.error('❌ Cannot create GitHub issue: service name is unknown', {
        incident,
        extracted_service: service,
        incident_service: incident.service,
        execution_results_service: incident.execution_results?.github_issue?.service,
        execution_metadata_service: incident.execution_metadata?.service
      });
      alert('Cannot create GitHub issue: Service name is unknown. Please ensure the incident has a valid service name.');
      return;
    }
    
    // Show approval dialog
    setPendingIncidentData({
      incident_id: incident.incident_id,
      service: service,
      root_cause: incident.root_cause,
      confidence: incident.confidence,
      execution_type: incident.execution_type || 'code_fix',
      message_id: null // Not needed for this flow
    });
    setShowIncidentDialog(true);
  };

  // Handle "Re-analyze Incident" button click
  const handleReanalyzeIncident = async (incidentId) => {
    if (!incidentId) {
      console.error('handleReanalyzeIncident: incidentId is null/undefined');
      return;
    }

    console.log(`🔄 Re-analyzing incident: ${incidentId}`);
    setReanalyzingIncidentId(incidentId);

    try {
      // Call re-analyze API
      const result = await reanalyzeIncident(incidentId);
      
      console.log('✅ Re-analysis complete:', result);

      // Find the message containing this incident and update it with new results
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.incident?.incident_id === incidentId) {
            // Parse the updated investigation result
            const updatedResult = result.investigation_result || result;
            
            // Update the incident data with new results
            return {
              ...msg,
              incident: {
                ...msg.incident,
                root_cause: updatedResult.root_cause || msg.incident.root_cause,
                confidence: updatedResult.confidence || msg.incident.confidence,
                execution_type: updatedResult.full_state?.remediation?.execution_type || 
                               updatedResult.execution_type || 
                               msg.incident.execution_type,
                error_count: updatedResult.full_state?.analysis?.error_count || 
                            updatedResult.error_count || 
                            msg.incident.error_count,
                full_state: updatedResult.full_state || msg.incident.full_state,
                investigation_result: updatedResult,
                // Update text to reflect new analysis
                text: updatedResult.executive_summary || 
                      `Re-analyzed: ${updatedResult.root_cause}` || 
                      msg.text
              }
            };
          }
          return msg;
        })
      );

      // Show success message
      alert(`Incident ${incidentId} has been re-analyzed successfully. The results have been updated.`);
    } catch (error) {
      console.error('❌ Error re-analyzing incident:', error);
      alert(`Failed to re-analyze incident: ${error.message}`);
    } finally {
      setReanalyzingIncidentId(null);
    }
  };
  
  // Start polling for remediation status
  const startRemediationPolling = (incidentId) => {
    // Clear any existing interval for this incident
    if (pollingIntervalsRef.current[incidentId]) {
      clearInterval(pollingIntervalsRef.current[incidentId]);
      console.log(`🧹 Cleared existing polling interval for incident: ${incidentId}`);
    }
    
    // Record start time for timeout tracking
    pollingStartTimeRef.current[incidentId] = Date.now();
    
    console.log(`🔄 Starting remediation polling for incident: ${incidentId}`);
    
    // Initial fetch
    fetchRemediationStatus(incidentId);
    
    // Poll every 5 seconds
    const interval = setInterval(() => {
      console.log(`⏰ Polling interval triggered for incident: ${incidentId}`);
      fetchRemediationStatus(incidentId);
    }, 5000);
    
    // Store interval in ref
    pollingIntervalsRef.current[incidentId] = interval;
    
    // Update polling status state to trigger re-render
    setPollingStatus(prev => ({ ...prev, [incidentId]: 'active' }));
    
    console.log(`✅ Polling interval set for incident: ${incidentId}, interval ID: ${interval}`);
  };
  
  // Stop polling for an incident
  const stopRemediationPolling = (incidentId) => {
    if (pollingIntervalsRef.current[incidentId]) {
      clearInterval(pollingIntervalsRef.current[incidentId]);
      delete pollingIntervalsRef.current[incidentId];
      // Clean up tracking refs
      delete pollingStartTimeRef.current[incidentId];
      delete lastStatusHashRef.current[incidentId];
      delete stableStatusCountRef.current[incidentId];
      delete pausedPollingRef.current[incidentId];
      
      // Update polling status state to trigger re-render
      setPollingStatus(prev => {
        const updated = { ...prev };
        delete updated[incidentId];
        return updated;
      });
      
      console.log(`⏹️ Stopped remediation polling for incident: ${incidentId}`);
    }
  };
  
  // Pause polling (user-initiated)
  const pauseRemediationPolling = (incidentId) => {
    if (pollingIntervalsRef.current[incidentId]) {
      clearInterval(pollingIntervalsRef.current[incidentId]);
      delete pollingIntervalsRef.current[incidentId];
      pausedPollingRef.current[incidentId] = true;
      
      // Update polling status state to trigger re-render
      setPollingStatus(prev => ({ ...prev, [incidentId]: 'paused' }));
      
      console.log(`⏸️ Paused remediation polling for incident: ${incidentId}`);
    }
  };
  
  // Resume polling (user-initiated)
  const resumeRemediationPolling = (incidentId) => {
    if (pausedPollingRef.current[incidentId]) {
      delete pausedPollingRef.current[incidentId];
      startRemediationPolling(incidentId);
      console.log(`▶️ Resumed remediation polling for incident: ${incidentId}`);
    }
  };
  
  // Check if polling is active for an incident
  const isPollingActive = (incidentId) => {
    return pollingStatus[incidentId] === 'active' || !!pollingIntervalsRef.current[incidentId];
  };
  
  // Check if polling is paused for an incident
  const isPollingPaused = (incidentId) => {
    return pollingStatus[incidentId] === 'paused' || !!pausedPollingRef.current[incidentId];
  };
  
  // Manual check PR status (on-demand, doesn't start polling)
  const checkPRStatus = async (incidentId) => {
    try {
      console.log(`🔍 Manually checking PR status for incident: ${incidentId}`);
      const status = await getRemediationStatus(incidentId);
      if (status) {
        setRemediationStatuses(prev => ({
          ...prev,
          [incidentId]: status
        }));
        console.log(`✅ Updated PR status for incident ${incidentId}:`, {
          pr_number: status.pr?.number,
          review_status: status.pr?.review_status,
          merge_status: status.pr?.merge_status
        });
      }
    } catch (error) {
      console.error(`❌ Error checking PR status for incident ${incidentId}:`, error);
    }
  };
  
  const MAX_POLLING_DURATION = 30 * 60 * 1000; // 30 minutes max polling
  const STABLE_STATUS_THRESHOLD = 12; // Stop if status unchanged for 12 polls (60 seconds at 5s intervals)
  const ACTIVE_WAITING_STABLE_THRESHOLD = 24; // Longer threshold for active waiting states (2 minutes)

  // Fetch remediation status
  const fetchRemediationStatus = async (incidentId) => {
    // Skip if polling is paused for this incident
    if (pausedPollingRef.current[incidentId]) {
      console.log(`⏸️ Skipping fetch for incident ${incidentId} - polling is paused`);
      return;
    }
    
    try {
      console.log(`🔍 Fetching remediation status for incident: ${incidentId}`);
      const status = await getRemediationStatus(incidentId);
      console.log(`📥 Received remediation status for ${incidentId}:`, status);
      
      if (status) {
        // Create a hash of the status to detect changes
        // Include all timeline events to detect progress updates
        const timelineLength = status.timeline?.length || 0;
        const timelineEvents = status.timeline?.map(e => e.event).join(',') || '';
        
        const statusHash = JSON.stringify({
          pr_status: status.pr?.status,
          pr_merge_status: status.pr?.merge_status,
          pr_review_status: status.pr?.review_status,
          next_action: status.next_action,
          timeline_length: timelineLength,
          timeline_events: timelineEvents, // Include all events, not just latest
          issue_number: status.issue?.number,
          pr_number: status.pr?.number
        });
        
        // Check if status has changed
        const lastHash = lastStatusHashRef.current[incidentId];
        if (lastHash === statusHash) {
          // Status hasn't changed - increment stable count
          stableStatusCountRef.current[incidentId] = (stableStatusCountRef.current[incidentId] || 0) + 1;
          
          // Determine if we're in an "active waiting" state (Issue Agent is working)
          const isActiveWaiting = status.next_action?.includes('Issue Agent') || 
                                 status.next_action?.includes('Issue agent') ||
                                 status.next_action?.includes('analyzing') ||
                                 status.next_action?.includes('generating') ||
                                 status.next_action?.includes('creating PR') ||
                                 (status.timeline && status.timeline.some(e => 
                                   ['analysis_started', 'fix_generation_started', 'pr_creation_started'].includes(e.event)
                                 ));
          
          // Determine if we're in a "passive waiting" state (waiting for human/PR review)
          const isPassiveWaiting = status.next_action?.includes('PR Review Agent') ||
                                  status.next_action?.includes('human approval') ||
                                  status.next_action?.includes('merge PR') ||
                                  (status.pr?.status === 'open' && status.pr?.review_status);
          
          // Use different thresholds based on waiting state type
          const threshold = isActiveWaiting ? ACTIVE_WAITING_STABLE_THRESHOLD : STABLE_STATUS_THRESHOLD;
          
          // Only stop if status is stable for the threshold AND we're in a passive waiting state
          // Don't stop during active waiting (Issue Agent is working) - keep polling to show progress
          if (stableStatusCountRef.current[incidentId] >= threshold && isPassiveWaiting && !isActiveWaiting) {
            stopRemediationPolling(incidentId);
            console.log(`⏹️ Status stable for incident ${incidentId} (${threshold} polls), stopped polling. User can manually refresh if needed.`);
            return;
          }
        } else {
          // Status changed - reset stable count
          stableStatusCountRef.current[incidentId] = 0;
          lastStatusHashRef.current[incidentId] = statusHash;
        }
        
        // Update status - use functional update to ensure React detects the change
        setRemediationStatuses(prev => {
          const newStatus = { ...status };
          // Log PR info for debugging
          if (newStatus.pr?.number) {
            console.log(`✅ PR detected in status update for ${incidentId}:`, {
              pr_number: newStatus.pr.number,
              pr_url: newStatus.pr.url,
              pr_status: newStatus.pr.status,
              review_status: newStatus.pr.review_status,
              merge_status: newStatus.pr.merge_status
            });
          }
          // Log timeline changes for debugging
          const prevStatus = prev[incidentId];
          if (prevStatus && prevStatus.timeline?.length !== newStatus.timeline?.length) {
            console.log(`📊 Timeline updated for ${incidentId}:`, {
              previous_length: prevStatus.timeline?.length || 0,
              new_length: newStatus.timeline?.length || 0,
              new_events: newStatus.timeline?.map(e => e.event) || []
            });
          }
          return {
            ...prev,
            [incidentId]: newStatus
          };
        });
        
        // Stop polling conditions:
        // 1. PR review is complete (approved or changes_requested) - end of automated flow
        if (status.pr?.review_status && status.pr.review_status !== 'pending') {
          stopRemediationPolling(incidentId);
          console.log(`✅ PR review complete for incident ${incidentId} (status: ${status.pr.review_status}), stopped polling. User can manually check merge status if needed.`);
          return;
        }
        
        // 2. PR is merged (remediation complete)
        if (status.pr?.merge_status === 'merged' || status.pr?.status === 'merged') {
          stopRemediationPolling(incidentId);
          console.log(`✅ Remediation complete for incident ${incidentId}, stopped polling`);
          return;
        }
        
        // 3. PR is closed without merge
        if (status.pr?.status === 'closed' && status.pr?.merge_status !== 'merged') {
          stopRemediationPolling(incidentId);
          console.log(`⏹️ PR closed without merge for incident ${incidentId}, stopped polling`);
          return;
        }
        
        // 4. Check timeout (stop after 30 minutes of polling)
        const startTime = pollingStartTimeRef.current[incidentId] || Date.now();
        pollingStartTimeRef.current[incidentId] = startTime;
        const elapsed = Date.now() - startTime;
        
        if (elapsed > MAX_POLLING_DURATION) {
          stopRemediationPolling(incidentId);
          console.log(`⏰ Polling timeout reached for incident ${incidentId} (30 minutes), stopped polling`);
          return;
        }
      } else {
        // Status not found yet - this is OK, keep polling
        console.log(`⏳ Remediation status not found yet for incident ${incidentId}, continuing to poll...`);
      }
    } catch (error) {
      console.error(`❌ Failed to fetch remediation status for ${incidentId}:`, error);
      // Don't stop polling on error - might be temporary network issue
    }
  };
  
  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      Object.values(pollingIntervalsRef.current).forEach(interval => {
        clearInterval(interval);
      });
      pollingIntervalsRef.current = {};
    };
  }, []);

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
      <div className="bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
              <span className="text-xl">🔍</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold">Triage Hub</h1>
              <p className="text-sm text-purple-100">AI-powered log analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Incidents Button */}
            <button
              onClick={() => setShowCloudWatchIncidentsDialog(true)}
              className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 rounded-lg px-3 py-1.5 text-xs text-white font-medium transition-colors"
              title="View CloudWatch alarm incidents"
            >
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              Incidents
            </button>
            {/* Save/Load Session Button */}
            <button
              onClick={() => setShowSessionDialog(true)}
              className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 rounded-lg px-3 py-1.5 text-xs text-white font-medium transition-colors"
              title="Save or load chat session"
            >
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
              </svg>
              Sessions
            </button>
            {/* Admin/Utility Panel Button */}
            {onShowUtilityPanel && (
              <button
                onClick={onShowUtilityPanel}
                className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 rounded-lg px-3 py-1.5 text-xs text-white font-medium transition-colors"
                title="Open Utility Panel (Create alarms, manage logs, view incidents)"
              >
                ⚙️ Admin
              </button>
            )}
            {/* Refresh Incidents Button */}
            <button
              onClick={async () => {
                console.log('Manual refresh triggered');
                try {
                  const incidents = await fetchIncidents({
                    limit: 10,
                    source: 'cloudwatch_alarm',
                    status: 'all'
                  });
                  console.log(`Manual refresh found ${incidents.length} CloudWatch incidents`, incidents);
                  
                  if (incidents.length > 0) {
                    const incidentMessages = incidents.map(incidentItem => incidentToMessage(incidentItem));
                    setMessages(prev => {
                      const existingIncidentIds = new Set(
                        prev
                          .filter(m => m.incident?.incident_id)
                          .map(m => m.incident.incident_id)
                      );
                      const newIncidentMessages = incidentMessages.filter(
                        msg => !existingIncidentIds.has(msg.incident?.incident_id)
                      );
                      if (newIncidentMessages.length > 0) {
                        return [...newIncidentMessages, ...prev];
                      }
                      return prev;
                    });
                  }
                } catch (error) {
                  console.error('Failed to refresh incidents:', error);
                }
              }}
              className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 rounded-lg px-3 py-1.5 text-xs text-white font-medium transition-colors"
              title="Refresh CloudWatch incidents"
            >
              🔄 Refresh
            </button>
            {/* MCP Toggle - Always visible, default ON */}
            <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5">
              <span className="text-xs text-purple-100">MCP:</span>
              <button
                onClick={() => setUseMCP(true)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  useMCP === true
                    ? 'bg-white text-purple-700 font-semibold'
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
                    ? 'bg-white text-purple-700 font-semibold'
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

      {/* Source (log) and Incident source selectors */}
      <div className="bg-gray-50 border-b border-gray-200 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 font-medium">Source:</span>
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
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Incident source:</span>
            <select
              value={defaultIncidentSource}
              onChange={(e) => setDefaultIncidentSource(e.target.value)}
              className="text-xs border border-gray-300 rounded-md px-2 py-1.5 text-gray-700 bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              title="Default source when opening Incidents"
            >
              <option value="cloudwatch_alarm">CloudWatch</option>
              <option value="servicenow">ServiceNow</option>
              <option value="jira">Jira</option>
            </select>
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
                title="Quick Search (70-75% accuracy)
• Real-time: No indexing delay, instant results
• Speed: 1-3 seconds
• Best for: Recent logs, simple keywords, live incidents
• Limitations: No aggregation or statistics
• Use when: You need the latest logs or correlation tracing"
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
                title="Deep Search (75-85% accuracy)
• Complex queries: SQL-like with aggregation & grouping
• Speed: 5-10 seconds
• Best for: Error patterns, statistics, historical analysis
• Note: 5-15 min indexing delay for new logs
• Use when: You need grouped results or trend analysis"
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
        </div>

        {/* Always Visible Disclaimer */}
        <div className="mt-2 text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
          {searchMode === 'quick' ? (
            <span>
              <strong className="text-blue-600">Quick Search:</strong> Real-time results (1-3s) with no indexing delay. Shows all log occurrences with timestamps. Best for live incidents and recent logs.
            </span>
          ) : (
            <span>
              <strong className="text-orange-600">Deep Search:</strong> Advanced analytics with aggregation and grouping (5-10s). Features: Error patterns, statistics, trend analysis. <strong>Note:</strong> 5-15 min indexing delay for new logs.
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
                onCreateGitHubIssue={handleCreateGitHubIssue}
                isCreatingIncident={creatingIncidentMessageId === message.id}
                remediationStatus={message.incident?.incident_id ? remediationStatuses[message.incident.incident_id] : null}
                onRefreshRemediation={() => message.incident?.incident_id && fetchRemediationStatus(message.incident.incident_id)}
                onPausePolling={() => message.incident?.incident_id && pauseRemediationPolling(message.incident.incident_id)}
                onResumePolling={() => message.incident?.incident_id && resumeRemediationPolling(message.incident.incident_id)}
                isPollingActive={message.incident?.incident_id ? isPollingActive(message.incident.incident_id) : false}
                isPollingPaused={message.incident?.incident_id ? isPollingPaused(message.incident.incident_id) : false}
                onCheckPRStatus={() => message.incident?.incident_id && checkPRStatus(message.incident.incident_id)}
                onReanalyzeIncident={handleReanalyzeIncident}
                isReanalyzing={message.incident?.incident_id === reanalyzingIncidentId}
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

      {/* Code Fix Approval Dialog (shown after investigation if code_fix needed) */}
      <IncidentApprovalDialog
        isOpen={showIncidentDialog}
        onApprove={handleApprovalConfirm}
        onCancel={handleApprovalCancel}
        incidentPreview={getIncidentPreview()}
      />

      {/* Chat Session Dialog */}
      <ChatSessionDialog
        isOpen={showSessionDialog}
        onClose={() => setShowSessionDialog(false)}
        onLoadSession={handleLoadSession}
        currentMessages={messages}
        currentIncidentData={pendingIncidentData || (messages.find(m => m.incident)?.incident || null)}
        currentRemediationStatuses={remediationStatuses}
      />

      {/* CloudWatch Incidents Dialog */}
      <CloudWatchIncidentsDialog
        isOpen={showCloudWatchIncidentsDialog}
        onClose={() => setShowCloudWatchIncidentsDialog(false)}
        onLoadIncident={handleLoadCloudWatchIncident}
        initialSource={defaultIncidentSource}
      />
    </div>
  );
});

export default ChatWindow;

