"""
LangGraph Orchestrator - Coordinates the agent workflow
"""

import os
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

import boto3

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from models.schemas import (
    IncidentEvent,
    InvestigationState,
    InvestigationResult,
    InvestigationDecision,
    ExecutionType,
    RemediationResult,
    DiagnosisResult
)
from agents import TriageAgent, AnalysisAgent, DiagnosisAgent, RemediationAgent
from integrations.github_client import GitHubClient

logger = logging.getLogger(__name__)


class InvestigationOrchestrator:
    """
    Orchestrates the multi-agent investigation workflow using LangGraph
    """

    def __init__(
        self,
        bedrock_client,
        mcp_client,
        model_id: str = "anthropic.claude-sonnet-4-20250514"
    ):
        """
        Initialize orchestrator with agents

        Args:
            bedrock_client: Boto3 Bedrock Runtime client
            mcp_client: MCP Log Analyzer client
            model_id: Bedrock model ID to use
        """
        self.bedrock_client = bedrock_client
        self.mcp_client = mcp_client
        self.model_id = model_id

        # Initialize agents
        self.triage_agent = TriageAgent(bedrock_client, model_id)
        self.analysis_agent = AnalysisAgent(bedrock_client, mcp_client, model_id)
        self.diagnosis_agent = DiagnosisAgent(bedrock_client, model_id)
        self.remediation_agent = RemediationAgent(bedrock_client, model_id)

        # Initialize GitHub client (optional - only if token provided)
        self.github_client = None
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            try:
                self.github_client = GitHubClient(github_token)
                logger.info("GitHub client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub client: {e}")

        # Build workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph workflow for investigation

        Returns:
            Compiled StateGraph
        """
        # Create state graph
        workflow = StateGraph(InvestigationState)

        # Add nodes for each agent (node names must not conflict with state field names)
        workflow.add_node("run_triage", self._triage_node)
        workflow.add_node("run_analysis", self._analysis_node)
        workflow.add_node("run_diagnosis", self._diagnosis_node)
        workflow.add_node("run_remediation", self._remediation_node)
        workflow.add_node("execute_remediation", self._execution_node)

        # Define edges
        workflow.set_entry_point("run_triage")

        # Conditional edge after triage
        workflow.add_conditional_edges(
            "run_triage",
            self._should_investigate,
            {
                "analyze": "run_analysis",
                "skip": END
            }
        )

        # Linear flow for investigation
        workflow.add_edge("run_analysis", "run_diagnosis")
        workflow.add_edge("run_diagnosis", "run_remediation")
        workflow.add_edge("run_remediation", "execute_remediation")
        workflow.add_edge("execute_remediation", END)

        # Compile with memory checkpointing
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)

    def _triage_node(self, state: InvestigationState) -> dict:
        """
        Triage node - assess incident severity

        Args:
            state: Current investigation state (read with attributes for type safety)

        Returns:
            Dict with updated fields (LangGraph convention)
        """
        logger.info(f"[TRIAGE] Starting triage for incident {state.incident.incident_id}")

        updates = {"current_step": "triage"}

        try:
            triage_result = self.triage_agent.assess(state.incident)
            updates["triage"] = triage_result

            logger.info(
                f"[TRIAGE] Complete: {triage_result.severity.value} - {triage_result.decision.value}"
            )

        except Exception as e:
            logger.error(f"[TRIAGE] Error: {str(e)}", exc_info=True)
            errors = list(state.errors) if state.errors else []
            errors.append(f"Triage failed: {str(e)}")
            updates["errors"] = errors

        return updates

    def _should_investigate(self, state: InvestigationState) -> str:
        """
        Conditional edge: decide whether to investigate

        Args:
            state: Current investigation state (Pydantic model - use attribute access)

        Returns:
            "analyze" to continue or "skip" to end
        """
        if not state.triage:
            logger.warning("[ROUTER] No triage result, defaulting to investigate")
            return "analyze"

        decision = state.triage.decision

        # Always investigate chat-triggered incidents (user explicitly requested investigation)
        raw_event = state.incident.raw_event or {}
        is_chat_query = raw_event.get('source') == 'chat_query'
        
        if is_chat_query:
            logger.info("[ROUTER] Chat-triggered incident - proceeding to investigation regardless of triage decision")
            return "analyze"

        if decision == InvestigationDecision.INVESTIGATE:
            logger.info("[ROUTER] Decision: INVESTIGATE - proceeding to analysis")
            return "analyze"
        else:
            logger.info(f"[ROUTER] Decision: {decision.value} - skipping investigation")
            return "skip"

    async def _analysis_node(self, state: InvestigationState) -> dict:
        """
        Analysis node - query logs via MCP

        Args:
            state: Current investigation state (read with attributes for type safety)

        Returns:
            Dict with updated fields (LangGraph convention)
        """
        logger.info(f"[ANALYSIS] Starting log analysis for incident {state.incident.incident_id}")

        updates = {"current_step": "analysis"}

        try:
            analysis_result = await self.analysis_agent.analyze(
                state.incident,
                state.triage
            )
            updates["analysis"] = analysis_result

            logger.info(
                f"[ANALYSIS] Complete: {len(analysis_result.error_patterns)} patterns, "
                f"{analysis_result.error_count} errors"
            )

        except Exception as e:
            logger.error(f"[ANALYSIS] Error: {str(e)}", exc_info=True)
            errors = list(state.errors) if state.errors else []
            errors.append(f"Analysis failed: {str(e)}")
            updates["errors"] = errors

        return updates

    def _diagnosis_node(self, state: InvestigationState) -> dict:
        """
        Diagnosis node - determine root cause

        Args:
            state: Current investigation state (read with attributes for type safety)

        Returns:
            Dict with updated fields (LangGraph convention)
        """
        logger.info(f"[DIAGNOSIS] Starting diagnosis for incident {state.incident.incident_id}")

        updates = {"current_step": "diagnosis"}

        try:
            # Safely extract analysis result - LangGraph might pass it as dict or object
            analysis = state.analysis
            if analysis is None:
                logger.error("[DIAGNOSIS] No analysis result available, cannot diagnose")
                raise ValueError("Analysis result is missing")
            
            # Log the type for debugging
            logger.debug(f"[DIAGNOSIS] analysis type: {type(analysis)}")
            
            # Ensure incident is properly typed
            incident = state.incident
            logger.debug(f"[DIAGNOSIS] incident type: {type(incident)}")
            
            diagnosis_result = self.diagnosis_agent.diagnose(
                incident,
                analysis
            )
            updates["diagnosis"] = diagnosis_result

            logger.info(
                f"[DIAGNOSIS] Complete: {diagnosis_result.root_cause} "
                f"({diagnosis_result.confidence}% confidence)"
            )

        except Exception as e:
            logger.error(f"[DIAGNOSIS] Error: {str(e)}", exc_info=True)
            errors = list(state.errors) if state.errors else []
            errors.append(f"Diagnosis failed: {str(e)}")
            updates["errors"] = errors

        return updates

    def _remediation_node(self, state: InvestigationState) -> dict:
        """
        Remediation node - propose fixes

        Args:
            state: Current investigation state (read with attributes for type safety)

        Returns:
            Dict with updated fields (LangGraph convention)
        """
        logger.info(f"[REMEDIATION] Proposing remediation for incident {state.incident.incident_id}")

        updates = {"current_step": "remediation"}

        try:
            # Ensure we have a diagnosis (remediation needs it)
            if not state.diagnosis:
                from models.schemas import DiagnosisResult
                logger.warning("[REMEDIATION] No diagnosis available, using fallback")
                state.diagnosis = DiagnosisResult(
                    root_cause="Unknown - diagnosis unavailable",
                    confidence=0,
                    category="UNKNOWN",
                    component="unknown",
                    supporting_evidence=[],
                    alternative_causes=[],
                    reasoning="Diagnosis step failed or was skipped"
                )
            
            remediation_result = self.remediation_agent.propose_remediation(
                state.incident,
                state.diagnosis
            )
            updates["remediation"] = remediation_result

            logger.info(
                f"[REMEDIATION] Complete: {remediation_result.recommended_action.action_type} "
                f"(requires approval: {remediation_result.requires_approval})"
            )

        except Exception as e:
            logger.error(f"[REMEDIATION] Error: {str(e)}", exc_info=True)
            errors = list(state.errors) if state.errors else []
            errors.append(f"Remediation failed: {str(e)}")
            updates["errors"] = errors
            
            # Provide fallback remediation result even on error
            from models.schemas import RemediationResult, RemediationAction, RiskLevel
            updates["remediation"] = RemediationResult(
                recommended_action=RemediationAction(
                    action_type="monitor_and_escalate",
                    description=f"Remediation failed: {str(e)}. Manual investigation required.",
                    steps=["Review error logs", "Contact SRE team", "Check service status"],
                    estimated_time_minutes=30,
                    risk_level=RiskLevel.LOW,
                    rollback_plan="No action taken, nothing to rollback"
                ),
                alternative_actions=[],
                requires_approval=True,
                approval_reason=f"Remediation agent error: {str(e)}",
                success_criteria=["Manual verification by SRE"],
                monitoring_duration_minutes=60,
                execution_type=ExecutionType.ESCALATE,
                execution_metadata={"reason": f"Remediation agent error: {str(e)}"}
            )

        return updates

    def _execution_node(self, state: InvestigationState) -> dict:
        """
        Execute remediation based on execution type

        Args:
            state: Current investigation state

        Returns:
            Dict with execution results
        """
        logger.info(f"[EXECUTION] Executing remediation for incident {state.incident.incident_id}")

        updates = {"current_step": "execution"}
        execution_results = {}

        if not state.remediation:
            logger.warning("[EXECUTION] No remediation result, skipping execution")
            return updates

        execution_type = state.remediation.execution_type
        metadata = state.remediation.execution_metadata

        try:
            if execution_type == ExecutionType.AUTO_EXECUTE:
                result = self._execute_auto_action(state.incident, state.remediation, metadata)
                execution_results['auto_execute'] = result
                logger.info(f"[EXECUTION] Auto-executed: {result.get('status')}")

            elif execution_type == ExecutionType.CODE_FIX:
                result = self._create_github_issue(state.incident, state.diagnosis, state.remediation, metadata)
                execution_results['github_issue'] = result
                logger.info(f"[EXECUTION] Created GitHub issue: {result.get('issue_url', 'N/A')}")

            elif execution_type == ExecutionType.ESCALATE:
                result = self._escalate_to_human(state.incident, state.remediation, metadata)
                execution_results['escalation'] = result
                logger.info(f"[EXECUTION] Escalated: {result.get('reason')}")

            updates['execution_results'] = execution_results

        except Exception as e:
            logger.error(f"[EXECUTION] Error: {str(e)}", exc_info=True)
            errors = list(state.errors) if state.errors else []
            errors.append(f"Execution failed: {str(e)}")
            updates["errors"] = errors
            execution_results['error'] = str(e)
            updates['execution_results'] = execution_results

        return updates

    def _execute_auto_action(
        self,
        incident: IncidentEvent,
        remediation: RemediationResult,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute auto-execute actions via AWS APIs

        Args:
            incident: Incident event
            remediation: Remediation result
            metadata: Execution metadata

        Returns:
            Execution result
        """
        action_type = remediation.recommended_action.action_type.lower()
        service = metadata.get('service', incident.service)
        region = metadata.get('region', incident.aws_region)

        # Check if service exists before attempting execution
        service_exists = self._check_service_exists(service, region)
        if not service_exists:
            logger.info(f"Service {service} does not exist - auto-execution not implemented for this environment")
            
            # Build detailed message based on action type
            if 'restart' in action_type:
                action_description = (
                    f"When implemented, this will automatically restart the {service} service by: "
                    f"(1) Identifying the service type (ECS or Lambda), "
                    f"(2) For ECS: triggering a force new deployment to restart all tasks, "
                    f"(3) For Lambda: updating environment variables to trigger a restart, "
                    f"(4) Verifying the service returns to healthy state. "
                    f"This will resolve transient issues and restore service availability."
                )
            elif 'scale' in action_type:
                desired_count = metadata.get('desired_count', 'increased')
                action_description = (
                    f"When implemented, this will automatically scale the {service} service by: "
                    f"(1) Identifying the current desired count, "
                    f"(2) Calculating optimal scale based on incident severity and load, "
                    f"(3) Updating the ECS service desired count, "
                    f"(4) Monitoring the scaling operation until completion. "
                    f"This will increase capacity to handle increased load or traffic spikes."
                )
            elif 'rollback' in action_type:
                action_description = (
                    f"When implemented, this will automatically rollback the {service} service by: "
                    f"(1) Identifying the previous stable deployment version, "
                    f"(2) Updating the service to use the previous task definition, "
                    f"(3) Triggering a new deployment with the rollback version, "
                    f"(4) Verifying the service returns to stable state. "
                    f"This will revert problematic deployments that caused the incident."
                )
            else:
                action_description = (
                    f"When implemented, this will automatically execute the recommended remediation action "
                    f"for the {service} service. The system will: "
                    f"(1) Validate the action is safe to execute, "
                    f"(2) Perform the remediation via AWS APIs, "
                    f"(3) Monitor the service health post-execution, "
                    f"(4) Report success or escalate if issues persist."
                )
            
            return {
                'status': 'not_implemented',
                'action': action_type,
                'service': service,
                'message': f'Auto-execution is not yet implemented for this service. This feature is coming soon. {action_description}'
            }

        try:
            if 'restart' in action_type:
                # Restart ECS service or Lambda
                result = self._restart_service(service, region)
                return {
                    'status': 'success',
                    'action': 'restart',
                    'service': service,
                    'result': result
                }

            elif 'scale' in action_type:
                # Scale service
                result = self._scale_service(service, region, metadata)
                return {
                    'status': 'success',
                    'action': 'scale',
                    'service': service,
                    'result': result
                }

            else:
                return {
                    'status': 'skipped',
                    'reason': f'Unknown action type: {action_type}'
                }

        except Exception as e:
            logger.error(f"Auto-execute failed: {e}")
            return {
                'status': 'failed',
                'action': action_type,
                'service': service,
                'error': str(e)
            }

    def _restart_service(self, service_name: str, region: str) -> Dict[str, Any]:
        """Restart ECS service or Lambda function"""
        try:
            # Try ECS first
            ecs = boto3.client('ecs', region_name=region)
            cluster = self._get_cluster_for_service(service_name)
            service_name_ecs = f"{service_name}-service"

            try:
                # Force new deployment (restarts tasks)
                response = ecs.update_service(
                    cluster=cluster,
                    service=service_name_ecs,
                    forceNewDeployment=True
                )
                return {
                    'type': 'ecs',
                    'cluster': cluster,
                    'service': service_name_ecs,
                    'deployment_id': response['service']['deployments'][0]['id']
                }
            except ecs.exceptions.ServiceNotFoundException:
                # Try Lambda
                lambda_client = boto3.client('lambda', region_name=region)
                function_name = f"{service_name}-handler"

                # Update environment to trigger restart
                config = lambda_client.get_function_configuration(FunctionName=function_name)
                env_vars = config.get('Environment', {}).get('Variables', {})
                env_vars['_RESTART_TRIGGER'] = str(int(time.time()))

                lambda_client.update_function_configuration(
                    FunctionName=function_name,
                    Environment={'Variables': env_vars}
                )
                return {
                    'type': 'lambda',
                    'function': function_name,
                    'restarted': True
                }

        except Exception as e:
            logger.error(f"Failed to restart service {service_name}: {e}")
            raise

    def _scale_service(self, service_name: str, region: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Scale ECS service"""
        try:
            ecs = boto3.client('ecs', region_name=region)
            cluster = self._get_cluster_for_service(service_name)
            service_name_ecs = f"{service_name}-service"

            # Get current desired count
            service = ecs.describe_services(cluster=cluster, services=[service_name_ecs])
            current_count = service['services'][0]['desiredCount']

            # Scale up by 50% (or use metadata if provided)
            new_count = metadata.get('desired_count', max(1, int(current_count * 1.5)))

            response = ecs.update_service(
                cluster=cluster,
                service=service_name_ecs,
                desiredCount=new_count
            )

            return {
                'cluster': cluster,
                'service': service_name_ecs,
                'old_count': current_count,
                'new_count': new_count
            }

        except Exception as e:
            logger.error(f"Failed to scale service {service_name}: {e}")
            raise

    def _get_cluster_for_service(self, service_name: str) -> str:
        """Get ECS cluster name for service"""
        # Default cluster name pattern
        return os.environ.get('ECS_CLUSTER', f'{service_name}-cluster')

    def _check_service_exists(self, service_name: str, region: str) -> bool:
        """
        Check if service exists in AWS (ECS or Lambda)
        
        Args:
            service_name: Service name
            region: AWS region
            
        Returns:
            True if service exists, False otherwise
        """
        try:
            # Check ECS first
            ecs = boto3.client('ecs', region_name=region)
            cluster = self._get_cluster_for_service(service_name)
            service_name_ecs = f"{service_name}-service"
            
            try:
                ecs.describe_services(
                    cluster=cluster,
                    services=[service_name_ecs]
                )
                logger.info(f"Service {service_name} found in ECS")
                return True
            except ecs.exceptions.ServiceNotFoundException:
                # Check Lambda
                lambda_client = boto3.client('lambda', region_name=region)
                function_name = f"{service_name}-handler"
                
                try:
                    lambda_client.get_function(FunctionName=function_name)
                    logger.info(f"Service {service_name} found as Lambda function")
                    return True
                except lambda_client.exceptions.ResourceNotFoundException:
                    logger.info(f"Service {service_name} not found in ECS or Lambda")
                    return False
                    
        except Exception as e:
            logger.warning(f"Error checking if service exists: {e}")
            # On error, assume service doesn't exist (safer - will show not_implemented)
            return False

    def _create_github_issue(
        self,
        incident: IncidentEvent,
        diagnosis: DiagnosisResult,
        remediation: RemediationResult,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create GitHub issue for code fix

        Args:
            incident: Incident event
            diagnosis: Diagnosis result
            remediation: Remediation result
            metadata: Execution metadata (includes repo)

        Returns:
            Issue creation result
        """
        repo = metadata.get('repo')
        if not repo:
            return {
                'status': 'failed',
                'error': 'No repository mapping found'
            }

        if not self.github_client:
            return {
                'status': 'failed',
                'error': 'GitHub client not initialized (GITHUB_TOKEN not set)'
            }

        try:
            # Format issue body
            issue_body = self._format_github_issue_body(incident, diagnosis, remediation)

            # Create issue
            issue_url = self.github_client.create_issue(
                repo=repo,
                title=f"Fix: {diagnosis.root_cause} - {incident.incident_id}",
                body=issue_body,
                labels=["auto-fix", f"incident-{incident.incident_id}"]
            )

            return {
                'status': 'success',
                'issue_url': issue_url,
                'repo': repo,
                'issue_number': self.github_client._extract_issue_number(issue_url)
            }

        except Exception as e:
            logger.error(f"GitHub issue creation failed: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }

    def _format_github_issue_body(
        self,
        incident: IncidentEvent,
        diagnosis: DiagnosisResult,
        remediation: RemediationResult
    ) -> str:
        """Format GitHub issue body with incident context"""
        # Get log entries from raw event
        log_entries = incident.raw_event.get('log_entries', [])[:10]
        log_summary = ""
        if log_entries:
            for entry in log_entries:
                message = entry.get('@message', entry.get('message', str(entry)))
                log_summary += f"{message}\n"

        # Get error patterns
        error_patterns = getattr(diagnosis, 'error_patterns', [])
        if not error_patterns and hasattr(diagnosis, 'supporting_evidence'):
            error_patterns = diagnosis.supporting_evidence

        return f"""## Incident: {incident.incident_id}

### Service
{incident.service}

### Root Cause
{diagnosis.root_cause}
Confidence: {diagnosis.confidence}%

### Error Patterns
{', '.join(error_patterns) if error_patterns else 'N/A'}

### Recommended Fix
{remediation.recommended_action.description}

### Steps
{chr(10).join(f"1. {step}" for step in remediation.recommended_action.steps)}

### Relevant Logs
```
{log_summary or 'No log entries available'}
```

### Context
- Incident Time: {incident.timestamp}
- Affected Components: {diagnosis.component}
- Correlation ID: {incident.raw_event.get('correlation_id', 'N/A')}
- Service Tier: {incident.service_tier}

---
**Auto-generated by Remediation Agent**
"""

    def _escalate_to_human(
        self,
        incident: IncidentEvent,
        remediation: RemediationResult,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Escalate to human for complex cases

        Args:
            incident: Incident event
            remediation: Remediation result
            metadata: Execution metadata

        Returns:
            Escalation result
        """
        # For MVP: Just log escalation
        # Future: Create ticket, send notification, etc.
        logger.warning(
            f"ESCALATION REQUIRED for incident {incident.incident_id}: "
            f"{metadata.get('reason', 'Complex remediation required')}"
        )

        return {
            'status': 'escalated',
            'reason': metadata.get('reason', 'Complex remediation required'),
            'incident_id': incident.incident_id,
            'action_required': remediation.recommended_action.description,
            'note': 'Escalation logged. Manual intervention required.'
        }

    async def investigate(self, incident: IncidentEvent) -> InvestigationResult:
        """
        Run complete investigation workflow

        Args:
            incident: Incident to investigate

        Returns:
            InvestigationResult with complete findings
        """
        logger.info(f"Starting investigation for incident {incident.incident_id}")

        start_time = datetime.utcnow()

        # Initialize state
        initial_state = InvestigationState(
            incident=incident,
            started_at=start_time
        )

        try:
            # Run workflow
            final_state = await self.workflow.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": incident.incident_id}}
            )

            # Mark completion
            final_state.completed_at = datetime.utcnow()
            duration = (final_state.completed_at - start_time).total_seconds()

            # Build result
            result = self._build_result(final_state, duration)

            logger.info(
                f"Investigation complete for {incident.incident_id} in {duration:.1f}s: "
                f"{result.root_cause} (confidence: {result.confidence}%)"
            )

            return result

        except Exception as e:
            logger.error(f"Investigation failed: {str(e)}", exc_info=True)
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Return error result
            return self._build_error_result(incident, str(e), duration)

    def _build_result(
        self,
        state: dict,
        duration: float
    ) -> InvestigationResult:
        """
        Build final investigation result

        Args:
            state: Final investigation state (dict from LangGraph)
            duration: Investigation duration in seconds

        Returns:
            InvestigationResult
        """
        # Extract key information using dict access (LangGraph returns AddableValuesDict)
        triage = state.get("triage")
        diagnosis = state.get("diagnosis")
        remediation = state.get("remediation")
        incident = state.get("incident")

        severity = triage.severity if triage else "P3"
        root_cause = diagnosis.root_cause if diagnosis else "Unknown"
        confidence = diagnosis.confidence if diagnosis else 0
        
        # Ensure we always have a valid RemediationAction (required by schema)
        if remediation and remediation.recommended_action:
            recommended_action = remediation.recommended_action
        else:
            # Fallback action when remediation fails or is missing
            from models.schemas import RemediationAction, RiskLevel
            recommended_action = RemediationAction(
                action_type="monitor_and_escalate",
                description="Remediation analysis unavailable. Manual investigation required.",
                steps=[
                    "Review incident logs and metrics",
                    "Check service health and dependencies",
                    "Escalate to SRE team if issue persists"
                ],
                estimated_time_minutes=30,
                risk_level=RiskLevel.LOW,
                rollback_plan="No action taken, nothing to rollback"
            )
            logger.warning("Remediation unavailable, using fallback action")

        # Build executive summary
        summary = self._build_summary(state)

        # Convert state dict back to InvestigationState for storage
        state_obj = InvestigationState(**state)

        return InvestigationResult(
            incident_id=incident.incident_id,
            service=incident.service,
            severity=severity,
            root_cause=root_cause,
            confidence=confidence,
            recommended_action=recommended_action,
            investigation_duration_seconds=duration,
            full_state=state_obj,
            executive_summary=summary
        )

    def _build_summary(self, state: dict) -> str:
        """
        Build executive summary for humans

        Args:
            state: Final investigation state (dict from LangGraph)

        Returns:
            Human-readable summary
        """
        # Use dict access for LangGraph state
        incident = state.get("incident")
        triage = state.get("triage")
        analysis = state.get("analysis")
        diagnosis = state.get("diagnosis")
        remediation = state.get("remediation")
        errors = state.get("errors", [])

        lines = [
            f"INCIDENT INVESTIGATION: {incident.incident_id}",
            f"Service: {incident.service}",
            ""
        ]

        if triage:
            lines.append(f"SEVERITY: {triage.severity.value}")
            lines.append(f"Decision: {triage.decision.value}")
            lines.append(f"Reasoning: {triage.reasoning}")
            lines.append("")

        if analysis:
            lines.append(f"LOG ANALYSIS:")
            lines.append(f"- Error count: {analysis.error_count}")
            lines.append(f"- Patterns: {', '.join(analysis.error_patterns[:3])}")
            lines.append(f"- Summary: {analysis.summary}")
            lines.append("")

        if diagnosis:
            lines.append(f"ROOT CAUSE ({diagnosis.confidence}% confidence):")
            lines.append(f"- {diagnosis.root_cause}")
            lines.append(f"- Category: {diagnosis.category}")
            lines.append(f"- Component: {diagnosis.component}")
            lines.append("")

        if remediation:
            action = remediation.recommended_action
            lines.append(f"RECOMMENDED ACTION:")
            lines.append(f"- {action.description}")
            lines.append(f"- Type: {action.action_type}")
            lines.append(f"- Risk: {action.risk_level.value}")
            lines.append(f"- Requires approval: {remediation.requires_approval}")

        if errors:
            lines.append("")
            lines.append("ERRORS:")
            for error in errors:
                lines.append(f"- {error}")

        return "\n".join(lines)

    def _build_error_result(
        self,
        incident: IncidentEvent,
        error: str,
        duration: float
    ) -> InvestigationResult:
        """
        Build error result when investigation fails

        Args:
            incident: Original incident
            error: Error message
            duration: Duration before failure

        Returns:
            InvestigationResult with error info
        """
        from models.schemas import RemediationAction, RiskLevel, Severity

        # Create minimal state
        error_state = InvestigationState(
            incident=incident,
            errors=[error]
        )

        return InvestigationResult(
            incident_id=incident.incident_id,
            service=incident.service,
            severity=Severity.P2,
            root_cause=f"Investigation failed: {error}",
            confidence=0,
            recommended_action=RemediationAction(
                action_type="escalate",
                description="Manual investigation required due to system error",
                steps=["Review error logs", "Contact SRE team"],
                estimated_time_minutes=30,
                risk_level=RiskLevel.LOW,
                reversible=True
            ),
            investigation_duration_seconds=duration,
            full_state=error_state,
            executive_summary=f"Investigation failed: {error}"
        )
