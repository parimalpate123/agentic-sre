"""
LangGraph Orchestrator - Coordinates the agent workflow
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from models.schemas import (
    IncidentEvent,
    InvestigationState,
    InvestigationResult,
    InvestigationDecision
)
from agents import TriageAgent, AnalysisAgent, DiagnosisAgent, RemediationAgent

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
        workflow.add_edge("run_remediation", END)

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
            diagnosis_result = self.diagnosis_agent.diagnose(
                state.incident,
                state.analysis
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

        return updates

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
        recommended_action = (
            remediation.recommended_action if remediation
            else None
        )

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
