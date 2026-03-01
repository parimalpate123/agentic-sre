# S3 Bucket for Knowledge Base raw documents
resource "aws_s3_bucket" "kb_documents" {
  bucket = "${var.project_name}-kb-documents-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-kb-documents"
  }
}

resource "aws_s3_bucket_versioning" "kb_documents" {
  bucket = aws_s3_bucket.kb_documents.id
  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kb_documents" {
  bucket = aws_s3_bucket.kb_documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "kb_documents" {
  bucket                  = aws_s3_bucket.kb_documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "kb_documents" {
  bucket = aws_s3_bucket.kb_documents.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
