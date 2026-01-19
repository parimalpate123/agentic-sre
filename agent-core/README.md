# Agent Core - LangGraph Orchestration

**Intelligent incident investigation using LangGraph and AWS Bedrock Claude**

## Overview

The Agent Core is the brain of the Agentic SRE system. It orchestrates multiple specialized agents using LangGraph to investigate incidents autonomously.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              LangGraph Workflow                      │
│                                                      │
│  START → Triage → Analysis → Diagnosis → Remediation → END
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Agents

1. **Triage Agent**: Assesses incident severity and priority
2. **Analysis Agent**: Queries logs via MCP, finds patterns
3. **Diagnosis Agent**: Determines root cause with confidence
4. **Remediation Agent**: Proposes safe fixes

## Quick Start

### Installation

```bash
cd agent-core
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Usage

```python
from agent_core import AgentCore
from mcp_client import MCPLogAnalyzerClient
import boto3

# Initialize clients
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
mcp_client = MCPLogAnalyzerClient('http://mcp-server.sre-poc.local:8000')

# Create agent
agent = AgentCore(
    bedrock_client=bedrock,
    mcp_client=mcp_client,
    model_id='anthropic.claude-sonnet-4-20250514'
)

# Investigate incident
incident = {
    'incident_id': 'inc-123',
    'service': 'api-service',
    'alert_name': 'HighLatency',
    'metric': 'p95_latency',
    'value': 2500,
    'threshold': 1000,
    'log_group': '/aws/lambda/api-service'
}

result = agent.investigate(incident)

print(f"Root Cause: {result.root_cause}")
print(f"Confidence: {result.confidence}%")
print(f"Remediation: {result.remediation}")
```

## Components

### 1. Models (`src/models/`)

Pydantic models for type safety:
- `IncidentEvent`: Input from CloudWatch alarm
- `TriageResult`: Severity assessment
- `AnalysisResult`: Log findings
- `DiagnosisResult`: Root cause hypothesis
- `RemediationResult`: Proposed fix
- `InvestigationState`: LangGraph state

### 2. Prompts (`src/prompts/`)

Carefully crafted prompts for each agent:
- System prompts
- Few-shot examples
- Template variables

### 3. Agents (`src/agents/`)

Individual agent implementations:
- `triage.py`: Severity assessment
- `analysis.py`: Log investigation
- `diagnosis.py`: Root cause determination
- `remediation.py`: Fix proposals

### 4. Orchestrator (`src/orchestrator/`)

LangGraph workflow:
- State machine definition
- Agent coordination
- Error handling
- Logging

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test
pytest tests/unit/test_triage.py
```

## Development

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Configuration

Environment variables:
- `BEDROCK_MODEL_ID`: Claude model to use (default: anthropic.claude-sonnet-4-20250514)
- `BEDROCK_REGION`: AWS region for Bedrock (default: us-east-1)
- `LOG_LEVEL`: Logging level (default: INFO)

## Dependencies

- **LangGraph**: Agent orchestration
- **LangChain**: LLM abstractions
- **Boto3**: AWS SDK
- **Pydantic**: Data validation

## Project Structure

```
agent-core/
├── src/
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── workflow.py         # LangGraph workflow
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── triage.py          # Triage agent
│   │   ├── analysis.py        # Analysis agent
│   │   ├── diagnosis.py       # Diagnosis agent
│   │   └── remediation.py     # Remediation agent
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── agent_prompts.py   # All prompts
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic models
│   └── agent_core.py          # Main API
├── tests/
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
├── requirements.txt
└── README.md
```

## License

Apache 2.0
