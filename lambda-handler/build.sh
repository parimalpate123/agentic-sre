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
cp handler.py package/
cp handler_incident_only.py package/
cp chat_handler.py package/
cp log_groups_handler.py package/
cp diagnosis_handler.py package/
cp log_management_handler.py package/
cp agent_invoker.py package/

# Create zip
echo "Creating deployment package..."
cd package
zip -r ../lambda-deployment.zip . -q
cd ..

echo "Deployment package created: lambda-deployment.zip"
echo "Size: $(du -h lambda-deployment.zip | cut -f1)"
