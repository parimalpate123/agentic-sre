/**
 * Utility functions for parsing incident data from DynamoDB format to UI format
 */

/**
 * Parse incident data from DynamoDB format to UI format
 * @param {string|object} data - Incident data (JSON string or object)
 * @returns {object} Parsed incident data in UI format
 */
export function parseIncidentData(data) {
  try {
    // If data is string, parse it
    const incidentData = typeof data === 'string' ? JSON.parse(data) : data;
    
    console.log('🔍 Parsing incident data:', incidentData);
    
    // Extract full_state if available (contains nested incident data)
    // MUST be declared before executionResults since executionResults references it
    const fullState = incidentData.full_state || {};
    
    // Extract execution results if available
    // Extract execution_results from multiple locations
    const executionResults = incidentData.execution_results || 
                            fullState.execution_results || 
                            {};
    const incident = fullState.incident || {};
    const remediation = fullState.remediation || {};
    const triage = fullState.triage || {};
    const diagnosis = fullState.diagnosis || {};
    
    // Get source from multiple possible locations
    const source = incidentData.source || incident.source || 'chat';
    
    // Extract execution_type from remediation (for CloudWatch incidents)
    const executionType = remediation.execution_type || incidentData.execution_type || null;
    
    // Extract root cause from multiple locations
    const rootCause = incidentData.root_cause || 
                     diagnosis.root_cause || 
                     remediation.root_cause || 
                     'Analysis in progress';
    
    // Extract confidence (might be 0-1 decimal or 0-100 integer)
    let confidence = incidentData.confidence || diagnosis.confidence || 0;
    // If confidence is between 0 and 1, convert to percentage
    if (confidence > 0 && confidence <= 1) {
      confidence = Math.round(confidence * 100);
    }
    
    // Extract severity
    const severity = incidentData.severity || 
                    triage.severity?.value || 
                    triage.severity || 
                    'P3';
    
    // Extract recommended action
    const recommendedAction = incidentData.recommended_action || 
                             remediation.recommended_action || 
                             null;
    
    // Extract executive summary (often contains detailed analysis)
    const executiveSummary = incidentData.executive_summary || 
                             fullState.executive_summary || 
                             null;
    
    // Extract service - check multiple locations with logging
    let service = incidentData.service || incident.service;
    if (!service && fullState.incident) {
      service = fullState.incident.service;
    }
    if (!service) {
      // Try to extract from alert_name as fallback
      const alertName = incidentData.alert_name || incident.alert_name;
      if (alertName && alertName.includes('-')) {
        const parts = alertName.split('-');
        if (parts.length >= 2) {
          service = parts.slice(0, 2).join('-');
          console.log(`⚠️ Service not found in incident data, extracted from alert_name: ${service}`);
        }
      }
    }
    service = service || 'unknown';
    console.log(`🔍 Extracted service: ${service} from incident_id: ${incidentData.incident_id || incident.incident_id}`);
    
    // Extract timestamp from multiple locations
    let timestamp = incidentData.timestamp || incident.timestamp || incidentData.created_at;
    // Also check top-level fields (from DynamoDB item structure)
    if (!timestamp && incidentData.created_at) {
      timestamp = incidentData.created_at;
    }
    if (!timestamp && incidentData.updated_at) {
      timestamp = incidentData.updated_at;
    }
    
    const parsed = {
      incident_id: incidentData.incident_id || incident.incident_id,
      source: source,
      service: service,
      severity: severity,
      root_cause: rootCause,
      confidence: confidence,
      recommended_action: recommendedAction,
      alert_name: incidentData.alert_name || incident.alert_name || incident.description,
      alert_description: incidentData.alert_description || incident.alert_description || incident.alert_name,
      timestamp: timestamp,
      execution_type: executionType,
      execution_results: {
        github_issue: executionResults.github_issue || null,
      },
      // Include full investigation result for detailed view
      investigation_result: incidentData,
      // Include full_state for remediation status
      full_state: fullState,
      // Include executive summary for detailed analysis
      executive_summary: executiveSummary,
      chat_transcript: Array.isArray(incidentData.chat_transcript) ? incidentData.chat_transcript : [],
      source_session_id: incidentData.source_session_id || null
    };
    
    console.log('✅ Parsed incident:', parsed);
    return parsed;
  } catch (error) {
    console.error('❌ Failed to parse incident data:', error, data);
    return {
      incident_id: 'unknown',
      source: 'unknown',
      service: 'unknown',
      severity: 'P3',
      root_cause: 'Failed to parse incident data',
      confidence: 0,
      execution_results: {},
      investigation_result: {},
      full_state: {},
      chat_transcript: [],
      source_session_id: null
    };
  }
}

/** True when stored executive_summary already embeds log analysis, root cause, and remediation text. */
export function executiveSummaryIsFullNarrative(text) {
  if (!text || typeof text !== 'string') return false;
  const t = text.trim();
  if (t.length < 280) return false;
  const u = t.toUpperCase();
  const markers = [
    'LOG ANALYSIS',
    'ROOT CAUSE',
    'RECOMMENDED ACTION',
    'INCIDENT INVESTIGATION',
    'SEVERITY:',
    'ERROR COUNT',
    'DECISION:',
  ];
  const hits = markers.filter((m) => u.includes(m)).length;
  return hits >= 2 || (t.length >= 650 && hits >= 1) || t.length >= 1600;
}

/**
 * Agent step strings often include "1. " (or repeated "1. 1. ") while the UI uses <ol>.
 * Strip leading numeric ordinals for display inside ordered lists.
 * @param {string|{description?:string,action?:string}} step
 * @returns {string}
 */
export function normalizeRemediationStepText(step) {
  if (step == null) return '';
  const raw =
    typeof step === 'string'
      ? step
      : step.description || step.action || JSON.stringify(step);
  let s = String(raw).trim();
  while (/^\d+\.\s+/.test(s)) {
    s = s.replace(/^\d+\.\s+/, '');
  }
  return s;
}

/** Markdown block for recommended action (object or string). */
function formatRecommendedActionMarkdown(recommendedAction) {
  if (!recommendedAction) return '';
  if (typeof recommendedAction === 'object') {
    const action = recommendedAction;
    let actionText = '';
    if (action.action_type) {
      actionText += `${String(action.action_type).replace(/_/g, ' ')}\n`;
    }
    if (action.description) {
      actionText += `${action.description}\n`;
    }
    if (action.steps && action.steps.length > 0) {
      actionText +=
        action.steps
          .map((step, i) => {
            const body = normalizeRemediationStepText(step);
            return `${i + 1}. ${body}`;
          })
          .join('\n') + '\n';
    }
    return `\n**Recommended action:**\n${actionText || JSON.stringify(action)}\n`;
  }
  return `\n**Recommended action:**\n${recommendedAction}\n`;
}

/**
 * Snapshot of execution / GitHub / escalation from stored investigation (matches live chat wording).
 * @param {{ omitPendingGithubIssue?: boolean }} [opts] — omit stale pending_approval line when remediation panel is source of truth
 */
function formatExecutionSnapshotMarkdown(executionResults, executionType, opts = {}) {
  const omitPendingGithub = !!opts.omitPendingGithubIssue;
  let s = '';
  if (executionResults && typeof executionResults === 'object') {
    if (executionResults.auto_execute) {
      const st = executionResults.auto_execute.status;
      const label =
        st === 'success'
          ? 'Auto-executed'
          : st === 'failed'
            ? 'Auto-execution failed'
            : 'Auto-execution skipped';
      s += `\n**Auto-execute:** ${label}`;
      if (executionResults.auto_execute.action) {
        s += ` (${executionResults.auto_execute.action})`;
      }
      s += '\n';
    }
    if (executionResults.github_issue) {
      const gh = executionResults.github_issue;
      if (gh.status === 'success') {
        s += `\n**GitHub issue:** ${gh.issue_url ? `created — ${gh.issue_url}` : 'created'}\n`;
      } else if (gh.status === 'pending_approval') {
        if (!omitPendingGithub) {
          s += `\n**GitHub issue:** approval required before creation\n`;
        }
      } else if (gh.error) {
        s += `\n**GitHub issue:** failed — ${gh.error}\n`;
      }
    }
    if (executionResults.escalation) {
      s += `\n**Escalation:** ${executionResults.escalation.reason || 'Human review required'}\n`;
    }
  }
  if (!s && executionType) {
    s += `\n**Execution type:** ${executionType}\n`;
  }
  return s;
}

function appendAnalysisAndDiagnosisFromFullState(messageContent, fullState) {
  if (!fullState || typeof fullState !== 'object') return messageContent;
  let out = messageContent;
  const analysis = fullState.analysis;
  if (analysis && typeof analysis === 'object') {
    const ec = analysis.error_count;
    const patterns = analysis.error_patterns;
    if (ec != null || (Array.isArray(patterns) && patterns.length > 0)) {
      out += `\n**Log analysis:**\n`;
      if (ec != null) out += `- Error count: ${ec}\n`;
      if (Array.isArray(patterns) && patterns.length > 0) {
        const brief = patterns.slice(0, 10).map((p) =>
          typeof p === 'string' ? p : p.pattern || p.message || p.description || JSON.stringify(p)
        );
        out += `- Sample patterns: ${brief.join('; ')}${patterns.length > 10 ? ' …' : ''}\n`;
      }
    }
  }
  const diagnosis = fullState.diagnosis;
  if (diagnosis && typeof diagnosis === 'object') {
    const cat = diagnosis.category || diagnosis.component;
    if (cat) {
      out += `\n**Diagnosis:** ${[cat].flat().filter(Boolean).join(' · ')}\n`;
    }
    const ev = diagnosis.supporting_evidence;
    if (Array.isArray(ev) && ev.length > 0) {
      const lines = ev.slice(0, 5).map((e, i) => {
        const line = typeof e === 'string' ? e : e.description || e.message || JSON.stringify(e);
        return `${i + 1}. ${line}`;
      });
      out += `\n**Supporting evidence (excerpt):**\n${lines.join('\n')}\n`;
    }
  }
  const triage = fullState.triage;
  if (triage && typeof triage === 'object') {
    const decision = triage.decision?.value ?? triage.decision;
    const sev = triage.severity?.value ?? triage.severity;
    if ((decision != null && decision !== '') || (sev != null && sev !== '')) {
      out += `\n**Triage:**`;
      if (decision != null && decision !== '') out += ` ${typeof decision === 'object' ? JSON.stringify(decision) : decision}`;
      if (sev != null && sev !== '') out += ` · Severity: ${typeof sev === 'object' ? JSON.stringify(sev) : sev}`;
      out += '\n';
    }
  }
  return out;
}

function extractRawIncidentData(incidentItem) {
  if (incidentItem.data) {
    return typeof incidentItem.data === 'string' ? JSON.parse(incidentItem.data) : incidentItem.data;
  }
  if (incidentItem.investigation_result) {
    return typeof incidentItem.investigation_result === 'string'
      ? JSON.parse(incidentItem.investigation_result)
      : incidentItem.investigation_result;
  }
  return incidentItem;
}

/** Single formal record when conversation replay is shown above (avoids duplicating executive summary blocks). */
function buildCompactInvestigationMarkdown(parsed, fullState, executionResults, executionType) {
  let s = '## Investigation record\n\n';
  s += `- **Incident ID:** \`${parsed.incident_id}\`\n`;
  s += `- **Service:** ${parsed.service}\n`;
  s += `- **Severity:** ${parsed.severity}\n`;
  if (parsed.confidence != null && parsed.confidence > 0) {
    s += `- **Confidence:** ${parsed.confidence}%\n`;
  }
  if (parsed.alert_description) {
    s += `- **Original question:** ${parsed.alert_description}\n`;
  }
  s += '\n';
  if (parsed.executive_summary && executiveSummaryIsFullNarrative(parsed.executive_summary)) {
    s += '### Full analysis\n\n';
    s += `${parsed.executive_summary.trim()}\n\n`;
  } else {
    if (parsed.root_cause && parsed.root_cause !== 'Unknown' && parsed.root_cause !== 'Analysis in progress') {
      s += `### Root cause\n\n${parsed.root_cause}\n\n`;
    }
    if (parsed.executive_summary) {
      s += `### Summary\n\n${parsed.executive_summary.trim()}\n\n`;
    }
    s += formatRecommendedActionMarkdown(parsed.recommended_action);
    s = appendAnalysisAndDiagnosisFromFullState(s, fullState);
  }
  s += formatExecutionSnapshotMarkdown(executionResults, executionType, {
    omitPendingGithubIssue: true,
  });
  return s.trim();
}

const MAX_TRANSCRIPT_MESSAGES = 40;
const MAX_TRANSCRIPT_TEXT_CHARS = 12000;

/**
 * Messages to inject when loading an incident: Ask-mode replay (if stored) + formal investigation card.
 * @param {object} incidentItem - DynamoDB row or investigation payload
 * @returns {object[]} Chat-shaped messages (last entry carries .incident for remediation UI)
 */
export function getIncidentLoadMessages(incidentItem) {
  const rawData = extractRawIncidentData(incidentItem);
  const transcript = Array.isArray(rawData.chat_transcript) ? rawData.chat_transcript : [];
  const sliced = transcript.slice(-MAX_TRANSCRIPT_MESSAGES);
  const replayMessages = sliced.map((t, i) => {
    const isUser = t.role === 'user';
    let text = String(t.text ?? '');
    if (text.length > MAX_TRANSCRIPT_TEXT_CHARS) {
      text = `${text.slice(0, MAX_TRANSCRIPT_TEXT_CHARS)}\n\n…[truncated]`;
    }
    return {
      id: `replay-${rawData.incident_id || 'inc'}-${t.id ?? i}`,
      isUser,
      text,
      timestamp: t.timestamp ? new Date(t.timestamp) : new Date(),
      replayFromIncident: true,
      formatMarkdown: Boolean(!isUser && text.trim().length > 0),
      searchMode: t.search_mode || undefined,
    };
  });
  const hasTranscript = replayMessages.length > 0;
  const incidentMessage = incidentToMessage(incidentItem, {
    layout: hasTranscript ? 'compact' : 'auto',
  });
  return [...replayMessages, incidentMessage];
}

/**
 * Convert DynamoDB incident item to chat message format
 * @param {object} incidentItem - Incident item from DynamoDB
 * @param {{ layout?: 'full' | 'compact' | 'auto' }} [options] - compact = deduped markdown; auto = compact when summary is long / narrative
 * @returns {object} Message object for chat UI
 */
export function incidentToMessage(incidentItem, options = {}) {
  const rawData = extractRawIncidentData(incidentItem);
  const parsed = parseIncidentData(rawData);
  const fullState = parsed.full_state || {};
  const storedExecutionResults =
    (typeof rawData === 'object' && rawData && rawData.execution_results) ||
    fullState.execution_results ||
    null;
  const executionResultsForIncident =
    storedExecutionResults && typeof storedExecutionResults === 'object'
      ? storedExecutionResults
      : parsed.execution_results;

  // Determine message content based on source
  const sourceLabel = parsed.source === 'cloudwatch_alarm' ? 'CloudWatch Alarm' : 'Chat';
  const alertName = parsed.alert_name || parsed.service || 'Unknown Alert';
  const alertDescription = parsed.alert_description || '';

  // Create a detailed message with incident analysis
  let messageContent = '';

  if (parsed.source === 'cloudwatch_alarm') {
    messageContent = `🔴 **${sourceLabel} triggered:** ${alertName}\n\n`;

    if (alertDescription) {
      messageContent += `**Alert details:**\n${alertDescription}\n\n`;
    }

    if (parsed.service) {
      messageContent += `**Service:** ${parsed.service}\n`;
    }

    if (parsed.severity) {
      messageContent += `**Severity:** ${parsed.severity}\n`;
    }

    // Show root cause or executive summary
    if (parsed.root_cause && parsed.root_cause !== 'Unknown' && parsed.root_cause !== 'Analysis in progress') {
      messageContent += `\n**Root cause analysis:**\n${parsed.root_cause}\n`;
    } else if (parsed.executive_summary) {
      messageContent += `\n**Analysis summary:**\n${parsed.executive_summary}\n`;
    } else if (parsed.root_cause) {
      messageContent += `\n**Root cause analysis:**\n${parsed.root_cause}\n`;
    }

    if (parsed.confidence && parsed.confidence > 0) {
      messageContent += `\n**Confidence:** ${parsed.confidence}%\n`;
    }

    messageContent += formatRecommendedActionMarkdown(parsed.recommended_action);
    messageContent += formatExecutionSnapshotMarkdown(executionResultsForIncident, parsed.execution_type);
    messageContent = appendAnalysisAndDiagnosisFromFullState(messageContent, fullState);

    // If no detailed analysis is available, at least show that investigation is complete
    if (!parsed.root_cause && !parsed.executive_summary && !parsed.recommended_action) {
      messageContent += `\n**Status:** Incident investigation completed. Review the alarm details above for more information.\n`;
    }
  } else {
    const layout = options.layout || 'auto';
    const useCompact =
      layout === 'compact' ||
      (layout !== 'full' &&
        (executiveSummaryIsFullNarrative(parsed.executive_summary) ||
          (parsed.executive_summary && String(parsed.executive_summary).trim().length > 900)));
    if (useCompact) {
      messageContent = buildCompactInvestigationMarkdown(
        parsed,
        fullState,
        executionResultsForIncident,
        parsed.execution_type
      );
    } else {
      messageContent = `## Chat incident\n\n### ${alertName}\n\n`;
      messageContent += `- **Incident ID:** \`${parsed.incident_id}\`\n`;
      if (alertDescription) {
        messageContent += `- **Original question / context:** ${alertDescription}\n`;
      }
      if (parsed.service) {
        messageContent += `- **Service:** ${parsed.service}\n`;
      }
      if (parsed.severity) {
        messageContent += `- **Severity:** ${parsed.severity}\n`;
      }
      if (parsed.confidence != null && parsed.confidence > 0) {
        messageContent += `- **Confidence:** ${parsed.confidence}%\n`;
      }
      messageContent += '\n';

      if (parsed.root_cause && parsed.root_cause !== 'Unknown' && parsed.root_cause !== 'Analysis in progress') {
        messageContent += `### Root cause\n\n${parsed.root_cause}\n\n`;
      }
      if (parsed.executive_summary) {
        messageContent += `### Investigation summary\n\n${parsed.executive_summary.trim()}\n\n`;
      }

      messageContent = appendAnalysisAndDiagnosisFromFullState(messageContent, fullState);
      messageContent += formatRecommendedActionMarkdown(parsed.recommended_action);
      messageContent += formatExecutionSnapshotMarkdown(executionResultsForIncident, parsed.execution_type);

      if (
        !parsed.executive_summary &&
        (!parsed.root_cause || parsed.root_cause === 'Analysis in progress') &&
        !fullState.analysis
      ) {
        messageContent += `\n> **Note:** Detailed investigation fields were not found on this record. Remediation status below reflects automated workflow progress.\n`;
      }
    }
  }

  return {
    id: `incident-${parsed.incident_id}`,
    role: 'system',
    isUser: false,
    formatMarkdown: true,
    text: messageContent,
    timestamp: parsed.timestamp ? new Date(parsed.timestamp) : new Date(),
    incident: {
      incident_id: parsed.incident_id,
      source: parsed.source,
      service: parsed.service,
      severity: parsed.severity,
      root_cause: parsed.root_cause,
      confidence: parsed.confidence,
      alert_name: parsed.alert_name,
      alert_description: parsed.alert_description,
      executive_summary: parsed.executive_summary,
      recommended_action: parsed.recommended_action,
      execution_type: parsed.execution_type,
      execution_results: executionResultsForIncident,
      investigation_result: parsed.investigation_result,
      full_state: parsed.full_state
    }
  };
}
