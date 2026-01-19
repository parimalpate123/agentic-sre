"""
Storage Layer - DynamoDB abstraction for incident persistence

This module provides a clean interface for storing and retrieving
investigation data from DynamoDB.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class Storage:
    """
    Storage layer for incident investigation data

    Manages three DynamoDB tables:
    - Incidents: Investigation results and history
    - Playbooks: Known patterns and remediation playbooks
    - Memory: Agent memory and context
    """

    def __init__(
        self,
        incidents_table: str,
        playbooks_table: str,
        memory_table: str,
        dynamodb_client=None
    ):
        """
        Initialize Storage

        Args:
            incidents_table: DynamoDB incidents table name
            playbooks_table: DynamoDB playbooks table name
            memory_table: DynamoDB memory table name
            dynamodb_client: Optional boto3 DynamoDB client
        """
        self.incidents_table = incidents_table
        self.playbooks_table = playbooks_table
        self.memory_table = memory_table

        self.dynamodb = dynamodb_client or boto3.client('dynamodb')

        logger.info(
            f"Storage initialized with tables: "
            f"{incidents_table}, {playbooks_table}, {memory_table}"
        )

    # ============================================
    # Incident Operations
    # ============================================

    def save_incident(
        self,
        incident_id: str,
        investigation_result: Dict[str, Any]
    ) -> bool:
        """
        Save investigation result to incidents table

        Args:
            incident_id: Unique incident ID
            investigation_result: Complete investigation result

        Returns:
            True if successful
        """
        logger.info(f"Saving incident {incident_id}")

        try:
            timestamp = datetime.utcnow().isoformat()

            # Convert to DynamoDB format
            item = {
                'incident_id': {'S': incident_id},
                'timestamp': {'S': timestamp},
                'service': {'S': investigation_result.get('service', 'unknown')},
                'severity': {'S': investigation_result.get('severity', 'P3')},
                'root_cause': {'S': investigation_result.get('root_cause', 'Unknown')},
                'confidence': {'N': str(investigation_result.get('confidence', 0))},
                'status': {'S': 'open'},
                'investigation_duration': {
                    'N': str(investigation_result.get('investigation_duration_seconds', 0))
                },
                'data': {'S': json.dumps(investigation_result, default=str)},
                'created_at': {'S': timestamp},
                'updated_at': {'S': timestamp}
            }

            # Add TTL (30 days from now)
            ttl = int(datetime.utcnow().timestamp()) + (30 * 24 * 60 * 60)
            item['ttl'] = {'N': str(ttl)}

            self.dynamodb.put_item(
                TableName=self.incidents_table,
                Item=item
            )

            logger.info(f"Incident {incident_id} saved successfully")
            return True

        except ClientError as e:
            logger.error(f"Failed to save incident: {str(e)}", exc_info=True)
            return False

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve incident by ID

        Args:
            incident_id: Incident ID

        Returns:
            Incident data or None if not found
        """
        logger.debug(f"Retrieving incident {incident_id}")

        try:
            response = self.dynamodb.get_item(
                TableName=self.incidents_table,
                Key={
                    'incident_id': {'S': incident_id}
                }
            )

            if 'Item' not in response:
                logger.info(f"Incident {incident_id} not found")
                return None

            # Parse item
            item = self._parse_dynamodb_item(response['Item'])

            # Parse nested JSON data
            if 'data' in item:
                item['investigation_result'] = json.loads(item['data'])
                del item['data']

            return item

        except ClientError as e:
            logger.error(f"Failed to get incident: {str(e)}", exc_info=True)
            return None

    def list_incidents(
        self,
        service: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List incidents with optional filtering

        Args:
            service: Filter by service name
            status: Filter by status (open, resolved)
            limit: Maximum number of incidents to return

        Returns:
            List of incident summaries
        """
        logger.debug(f"Listing incidents (service={service}, status={status})")

        try:
            # Build query parameters
            params = {
                'TableName': self.incidents_table,
                'Limit': limit,
                'ScanIndexForward': False  # Most recent first
            }

            # Use GSI if filtering
            if service:
                params['IndexName'] = 'service-timestamp-index'
                params['KeyConditionExpression'] = 'service = :service'
                params['ExpressionAttributeValues'] = {
                    ':service': {'S': service}
                }
                response = self.dynamodb.query(**params)
            elif status:
                params['IndexName'] = 'status-timestamp-index'
                params['KeyConditionExpression'] = 'status = :status'
                params['ExpressionAttributeValues'] = {
                    ':status': {'S': status}
                }
                response = self.dynamodb.query(**params)
            else:
                # Full scan (not efficient for large datasets)
                response = self.dynamodb.scan(**params)

            # Parse items
            incidents = []
            for item in response.get('Items', []):
                incidents.append(self._parse_dynamodb_item(item))

            logger.info(f"Found {len(incidents)} incidents")
            return incidents

        except ClientError as e:
            logger.error(f"Failed to list incidents: {str(e)}", exc_info=True)
            return []

    def update_incident_status(
        self,
        incident_id: str,
        status: str,
        resolution_notes: Optional[str] = None
    ) -> bool:
        """
        Update incident status

        Args:
            incident_id: Incident ID
            status: New status (open, investigating, resolved)
            resolution_notes: Optional resolution notes

        Returns:
            True if successful
        """
        logger.info(f"Updating incident {incident_id} status to {status}")

        try:
            update_expr = "SET #status = :status, updated_at = :updated_at"
            expr_values = {
                ':status': {'S': status},
                ':updated_at': {'S': datetime.utcnow().isoformat()}
            }

            if resolution_notes:
                update_expr += ", resolution_notes = :notes"
                expr_values[':notes'] = {'S': resolution_notes}

            self.dynamodb.update_item(
                TableName=self.incidents_table,
                Key={
                    'incident_id': {'S': incident_id}
                },
                UpdateExpression=update_expr,
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues=expr_values
            )

            return True

        except ClientError as e:
            logger.error(f"Failed to update incident status: {str(e)}", exc_info=True)
            return False

    # ============================================
    # Playbook Operations
    # ============================================

    def save_playbook(
        self,
        pattern_id: str,
        pattern: Dict[str, Any],
        remediation: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save a playbook for pattern-based remediation

        Args:
            pattern_id: Unique pattern identifier
            pattern: Pattern definition (error patterns, symptoms)
            remediation: Remediation steps
            metadata: Additional metadata

        Returns:
            True if successful
        """
        logger.info(f"Saving playbook {pattern_id}")

        try:
            timestamp = datetime.utcnow().isoformat()
            version = metadata.get('version', '1') if metadata else '1'

            item = {
                'pattern_id': {'S': pattern_id},
                'version': {'S': version},
                'pattern': {'S': json.dumps(pattern)},
                'remediation': {'S': json.dumps(remediation)},
                'created_at': {'S': timestamp},
                'updated_at': {'S': timestamp}
            }

            if metadata:
                item['metadata'] = {'S': json.dumps(metadata)}

            self.dynamodb.put_item(
                TableName=self.playbooks_table,
                Item=item
            )

            logger.info(f"Playbook {pattern_id} saved successfully")
            return True

        except ClientError as e:
            logger.error(f"Failed to save playbook: {str(e)}", exc_info=True)
            return False

    def get_playbook(
        self,
        pattern_id: str,
        version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve playbook by pattern ID

        Args:
            pattern_id: Pattern identifier
            version: Optional version (defaults to latest)

        Returns:
            Playbook data or None
        """
        logger.debug(f"Retrieving playbook {pattern_id}")

        try:
            key = {'pattern_id': {'S': pattern_id}}

            if version:
                key['version'] = {'S': version}
            else:
                # Get latest version - query and sort
                response = self.dynamodb.query(
                    TableName=self.playbooks_table,
                    KeyConditionExpression='pattern_id = :pid',
                    ExpressionAttributeValues={
                        ':pid': {'S': pattern_id}
                    },
                    ScanIndexForward=False,
                    Limit=1
                )

                if not response.get('Items'):
                    return None

                item = response['Items'][0]

            if not version:
                # Already have item from query above
                pass
            else:
                response = self.dynamodb.get_item(
                    TableName=self.playbooks_table,
                    Key=key
                )

                if 'Item' not in response:
                    return None

                item = response['Item']

            # Parse and return
            playbook = self._parse_dynamodb_item(item)

            # Parse JSON fields
            if 'pattern' in playbook:
                playbook['pattern'] = json.loads(playbook['pattern'])
            if 'remediation' in playbook:
                playbook['remediation'] = json.loads(playbook['remediation'])
            if 'metadata' in playbook:
                playbook['metadata'] = json.loads(playbook['metadata'])

            return playbook

        except ClientError as e:
            logger.error(f"Failed to get playbook: {str(e)}", exc_info=True)
            return None

    # ============================================
    # Memory Operations
    # ============================================

    def save_memory(
        self,
        context_type: str,
        reference_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Save agent memory/context

        Args:
            context_type: Type of context (e.g., "deployment", "incident_pattern")
            reference_id: Reference ID (e.g., deployment ID, incident ID)
            data: Context data

        Returns:
            True if successful
        """
        logger.debug(f"Saving memory: {context_type}/{reference_id}")

        try:
            timestamp = datetime.utcnow().isoformat()

            item = {
                'context_type': {'S': context_type},
                'reference_id': {'S': reference_id},
                'data': {'S': json.dumps(data, default=str)},
                'created_at': {'S': timestamp},
                'updated_at': {'S': timestamp}
            }

            # Add TTL (7 days)
            ttl = int(datetime.utcnow().timestamp()) + (7 * 24 * 60 * 60)
            item['ttl'] = {'N': str(ttl)}

            self.dynamodb.put_item(
                TableName=self.memory_table,
                Item=item
            )

            return True

        except ClientError as e:
            logger.error(f"Failed to save memory: {str(e)}", exc_info=True)
            return False

    def get_memory(
        self,
        context_type: str,
        reference_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve memory by context type and reference ID

        Args:
            context_type: Context type
            reference_id: Reference ID

        Returns:
            Memory data or None
        """
        try:
            response = self.dynamodb.get_item(
                TableName=self.memory_table,
                Key={
                    'context_type': {'S': context_type},
                    'reference_id': {'S': reference_id}
                }
            )

            if 'Item' not in response:
                return None

            memory = self._parse_dynamodb_item(response['Item'])

            # Parse data JSON
            if 'data' in memory:
                memory['data'] = json.loads(memory['data'])

            return memory

        except ClientError as e:
            logger.error(f"Failed to get memory: {str(e)}", exc_info=True)
            return None

    # ============================================
    # Helper Methods
    # ============================================

    def _parse_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse DynamoDB item to Python dict

        Args:
            item: DynamoDB item with type descriptors

        Returns:
            Plain Python dictionary
        """
        result = {}

        for key, value in item.items():
            if 'S' in value:
                result[key] = value['S']
            elif 'N' in value:
                result[key] = float(value['N'])
            elif 'BOOL' in value:
                result[key] = value['BOOL']
            elif 'NULL' in value:
                result[key] = None
            elif 'M' in value:
                result[key] = self._parse_dynamodb_item(value['M'])
            elif 'L' in value:
                result[key] = [self._parse_dynamodb_value(v) for v in value['L']]

        return result

    def _parse_dynamodb_value(self, value: Dict[str, Any]) -> Any:
        """Parse a single DynamoDB value"""
        if 'S' in value:
            return value['S']
        elif 'N' in value:
            return float(value['N'])
        elif 'BOOL' in value:
            return value['BOOL']
        elif 'NULL' in value:
            return None
        elif 'M' in value:
            return self._parse_dynamodb_item(value['M'])
        elif 'L' in value:
            return [self._parse_dynamodb_value(v) for v in value['L']]
        return None


# Convenience function
def create_storage(
    incidents_table: Optional[str] = None,
    playbooks_table: Optional[str] = None,
    memory_table: Optional[str] = None
) -> Storage:
    """
    Create storage from environment variables

    Args:
        incidents_table: Optional incidents table name
        playbooks_table: Optional playbooks table name
        memory_table: Optional memory table name

    Returns:
        Initialized Storage instance
    """
    import os

    incidents_table = incidents_table or os.environ.get('INCIDENTS_TABLE')
    playbooks_table = playbooks_table or os.environ.get('PLAYBOOKS_TABLE')
    memory_table = memory_table or os.environ.get('MEMORY_TABLE')

    if not all([incidents_table, playbooks_table, memory_table]):
        raise ValueError(
            "Table names must be provided or set in environment variables: "
            "INCIDENTS_TABLE, PLAYBOOKS_TABLE, MEMORY_TABLE"
        )

    return Storage(
        incidents_table=incidents_table,
        playbooks_table=playbooks_table,
        memory_table=memory_table
    )
