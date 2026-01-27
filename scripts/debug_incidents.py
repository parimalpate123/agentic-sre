#!/usr/bin/env python3
"""
Debug script to test incident listing and source filtering
"""
import json
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'storage', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-handler'))

from storage.storage import create_storage

def test_list_incidents():
    """Test listing incidents with different filters"""
    
    # Get table name from environment or use default
    incidents_table = os.environ.get('INCIDENTS_TABLE', 'sre-poc-incidents')
    
    print(f"=== Testing Incident Listing ===")
    print(f"Table: {incidents_table}")
    print()
    
    try:
        # Initialize storage
        storage = create_storage(
            incidents_table=incidents_table,
            playbooks_table=os.environ.get('PLAYBOOKS_TABLE', ''),
            memory_table=os.environ.get('MEMORY_TABLE', '')
        )
        
        # Test 1: List all incidents
        print("1. Testing: List ALL incidents (no filter)")
        all_incidents = storage.list_incidents(limit=10)
        print(f"   Found: {len(all_incidents)} incidents")
        for inc in all_incidents[:3]:
            inc_id = inc.get('incident_id', 'unknown')
            source = inc.get('source', 'missing')
            service = inc.get('service', 'unknown')
            timestamp = inc.get('timestamp', 'unknown')
            print(f"   - {inc_id}: source={source}, service={service}, timestamp={timestamp}")
        print()
        
        # Test 2: List CloudWatch incidents only
        print("2. Testing: List CloudWatch alarm incidents only")
        cw_incidents = storage.list_incidents(source='cloudwatch_alarm', limit=10)
        print(f"   Found: {len(cw_incidents)} incidents")
        for inc in cw_incidents[:3]:
            inc_id = inc.get('incident_id', 'unknown')
            source = inc.get('source', 'missing')
            service = inc.get('service', 'unknown')
            timestamp = inc.get('timestamp', 'unknown')
            print(f"   - {inc_id}: source={source}, service={service}, timestamp={timestamp}")
        print()
        
        # Test 3: List chat incidents only
        print("3. Testing: List chat incidents only")
        chat_incidents = storage.list_incidents(source='chat', limit=10)
        print(f"   Found: {len(chat_incidents)} incidents")
        for inc in chat_incidents[:3]:
            inc_id = inc.get('incident_id', 'unknown')
            source = inc.get('source', 'missing')
            service = inc.get('service', 'unknown')
            timestamp = inc.get('timestamp', 'unknown')
            print(f"   - {inc_id}: source={source}, service={service}, timestamp={timestamp}")
        print()
        
        # Test 4: Check source field in investigation_result
        print("4. Testing: Check source field in investigation_result")
        for inc in all_incidents[:3]:
            inc_id = inc.get('incident_id', 'unknown')
            investigation_result = inc.get('investigation_result', {})
            if isinstance(investigation_result, str):
                investigation_result = json.loads(investigation_result)
            
            top_source = inc.get('source', 'missing')
            nested_source = investigation_result.get('source', 'missing')
            full_state_source = investigation_result.get('full_state', {}).get('incident', {}).get('source', 'missing')
            
            print(f"   - {inc_id}:")
            print(f"     Top level source: {top_source}")
            print(f"     investigation_result.source: {nested_source}")
            print(f"     full_state.incident.source: {full_state_source}")
        print()
        
        # Summary
        print("=== Summary ===")
        print(f"Total incidents: {len(all_incidents)}")
        print(f"CloudWatch incidents: {len(cw_incidents)}")
        print(f"Chat incidents: {len(chat_incidents)}")
        print(f"Incidents without source: {len(all_incidents) - len(cw_incidents) - len(chat_incidents)}")
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    exit(test_list_incidents())
