#!/bin/bash
# Build script for Lambda deployment package

set -e

echo "Building Lambda deployment package..."

# Clean previous builds
rm -rf package
rm -f lambda-deployment.zip

# Create package directory
mkdir -p package

# Install dependencies for Linux x86_64 (Lambda runtime)
echo "Installing dependencies for Linux x86_64 (Lambda runtime)..."
# Use pip3 for Mac compatibility, install for correct platform
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt -t package/ \
        --platform manylinux2014_x86_64 \
        --only-binary=:all: \
        --python-version 3.11 \
        --implementation cp
elif command -v pip &> /dev/null; then
    pip install -r requirements.txt -t package/ \
        --platform manylinux2014_x86_64 \
        --only-binary=:all: \
        --python-version 3.11 \
        --implementation cp
else
    echo "Error: Neither pip nor pip3 found. Please install Python pip."
    exit 1
fi

# Copy our modules directly to package root for Lambda function
echo "Copying agent-core..."
cp -r ../agent-core/src package/agent_core

echo "Copying mcp-client..."
cp -r ../mcp-client/src package/mcp_client

echo "Copying storage..."
cp -r ../storage/src package/storage

# Copy handlers
echo "Copying handlers..."
cp handler.py package/ && echo "  ✓ handler.py"
cp handler_incident_only.py package/ && echo "  ✓ handler_incident_only.py"
cp chat_handler.py package/ && echo "  ✓ chat_handler.py"
cp log_groups_handler.py package/ && echo "  ✓ log_groups_handler.py"
cp diagnosis_handler.py package/ && echo "  ✓ diagnosis_handler.py"
cp log_management_handler.py package/ && echo "  ✓ log_management_handler.py"
cp incident_from_chat_handler.py package/ && echo "  ✓ incident_from_chat_handler.py"
cp remediation_webhook_handler.py package/ && echo "  ✓ remediation_webhook_handler.py"
cp remediation_status_handler.py package/ && echo "  ✓ remediation_status_handler.py"
cp create_github_issue_handler.py package/ && echo "  ✓ create_github_issue_handler.py"
cp chat_session_handler.py package/ && echo "  ✓ chat_session_handler.py"
cp list_incidents_handler.py package/ && echo "  ✓ list_incidents_handler.py"
cp cloudwatch_alarm_handler.py package/ && echo "  ✓ cloudwatch_alarm_handler.py"
cp delete_incident_handler.py package/ && echo "  ✓ delete_incident_handler.py"
cp reanalyze_incident_handler.py package/ && echo "  ✓ reanalyze_incident_handler.py"
cp agent_invoker.py package/ && echo "  ✓ agent_invoker.py"
cp incident_mcp_client.py package/ && echo "  ✓ incident_mcp_client.py"
cp incident_sources_handler.py package/ && echo "  ✓ incident_sources_handler.py"

# Verify chat_session_handler.py was copied
echo ""
echo "Verifying handler files were copied..."
if [ -f "package/chat_session_handler.py" ]; then
    echo "✅ Verified: chat_session_handler.py is in package"
else
    echo "❌ ERROR: chat_session_handler.py NOT found in package!"
    echo "   Listing package directory:"
    ls -la package/*.py | head -10
    exit 1
fi

# Verify other critical handlers
for handler in handler.py remediation_status_handler.py create_github_issue_handler.py list_incidents_handler.py cloudwatch_alarm_handler.py delete_incident_handler.py reanalyze_incident_handler.py incident_sources_handler.py incident_mcp_client.py; do
    if [ -f "package/$handler" ]; then
        echo "✅ Verified: $handler"
    else
        echo "❌ ERROR: $handler NOT found in package!"
        exit 1
    fi
done

# Create zip
echo ""
echo "Creating deployment package..."
cd package
zip -r ../lambda-deployment.zip . -q
cd ..

echo "Deployment package created: lambda-deployment.zip"
echo "Size: $(du -h lambda-deployment.zip | cut -f1)"

# Final verification - check if chat_session_handler.py is in the zip
echo ""
echo "Verifying chat_session_handler.py in deployment zip..."
if unzip -l lambda-deployment.zip 2>/dev/null | grep -q "chat_session_handler.py"; then
    echo "✅ Verified: chat_session_handler.py is in deployment zip"
    unzip -l lambda-deployment.zip | grep "chat_session_handler.py"
else
    echo "❌ WARNING: chat_session_handler.py NOT found in deployment zip!"
    echo "   Listing handler files in zip:"
    unzip -l lambda-deployment.zip | grep "handler" | head -15
fi
