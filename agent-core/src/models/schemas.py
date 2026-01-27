"""
Pydantic models for Agent Core

These models define the data structures used throughout the agent workflow.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


# ============================================
# Enums
# ============================================


class Severity(str, Enum):
    """Incident severity levels"""
    P1 = "P1"  # Critical - immediate action required
    P2 = "P2"  # High - action required soon
    P3 = "P3"  # Medium - can be scheduled
    P4 = "P4"  # Low - monitoring only


class InvestigationDecision(str, Enum):
    """Triage decision on whether to investigate"""
    INVESTIGATE = "INVESTIGATE"  # Proceed with full investigation
    MONITOR = "MONITOR"          # Create ticket but don't investigate
    LOG = "LOG"                  # Record for pattern analysis only


class RiskLevel(str, Enum):
    """Risk level for remediation actions"""
    LOW = "LOW"        # Safe to auto-execute
    MEDIUM = "MEDIUM"  # Requires approval
    HIGH = "HIGH"      # Requires senior approval
    CRITICAL = "CRITICAL"  # Do not auto-execute


class ExecutionType(str, Enum):
    """Type of execution for remediation"""
    AUTO_EXECUTE = "auto_execute"  # Execute via Lambda/AWS APIs
    CODE_FIX = "code_fix"          # Create GitHub issue
    ESCALATE = "escalate"           # Require human intervention


# ============================================
# Input Models
# ============================================


class IncidentEvent(BaseModel):
    """
    Incident event from CloudWatch alarm or manual trigger
    """
    incident_id: str = Field(..., description="Unique incident identifier")
    source: Optional[str] = Field(default="chat", description="Incident source: 'chat' or 'cloudwatch_alarm'")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Incident timestamp")

    # Service information
    service: str = Field(..., description="Affected service name")
    service_tier: str = Field(default="standard", description="Service tier (critical/important/standard)")

    # Alert information
    alert_name: str = Field(..., description="CloudWatch alarm name")
    alert_description: Optional[str] = Field(None, description="Alert description")

    # Metrics
    metric: str = Field(..., description="Metric name (e.g., p95_latency, error_rate)")
    value: float = Field(..., description="Current metric value")
    threshold: float = Field(..., description="Alarm threshold")
    unit: Optional[str] = Field(None, description="Metric unit")

    # AWS metadata
    log_group: Optional[str] = Field(None, description="CloudWatch Log Group")
    aws_account: Optional[str] = Field(None, description="AWS account ID")
    aws_region: str = Field(default="us-east-1", description="AWS region")

    # Additional context
    tags: Dict[str, str] = Field(default_factory=dict, description="Additional tags")
    raw_event: Dict[str, Any] = Field(default_factory=dict, description="Raw CloudWatch event")


# ============================================
# Agent Output Models
# ============================================


class TriageResult(BaseModel):
    """
    Output from Triage Agent
    """
    severity: Severity = Field(..., description="Incident severity")
    decision: InvestigationDecision = Field(..., description="Investigation decision")
    priority: int = Field(..., ge=1, le=10, description="Priority score (1-10, 10 is highest)")
    reasoning: str = Field(..., description="Explanation for severity assessment")

    # Context gathered
    recent_deployments: List[str] = Field(default_factory=list, description="Recent deployments")
    similar_incidents: List[str] = Field(default_factory=list, description="Similar past incidents")
    affected_customers: Optional[int] = Field(None, description="Estimated affected customers")


class LogQueryResult(BaseModel):
    """
    Single log query result
    """
    query: str = Field(..., description="CloudWatch Logs Insights query")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Query results")
    record_count: int = Field(default=0, description="Number of records returned")
    execution_time_ms: Optional[int] = Field(None, description="Query execution time")


class AnalysisResult(BaseModel):
    """
    Output from Analysis Agent
    """
    # Log findings
    log_queries: List[LogQueryResult] = Field(default_factory=list, description="Executed log queries")
    error_patterns: List[str] = Field(default_factory=list, description="Identified error patterns")
    error_count: int = Field(default=0, description="Total errors found")

    # Correlations
    correlated_services: List[str] = Field(default_factory=list, description="Related services affected")
    deployment_correlation: Optional[str] = Field(None, description="Deployment correlation if found")

    # Timing analysis
    incident_start: Optional[datetime] = Field(None, description="Estimated incident start time")
    incident_duration_minutes: Optional[int] = Field(None, description="Duration so far")

    # Key findings
    key_findings: List[str] = Field(default_factory=list, description="Important observations")
    summary: str = Field(..., description="Summary of analysis")


class DiagnosisResult(BaseModel):
    """
    Output from Diagnosis Agent
    """
    root_cause: str = Field(..., description="Most likely root cause")
    confidence: int = Field(..., ge=0, le=100, description="Confidence percentage (0-100)")

    # Evidence
    supporting_evidence: List[str] = Field(default_factory=list, description="Evidence supporting diagnosis")
    alternative_causes: List[str] = Field(default_factory=list, description="Other possible causes")

    # Details
    category: str = Field(..., description="Category (deployment, configuration, resource, code, dependency)")
    component: str = Field(..., description="Specific component involved")

    # Reasoning
    reasoning: str = Field(..., description="Detailed reasoning process")


class RemediationAction(BaseModel):
    """
    Single remediation action
    """
    action_type: str = Field(..., description="Type of action (restart, scale, rollback, config_change)")
    description: str = Field(..., description="Human-readable description")
    steps: List[str] = Field(default_factory=list, description="Step-by-step instructions")
    estimated_time_minutes: int = Field(..., description="Estimated time to execute")
    risk_level: RiskLevel = Field(..., description="Risk level")
    reversible: bool = Field(default=True, description="Whether action can be reversed")
    rollback_plan: Optional[str] = Field(None, description="How to rollback if needed")


class RemediationResult(BaseModel):
    """
    Output from Remediation Agent
    """
    recommended_action: RemediationAction = Field(..., description="Primary recommended action")
    alternative_actions: List[RemediationAction] = Field(default_factory=list, description="Alternative actions")

    # Execution categorization
    execution_type: ExecutionType = Field(..., description="How to execute this remediation")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata for execution")

    # Approval
    requires_approval: bool = Field(..., description="Whether human approval is needed")
    approval_reason: Optional[str] = Field(None, description="Reason why approval is needed")

    # Monitoring
    success_criteria: List[str] = Field(default_factory=list, description="How to verify success")
    monitoring_duration_minutes: int = Field(default=15, description="How long to monitor after")


# ============================================
# LangGraph State
# ============================================


class InvestigationState(BaseModel):
    """
    State object passed through LangGraph workflow
    """
    # Input
    incident: IncidentEvent = Field(..., description="Original incident event")

    # Agent outputs (populated as workflow progresses)
    triage: Optional[TriageResult] = Field(None, description="Triage result")
    analysis: Optional[AnalysisResult] = Field(None, description="Analysis result")
    diagnosis: Optional[DiagnosisResult] = Field(None, description="Diagnosis result")
    remediation: Optional[RemediationResult] = Field(None, description="Remediation result")

    # Execution results
    execution_results: Optional[Dict[str, Any]] = Field(
        None,
        description="Results from remediation execution"
    )

    # Workflow metadata
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Investigation start time")
    completed_at: Optional[datetime] = Field(None, description="Investigation completion time")
    current_step: str = Field(default="triage", description="Current workflow step")

    # Errors and warnings
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Warnings")

    class Config:
        arbitrary_types_allowed = True


# ============================================
# Final Output
# ============================================


class InvestigationResult(BaseModel):
    """
    Final result of complete investigation
    """
    incident_id: str = Field(..., description="Incident ID")
    service: str = Field(..., description="Service name")
    source: str = Field(default="chat", description="Incident source: 'chat' or 'cloudwatch_alarm'")

    # Results from each stage
    severity: Severity = Field(..., description="Final severity")
    root_cause: str = Field(..., description="Root cause")
    confidence: int = Field(..., ge=0, le=100, description="Confidence in diagnosis")
    recommended_action: RemediationAction = Field(..., description="Recommended action")

    # Timing
    investigation_duration_seconds: float = Field(..., description="Time taken for investigation")

    # Complete state
    full_state: InvestigationState = Field(..., description="Complete investigation state")

    # Summary for humans
    executive_summary: str = Field(..., description="Human-readable summary")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return self.model_dump()

    def to_json(self) -> str:
        """Convert to JSON string"""
        return self.model_dump_json(indent=2)
