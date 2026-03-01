# DynamoDB Table: KB Documents
# Stores metadata for uploaded KB documents
resource "aws_dynamodb_table" "kb_documents" {
  name         = "${var.project_name}-kb-documents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "document_id"

  attribute {
    name = "document_id"
    type = "S"
  }

  attribute {
    name = "service_name"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  # GSI1: Query by service + status
  global_secondary_index {
    name            = "ServiceIndex"
    hash_key        = "service_name"
    range_key       = "status"
    projection_type = "ALL"
  }

  # GSI2: Query by status
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-kb-documents"
  }
}

# DynamoDB Table: KB Chunks
# Stores text chunks with embeddings for vector similarity search
resource "aws_dynamodb_table" "kb_chunks" {
  name         = "${var.project_name}-kb-chunks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "chunk_id"

  attribute {
    name = "chunk_id"
    type = "S"
  }

  attribute {
    name = "document_id"
    type = "S"
  }

  attribute {
    name = "service_name"
    type = "S"
  }

  # GSI1: Query all chunks for a document
  global_secondary_index {
    name            = "DocumentIndex"
    hash_key        = "document_id"
    projection_type = "ALL"
  }

  # GSI2: Query all chunks for a service (for retrieval)
  global_secondary_index {
    name            = "ServiceIndex"
    hash_key        = "service_name"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-kb-chunks"
  }
}
