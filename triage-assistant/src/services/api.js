/**
 * API Service for Triage Assistant
 * Connects to the Lambda chat API endpoint
 */

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT ||
  'https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/';

/**
 * Send a question to the chat API
 * @param {string} question - The user's question
 * @param {string} service - Optional service name to focus on
 * @param {string} timeRange - Time range to search (e.g., "1h", "6h", "24h")
 * @param {boolean} useMCP - Optional override to use MCP client (null = use server default)
 * @param {string} searchMode - 'quick' for real-time filter_log_events, 'deep' for Logs Insights
 * @returns {Promise<Object>} - The API response
 */
export async function askQuestion(question, service = null, timeRange = '1h', useMCP = null, searchMode = 'quick') {
  const payload = {
    question,
    time_range: timeRange,
    search_mode: searchMode,  // 'quick' = real-time, 'deep' = Logs Insights
  };

  if (service) {
    payload.service = service;
  }

  // Add use_mcp parameter if explicitly provided (overrides server default)
  if (useMCP !== null) {
    payload.use_mcp = useMCP;
  }

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    // Parse the body if it's a string (Lambda response format)
    if (typeof data.body === 'string') {
      return JSON.parse(data.body);
    }

    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}

/**
 * Health check for the API
 * @returns {Promise<boolean>} - True if API is healthy
 */
export async function checkHealth() {
  try {
    const response = await askQuestion('health check', null, '1h');
    return !!response.answer;
  } catch (error) {
    return false;
  }
}

/**
 * Fetch CloudWatch log groups for dropdown
 * @param {string} prefix - Optional prefix to filter log groups (default: '/aws/')
 * @param {number} limit - Maximum number of log groups to return (default: 50, max 50)
 * @returns {Promise<Object>} - Response with logGroups array and grouped object
 */
export async function fetchLogGroups(prefix = '/aws/', limit = 50) {
  try {
    const params = new URLSearchParams({
      action: 'list_log_groups',  // Required for router to identify this request
      prefix: prefix,
      limit: limit.toString()
    });
    
    const url = `${API_ENDPOINT}?${params.toString()}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    // Parse the body if it's a string (Lambda response format)
    if (typeof data.body === 'string') {
      return JSON.parse(data.body);
    }

    return data;
  } catch (error) {
    console.error('Error fetching log groups:', error);
    throw error;
  }
}

/**
 * Request AI diagnosis for log data
 * @param {Object} logData - Log analysis results from chat handler
 * @param {string} service - Service name
 * @param {string} context - Optional additional context
 * @returns {Promise<Object>} - Diagnosis result
 */
export async function requestDiagnosis(logData, service, context = null) {
  const payload = {
    action: 'diagnose',
    log_data: logData,
    service: service,
  };

  if (context) {
    payload.context = context;
  }

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    // Parse the body if it's a string (Lambda response format)
    if (typeof data.body === 'string') {
      return JSON.parse(data.body);
    }

    return data;
  } catch (error) {
    console.error('Diagnosis API Error:', error);
    throw error;
  }
}

/**
 * Create incident investigation from chat query results
 * @param {Object} logData - Log analysis results from chat handler
 * @param {string} service - Service name
 * @param {string} question - Original user question
 * @param {string} logGroup - Log group name
 * @param {string} alertName - Optional custom alert name
 * @param {string} context - Optional additional context
 * @returns {Promise<Object>} - Incident creation result with incident_id
 */
export async function createIncident(logData, service, question, logGroup = null, alertName = null, context = null) {
  const payload = {
    action: 'create_incident',
    log_data: logData,
    service: service,
    question: question,
  };

  if (logGroup) {
    payload.log_group = logGroup;
  }
  if (alertName) {
    payload.alert_name = alertName;
  }
  if (context) {
    payload.context = context;
  }

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    // Parse the body if it's a string (Lambda response format)
    const result = typeof data.body === 'string' ? JSON.parse(data.body) : data;

    if (!response.ok) {
      const error = new Error(result.message || `API error: ${response.status} ${response.statusText}`);
      error.status = response.status;
      error.data = result;
      throw error;
    }

    return result;
  } catch (error) {
    console.error('Create Incident API Error:', error);
    throw error;
  }
}

/**
 * Manage sample logs (clean, regenerate, or clean and regenerate)
 * @param {string} operation - 'clean', 'regenerate', or 'clean_and_regenerate'
 * @param {string} password - Password for authentication
 * @returns {Promise<Object>} - Result with status and message
 */
export async function manageSampleLogs(operation = 'clean_and_regenerate', password) {
  const payload = {
    action: 'manage_logs',
    operation: operation,
    password: password,
  };

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    // Parse the body if it's a string (Lambda response format)
    const result = typeof data.body === 'string' ? JSON.parse(data.body) : data;

    if (!response.ok) {
      const error = new Error(result.message || `API error: ${response.status} ${response.statusText}`);
      error.status = response.status;
      error.data = result;
      throw error;
    }

    return result;
  } catch (error) {
    console.error('Log Management API Error:', error);
    throw error;
  }
}

/**
 * Create GitHub issue after user approval (for code_fix execution type)
 * @param {string} incidentId - Incident ID
 * @param {string} service - Service name
 * @returns {Promise<Object>} - Result with github_issue details
 */
export async function createGitHubIssueAfterApproval(incidentId, service, fullState = null) {
  // Validate inputs
  if (!incidentId) {
    throw new Error('incidentId is required');
  }
  if (!service || service === 'unknown-service') {
    throw new Error(`Invalid service name: ${service}. Service must be a known service name.`);
  }

  const payload = {
    action: 'create_github_issue_after_approval',
    incident_id: incidentId,
    service: service,
  };
  
  // Include full_state if provided (for chat-created incidents not yet in DynamoDB)
  if (fullState) {
    payload.full_state = fullState;
  }

  console.log('🔍 createGitHubIssueAfterApproval: Sending request:', {
    incidentId,
    service,
    payload
  });

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    console.log('🔍 createGitHubIssueAfterApproval: Response status:', response.status);

    const data = await response.json();

    // Parse the body if it's a string (Lambda response format)
    const result = typeof data.body === 'string' ? JSON.parse(data.body) : data;

    console.log('🔍 createGitHubIssueAfterApproval: Parsed result:', result);

    if (!response.ok) {
      const errorMessage = result.error || result.message || `API error: ${response.status} ${response.statusText}`;
      const error = new Error(errorMessage);
      error.status = response.status;
      error.data = result;
      console.error('❌ createGitHubIssueAfterApproval: API error:', {
        status: response.status,
        error: errorMessage,
        full_result: result
      });
      throw error;
    }

    return result;
  } catch (error) {
    console.error('❌ Create GitHub Issue API Error:', error);
    throw error;
  }
}

/**
 * Get remediation status for an incident
 * @param {string} incidentId - Incident ID
 * @returns {Promise<Object>} - Remediation status with issue, PR, timeline
 */
/**
 * Save chat session
 * @param {string} sessionId - Optional session ID (if not provided, generates new one)
 * @param {string} sessionName - Optional session name
 * @param {Array} messages - Chat messages
 * @param {Object} incidentData - Current incident data if any
 * @param {Object} remediationStatuses - Current remediation statuses
 * @returns {Promise<Object>} - The saved session info
 */
export async function saveChatSession(sessionId, sessionName, messages, incidentData, remediationStatuses) {
  const payload = {
    action: 'save_session',
    session_id: sessionId,
    session_name: sessionName,
    messages: messages,
    incident_data: incidentData,
    remediation_statuses: remediationStatuses
  };

  try {
    const response = await fetch(`${API_ENDPOINT}?action=save_session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return typeof data.body === 'string' ? JSON.parse(data.body) : data;
  } catch (error) {
    console.error('Error saving chat session:', error);
    throw error;
  }
}

/**
 * Load chat session
 * @param {string} sessionId - Session ID to load
 * @returns {Promise<Object>} - The loaded session data
 */
export async function loadChatSession(sessionId) {
  try {
    const response = await fetch(`${API_ENDPOINT}?action=load_session&session_id=${sessionId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return typeof data.body === 'string' ? JSON.parse(data.body) : data;
  } catch (error) {
    console.error('Error loading chat session:', error);
    throw error;
  }
}

/**
 * List chat sessions
 * @param {number} limit - Maximum number of sessions to return (default 20)
 * @returns {Promise<Object>} - List of sessions
 */
export async function listChatSessions(limit = 20) {
  try {
    const response = await fetch(`${API_ENDPOINT}?action=list_sessions&limit=${limit}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return typeof data.body === 'string' ? JSON.parse(data.body) : data;
  } catch (error) {
    console.error('Error listing chat sessions:', error);
    throw error;
  }
}

export async function getRemediationStatus(incidentId) {
  try {
    const params = new URLSearchParams({
      action: 'get_remediation_status',
      incident_id: incidentId
    });
    
    const url = `${API_ENDPOINT}?${params.toString()}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      // 404 is OK - remediation state might not exist yet (issue just created)
      if (response.status === 404) {
        console.log(`⏳ Remediation state not found for incident ${incidentId} - this is normal if issue was just created`);
        return null;
      }
      
      // Log error details for debugging
      const errorText = await response.text().catch(() => 'Unable to read error response');
      console.error(`❌ Remediation status API error: ${response.status} ${response.statusText}`, errorText);
      
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    // Parse the body if it's a string (Lambda response format)
    if (typeof data.body === 'string') {
      return JSON.parse(data.body);
    }

    return data;
  } catch (error) {
    console.error('Error fetching remediation status:', error);
    // Don't throw - return null so UI can handle gracefully
    return null;
  }
}

/**
 * Fetch recent incidents from DynamoDB
 * @param {Object} options - Query options
 * @param {number} options.limit - Number of incidents to fetch (default: 20)
 * @param {string} options.source - Filter by source ('chat', 'cloudwatch_alarm', 'all')
 * @param {string} options.status - Filter by status ('open', 'resolved', 'all')
 * @param {string} options.service - Filter by service name (optional)
 * @returns {Promise<Array>} Array of incident objects
 */
export async function fetchIncidents(options = {}) {
  const { limit = 20, source = 'all', status = 'all', service = null } = options;
  
  try {
    const params = new URLSearchParams({
      action: 'list_incidents',
      limit: limit.toString(),
      source,
      status
    });
    
    if (service) {
      params.append('service', service);
    }
    
    const url = `${API_ENDPOINT}?${params.toString()}`;
    
    console.log('🔍 fetchIncidents: Request URL:', url);
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    console.log('🔍 fetchIncidents: Response status:', response.status, response.statusText);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('🔍 fetchIncidents: Error response:', errorText);
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    console.log('🔍 fetchIncidents: Raw response:', data);

    // Parse the body if it's a string (Lambda response format)
    const result = typeof data.body === 'string' ? JSON.parse(data.body) : data;
    console.log('🔍 fetchIncidents: Parsed result:', result);
    console.log('🔍 fetchIncidents: Incidents count:', result.incidents?.length || 0);

    return result.incidents || [];
  } catch (error) {
    console.error('❌ Error fetching incidents:', error);
    console.error('❌ Error details:', {
      message: error.message,
      stack: error.stack,
      name: error.name
    });
    throw error;
  }
}

// Fallback mock data when Incident MCP is not deployed or unreachable (demo only)
const MOCK_SERVICENOW_TICKETS = [
  { number: 'INC001', short_description: 'Payment gateway timeout affecting checkout', description: 'Customers report checkout failures. Payment service times out after 30s. Started around 14:00 UTC. Steps: 1) Reproduce via checkout flow, 2) Check payment-service logs for timeouts.', opened_at: '2026-02-19T14:05:00Z', state: '2', urgency: '2', service: 'payment-service', assigned_to: 'john.doe' },
  { number: 'INC002', short_description: 'Card declined errors spike in production', description: 'Error rate for card declined responses increased from 0.1% to 2.5%. Logs show connection pool exhaustion to acquirer. Reproduce: run load test against payment API.', opened_at: '2026-02-19T11:30:00Z', state: '1', urgency: '1', service: 'payment-service', assigned_to: 'jane.smith' },
  { number: 'INC003', short_description: 'Rating calculation failure for bulk requests', description: 'Bulk rating API returns 500 for requests with more than 50 items. Stack trace points to timeout in rating-engine.', opened_at: '2026-02-18T16:20:00Z', state: '2', urgency: '2', service: 'rating-service', assigned_to: 'alex.wong' },
  { number: 'INC004', short_description: 'Premium computation returning incorrect values', description: 'Premium for multi-coverage policies is under-calculated. Affects policy renewals. Suspected rounding in rating-service.', opened_at: '2026-02-18T09:15:00Z', state: '3', urgency: '2', service: 'rating-service', assigned_to: 'alex.wong' },
  { number: 'INC005', short_description: 'Policy validation timeout on policy-service', description: 'Policy validation endpoint times out under load. P99 latency > 10s. Redis cache hit rate dropped to 60%.', opened_at: '2026-02-19T08:45:00Z', state: '2', urgency: '2', service: 'policy-service', assigned_to: 'sarah.chen' },
  { number: 'INC006', short_description: 'Policy-service 5xx errors during peak load', description: '5xx error rate increased during 18:00-20:00 UTC. Correlated with high request volume. Possible DB connection exhaustion.', opened_at: '2026-02-19T18:10:00Z', state: '1', urgency: '1', service: 'policy-service', assigned_to: 'sarah.chen' },
];
const MOCK_JIRA_ISSUES = [
  { key: 'PAY-101', summary: 'Payment service p99 latency above threshold', description: 'CloudWatch alarm: p99 latency for payment-service exceeds 2000ms. Occurs during peak checkout hours. Steps to reproduce: run load test; check DB queries and external gateway calls.', priority: 'High', status: 'Open', created: '2026-02-19T13:00:00Z', service: 'payment-service', assignee: 'john.doe' },
  { key: 'PAY-102', summary: 'Idempotency key collision under high load', description: 'Duplicate payment attempts when same idempotency key used within 1s. Race condition in payment-service idempotency store.', priority: 'Medium', status: 'In Progress', created: '2026-02-18T10:30:00Z', service: 'payment-service', assignee: 'jane.smith' },
  { key: 'RAT-201', summary: 'Rating API returning 500 for discount rules', description: 'POST /rating/quote returns 500 when discount rules contain null effective_date. Stack trace in rating-service discount engine.', priority: 'High', status: 'Open', created: '2026-02-19T09:45:00Z', service: 'rating-service', assignee: 'alex.wong' },
  { key: 'RAT-202', summary: 'Discount calculation wrong for multi-tier policies', description: 'Premium discount not applied correctly when policy has multiple tiers. Calculation uses wrong tier index in rating-service.', priority: 'Medium', status: 'In Progress', created: '2026-02-17T14:00:00Z', service: 'rating-service', assignee: 'alex.wong' },
  { key: 'POL-301', summary: 'Policy cache returning stale data', description: 'Policy lookup returns outdated coverage after policy update. TTL on Redis cache may be too long or invalidation missing in policy-service.', priority: 'High', status: 'Open', created: '2026-02-19T07:20:00Z', service: 'policy-service', assignee: 'sarah.chen' },
  { key: 'POL-302', summary: 'Policy lookup timeout in API gateway', description: 'Policy validation calls from API gateway time out after 5s. policy-service P95 latency increased to 4.2s. Check DB and dependency calls.', priority: 'High', status: 'Open', created: '2026-02-19T15:00:00Z', service: 'policy-service', assignee: 'sarah.chen' },
];

/**
 * Fetch ServiceNow tickets from Incident MCP (Lambda proxy).
 * Uses mock data when backend returns empty (e.g. Incident MCP not deployed).
 * @param {Object} options - { service?, category?, limit? }
 * @returns {Promise<Array>} Array of ticket objects (with source: 'servicenow')
 */
export async function fetchServiceNowTickets(options = {}) {
  const { service = null, category = null, limit = 20 } = options;
  try {
    const params = new URLSearchParams({
      action: 'list_servicenow_tickets',
      limit: String(limit),
    });
    if (service) params.append('service', service);
    if (category) params.append('category', category);
    const url = `${API_ENDPOINT}?${params.toString()}`;
    const response = await fetch(url, { method: 'GET', headers: { 'Content-Type': 'application/json' } });
    if (!response.ok) throw new Error(`API error: ${response.status} ${response.statusText}`);
    const data = await response.json();
    const result = typeof data.body === 'string' ? JSON.parse(data.body) : data;
    const tickets = result.tickets || [];
    return tickets.length > 0 ? tickets : MOCK_SERVICENOW_TICKETS;
  } catch (error) {
    console.warn('ServiceNow tickets unavailable, using mock data:', error?.message || error);
    return MOCK_SERVICENOW_TICKETS;
  }
}

/**
 * Fetch Jira issues from Incident MCP (Lambda proxy).
 * Uses mock data when backend returns empty (e.g. Incident MCP not deployed).
 * @param {Object} options - { project?, service?, limit? }
 * @returns {Promise<Array>} Array of issue objects (with source: 'jira')
 */
export async function fetchJiraIssues(options = {}) {
  const { project = null, service = null, limit = 20 } = options;
  try {
    const params = new URLSearchParams({
      action: 'list_jira_issues',
      limit: String(limit),
    });
    if (project) params.append('project', project);
    if (service) params.append('service', service);
    const url = `${API_ENDPOINT}?${params.toString()}`;
    const response = await fetch(url, { method: 'GET', headers: { 'Content-Type': 'application/json' } });
    if (!response.ok) throw new Error(`API error: ${response.status} ${response.statusText}`);
    const data = await response.json();
    const result = typeof data.body === 'string' ? JSON.parse(data.body) : data;
    const issues = result.issues || [];
    return issues.length > 0 ? issues : MOCK_JIRA_ISSUES;
  } catch (error) {
    console.warn('Jira issues unavailable, using mock data:', error?.message || error);
    return MOCK_JIRA_ISSUES;
  }
}

/**
 * Delete an incident from DynamoDB
 * @param {string} incidentId - Incident ID to delete
 * @returns {Promise<Object>} - Result with success status and message
 */
export async function deleteIncident(incidentId) {
  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'delete_incident',
        incident_id: incidentId
      }),
    });

    const data = await response.json();
    const result = typeof data.body === 'string' ? JSON.parse(data.body) : data;

    if (!response.ok) {
      throw new Error(result.error || `API error: ${response.status} ${response.statusText}`);
    }

    return result;
  } catch (error) {
    console.error('Error deleting incident:', error);
    throw error;
  }
}

/**
 * Re-analyze an existing incident
 * Re-runs the investigation workflow and updates the incident with new results
 * 
 * @param {string} incidentId - The ID of the incident to re-analyze
 * @returns {Promise<Object>} Updated investigation result
 */
export async function reanalyzeIncident(incidentId) {
  try {
    console.log(`🔄 Re-analyzing incident: ${incidentId}`);
    
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'reanalyze_incident',
        incident_id: incidentId
      }),
    });

    const data = await response.json();
    const result = typeof data.body === 'string' ? JSON.parse(data.body) : data;

    if (!response.ok) {
      throw new Error(result.error || result.message || `API error: ${response.status} ${response.statusText}`);
    }

    console.log(`✅ Re-analysis complete for incident: ${incidentId}`, result);
    return result;
  } catch (error) {
    console.error('❌ Error re-analyzing incident:', error);
    throw error;
  }
}

export default {
  askQuestion,
  checkHealth,
  fetchLogGroups,
  requestDiagnosis,
  createIncident,
  manageSampleLogs,
  createGitHubIssueAfterApproval,
  getRemediationStatus,
  fetchIncidents,
  fetchServiceNowTickets,
  fetchJiraIssues,
  deleteIncident,
  reanalyzeIncident,
  saveChatSession,
  loadChatSession,
  listChatSessions,
};
