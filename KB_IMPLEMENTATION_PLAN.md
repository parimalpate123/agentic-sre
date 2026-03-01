# Knowledge Base Feature — Phased Implementation Plan

**Project:** TARS (Telemetry Analysis & Resolution System)
**Date:** 2026-02-28
**Approach:** Cost-Optimized MVP (DynamoDB + FAISS) with Aurora pgvector migration path
**Estimated MVP Cost Addition:** ~$15-25/month

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Phase 1 — Foundation (Infrastructure + Ingestion)](#2-phase-1--foundation)
3. [Phase 2 — KB Upload UI + API](#3-phase-2--kb-upload-ui--api)
4. [Phase 3 — Chat Integration (RAG)](#4-phase-3--chat-integration-rag)
5. [Phase 4 — KB Management](#5-phase-4--kb-management)
6. [Phase 5 — Incident-to-KB + Feedback Loop](#6-phase-5--incident-to-kb--feedback-loop)
7. [Phase 6 — Advanced (Post-MVP)](#7-phase-6--advanced-post-mvp)
8. [Migration Path: DynamoDB+FAISS to Aurora pgvector](#8-migration-path)
9. [Cost Breakdown](#9-cost-breakdown)
10. [API Reference](#10-api-reference)
11. [Database Schema](#11-database-schema)
12. [Frontend Component Map](#12-frontend-component-map)
13. [Prompt Engineering](#13-prompt-engineering)
14. [Testing Strategy](#14-testing-strategy)

---

## 1. Architecture Overview

### MVP Architecture (DynamoDB + FAISS)

```
                         ┌─────────────────────────────────┐
                         │          TARS Frontend           │
                         │   (React + React Router + TW)    │
                         └──────────────┬──────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────────┐
                         │     Existing Lambda Handler      │
                         │      (handler_router.py)         │
                         │                                  │
                         │  Existing actions:               │
                         │  - chat, diagnose, incidents...  │
                         │                                  │
                         │  NEW KB actions:                 │
                         │  - kb_upload, kb_upload_complete  │
                         │  - kb_search, kb_list, kb_delete │
                         │  - kb_update, kb_reembed         │
                         │  - kb_promote_incident           │
                         └──────┬────────┬────────┬────────┘
                                │        │        │
                   ┌────────────┘        │        └────────────┐
                   ▼                     ▼                     ▼
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │    S3 Bucket     │  │    DynamoDB       │  │  Bedrock         │
        │  (raw documents) │  │  kb_documents     │  │  Titan V2        │
        │  versioned       │  │  kb_chunks        │  │  (embeddings)    │
        └──────────────────┘  └──────────────────┘  │  Claude Sonnet   │
                                                     │  Claude Haiku    │
                                                     └──────────────────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │  FAISS In-Memory  │
                              │  (Lambda runtime) │
                              │  Cosine similarity│
                              │  on filtered set  │
                              └──────────────────┘
```

### Why DynamoDB + FAISS for MVP (not Aurora pgvector)

| Factor | DynamoDB + FAISS | Aurora pgvector |
|--------|-----------------|-----------------|
| Monthly fixed cost | ~$3-5 (on-demand) | ~$45-75 (min ACU) |
| Setup complexity | Low (reuse existing DynamoDB patterns) | Medium (new cluster, VPC, proxy) |
| Query latency (warm) | ~50-200ms | ~10-50ms |
| Query latency (cold) | ~1-3s (index rebuild) | ~5-10s (Aurora cold start) |
| Max practical scale | ~5,000-10,000 chunks | Unlimited |
| Terraform changes | 2 new DynamoDB tables + S3 bucket | Aurora cluster + subnet groups + SGs + proxy |
| Matches existing stack | Yes (5 DynamoDB tables already) | No (new technology to manage) |

**Decision:** Start with DynamoDB + FAISS. Migrate to Aurora pgvector when chunk count exceeds 10,000 or query latency requirements tighten.

### Key Design Principles

1. **Abstraction layer for storage** — `kb_storage.py` with interface that works for both DynamoDB and Aurora
2. **Extend existing Lambda** — new actions in `handler_router.py`, no new Lambda functions
3. **Titan V2 at 256 dimensions** — adequate for filtered search, 4x cheaper/faster than 1024
4. **Metadata-first filtering** — filter by service + ai_context + doc_type BEFORE vector similarity
5. **Top 3 chunks, 0.7 similarity threshold** — balance relevance vs Claude token cost

---

## 2. Phase 1 — Foundation

**Duration:** 3-5 days
**Goal:** Infrastructure + ingestion pipeline + storage layer
**Cost impact:** ~$3-5/month (DynamoDB on-demand + S3)

### 2.1 Terraform — New Resources

**File: `infrastructure/s3_kb.tf`**

```hcl
# S3 bucket for KB raw documents
resource "aws_s3_bucket" "kb_documents" {
  bucket = "${var.project_name}-kb-documents-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-kb-documents"
  }
}

resource "aws_s3_bucket_versioning" "kb_documents" {
  bucket = aws_s3_bucket.kb_documents.id
  versioning_configuration {
    status = "Enabled"
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

resource "aws_s3_bucket_lifecycle_configuration" "kb_documents" {
  bucket = aws_s3_bucket.kb_documents.id

  rule {
    id     = "move-to-ia"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }
}
```

**File: `infrastructure/dynamodb_kb.tf`**

```hcl
# DynamoDB Table: KB Documents (metadata)
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

  global_secondary_index {
    name            = "ServiceIndex"
    hash_key        = "service_name"
    range_key       = "status"
    projection_type = "ALL"
  }

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

# DynamoDB Table: KB Chunks (content + embeddings)
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

  global_secondary_index {
    name            = "DocumentIndex"
    hash_key        = "document_id"
    projection_type = "ALL"
  }

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
```

**Update: `infrastructure/lambda.tf`** — add env vars + S3/Bedrock permissions

```hcl
# Add to Lambda environment variables:
KB_DOCUMENTS_TABLE  = aws_dynamodb_table.kb_documents.name
KB_CHUNKS_TABLE     = aws_dynamodb_table.kb_chunks.name
KB_S3_BUCKET        = aws_s3_bucket.kb_documents.id
TITAN_EMBED_MODEL   = "amazon.titan-embed-text-v2:0"
TITAN_EMBED_DIMS    = "256"

# Add to Lambda IAM policy:
# - s3:PutObject, s3:GetObject, s3:DeleteObject on kb_documents bucket
# - bedrock:InvokeModel for amazon.titan-embed-text-v2:0
# - dynamodb:* on kb_documents and kb_chunks tables
```

### 2.2 Deliverables Checklist

| # | Task | File(s) | Details |
|---|------|---------|---------|
| 1.1 | S3 KB bucket | `infrastructure/s3_kb.tf` | Versioned, encrypted, lifecycle to IA |
| 1.2 | DynamoDB kb_documents table | `infrastructure/dynamodb_kb.tf` | Document metadata, GSIs for service + status |
| 1.3 | DynamoDB kb_chunks table | `infrastructure/dynamodb_kb.tf` | Chunks with embeddings stored as binary |
| 1.4 | Lambda env vars + IAM | `infrastructure/lambda.tf`, `infrastructure/iam.tf` | New env vars, S3 + Bedrock embed permissions |
| 1.5 | KB storage abstraction | `lambda-handler/kb_storage.py` | CRUD for documents + chunks, DynamoDB backend |
| 1.6 | Document parser | `lambda-handler/kb_parser.py` | Parse PDF, MD, TXT into raw text |
| 1.7 | Chunking engine | `lambda-handler/kb_chunker.py` | Recursive text splitting, 500-800 tokens, 100 overlap |
| 1.8 | Embedding service | `lambda-handler/kb_embedder.py` | Titan V2 256-dim, batch embedding, caching |
| 1.9 | Ingestion orchestrator | `lambda-handler/kb_ingestion_handler.py` | S3 download → parse → chunk → embed → store |
| 1.10 | Terraform apply + validate | — | Deploy infra, verify tables + bucket created |

### 2.3 DynamoDB Item Schemas

**kb_documents item:**
```json
{
  "document_id": "doc-uuid-1234",
  "service_name": "payment-service",
  "feature_name": "checkout",
  "ai_context": ["triage", "remediation"],
  "doc_type": "runbook",
  "file_name": "payment-restart-runbook.md",
  "s3_key": "payment-service/runbook/payment-restart-runbook.md",
  "file_size_bytes": 15230,
  "mime_type": "text/markdown",
  "version": 1,
  "version_notes": "Initial upload",
  "status": "active",
  "chunk_count": 12,
  "uploaded_by": "admin",
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-03-01T10:00:30Z"
}
```

**kb_chunks item:**
```json
{
  "chunk_id": "chunk-uuid-5678",
  "document_id": "doc-uuid-1234",
  "service_name": "payment-service",
  "feature_name": "checkout",
  "ai_context": ["triage", "remediation"],
  "doc_type": "runbook",
  "content": "## Step 3: Restart Payment Service\n\nSSH into the payment server...",
  "embedding": "<Binary: 256-dim float32 vector, 1024 bytes>",
  "chunk_index": 2,
  "total_chunks": 12,
  "section_title": "Step 3: Restart Payment Service",
  "token_count": 487,
  "source_doc": "payment-restart-runbook.md",
  "created_at": "2026-03-01T10:00:25Z"
}
```

### 2.4 Key Implementation Details

**Chunking strategy (`kb_chunker.py`):**
```
Input: raw document text
  │
  ├─ Detect structure (markdown headers, numbered steps, paragraphs)
  │
  ├─ Split by structure boundaries first:
  │   - ## Header → new chunk boundary
  │   - Numbered step → new chunk boundary
  │   - If chunk > 800 tokens, sub-split by paragraph
  │   - If chunk < 200 tokens, merge with next
  │
  ├─ Add overlap (100 tokens from end of previous chunk)
  │
  └─ Output: list of { content, chunk_index, section_title, token_count }
```

**Embedding storage in DynamoDB:**
- Store as Binary attribute (not String/JSON) — 256 floats × 4 bytes = 1,024 bytes per chunk
- DynamoDB max item size is 400KB — easily fits content + embedding + metadata
- Use `struct.pack('256f', *embedding)` to serialize, `struct.unpack` to deserialize

**FAISS index strategy (`kb_embedder.py`):**
```
At query time:
  1. Filter chunks from DynamoDB by service_name + ai_context + doc_type
  2. Load embeddings into numpy array
  3. Build FAISS IndexFlatIP (inner product = cosine on normalized vectors)
  4. Query with embedded question
  5. Return top 3 above 0.7 similarity threshold

Optimization:
  - Cache FAISS index in Lambda /tmp by service_name (persists across warm invocations)
  - Invalidate cache when new documents are uploaded for that service
  - For <1000 chunks per service, index build takes <100ms
```

---

## 3. Phase 2 — KB Upload UI + API

**Duration:** 3-5 days
**Goal:** Users can upload documents through the UI, documents get processed and stored
**Depends on:** Phase 1 complete

### 3.1 Backend — New Handler Actions

**File: `lambda-handler/kb_handler.py`** (new)

| Action | Method | Description |
|--------|--------|-------------|
| `kb_upload` | POST | Generate presigned S3 URL + create document record |
| `kb_upload_complete` | POST | Trigger ingestion pipeline for uploaded document |
| `kb_list` | GET | List documents with filters (service, status, doc_type) |
| `kb_get_document` | GET | Get document detail + chunk previews |
| `kb_delete` | POST | Delete document + all chunks from DynamoDB + S3 |
| `kb_update` | POST | Update document metadata (ai_context, doc_type, status) |

**Update: `lambda-handler/handler_router.py`**

```python
# Add to router:
elif action == 'kb_upload':
    return kb_upload_handler(body)
elif action == 'kb_upload_complete':
    return kb_upload_complete_handler(body)
elif action == 'kb_list':
    return kb_list_handler(params)
elif action == 'kb_get_document':
    return kb_get_document_handler(params)
elif action == 'kb_delete':
    return kb_delete_handler(body)
elif action == 'kb_update':
    return kb_update_handler(body)
```

### 3.2 Upload Flow (End-to-End)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend  │     │  Lambda  │     │    S3    │     │ DynamoDB │
│ Upload    │     │  API     │     │  Bucket  │     │  Tables  │
│ Form      │     │          │     │          │     │          │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. POST kb_upload              │                │
     │ (metadata)     │                │                │
     │───────────────>│                │                │
     │                │ 2. Create doc record            │
     │                │   (status=pending)              │
     │                │───────────────────────────────->│
     │                │                │                │
     │                │ 3. Generate presigned URL       │
     │                │───────────────>│                │
     │                │                │                │
     │ 4. Return      │                │                │
     │ {document_id,  │                │                │
     │  upload_url}   │                │                │
     │<───────────────│                │                │
     │                │                │                │
     │ 5. PUT file directly to S3     │                │
     │ (presigned URL)│                │                │
     │────────────────────────────────>│                │
     │                │                │                │
     │ 6. POST kb_upload_complete     │                │
     │ {document_id}  │                │                │
     │───────────────>│                │                │
     │                │ 7. Update status=processing     │
     │                │───────────────────────────────->│
     │                │                │                │
     │                │ 8. Download from S3             │
     │                │<───────────────│                │
     │                │                │                │
     │                │ 9. Parse → Chunk → Embed        │
     │                │ (Titan V2)     │                │
     │                │                │                │
     │                │ 10. Store chunks                │
     │                │───────────────────────────────->│
     │                │                │                │
     │                │ 11. Update status=active        │
     │                │    chunk_count=N                │
     │                │───────────────────────────────->│
     │                │                │                │
     │ 12. Return     │                │                │
     │ {status, chunks}│               │                │
     │<───────────────│                │                │
```

### 3.3 Frontend — Knowledge Base Page

**New route in `main.jsx`:**
```jsx
<Route path="/knowledge-base" element={<App view="kb" />} />
<Route path="/knowledge-base/:documentId" element={<App view="kb-detail" />} />
```

**New components:**

| Component | File | Description |
|-----------|------|-------------|
| `KnowledgeBase.jsx` | `src/components/KnowledgeBase.jsx` | Main KB page with Upload / Manage tabs |
| `KBUploadForm.jsx` | `src/components/KBUploadForm.jsx` | Upload form with metadata fields + file picker |
| `KBDocumentList.jsx` | `src/components/KBDocumentList.jsx` | Table view of uploaded documents |
| `KBDocumentDetail.jsx` | `src/components/KBDocumentDetail.jsx` | Single document view with chunk list |

**Upload form fields:**

```
┌──────────────────────────────────────────────────────────┐
│  Upload Knowledge Base Document                          │
│                                                          │
│  Service Name *        [ payment-service        ▼ ]      │
│  Feature Name          [ checkout               ▼ ]      │
│  AI Context *          [✓] Triage  [✓] Remediation       │
│                        [ ] PR Review  [ ] Architecture   │
│  Document Type *       [ Runbook                ▼ ]      │
│  Version Notes         [ Initial upload____________ ]    │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │  📄 Drag & drop file here or click to browse │       │
│  │     PDF, MD, TXT (max 10MB)                  │       │
│  └──────────────────────────────────────────────┘       │
│                                                          │
│                              [ Cancel ]  [ Upload ]      │
└──────────────────────────────────────────────────────────┘
```

**Update `SessionSidebar.jsx`:**
- Enable the "Knowledge base" button (currently disabled)
- Add `onClick` → `navigate('/knowledge-base')`
- Add active state styling when on `/knowledge-base` route

**Update `api.js`:**
```javascript
// New KB API functions
export async function kbUpload(metadata) { ... }
export async function kbUploadComplete(documentId) { ... }
export async function kbUploadFile(presignedUrl, file) { ... }
export async function kbListDocuments(filters) { ... }
export async function kbGetDocument(documentId) { ... }
export async function kbDeleteDocument(documentId) { ... }
export async function kbUpdateDocument(documentId, updates) { ... }
```

### 3.4 Deliverables Checklist

| # | Task | File(s) |
|---|------|---------|
| 2.1 | KB handler with all actions | `lambda-handler/kb_handler.py` |
| 2.2 | Router integration | `lambda-handler/handler_router.py` |
| 2.3 | Presigned URL generation | `lambda-handler/kb_handler.py` |
| 2.4 | KB page (main + tabs) | `src/components/KnowledgeBase.jsx` |
| 2.5 | Upload form component | `src/components/KBUploadForm.jsx` |
| 2.6 | Document list component | `src/components/KBDocumentList.jsx` |
| 2.7 | Routes + sidebar activation | `src/main.jsx`, `src/components/SessionSidebar.jsx` |
| 2.8 | API service functions | `src/services/api.js` |
| 2.9 | File type validation (frontend) | Max 10MB, PDF/MD/TXT only for Phase 1 |
| 2.10 | Upload progress indicator | Loading states, processing status polling |

---

## 4. Phase 3 — Chat Integration (RAG)

**Duration:** 3-4 days
**Goal:** Chat responses are augmented with relevant KB content
**Depends on:** Phase 1 + Phase 2 complete
**This is the highest-value phase — where KB delivers actual user impact.**

### 4.1 Retrieval Logic

**New file: `lambda-handler/kb_retriever.py`**

```python
# Pseudocode

def retrieve_kb_context(query, service_name, ai_context, doc_types, top_k=3, threshold=0.7):
    """
    1. Embed the query using Titan V2 (256 dims)
    2. Fetch chunks from DynamoDB filtered by service + ai_context + doc_type
    3. Build FAISS index from filtered chunks
    4. Search for top_k similar chunks above threshold
    5. Return chunks with similarity scores
    """

    # Step 1: Embed query
    query_embedding = embed_text(query)  # Titan V2, 256 dims

    # Step 2: Filter chunks from DynamoDB
    chunks = kb_storage.query_chunks_by_filters(
        service_name=service_name,
        ai_context=ai_context,      # e.g., 'triage'
        doc_types=doc_types          # e.g., ['technical', 'runbook']
    )

    if not chunks:
        return []

    # Step 3: Build FAISS index (cached in /tmp for warm Lambda)
    embeddings = np.array([deserialize_embedding(c['embedding']) for c in chunks])
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(256)
    index.add(embeddings)

    # Step 4: Search
    query_vec = np.array([query_embedding]).astype('float32')
    faiss.normalize_L2(query_vec)
    scores, indices = index.search(query_vec, top_k)

    # Step 5: Filter by threshold and return
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if score >= threshold and idx >= 0:
            chunk = chunks[idx]
            results.append({
                'content': chunk['content'],
                'source_doc': chunk['source_doc'],
                'section_title': chunk.get('section_title', ''),
                'similarity': round(float(score), 3),
                'service_name': chunk['service_name'],
                'doc_type': chunk['doc_type']
            })

    return results
```

### 4.2 Chat Handler Modification

**File: `lambda-handler/chat_handler.py`**

Insert KB retrieval **before** the final Claude invocation:

```python
# In chat_handler.py, before calling Bedrock invoke_model:

# Retrieve KB context if service is known
kb_context = []
if service_name:
    kb_context = retrieve_kb_context(
        query=user_question,
        service_name=service_name,
        ai_context='triage',           # default for chat
        doc_types=['technical', 'runbook', 'guideline'],
        top_k=3,
        threshold=0.7
    )

# Inject into prompt
if kb_context:
    kb_section = format_kb_for_prompt(kb_context)
    # Insert between system prompt and user message
```

### 4.3 Prompt Template with KB

```
You are TARS, an SRE AI assistant.

## Instructions
- Use the provided Knowledge Base context as your primary reference.
- Prefer organization-specific guidance over generic reasoning.
- If KB content conflicts with log evidence, explain the discrepancy.
- Always cite which KB source(s) you referenced.

## Knowledge Base Context
{kb_chunks_formatted}

Source: {source_doc_1} (Section: {section_title_1}, Relevance: {similarity_1})
---
{chunk_content_1}

Source: {source_doc_2} (Section: {section_title_2}, Relevance: {similarity_2})
---
{chunk_content_2}

## Log Analysis Results
{log_analysis_results}

## User Question
{user_question}

## Response Format
Provide:
1. Answer (grounded in KB + log evidence)
2. KB sources referenced
3. Confidence level (High/Medium/Low based on KB match quality + log correlation)
4. Recommended next steps
```

### 4.4 Response Schema Enhancement

Add KB metadata to chat response:

```json
{
  "answer": "Based on the payment-service runbook...",
  "log_entries": [...],
  "insights": [...],
  "recommendations": [...],
  "kb_sources": [
    {
      "source_doc": "payment-restart-runbook.md",
      "section_title": "Step 3: Restart Payment Service",
      "similarity": 0.89,
      "doc_type": "runbook"
    },
    {
      "source_doc": "payment-error-codes.md",
      "section_title": "Error 5xx Handling",
      "similarity": 0.82,
      "doc_type": "technical"
    }
  ],
  "kb_confidence": "high",
  "kb_chunks_used": 2
}
```

### 4.5 Frontend — KB Indicators in Chat

**New component: `KBSourceIndicator.jsx`**

Shown inside `MessageBubble.jsx` when `kb_sources` is present:

```
┌─────────────────────────────────────────────────────┐
│  TARS response here...                              │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ 📚 Knowledge Context Used (2 sources)  [▼]  │   │
│  │                                              │   │
│  │ • payment-restart-runbook.md                 │   │
│  │   Section: Step 3: Restart Payment Service   │   │
│  │   Relevance: 89%                             │   │
│  │                                              │   │
│  │ • payment-error-codes.md                     │   │
│  │   Section: Error 5xx Handling                │   │
│  │   Relevance: 82%                             │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Confidence: High (2 KB matches + log correlation)  │
└─────────────────────────────────────────────────────┘
```

### 4.6 Retrieval Strategy Per AI Context

| AI Context | Filter: doc_type | Trigger |
|------------|-----------------|---------|
| `triage` | technical, runbook | Default for chat questions |
| `remediation` | runbook, previous_incident | When incident is created or remediation starts |
| `pr_review` | guideline | When PR review is triggered |
| `architecture` | functional, technical | When architecture questions are asked |

### 4.7 Deliverables Checklist

| # | Task | File(s) |
|---|------|---------|
| 3.1 | KB retriever module | `lambda-handler/kb_retriever.py` |
| 3.2 | FAISS integration + caching | `lambda-handler/kb_retriever.py` |
| 3.3 | Chat handler KB injection | `lambda-handler/chat_handler.py` |
| 3.4 | Prompt template with KB section | `lambda-handler/chat_handler.py` |
| 3.5 | Response schema with kb_sources | `lambda-handler/chat_handler.py` |
| 3.6 | KB source indicator component | `src/components/KBSourceIndicator.jsx` |
| 3.7 | MessageBubble KB integration | `src/components/MessageBubble.jsx` |
| 3.8 | Haiku routing for KB-only queries | `lambda-handler/chat_handler.py` |
| 3.9 | FAISS Lambda layer or bundling | `lambda-handler/requirements.txt` |
| 3.10 | End-to-end test: upload doc → ask question → verify KB in response | Manual |

### 4.8 FAISS in Lambda — Packaging Note

FAISS needs to be included in the Lambda deployment package:

```
# Option A: faiss-cpu in requirements.txt (adds ~30MB)
faiss-cpu==1.7.4

# Option B: Lambda Layer with pre-compiled faiss
# Build layer: pip install faiss-cpu -t python/ && zip layer.zip python/

# Option C: Pure numpy fallback (no FAISS dependency)
# For <1000 chunks, numpy cosine similarity is fast enough:
# similarities = np.dot(embeddings, query_vec.T).flatten()
```

**Recommendation:** Start with **Option C (numpy fallback)** for MVP. It handles up to ~5000 chunks easily. Add FAISS layer only if performance becomes an issue.

---

## 5. Phase 4 — KB Management

**Duration:** 2-3 days
**Goal:** Full document lifecycle — list, view, disable, re-embed, delete
**Depends on:** Phase 2 complete

### 5.1 Manage KB Screen

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Knowledge Base                                                              │
│  [ Upload ]  [ Manage ]                                                      │
│                                                                              │
│  Filters: Service [ All ▼ ]  Type [ All ▼ ]  Status [ Active ▼ ]            │
│                                                                              │
│  ┌────────────┬──────────┬────────────┬──────────┬────────┬────────┬───────┐ │
│  │ Document   │ Service  │ AI Context │ Doc Type │ Chunks │ Status │Actions│ │
│  ├────────────┼──────────┼────────────┼──────────┼────────┼────────┼───────┤ │
│  │ payment-   │ payment- │ triage,    │ runbook  │   12   │ active │ ⋮    │ │
│  │ restart.md │ service  │ remediation│          │        │        │       │ │
│  ├────────────┼──────────┼────────────┼──────────┼────────┼────────┼───────┤ │
│  │ error-     │ payment- │ triage     │ technical│    8   │ active │ ⋮    │ │
│  │ codes.pdf  │ service  │            │          │        │        │       │ │
│  ├────────────┼──────────┼────────────┼──────────┼────────┼────────┼───────┤ │
│  │ deploy-    │ order-   │ remediation│ guideline│   15   │disabled│ ⋮    │ │
│  │ guide.md   │ service  │            │          │        │        │       │ │
│  └────────────┴──────────┴────────────┴──────────┴────────┴────────┴───────┘ │
│                                                                              │
│  Actions menu (⋮):                                                           │
│  • View chunks                                                               │
│  • Edit metadata                                                             │
│  • Disable / Enable                                                          │
│  • Re-embed                                                                  │
│  • Delete                                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Document Detail View

Accessed by clicking a document name or "View chunks":

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Back to KB                                                    │
│                                                                  │
│  payment-restart-runbook.md                                      │
│  Service: payment-service  │  Type: runbook  │  Status: active   │
│  Uploaded: 2026-03-01  │  Chunks: 12  │  Version: 1              │
│                                                                  │
│  [ Edit Metadata ]  [ Re-embed ]  [ Disable ]  [ Delete ]       │
│                                                                  │
│  ─── Chunks ─────────────────────────────────────────────────    │
│                                                                  │
│  #1  "Introduction"                              487 tokens      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ This runbook covers the standard procedure for           │   │
│  │ restarting the payment service in production...          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  #2  "Prerequisites"                             312 tokens      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Before proceeding, ensure you have:                      │   │
│  │ - SSH access to payment-prod-*                           │   │
│  │ - PagerDuty escalation confirmed...                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ... (10 more chunks)                                            │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Re-embed Action

When user clicks "Re-embed":
1. Set document status to `processing`
2. Delete existing chunks from DynamoDB
3. Re-download from S3 → parse → chunk → embed with latest Titan model
4. Store new chunks
5. Set status back to `active`

Useful when: embedding model is upgraded, chunking strategy changes, or document was edited in S3.

### 5.4 Deliverables Checklist

| # | Task | File(s) |
|---|------|---------|
| 4.1 | Manage KB tab (document table) | `src/components/KBDocumentList.jsx` |
| 4.2 | Document detail view | `src/components/KBDocumentDetail.jsx` |
| 4.3 | Action handlers (disable, delete, re-embed) | `lambda-handler/kb_handler.py` |
| 4.4 | Edit metadata modal | `src/components/KBEditMetadataModal.jsx` |
| 4.5 | Confirmation dialogs for destructive actions | `src/components/KBDocumentList.jsx` |
| 4.6 | Status badges (active, disabled, processing, failed) | Shared component |
| 4.7 | Filters (service, type, status) | `src/components/KBDocumentList.jsx` |

---

## 6. Phase 5 — Incident-to-KB + Feedback Loop

**Duration:** 2-3 days
**Goal:** Build institutional memory from resolved incidents + improve retrieval quality
**Depends on:** Phase 3 + Phase 4 complete

### 6.1 Promote Incident to KB

Add a button on resolved incidents:

```
┌─────────────────────────────────────────────────────┐
│  Incident: inc-abc123                               │
│  Status: Resolved ✓                                 │
│  Service: payment-service                           │
│  Root Cause: Database connection pool exhaustion    │
│                                                     │
│  [ Reanalyze ]  [ 📌 Promote to Knowledge Base ]   │
└─────────────────────────────────────────────────────┘
```

**When clicked:**

1. Open modal pre-filled with:
   - Service name (from incident)
   - AI context: `['remediation']`
   - Doc type: `previous_incident`
   - Content: auto-generated from incident data:
     ```
     # Incident: {incident_id}
     ## Service: {service_name}
     ## Date: {timestamp}
     ## Root Cause
     {root_cause}
     ## Resolution
     {resolution_steps}
     ## Symptoms
     {symptoms/log_patterns}
     ## Prevention
     {recommendations}
     ```
2. User can edit before confirming
3. System creates KB document (no S3 upload needed — content is generated)
4. Chunks and embeds the generated content

### 6.2 Feedback Loop (Lightweight)

After each KB-augmented response, show:

```
Was this KB-informed answer helpful?  [ 👍 Yes ]  [ 👎 No ]
```

Store feedback in DynamoDB:

```json
{
  "feedback_id": "fb-uuid",
  "session_id": "sess-123",
  "query": "how to restart payment service",
  "kb_chunks_used": ["chunk-id-1", "chunk-id-2"],
  "helpful": true,
  "created_at": "2026-03-15T10:00:00Z"
}
```

**Usage (Phase 6):** Aggregate feedback to identify:
- Low-performing documents (high retrieval, low helpfulness)
- Missing KB areas (queries with no KB hits that get negative feedback)
- High-value documents (frequently retrieved + positive feedback)

### 6.3 Deliverables Checklist

| # | Task | File(s) |
|---|------|---------|
| 5.1 | "Promote to KB" button on resolved incidents | `src/components/MessageBubble.jsx` or incident view |
| 5.2 | Incident-to-KB content generator | `lambda-handler/kb_handler.py` (kb_promote_incident) |
| 5.3 | Promote modal with editable preview | `src/components/KBPromoteModal.jsx` |
| 5.4 | Feedback thumbs up/down UI | `src/components/KBFeedbackButtons.jsx` |
| 5.5 | Feedback storage (DynamoDB or extend chat_sessions) | `lambda-handler/kb_handler.py` |

---

## 7. Phase 6 — Advanced (Post-MVP)

**Duration:** Ongoing
**Goal:** Analytics, multi-agent integration, and production hardening

### 7.1 Usage Analytics Dashboard

```
┌──────────────────────────────────────────────────────────────────┐
│  Knowledge Base                                                  │
│  [ Upload ]  [ Manage ]  [ Analytics ]                          │
│                                                                  │
│  Period: [ Last 30 days ▼ ]                                     │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ KB Queries       │  │ Avg Similarity   │  │ Feedback Score  │ │
│  │     347          │  │     0.83         │  │     87%         │ │
│  │ ▲ 23% vs prev   │  │ ▲ 0.05 vs prev  │  │ ▲ 5% vs prev   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                  │
│  Top Retrieved Documents:                                        │
│  1. payment-restart-runbook.md       (89 retrievals, 94% helpful)│
│  2. error-handling-guideline.pdf     (67 retrievals, 88% helpful)│
│  3. deployment-checklist.md          (45 retrievals, 91% helpful)│
│                                                                  │
│  Queries with No KB Match:                                       │
│  1. "how to scale order-service" (12 times) ← needs KB doc      │
│  2. "redis cache eviction policy" (8 times) ← needs KB doc      │
└──────────────────────────────────────────────────────────────────┘
```

### 7.2 Multi-Agent KB Integration

| Agent | KB Integration |
|-------|---------------|
| Diagnosis Agent (`agent_invoker.py`) | Inject relevant KB into diagnosis prompt for richer root cause analysis |
| Remediation Agent | Surface runbooks + past incidents when creating GitHub issues |
| PR Review | Include coding guidelines from KB when reviewing PRs |
| Incident Auto-Triage | Auto-retrieve KB when CloudWatch alarm triggers incident |

### 7.3 Additional Post-MVP Features

- [ ] DOCX and CSV parser support
- [ ] Bulk upload (zip file with multiple documents)
- [ ] KB search standalone page (outside chat)
- [ ] Auto-suggest KB during incident creation
- [ ] Scheduled re-embedding (when model upgrades)
- [ ] KB sharing across services (global docs)
- [ ] Document expiry warnings (stale content alerts)
- [ ] RBAC for KB upload/delete (when auth is added)

---

## 8. Migration Path

### DynamoDB + FAISS → Aurora pgvector

**When to migrate:**
- Chunk count exceeds 10,000 across all services
- Need sub-50ms query latency consistently
- Need complex queries (e.g., cross-service similarity, aggregations)

**How to migrate (zero-downtime):**

```
Step 1: Deploy Aurora Serverless v2 (Terraform)
Step 2: Create pgvector schema (tables + indexes)
Step 3: Write migration script:
        - Read all chunks from DynamoDB
        - Insert into Aurora with same embeddings
        - Verify row counts match
Step 4: Update kb_storage.py:
        - Add AuroraKBStorage class (same interface as DynamoKBStorage)
        - Feature flag: KB_STORAGE_BACKEND = 'aurora' | 'dynamodb'
Step 5: Switch flag to 'aurora'
Step 6: Verify queries work
Step 7: (Optional) Decommission DynamoDB KB tables
```

**Abstraction interface (`kb_storage.py`):**

```python
class KBStorageInterface:
    def store_document(self, doc_metadata) -> str: ...
    def store_chunks(self, document_id, chunks) -> int: ...
    def query_chunks_by_filters(self, service, ai_context, doc_types) -> list: ...
    def get_document(self, document_id) -> dict: ...
    def list_documents(self, filters) -> list: ...
    def delete_document(self, document_id) -> bool: ...
    def update_document(self, document_id, updates) -> dict: ...

class DynamoKBStorage(KBStorageInterface): ...   # Phase 1 (MVP)
class AuroraKBStorage(KBStorageInterface): ...    # Phase 6+ (Growth)
```

This abstraction ensures that all handler code, retriever code, and frontend API remain unchanged during migration.

### Re-embedding at Higher Dimensions

When migrating to Aurora:
1. Switch Titan V2 from 256 → 1024 dimensions
2. Re-embed all existing documents (batch job)
3. Update VECTOR column and indexes
4. Improves similarity accuracy for larger corpus

---

## 9. Cost Breakdown

### MVP (Phases 1-5) — Monthly

| Resource | Cost | Notes |
|----------|------|-------|
| DynamoDB kb_documents table | ~$1-2 | On-demand, low volume |
| DynamoDB kb_chunks table | ~$2-5 | On-demand, embedding storage as Binary |
| S3 KB bucket | <$1 | <1GB of documents |
| Titan V2 Embeddings (ingestion) | <$1 | One-time per upload, 256 dims |
| Titan V2 Embeddings (query) | <$1 | Per chat request, cached |
| Claude cost increase (KB in prompt) | $5-15 | Top 3 chunks, ~1500-2500 extra tokens |
| Lambda compute (KB operations) | <$2 | Marginal increase on existing Lambda |
| **Total MVP addition** | **$12-25/month** | |

### Growth (Post-Migration to Aurora)

| Resource | Cost | Notes |
|----------|------|-------|
| Aurora Serverless v2 (0.5-2 ACU) | $45-85 | Replaces DynamoDB KB tables |
| Bedrock VPC Endpoint | $7.50 | Added for cost optimization |
| Titan V2 at 1024 dims | $2-10 | Higher quality embeddings |
| Claude cost increase | $15-40 | More queries, same chunk limit |
| **Total growth addition** | **$80-150/month** | |

### Cost Comparison: Optimized vs Original Proposal

| | Original Proposal | Optimized MVP | Savings |
|---|-------------------|--------------|---------|
| Month 1-6 | $70-130/month | $12-25/month | **~80%** |
| Month 7-12 | $70-130/month | $80-150/month | Comparable (Aurora added) |
| Year 1 total | $840-1,560 | $624-1,200 | **~25-30%** |

---

## 10. API Reference

### KB Upload

```
POST /  (Lambda Function URL)
Content-Type: application/json

{
  "action": "kb_upload",
  "service_name": "payment-service",        // required
  "feature_name": "checkout",               // optional
  "ai_context": ["triage", "remediation"],  // required, array
  "doc_type": "runbook",                    // required: functional|technical|runbook|guideline|previous_incident
  "file_name": "restart-guide.md",          // required
  "version_notes": "Initial upload"         // optional
}

Response:
{
  "document_id": "doc-uuid-1234",
  "upload_url": "https://s3.amazonaws.com/...(presigned)...",
  "expires_in": 3600
}
```

### KB Upload Complete

```
POST /
{
  "action": "kb_upload_complete",
  "document_id": "doc-uuid-1234"
}

Response:
{
  "document_id": "doc-uuid-1234",
  "status": "processing"
}

// Poll kb_get_document until status = "active" or "failed"
```

### KB Search

```
POST /
{
  "action": "kb_search",
  "query": "how to restart payment service",
  "service_name": "payment-service",
  "ai_context": "triage",
  "doc_types": ["runbook", "technical"],
  "limit": 3,
  "threshold": 0.7
}

Response:
{
  "results": [
    {
      "content": "## Step 3: Restart Payment Service\nSSH into...",
      "source_doc": "restart-guide.md",
      "section_title": "Step 3: Restart Payment Service",
      "similarity": 0.89,
      "doc_type": "runbook",
      "chunk_index": 2
    }
  ],
  "query_embedding_cached": true,
  "total_chunks_searched": 45
}
```

### KB List Documents

```
GET /?action=kb_list&service_name=payment-service&status=active

Response:
{
  "documents": [
    {
      "document_id": "doc-uuid-1234",
      "file_name": "restart-guide.md",
      "service_name": "payment-service",
      "ai_context": ["triage", "remediation"],
      "doc_type": "runbook",
      "chunk_count": 12,
      "status": "active",
      "version": 1,
      "created_at": "2026-03-01T10:00:00Z"
    }
  ],
  "total": 1
}
```

### KB Delete Document

```
POST /
{
  "action": "kb_delete",
  "document_id": "doc-uuid-1234"
}

Response:
{
  "deleted": true,
  "chunks_deleted": 12
}
```

### KB Promote Incident

```
POST /
{
  "action": "kb_promote_incident",
  "incident_id": "inc-abc123",
  "service_name": "payment-service",
  "feature_name": "checkout",
  "additional_notes": "Optional extra context from the engineer"
}

Response:
{
  "document_id": "doc-uuid-9999",
  "status": "processing",
  "generated_content_preview": "# Incident: inc-abc123\n## Root Cause..."
}
```

---

## 11. Database Schema

### DynamoDB Table: kb_documents

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `document_id` | S | PK | UUID |
| `service_name` | S | GSI-PK | Service filter |
| `status` | S | GSI-SK | active, disabled, processing, failed |
| `feature_name` | S | — | Optional feature scope |
| `ai_context` | L (list of S) | — | ['triage','remediation'] |
| `doc_type` | S | — | runbook, technical, guideline, functional, previous_incident |
| `file_name` | S | — | Original filename |
| `s3_key` | S | — | S3 object path |
| `file_size_bytes` | N | — | File size |
| `mime_type` | S | — | text/markdown, application/pdf, etc. |
| `version` | N | — | Version number |
| `version_notes` | S | — | Change notes |
| `chunk_count` | N | — | Total chunks generated |
| `uploaded_by` | S | — | Who uploaded |
| `created_at` | S | — | ISO 8601 |
| `updated_at` | S | — | ISO 8601 |

### DynamoDB Table: kb_chunks

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `chunk_id` | S | PK | UUID |
| `document_id` | S | GSI-PK | Links to kb_documents |
| `service_name` | S | GSI-PK | Service filter for retrieval |
| `ai_context` | L (list of S) | — | Inherited from document |
| `doc_type` | S | — | Inherited from document |
| `feature_name` | S | — | Inherited from document |
| `content` | S | — | Chunk text |
| `embedding` | B (binary) | — | 256-dim float32 vector (1,024 bytes) |
| `chunk_index` | N | — | Position in document |
| `total_chunks` | N | — | Total chunks in parent doc |
| `section_title` | S | — | Detected section header |
| `token_count` | N | — | Token count of content |
| `source_doc` | S | — | Original filename |
| `created_at` | S | — | ISO 8601 |

---

## 12. Frontend Component Map

```
src/
├── main.jsx                          # Add /knowledge-base routes
├── App.jsx                           # Add view prop handling
│
├── components/
│   ├── SessionSidebar.jsx            # Enable KB button, add navigation
│   ├── ChatWindow.jsx                # No changes (MessageBubble handles KB)
│   ├── MessageBubble.jsx             # Add KBSourceIndicator rendering
│   ├── InputBox.jsx                  # No changes
│   │
│   ├── KnowledgeBase.jsx             # Phase 2: Main KB page (tab container)
│   ├── KBUploadForm.jsx              # Phase 2: Upload form
│   ├── KBDocumentList.jsx            # Phase 4: Document management table
│   ├── KBDocumentDetail.jsx          # Phase 4: Chunk viewer
│   ├── KBEditMetadataModal.jsx       # Phase 4: Edit doc metadata
│   ├── KBSourceIndicator.jsx         # Phase 3: "KB Used (N sources)" in chat
│   ├── KBPromoteModal.jsx            # Phase 5: Incident → KB promotion
│   └── KBFeedbackButtons.jsx         # Phase 5: Thumbs up/down
│
├── services/
│   └── api.js                        # Add all kb* API functions
│
└── config/
    └── kbConfig.js                   # Service list, AI contexts, doc types
```

### Component Build Order (by phase)

| Phase | Components | Priority |
|-------|-----------|----------|
| Phase 2 | `KnowledgeBase.jsx`, `KBUploadForm.jsx`, sidebar update, routes, `api.js` KB functions | Must have |
| Phase 3 | `KBSourceIndicator.jsx`, `MessageBubble.jsx` update | Must have |
| Phase 4 | `KBDocumentList.jsx`, `KBDocumentDetail.jsx`, `KBEditMetadataModal.jsx` | Should have |
| Phase 5 | `KBPromoteModal.jsx`, `KBFeedbackButtons.jsx` | Nice to have |

---

## 13. Prompt Engineering

### System Prompt Addition (when KB context is available)

```
## Knowledge Base Integration
You have access to organization-specific knowledge base documents.
These documents take PRIORITY over your general training data.

Rules:
1. If KB provides a specific procedure, follow it exactly — do not improvise.
2. Always cite the source document and section when using KB content.
3. If KB content contradicts log evidence, clearly state the discrepancy.
4. If no relevant KB content is found, say so and proceed with general analysis.
5. Never fabricate KB references — only cite what was actually retrieved.
```

### KB Context Injection Format

```
--- KNOWLEDGE BASE CONTEXT ---

[Source: payment-restart-runbook.md | Section: Step 3: Restart Payment Service | Relevance: 89%]
This runbook covers the standard procedure for restarting the payment service in production.
Before proceeding, ensure you have SSH access to payment-prod-* instances...

[Source: payment-error-codes.md | Section: Error 5xx Handling | Relevance: 82%]
When payment service returns 500-series errors, check the following:
1. Database connection pool status
2. Redis cache connectivity...

--- END KNOWLEDGE BASE CONTEXT ---
```

### No-KB Fallback

When no KB chunks pass the similarity threshold:

```
Note: No relevant Knowledge Base documents were found for this query.
Proceeding with general analysis based on log data.
Consider uploading relevant documentation to improve future responses.
```

---

## 14. Testing Strategy

### Phase 1 Tests

| Test | Type | Validation |
|------|------|-----------|
| Terraform apply | Infra | DynamoDB tables created, S3 bucket exists |
| Document parser (MD) | Unit | Parse markdown, extract sections correctly |
| Document parser (TXT) | Unit | Parse plain text, split by paragraphs |
| Document parser (PDF) | Unit | Extract text from single/multi-page PDF |
| Chunker | Unit | Correct chunk sizes (500-800 tokens), overlap works |
| Embedder | Integration | Titan V2 returns 256-dim vector |
| Storage (DynamoDB) | Integration | Write/read document + chunks |
| Ingestion e2e | Integration | Upload file → parse → chunk → embed → store → verify |

### Phase 2 Tests

| Test | Type | Validation |
|------|------|-----------|
| Presigned URL generation | Integration | URL works, file uploads to correct S3 path |
| Upload flow e2e | E2E | Frontend upload → S3 → ingestion → status = active |
| KB list API | Integration | Filters by service, status, doc_type |
| KB delete API | Integration | Removes document + all chunks + S3 object |

### Phase 3 Tests

| Test | Type | Validation |
|------|------|-----------|
| Retriever (filtered search) | Integration | Returns relevant chunks for service + context |
| Retriever (threshold) | Unit | Chunks below 0.7 are excluded |
| Chat + KB | E2E | Ask question → response includes kb_sources |
| Chat without KB | E2E | No KB service → response has no kb_sources, works normally |
| Prompt injection | Security | KB content doesn't override system instructions |

### Phase 4-5 Tests

| Test | Type | Validation |
|------|------|-----------|
| Disable document | Integration | Disabled docs excluded from retrieval |
| Re-embed | Integration | Old chunks deleted, new chunks with fresh embeddings |
| Incident promotion | E2E | Resolved incident → KB document created → retrievable |
| Feedback storage | Integration | Thumbs up/down recorded correctly |

---

## Summary Timeline

```
Phase 1: Foundation (Infrastructure + Ingestion)        3-5 days
Phase 2: KB Upload UI + API                             3-5 days
Phase 3: Chat Integration (RAG) ← highest value         3-4 days
Phase 4: KB Management                                  2-3 days
Phase 5: Incident-to-KB + Feedback                      2-3 days
────────────────────────────────────────────────────────────────
Total MVP:                                              ~3-4 weeks

Phase 6: Advanced (Analytics, Multi-agent, Aurora)       Ongoing
```

### Critical Path

```
Phase 1 ──→ Phase 2 ──→ Phase 3 (highest value delivery)
                  │
                  └──→ Phase 4 (can parallel with Phase 3)
                            │
                            └──→ Phase 5
```

Phase 3 (Chat Integration) is where the KB feature delivers real user value. Phases 1 and 2 are prerequisites. Phase 4 and 5 can be developed in parallel or deferred without blocking the core experience.
