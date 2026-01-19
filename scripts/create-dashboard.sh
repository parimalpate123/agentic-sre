#!/bin/bash
# Create CloudWatch Dashboard for Agentic SRE Observability

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}📊 Creating Agentic SRE Observability Dashboard${NC}"
echo "================================================"
echo ""

AWS_REGION="us-east-1"
DASHBOARD_NAME="agentic-sre-observability"
LAMBDA_NAME="sre-poc-incident-handler"
ECS_CLUSTER="sre-poc-mcp-cluster"
ECS_SERVICE="sre-poc-mcp-server"
LAMBDA_LOG_GROUP="/aws/lambda/sre-poc-incident-handler"
MCP_LOG_GROUP="/ecs/sre-poc-mcp-server"

echo -e "${YELLOW}Creating dashboard: $DASHBOARD_NAME${NC}"

# Create dashboard JSON
cat > /tmp/dashboard.json <<EOF
{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# Agentic SRE System - Live Observability\\n\\n**Architecture Flow:** CloudWatch Alarm → EventBridge → Lambda (Chat/Incident) → MCP Server → CloudWatch Logs + Bedrock + DynamoDB\\n\\nLast Updated: $(date)"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Invocations", { "stat": "Sum", "label": "Total Requests" } ],
          [ ".", ".", { "stat": "Sum", "label": "Success", "color": "#2ca02c" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$AWS_REGION",
        "title": "Lambda Invocations",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 8,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Errors", { "stat": "Sum", "color": "#d62728" } ],
          [ ".", "Throttles", { "stat": "Sum", "color": "#ff7f0e" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$AWS_REGION",
        "title": "Lambda Errors & Throttles",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Duration", { "stat": "Average", "label": "Avg Duration" } ],
          [ "...", { "stat": "p50", "label": "P50" } ],
          [ "...", { "stat": "p90", "label": "P90" } ],
          [ "...", { "stat": "p99", "label": "P99", "color": "#d62728" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$AWS_REGION",
        "title": "Lambda Duration (ms)",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Milliseconds"
          }
        }
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "query": "SOURCE '$LAMBDA_LOG_GROUP'\\n| fields @timestamp, @message\\n| filter @message like /Router received|Routing to|chat_handler|incident_handler/\\n| sort @timestamp desc\\n| limit 20",
        "region": "$AWS_REGION",
        "title": "Lambda Request Routing (Last 20)",
        "stacked": false
      }
    },
    {
      "type": "log",
      "x": 12,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "query": "SOURCE '$LAMBDA_LOG_GROUP'\\n| fields @timestamp, @message\\n| filter @message like /TRIAGE|ANALYSIS|DIAGNOSIS|REMEDIATION/\\n| parse @message /\\\\[(?<agent>\\\\w+)\\\\]/\\n| sort @timestamp desc\\n| limit 20",
        "region": "$AWS_REGION",
        "title": "Agent Execution Flow (Last 20)",
        "stacked": false
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/ECS", "CPUUtilization", { "stat": "Average" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$AWS_REGION",
        "title": "MCP Server CPU Utilization",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Percent",
            "min": 0,
            "max": 100
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 8,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/ECS", "MemoryUtilization", { "stat": "Average" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$AWS_REGION",
        "title": "MCP Server Memory Utilization",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Percent",
            "min": 0,
            "max": 100
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/ECS", "RunningTaskCount", { "stat": "Average" } ],
          [ ".", "DesiredTaskCount", { "stat": "Average", "color": "#2ca02c" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$AWS_REGION",
        "title": "MCP Server Task Count",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 20,
      "width": 12,
      "height": 6,
      "properties": {
        "query": "SOURCE '$MCP_LOG_GROUP'\\n| fields @timestamp, @message\\n| filter @message like /POST|GET|search_logs|health/\\n| sort @timestamp desc\\n| limit 20",
        "region": "$AWS_REGION",
        "title": "MCP Server Requests (Last 20)",
        "stacked": false
      }
    },
    {
      "type": "log",
      "x": 12,
      "y": 20,
      "width": 12,
      "height": 6,
      "properties": {
        "query": "SOURCE '$LAMBDA_LOG_GROUP'\\n| fields @timestamp, @message\\n| filter @message like /ERROR|Exception|Failed|Error/\\n| sort @timestamp desc\\n| limit 20",
        "region": "$AWS_REGION",
        "title": "System Errors (Last 20)",
        "stacked": false
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 26,
      "width": 24,
      "height": 6,
      "properties": {
        "query": "SOURCE '$LAMBDA_LOG_GROUP'\\n| fields @timestamp, @message\\n| filter @message like /Chat query|question|answer/\\n| sort @timestamp desc\\n| limit 10",
        "region": "$AWS_REGION",
        "title": "Recent Chat Queries (Last 10)",
        "stacked": false
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 32,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "ConcurrentExecutions", { "stat": "Maximum" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$AWS_REGION",
        "title": "Lambda Concurrent Executions",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    },
    {
      "type": "log",
      "x": 12,
      "y": 32,
      "width": 12,
      "height": 6,
      "properties": {
        "query": "SOURCE '$LAMBDA_LOG_GROUP'\\n| fields @timestamp, @duration, @billedDuration, @maxMemoryUsed\\n| filter @type = \\"REPORT\\"\\n| stats avg(@duration) as avg_duration, max(@duration) as max_duration, avg(@maxMemoryUsed)/1024/1024 as avg_memory_mb by bin(5m)\\n| sort bin desc\\n| limit 20",
        "region": "$AWS_REGION",
        "title": "Lambda Performance Stats (5min bins)",
        "stacked": false
      }
    }
  ]
}
EOF

# Create or update dashboard
echo ""
echo "Creating dashboard..."
aws cloudwatch put-dashboard \
    --dashboard-name "$DASHBOARD_NAME" \
    --dashboard-body file:///tmp/dashboard.json \
    --region $AWS_REGION > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Dashboard created successfully!${NC}"
else
    echo -e "${RED}❌ Failed to create dashboard${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Dashboard is ready!${NC}"
echo ""
echo "View your dashboard:"
echo -e "${BLUE}https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#dashboards:name=$DASHBOARD_NAME${NC}"
echo ""
echo "Dashboard includes:"
echo "  📈 Lambda invocations, errors, duration (P50/P90/P99)"
echo "  🖥️  MCP Server CPU, memory, task count"
echo "  📝 Request routing logs (Chat vs Incident)"
echo "  🤖 Agent execution flow (Triage → Analysis → Diagnosis → Remediation)"
echo "  🔍 MCP server requests"
echo "  ⚠️  System errors"
echo "  💬 Recent chat queries"
echo "  ⚡ Lambda performance stats"
echo ""
echo "Pro tip: Click 'Auto refresh' in the dashboard and set to 1 minute for live monitoring!"
echo ""
