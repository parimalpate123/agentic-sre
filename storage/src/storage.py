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
            
            # Add source field if present (for distinguishing chat vs CloudWatch incidents)
            # Source can be at top level or nested in full_state.incident
            source = investigation_result.get('source')
            logger.info(f"[SAVE] Extracting source field for incident {incident_id}: top level = {repr(source)}")
            
            # Try multiple locations to find source
            if not source:
                # Try full_state.incident.source
                full_state = investigation_result.get('full_state', {})
                if isinstance(full_state, dict):
                    incident = full_state.get('incident', {})
                    if isinstance(incident, dict):
                        source = incident.get('source')
                        logger.info(f"[SAVE] Extracting source from full_state.incident.source = {repr(source)}")
            
            # If still not found, try to infer from incident_id pattern
            if not source:
                # CloudWatch incidents typically have IDs like "inc-1234567890" or "test-2026-01-27T..."
                # Chat incidents have IDs like "chat-1234567890-abc123"
                if incident_id.startswith('inc-') or incident_id.startswith('test-') or incident_id.startswith('cw-'):
                    source = 'cloudwatch_alarm'
                    logger.info(f"[SAVE] Inferred source='cloudwatch_alarm' from incident_id pattern: {incident_id}")
                elif incident_id.startswith('chat-'):
                    source = 'chat'
                    logger.info(f"[SAVE] Inferred source='chat' from incident_id pattern: {incident_id}")
                else:
                    # Default to chat for backward compatibility
                    source = 'chat'
                    logger.warning(f"[SAVE] Could not determine source, defaulting to 'chat' for incident {incident_id}")
            
            # Always save source field (even if inferred)
            if not source:
                # Final fallback: infer from incident_id
                if incident_id.startswith('inc-') or incident_id.startswith('test-') or incident_id.startswith('cw-'):
                    source = 'cloudwatch_alarm'
                    logger.warning(f"[SAVE] Source was None/empty, inferred 'cloudwatch_alarm' from incident_id: {incident_id}")
                elif incident_id.startswith('chat-'):
                    source = 'chat'
                    logger.warning(f"[SAVE] Source was None/empty, inferred 'chat' from incident_id: {incident_id}")
                else:
                    source = 'chat'  # Default
                    logger.warning(f"[SAVE] Source was None/empty, defaulting to 'chat' for incident_id: {incident_id}")
            
            item['source'] = {'S': str(source)}
            logger.info(f"[SAVE] ✅ Saved incident {incident_id} with source: {repr(source)} (type: {type(source)})")
            
            # Also ensure source is in the nested data JSON for consistency
            if not investigation_result.get('source'):
                investigation_result['source'] = source
                # Update the data field with the source
                item['data'] = {'S': json.dumps(investigation_result, default=str)}

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
        source: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List incidents with optional filtering

        Args:
            service: Filter by service name
            status: Filter by status (open, resolved)
            source: Filter by source ('chat', 'cloudwatch_alarm', or None for all)
            limit: Maximum number of incidents to return

        Returns:
            List of incident summaries
        """
        logger.info(f"Listing incidents (service={service}, status={status}, source={source})")

        try:
            # Build query parameters
            params = {
                'TableName': self.incidents_table
                # Note: Don't use Limit here when filtering by source, as Limit applies BEFORE filtering
                # Instead, we'll apply the limit after in-memory filtering
            }
            
            # Build filter expression for source (if specified)
            filter_expressions = []
            expression_attribute_values = {}
            expression_attribute_names = {}
            use_in_memory_source_filter = False  # Flag for fallback filtering
            
            # Always use in-memory filtering for source because:
            # 1. Source might be in nested JSON data, not at top level
            # 2. We need to extract it from investigation_result anyway
            # 3. More reliable than DynamoDB FilterExpression for nested fields
            if source:
                use_in_memory_source_filter = True
                logger.info(f"Will filter by source '{source}' in memory after parsing items")
            
            # Use GSI if filtering by service or status
            if service:
                params['IndexName'] = 'ServiceIndex'
                params['KeyConditionExpression'] = 'service = :service'
                params['ExpressionAttributeValues'] = {
                    ':service': {'S': service}
                }
                if filter_expressions:
                    params['FilterExpression'] = ' AND '.join(filter_expressions)
                    params['ExpressionAttributeValues'].update(expression_attribute_values)
                    if expression_attribute_names:
                        params['ExpressionAttributeNames'] = expression_attribute_names
                logger.debug(f"Querying DynamoDB with ServiceIndex, params keys: {list(params.keys())}")
                all_items = []
                while True:
                    response = self.dynamodb.query(**params)
                    all_items.extend(response.get('Items', []))
                    last_key = response.get('LastEvaluatedKey')
                    if not last_key:
                        break
                    params['ExclusiveStartKey'] = last_key
            elif status:
                params['IndexName'] = 'StatusIndex'
                params['KeyConditionExpression'] = 'status = :status'
                params['ExpressionAttributeValues'] = {
                    ':status': {'S': status}
                }
                if filter_expressions:
                    params['FilterExpression'] = ' AND '.join(filter_expressions)
                    params['ExpressionAttributeValues'].update(expression_attribute_values)
                    if expression_attribute_names:
                        params['ExpressionAttributeNames'] = expression_attribute_names
                logger.debug(f"Querying DynamoDB with StatusIndex, params keys: {list(params.keys())}")
                all_items = []
                while True:
                    response = self.dynamodb.query(**params)
                    all_items.extend(response.get('Items', []))
                    last_key = response.get('LastEvaluatedKey')
                    if not last_key:
                        break
                    params['ExclusiveStartKey'] = last_key
            else:
                # Full scan (not efficient for large datasets)
                if filter_expressions:
                    params['FilterExpression'] = ' AND '.join(filter_expressions)
                    params['ExpressionAttributeValues'] = expression_attribute_values
                    if expression_attribute_names:
                        params['ExpressionAttributeNames'] = expression_attribute_names
                
                logger.debug(f"Scanning DynamoDB table: {self.incidents_table}, filter: {filter_expressions}")
                all_items = []
                try:
                    while True:
                        response = self.dynamodb.scan(**params)
                        all_items.extend(response.get('Items', []))
                        last_key = response.get('LastEvaluatedKey')
                        if not last_key:
                            break
                        params['ExclusiveStartKey'] = last_key
                    logger.info(f"Scan returned {len(all_items)} items from DynamoDB")
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    error_message = e.response.get('Error', {}).get('Message', str(e))
                    logger.error(f"DynamoDB scan failed: {error_code} - {error_message}", exc_info=True)
                    # If it's a validation error, try without filter expressions as fallback
                    if error_code == 'ValidationException' and filter_expressions:
                        logger.warning(f"Retrying scan without filter expressions due to ValidationException")
                        params.pop('FilterExpression', None)
                        params.pop('ExpressionAttributeValues', None)
                        params.pop('ExpressionAttributeNames', None)
                        all_items = []
                        while True:
                            response = self.dynamodb.scan(**params)
                            all_items.extend(response.get('Items', []))
                            last_key = response.get('LastEvaluatedKey')
                            if not last_key:
                                break
                            params['ExclusiveStartKey'] = last_key
                        logger.info(f"Retry scan returned {len(all_items)} items from DynamoDB")
                    else:
                        raise

            # Parse items
            incidents = []
            # Note: use_in_memory_filter is set in the scan block above if we had to fallback
            
            for item in all_items:
                parsed_item = self._parse_dynamodb_item(item)
                incident_id = parsed_item.get('incident_id', 'unknown')
                logger.debug(f"[LIST] Processing item: incident_id={incident_id}, has_source_field={('source' in parsed_item)}")
                
                # Parse nested JSON data if present
                if 'data' in parsed_item:
                    try:
                        parsed_item['investigation_result'] = json.loads(parsed_item['data'])
                        # Extract source from parsed data if not at top level
                        if 'source' not in parsed_item or not parsed_item.get('source'):
                            nested_source = parsed_item['investigation_result'].get('source')
                            if not nested_source:
                                # Try nested location
                                full_state = parsed_item['investigation_result'].get('full_state', {})
                                incident = full_state.get('incident', {})
                                if isinstance(incident, dict):
                                    nested_source = incident.get('source')
                            
                            # If still not found, infer from incident_id
                            if not nested_source:
                                incident_id = parsed_item.get('incident_id', '')
                                if incident_id.startswith('inc-') or incident_id.startswith('test-') or incident_id.startswith('cw-'):
                                    nested_source = 'cloudwatch_alarm'
                                elif incident_id.startswith('chat-'):
                                    nested_source = 'chat'
                                else:
                                    nested_source = 'chat'  # Default
                            
                            if nested_source:
                                parsed_item['source'] = nested_source
                                logger.debug(f"Extracted/inferred source: {nested_source} for incident {parsed_item.get('incident_id', 'unknown')}")
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Failed to parse investigation_result data: {e}")
                        pass
                
                # If source still not set, try to infer from incident_id (fallback)
                if 'source' not in parsed_item or not parsed_item.get('source'):
                    incident_id = parsed_item.get('incident_id', '')
                    if incident_id.startswith('inc-') or incident_id.startswith('test-') or incident_id.startswith('cw-'):
                        parsed_item['source'] = 'cloudwatch_alarm'
                        logger.debug(f"Inferred source='cloudwatch_alarm' from incident_id: {incident_id}")
                    elif incident_id.startswith('chat-'):
                        parsed_item['source'] = 'chat'
                        logger.debug(f"Inferred source='chat' from incident_id: {incident_id}")
                    else:
                        parsed_item['source'] = 'chat'  # Default
                        logger.debug(f"Defaulted source='chat' for incident_id: {incident_id}")
                
                # Filter by source in memory (always used for source filtering)
                if use_in_memory_source_filter and source:
                    item_source = parsed_item.get('source')
                    incident_id = parsed_item.get('incident_id', 'unknown')
                    
                    if not item_source:
                        # Try to extract from investigation_result if not already extracted
                        if parsed_item.get('investigation_result'):
                            item_source = parsed_item['investigation_result'].get('source')
                            if not item_source:
                                full_state = parsed_item['investigation_result'].get('full_state', {})
                                incident = full_state.get('incident', {})
                                if isinstance(incident, dict):
                                    item_source = incident.get('source')
                    
                    # If still not found, infer from incident_id pattern
                    if not item_source:
                        if incident_id.startswith('inc-') or incident_id.startswith('test-') or incident_id.startswith('cw-'):
                            item_source = 'cloudwatch_alarm'
                            logger.info(f"Inferred source='cloudwatch_alarm' from incident_id pattern: {incident_id}")
                        elif incident_id.startswith('chat-'):
                            item_source = 'chat'
                            logger.info(f"Inferred source='chat' from incident_id pattern: {incident_id}")
                        else:
                            # Default to 'chat' for old items without source field
                            item_source = 'chat'
                            logger.info(f"Item {incident_id} has no source field, defaulting to 'chat'")
                    
                    logger.info(f"Checking item {incident_id}: source={repr(item_source)}, filter={repr(source)}, match={item_source == source}")
                    if item_source != source:
                        logger.info(f"Skipping item {incident_id} - source mismatch (item_source={repr(item_source)}, filter={repr(source)})")
                        continue  # Skip this item
                    logger.info(f"Including item {incident_id} - source matches")
                
                incidents.append(parsed_item)

            logger.info(f"Found {len(incidents)} incidents before applying limit")
            # Apply limit after filtering
            incidents = incidents[:limit]
            logger.info(f"Returning {len(incidents)} incidents (after limit={limit})")
            
            # Log incident IDs for debugging
            if len(incidents) > 0:
                incident_ids = [inc.get('incident_id', 'unknown') for inc in incidents]
                logger.info(f"Returning incident IDs: {incident_ids}")
            else:
                logger.warning(f"No incidents found matching filters: source={source}, status={status}, service={service}")
                logger.warning(f"Total items scanned from DynamoDB: {len(response.get('Items', []))}")
            
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

    def delete_incident(self, incident_id: str) -> bool:
        """
        Delete an incident from DynamoDB

        Args:
            incident_id: Incident ID to delete

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Deleting incident {incident_id}")

        try:
            self.dynamodb.delete_item(
                TableName=self.incidents_table,
                Key={
                    'incident_id': {'S': incident_id}
                }
            )
            logger.info(f"Successfully deleted incident {incident_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete incident {incident_id}: {str(e)}", exc_info=True)
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
