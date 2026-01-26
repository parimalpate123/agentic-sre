# DynamoDB Table: Incidents
resource "aws_dynamodb_table" "incidents" {
  name         = "${var.project_name}-incidents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "incident_id"
  range_key    = "timestamp"

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "service"
    type = "S"
  }

  # GSI for querying by status
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # GSI for querying by service
  global_secondary_index {
    name            = "ServiceIndex"
    hash_key        = "service"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # TTL configuration
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-incidents"
  }
}

# DynamoDB Table: Playbooks
resource "aws_dynamodb_table" "playbooks" {
  name         = "${var.project_name}-playbooks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pattern_id"
  range_key    = "version"

  attribute {
    name = "pattern_id"
    type = "S"
  }

  attribute {
    name = "version"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-playbooks"
  }
}

# DynamoDB Table: Agent Memory
resource "aws_dynamodb_table" "memory" {
  name         = "${var.project_name}-memory"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "context_type"
  range_key    = "reference_id"

  attribute {
    name = "context_type"
    type = "S"
  }

  attribute {
    name = "reference_id"
    type = "S"
  }

  # TTL configuration for temporary context
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-memory"
  }
}

# DynamoDB Table: Remediation State
# Tracks the full lifecycle: Issue → PR → Review → Merge
resource "aws_dynamodb_table" "remediation_state" {
  name         = "${var.project_name}-remediation-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "incident_id"

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "issue_number"
    type = "N"
  }

  # GSI for querying by issue number
  global_secondary_index {
    name            = "IssueNumberIndex"
    hash_key        = "issue_number"
    projection_type = "ALL"
  }

  # TTL configuration
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-remediation-state"
  }
}

# DynamoDB Table: Chat Sessions
# Stores chat conversations and incident data for resuming later
resource "aws_dynamodb_table" "chat_sessions" {
  name         = "${var.project_name}-chat-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  # GSI for querying by creation time (list recent sessions)
  global_secondary_index {
    name            = "CreatedAtIndex"
    hash_key        = "created_at"
    projection_type = "ALL"
  }

  # TTL configuration (sessions expire after 90 days)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-chat-sessions"
  }
}
