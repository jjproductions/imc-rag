# RAG System Architecture Diagrams

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                              │
│                        http://localhost:3000                             │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        OpenWebUI Frontend                          │  │
│  │  • Chat interface                                                  │  │
│  │  • Message history                                                 │  │
│  │  • Streaming display                                               │  │
│  │  • Settings management                                             │  │
│  └────────────────────────────┬──────────────────────────────────────┘  │
└─────────────────────────────────┼──────────────────────────────────────┘
                                  │ HTTP/SSE
                                  │ Authorization: Bearer local-key
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            API GATEWAY                                   │
│                        http://localhost:8000                             │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      RAG-API (FastAPI)                             │  │
│  │                                                                    │  │
│  │  Routes:                     Services:                            │  │
│  │  • /ingest   ─────────────► embeddings.py                        │  │
│  │  • /query    ─────────────► retriever.py                         │  │
│  │  • /stream   ─────────────► llm.py                               │  │
│  │  • /v1/chat  ─────────────► prompt.py                            │  │
│  │  • /health                                                        │  │
│  │  • /stats                                                         │  │
│  │                                                                    │  │
│  │  Utils:                      Core:                                │  │
│  │  • chunking.py              • config.py                           │  │
│  │  • auth middleware          • schemas.py                          │  │
│  └────┬────────────────┬────────────────┬──────────────────┬────────┘  │
└────────┼────────────────┼────────────────┼──────────────────┼──────────┘
         │                │                │                  │
         │ embed          │ search         │ generate         │ store
         ▼                ▼                ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ BAAI/bge-m3  │  │   Qdrant     │  │   Ollama     │  │ Qdrant       │
│ Embeddings   │  │  Vector DB   │  │   LLM        │  │ Metadata     │
│              │  │              │  │              │  │              │
│ • 1024-dim   │  │ • Cosine     │  │ • llama3.1   │  │ • doc_id     │
│ • Normalized │  │ • HNSW       │  │ • Streaming  │  │ • chunk_id   │
│ • Batch      │  │ • Top-K      │  │ • Local      │  │ • text       │
│ • Cache      │  │ • Filter     │  │ • No API     │  │ • source     │
│              │  │              │  │              │  │ • hash       │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
   Port: N/A        Port: 6333       Port: 11434       Port: 6333
```

## Data Flow - Ingestion Pipeline

```
┌────────────┐
│   User     │
│  uploads   │
│ documents  │
└─────┬──────┘
      │ POST /ingest
      ▼
┌─────────────────────────────────────────────────────┐
│                  RAG-API                             │
│                                                      │
│  1. Accept files/folders                            │
│     └─► app/routes/ingest.py                        │
│                                                      │
│  2. Load documents by type                          │
│     └─► app/utils/chunking.py                       │
│          ├─► load_pdf()      (PyPDF2)               │
│          ├─► load_markdown() (text parsing)         │
│          └─► load_text()     (plain text)           │
│                                                      │
│  3. Split into chunks                               │
│     └─► chunk_document()                            │
│          • Size: 800 chars (configurable)           │
│          • Overlap: 100 chars                       │
│          • Sentence-aware splitting                 │
│                                                      │
│  4. Generate embeddings                             │
│     └─► app/services/embeddings.py                  │
│          • Model: BAAI/bge-m3                       │
│          • Batch processing: 32 chunks              │
│          • L2 normalization                         │
│          • Output: 1024-dim vectors                 │
│                                                      │
│  5. Create point payloads                           │
│     └─► Metadata extraction                         │
│          {                                          │
│            "doc_id": "file.pdf",                    │
│            "chunk_id": 0,                           │
│            "text": "chunk content...",              │
│            "source_path": "/docs/file.pdf",         │
│            "page": 1,                               │
│            "hash": "abc123...",                     │
│            "created_at": "2026-02-01T10:00:00Z"     │
│          }                                          │
│                                                      │
│  6. Upsert to Qdrant                                │
│     └─► app/services/qdrant_client.py              │
│          • Idempotent (hash-based deduplication)   │
│          • Batch upsert                            │
│          • Skip existing hashes                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │     Qdrant      │
         │   Vector Store   │
         │                 │
         │  Collection:    │
         │  • Name: corpus │
         │  • Dim: 1024    │
         │  • Distance:    │
         │    COSINE       │
         │  • Index: HNSW  │
         └─────────────────┘
```

## Data Flow - Query Pipeline

```
┌────────────┐
│   User     │
│   asks     │
│  question  │
└─────┬──────┘
      │ POST /query or /stream
      │ {"query": "What is ML?", "top_k": 5}
      ▼
┌─────────────────────────────────────────────────────────────┐
│                      RAG-API                                 │
│                                                              │
│  1. Authenticate                                            │
│     └─► Check Bearer token                                  │
│          • Expected: local-key                              │
│          • Returns: 401 if invalid                          │
│                                                              │
│  2. Embed query                                             │
│     └─► app/services/embeddings.py                          │
│          • "What is ML?" → [0.23, -0.15, ..., 0.08]         │
│          • L2 normalized 1024-dim vector                    │
│                                                              │
│  3. Vector similarity search                                │
│     └─► app/services/qdrant_client.py                       │
│          • Query vector → Qdrant                            │
│          • HNSW index traversal                             │
│          • Cosine similarity scoring                        │
│          • Return top-K chunks (K=5 default)                │
│          • Time: ~40-60ms                                   │
│                                                              │
│  4. Retrieve results                                        │
│     └─► app/services/retriever.py                           │
│          [                                                  │
│            {                                                │
│              "text": "Machine learning is...",              │
│              "doc_id": "ml_intro.md",                       │
│              "chunk_id": 0,                                 │
│              "score": 0.89,                                 │
│              "page": null                                   │
│            },                                               │
│            { ... top-K results ... }                        │
│          ]                                                  │
│                                                              │
│  5. Format context                                          │
│     └─► retriever.format_context()                          │
│          "[Source 1: ml_intro.md#chunk0]                    │
│           Machine learning is...                            │
│                                                              │
│           [Source 2: ml_intro.md#chunk1]                    │
│           The main types are...                             │
│           ..."                                              │
│                                                              │
│  6. Build RAG prompt                                        │
│     └─► app/services/prompt.py                              │
│          "You are a helpful AI assistant...                 │
│                                                              │
│           RULES:                                            │
│           1. Use ONLY provided context                      │
│           2. Cite sources as [Source X]                     │
│           3. Say 'I don't know' if insufficient            │
│                                                              │
│           CONTEXT:                                          │
│           [formatted context from step 5]                   │
│                                                              │
│           QUESTION:                                         │
│           What is ML?                                       │
│                                                              │
│           ANSWER:"                                          │
│                                                              │
│  7. Generate response                                       │
│     └─► app/services/llm.py                                 │
│          • Send prompt to Ollama                            │
│          • Model: llama3.1:8b-instruct-q4_0                 │
│          • Temperature: 0.2                                 │
│          • Max tokens: 2048                                 │
│                                                              │
│          If streaming (/stream or /v1/chat):                │
│          ┌──────────────────────────────────┐               │
│          │  Token-by-token generation       │               │
│          │  "Machine" → "learning" → "is"   │               │
│          │  SSE format: {"delta": "..."}    │               │
│          │  Time to first token: ~300ms     │               │
│          │  Throughput: ~25 tokens/sec      │               │
│          └──────────────────────────────────┘               │
│                                                              │
│          If non-streaming (/query):                         │
│          ┌──────────────────────────────────┐               │
│          │  Wait for complete response      │               │
│          │  Return full text + metadata     │               │
│          └──────────────────────────────────┘               │
│                                                              │
│  8. Add citations & metrics                                 │
│     └─► Extract sources from retrieved chunks               │
│          Add usage stats:                                   │
│          • trace_id: uuid                                   │
│          • latency_ms: total time                           │
│          • retrieval_time_ms: search time                   │
│          • tokens_generated: count                          │
│          • time_to_first_token_ms: TTFT                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
              ┌─────────┐
              │  User   │
              │receives │
              │ answer  │
              │  with   │
              │citations│
              └─────────┘
```

## Service Dependencies

```
┌─────────────────────────────────────────────────────────┐
│                    Service Startup Order                 │
└─────────────────────────────────────────────────────────┘

1. Qdrant (Vector Database)
   ├─► Starts immediately
   ├─► Health check: GET /health
   ├─► Ready in: ~5 seconds
   └─► Persistent volume: qdrant_data

2. Ollama (LLM Runtime)
   ├─► Starts immediately
   ├─► Downloads model on first run (if not cached)
   ├─► Health check: GET /api/tags
   ├─► Ready in: ~30-120 seconds (depends on model download)
   └─► Persistent volume: ollama_models

3. RAG-API (FastAPI Backend)
   ├─► Waits for: Qdrant + Ollama (healthy)
   ├─► Loads: bge-m3 embeddings (~2GB, 30-60s first time)
   ├─► Creates: Qdrant collection if not exists
   ├─► Health check: GET /health
   ├─► Ready in: ~60-180 seconds total
   └─► Depends on: qdrant, ollama

4. OpenWebUI (Frontend)
   ├─► Waits for: RAG-API (healthy)
   ├─► Starts: Web server
   ├─► Ready in: ~10 seconds
   └─► Depends on: rag-api
```

## Network & Ports

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network Topology               │
└─────────────────────────────────────────────────────────┘

                    rag-network (bridge)
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Qdrant     │    │   Ollama     │    │   RAG-API    │
│              │    │              │    │              │
│ Internal:    │    │ Internal:    │    │ Internal:    │
│   6333       │    │   11434      │    │   8000       │
│   6334       │    │              │    │              │
│              │    │              │    │              │
│ External:    │    │ External:    │    │ External:    │
│ 0.0.0.0:6333 │    │ 0.0.0.0:11434│    │ 0.0.0.0:8000 │
└──────────────┘    └──────────────┘    └──────────────┘
        ▲                   ▲                   ▲
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  OpenWebUI   │
                    │              │
                    │ Internal:    │
                    │   8080       │
                    │              │
                    │ External:    │
                    │ 0.0.0.0:3000 │
                    └──────────────┘
                            │
                            ▼
                    [User's Browser]
                  http://localhost:3000
```

## State & Persistence

```
┌─────────────────────────────────────────────────────────┐
│                   Persistent Volumes                     │
└─────────────────────────────────────────────────────────┘

qdrant_data/
├── storage/
│   ├── collections/
│   │   └── imc_corpus/
│   │       ├── segments/          # Vector data
│   │       ├── wal/               # Write-ahead log
│   │       └── snapshots/         # Backup points
│   └── meta/                      # Metadata
└── [persists across restarts]

ollama_models/
├── models/
│   ├── manifests/
│   │   └── llama3.1:8b-instruct-q4_0
│   └── blobs/                     # Model weights
└── [persists across restarts]

openwebui_data/
├── backend/
│   ├── data/
│   │   ├── chats/                 # Chat history
│   │   └── settings/              # User settings
└── [persists across restarts]

[No persistence for rag-api - stateless]
```

## Security Model

```
┌─────────────────────────────────────────────────────────┐
│                   Authentication Flow                    │
└─────────────────────────────────────────────────────────┘

Client Request
     │
     ├─► Header: Authorization: Bearer <token>
     │
     ▼
FastAPI Middleware
     │
     ├─► Extract token from header
     │
     ▼
verify_api_key()
     │
     ├─► Compare with settings.api_key
     │
     ├─► Match? ────► Allow request
     │                      │
     │                      ▼
     │              Execute endpoint logic
     │                      │
     │                      ▼
     │              Return response
     │
     └─► No match? ───► 401 Unauthorized
                             │
                             ▼
                      {
                        "detail": "Invalid API key"
                      }

Public Endpoints (no auth):
  • GET /
  • GET /health
  • GET /docs
  • GET /openapi.json

Protected Endpoints (require auth):
  • POST /ingest
  • POST /query
  • POST /stream
  • POST /v1/chat/completions
  • GET /stats
```

## Performance Characteristics

```
┌─────────────────────────────────────────────────────────┐
│                   Latency Breakdown                      │
└─────────────────────────────────────────────────────────┘

Query Request → Response
│
├─► [1-2ms]    HTTP parsing & auth
│
├─► [50-100ms] Query embedding (bge-m3)
│
├─► [40-60ms]  Vector search (Qdrant HNSW)
│
├─► [5-10ms]   Context formatting
│
├─► [250-350ms] LLM time-to-first-token
│   │
│   └─► Ollama model loading (if cold)
│       Prompt processing
│       First token generation
│
├─► [2000-4000ms] Token streaming
│   │             (~25 tokens/sec × 50-100 tokens)
│   │
│   └─► Each token: ~40ms
│
└─► [10ms]     Final metadata assembly

Total: 2.5-4.5 seconds for typical query

Ingestion Performance:
• Document loading: ~100ms per file
• Chunking: ~10ms per document
• Embedding batch (32 chunks): ~4 seconds
• Qdrant upsert (32 points): ~50ms
• Throughput: ~50-100 chunks/minute
```

---

**Last Updated**: February 1, 2026  
**Version**: 1.0.0
