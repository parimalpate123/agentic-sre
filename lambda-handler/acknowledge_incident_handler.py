"""
Acknowledge alarm-triggered incident — persists flag on DynamoDB for sidebar bell / triage UX.
"""

import json
import logging
import os
from typing import Any, Dict

from storage.storage import create_storage

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE")
PLAYBOOKS_TABLE = os.environ.get("PLAYBOOKS_TABLE")
MEMORY_TABLE = os.environ.get("MEMORY_TABLE")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        query_params = event.get("queryStringParameters") or {}
        body = event.get("body")
        if body:
            if isinstance(body, str):
                body = json.loads(body)
        else:
            body = {}

        incident_id = query_params.get("incident_id") or body.get("incident_id")
        if not incident_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"success": False, "error": "incident_id is required"}),
            }

        storage = create_storage(
            incidents_table=INCIDENTS_TABLE,
            playbooks_table=PLAYBOOKS_TABLE,
            memory_table=MEMORY_TABLE,
        )

        existing = storage.get_incident(incident_id)
        if not existing:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"success": False, "error": f"Incident {incident_id} not found"}),
            }

        ok = storage.acknowledge_alarm_incident(incident_id)
        if not ok:
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(
                    {"success": False, "error": f"Failed to acknowledge incident {incident_id}"}
                ),
            }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "success": True,
                    "incident_id": incident_id,
                    "alarm_acknowledged": True,
                }
            ),
        }
    except Exception as e:
        logger.error(f"Error acknowledging incident: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": False, "error": str(e)}),
        }
