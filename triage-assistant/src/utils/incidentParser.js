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
    
    // Extract execution results if available
    const executionResults = incidentData.execution_results || {};
    
    // Extract full_state if available (contains nested incident data)
    const fullState = incidentData.full_state || {};
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
      executive_summary: executiveSummary
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
      full_state: {}
    };
  }
}

/**
 * Convert DynamoDB incident item to chat message format
 * @param {object} incidentItem - Incident item from DynamoDB
 * @returns {object} Message object for chat UI
 */
export function incidentToMessage(incidentItem) {
  // Handle different data structures from DynamoDB
  let rawData = incidentItem;
  
  // If it's a DynamoDB item, extract the data field
  if (incidentItem.data) {
    rawData = typeof incidentItem.data === 'string' 
      ? JSON.parse(incidentItem.data) 
      : incidentItem.data;
  } else if (incidentItem.investigation_result) {
    rawData = typeof incidentItem.investigation_result === 'string'
      ? JSON.parse(incidentItem.investigation_result)
      : incidentItem.investigation_result;
  }
  
  const parsed = parseIncidentData(rawData);
  
  // Determine message content based on source
  const sourceLabel = parsed.source === 'cloudwatch_alarm' ? 'CloudWatch Alarm' : 'Chat';
  const alertName = parsed.alert_name || parsed.service || 'Unknown Alert';
  const alertDescription = parsed.alert_description || '';
  
  // Create a detailed message with incident analysis
  let messageContent = '';
  
  if (parsed.source === 'cloudwatch_alarm') {
    messageContent = `🔴 **${sourceLabel} Triggered: ${alertName}**\n\n`;
    
    if (alertDescription) {
      messageContent += `**Alert Details:**\n${alertDescription}\n\n`;
    }
    
    if (parsed.service) {
      messageContent += `**Service:** ${parsed.service}\n`;
    }
    
    if (parsed.severity) {
      messageContent += `**Severity:** ${parsed.severity}\n`;
    }
    
    // Show root cause or executive summary
    if (parsed.root_cause && parsed.root_cause !== 'Unknown' && parsed.root_cause !== 'Analysis in progress') {
      messageContent += `\n**Root Cause Analysis:**\n${parsed.root_cause}\n`;
    } else if (parsed.executive_summary) {
      messageContent += `\n**Analysis Summary:**\n${parsed.executive_summary}\n`;
    } else if (parsed.root_cause) {
      messageContent += `\n**Root Cause Analysis:**\n${parsed.root_cause}\n`;
    }
    
    if (parsed.confidence && parsed.confidence > 0) {
      messageContent += `\n**Confidence:** ${parsed.confidence}%\n`;
    }
    
    if (parsed.recommended_action) {
      if (typeof parsed.recommended_action === 'object') {
        const action = parsed.recommended_action;
        let actionText = '';
        if (action.action_type) {
          actionText += action.action_type.replace(/_/g, ' ') + '\n';
        }
        if (action.description) {
          actionText += action.description + '\n';
        }
        if (action.steps && action.steps.length > 0) {
          actionText += action.steps.map((step, i) => {
            const stepText = typeof step === 'string' ? step : (step.description || step.action || JSON.stringify(step));
            return `${i + 1}. ${stepText}`;
          }).join('\n') + '\n';
        }
        messageContent += `\n**Recommended Action:**\n${actionText || JSON.stringify(action)}\n`;
      } else {
        messageContent += `\n**Recommended Action:**\n${parsed.recommended_action}\n`;
      }
    }
    
    // If no detailed analysis is available, at least show that investigation is complete
    if (!parsed.root_cause && !parsed.executive_summary && !parsed.recommended_action) {
      messageContent += `\n**Status:** Incident investigation completed. Review the alarm details above for more information.\n`;
    }
    
  } else {
    messageContent = `💬 ${sourceLabel} Incident: ${alertName}`;
  }
  
  return {
    id: `incident-${parsed.incident_id}`,
    role: 'system',
    text: messageContent,  // MessageBubble expects 'text', not 'content'
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
      execution_type: parsed.execution_type,
      execution_results: parsed.execution_results,
      investigation_result: parsed.investigation_result,
      full_state: parsed.full_state
    }
  };
}
