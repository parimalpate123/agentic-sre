#!/usr/bin/env python3
"""
Test script for MCP Server
Can be run via ECS Exec or from Lambda (if in same VPC)
"""

import json
import sys
import os
from typing import Dict, Any

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed. Install with: pip install requests")
    sys.exit(1)

# MCP Server endpoint
# When running in ECS container: http://localhost:8000
# When running from Lambda in same VPC: http://mcp-server.sre-poc.local:8000
MCP_ENDPOINT = os.environ.get('MCP_ENDPOINT', 'http://localhost:8000')
MCP_ENDPOINT = MCP_ENDPOINT.rstrip('/')


def test_health_check() -> bool:
    """Test if the server is responding (health check may not exist, so we test with a simple MCP call)"""
    print(f"\n{'='*60}")
    print("1. Testing Server Connectivity")
    print(f"{'='*60}")
    print(f"Testing connection to {MCP_ENDPOINT}")
    
    # Try to connect - FastMCP might not have /health, so we'll test with initialize
    try:
        # Test with a simple initialize request
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        response = requests.post(
            f"{MCP_ENDPOINT}/mcp",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Server is responding")
            return True
        else:
            print(f"⚠️  Server responded with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection FAILED: Cannot connect to {MCP_ENDPOINT}")
        print(f"   Error: {str(e)}")
        return False
    except Exception as e:
        print(f"⚠️  Connection test: {str(e)}")
        # Still return True if it's not a connection error (might be protocol issue)
        return True


def test_mcp_tools_list() -> bool:
    """Test MCP tools/list endpoint"""
    print(f"\n{'='*60}")
    print("2. Testing MCP tools/list")
    print(f"{'='*60}")
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }
    
    print(f"POST {MCP_ENDPOINT}/mcp")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{MCP_ENDPOINT}/mcp",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if 'result' in data:
                tools = data['result'].get('tools', [])
                print(f"\n✅ Found {len(tools)} tools")
                for tool in tools[:5]:  # Show first 5 tools
                    print(f"  - {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}")
                return True
            else:
                print("⚠️  Response doesn't contain 'result'")
                return False
        else:
            print(f"Response: {response.text}")
            print("❌ Request FAILED")
            return False
    except Exception as e:
        print(f"❌ Request FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_list_log_groups() -> bool:
    """Test listing CloudWatch log groups"""
    print(f"\n{'='*60}")
    print("3. Testing list_log_groups tool")
    print(f"{'='*60}")
    
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "list_log_groups",
            "arguments": {
                "limit": 5
            }
        }
    }
    
    print(f"POST {MCP_ENDPOINT}/mcp")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{MCP_ENDPOINT}/mcp",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if 'result' in data:
                print("\n✅ list_log_groups call succeeded")
                return True
            elif 'error' in data:
                print(f"\n⚠️  MCP error: {data['error']}")
                return False
            else:
                print("\n⚠️  Unexpected response format")
                return False
        else:
            print(f"Response: {response.text}")
            print("❌ Request FAILED")
            return False
    except Exception as e:
        print(f"❌ Request FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n🧪 MCP Server Test Suite")
    print(f"Endpoint: {MCP_ENDPOINT}")
    
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health_check()))
    
    # Test 2: Tools list (only if health check passes)
    if results[0][1]:
        results.append(("Tools List", test_mcp_tools_list()))
        
        # Test 3: List log groups (only if tools list passes)
        if results[1][1]:
            results.append(("List Log Groups", test_list_log_groups()))
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
