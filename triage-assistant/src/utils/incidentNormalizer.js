/**
 * Normalize CloudWatch incidents, ServiceNow tickets, and Jira issues to a common shape
 * for the unified Incidents tab (id, source, title, service, timestamp, status, raw).
 */

/**
 * Normalize a CloudWatch incident (from fetchIncidents / DynamoDB) to shared shape.
 * @param {object} item - Raw incident from list_incidents (may have data, investigation_result, etc.)
 * @param {object} parseIncidentData - Optional parser from incidentParser (for nested data)
 * @returns {object} { id, source, title, service, timestamp, status, priority, raw }
 */
export function normalizeCloudWatchIncident(item, parseIncidentData = null) {
  let parsed = item;
  if (item?.data && typeof item.data === 'string') {
    try {
      parsed = JSON.parse(item.data);
    } catch {
      parsed = item;
    }
  } else if (item?.data && typeof item.data === 'object') {
    parsed = item.data;
  }
  if (parseIncidentData && (parsed?.full_state || parsed?.incident_id)) {
    try {
      parsed = parseIncidentData(parsed);
    } catch {
      // keep parsed as-is
    }
  }
  const incidentId = parsed?.incident_id || item?.incident_id || item?.timestamp || 'unknown';
  const alertName = parsed?.alert_name || parsed?.alertName || '';
  const service = parsed?.service || item?.service || 'unknown';
  const timestamp = parsed?.timestamp || parsed?.created_at || item?.timestamp || item?.created_at || '';
  const status = parsed?.status || item?.status || 'open';
  const severity = parsed?.severity || parsed?.priority || 'P3';

  return {
    id: incidentId,
    source: 'cloudwatch_alarm',
    title: alertName ? `${alertName} (${incidentId})` : String(incidentId),
    service,
    timestamp,
    status,
    priority: severity,
    raw: item,
    parsed,
  };
}

// ServiceNow often returns numeric state/urgency; map to human-readable labels like Jira
const SERVICENOW_STATE_LABELS = { 1: 'New', 2: 'In Progress', 3: 'On Hold', 4: 'Resolved', 5: 'Closed', 6: 'Canceled' };
const SERVICENOW_PRIORITY_LABELS = { 1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low', 5: 'Planning' };

function servicenowStateLabel(val) {
  if (val == null || val === '') return 'Open';
  const n = typeof val === 'string' ? parseInt(val, 10) : val;
  return Number.isNaN(n) ? String(val) : (SERVICENOW_STATE_LABELS[n] ?? String(val));
}
function servicenowPriorityLabel(val) {
  if (val == null || val === '') return '';
  const n = typeof val === 'string' ? parseInt(val, 10) : val;
  return Number.isNaN(n) ? String(val) : (SERVICENOW_PRIORITY_LABELS[n] ?? String(val));
}

/**
 * Normalize a ServiceNow ticket (from Incident MCP) to shared shape.
 * @param {object} ticket - Raw ticket from list_servicenow_tickets
 * @returns {object} { id, source, title, service, timestamp, status, priority, description, steps_to_reproduce, app_name, system_name, created_by, raw }
 */
export function normalizeServiceNowTicket(ticket) {
  const id = ticket?.number || ticket?.sys_id || 'unknown';
  const title = ticket?.short_description || ticket?.description || id;
  const service = ticket?.service || 'unknown';
  const timestamp = ticket?.opened_at || ticket?.sys_created_on || '';
  const stateRaw = ticket?.state ?? 'open';
  const urgencyRaw = ticket?.urgency ?? ticket?.impact ?? '';
  const status = servicenowStateLabel(stateRaw);
  const priority = servicenowPriorityLabel(urgencyRaw) || servicenowPriorityLabel(ticket?.impact);

  return {
    id,
    source: 'servicenow',
    title,
    service,
    timestamp,
    status,
    priority: priority || String(urgencyRaw),
    description: ticket?.description || '',
    steps_to_reproduce: ticket?.steps_to_reproduce || '',
    app_name: ticket?.app_name || ticket?.application_name || '',
    system_name: ticket?.system_name || ticket?.cmdb_ci || '',
    created_by: ticket?.created_by || ticket?.caller_id || ticket?.opened_by || '',
    raw: ticket,
  };
}

/**
 * Normalize a Jira issue (from Incident MCP) to shared shape.
 * @param {object} issue - Raw issue from list_jira_issues
 * @returns {object} { id, source, title, service, timestamp, status, priority, description, steps_to_reproduce, app_name, system_name, created_by, raw }
 */
export function normalizeJiraIssue(issue) {
  const id = issue?.key || issue?.id || 'unknown';
  const title = issue?.summary || issue?.description || id;
  const service = issue?.service || 'unknown';
  const timestamp = issue?.created || issue?.updated || '';
  const status = issue?.status || 'Open';
  const priority = issue?.priority || '';

  return {
    id,
    source: 'jira',
    title,
    service,
    timestamp,
    status,
    priority: String(priority),
    description: issue?.description || '',
    steps_to_reproduce: issue?.steps_to_reproduce || '',
    app_name: issue?.app_name || issue?.application_name || '',
    system_name: issue?.system_name || '',
    created_by: issue?.created_by || issue?.reporter || '',
    raw: issue,
  };
}
