# RAG System - Complete Project Structure

```
rag-system/
├── README.md                          # Main documentation
├── QUICKSTART.md                      # Quick start guide
├── CURL_EXAMPLES.md                   # cURL command examples
├── SMOKE_TEST_TRANSCRIPT.md           # Example test run output
├── docker-compose.yml                 # Multi-service orchestration
├── Dockerfile                         # RAG-API container image
├── Makefile                          # Convenient commands
├── requirements.txt                   # Python dependencies
├── requirements-dev.txt               # Development dependencies
├── pytest.ini                        # Pytest configuration
├── smoke_test.py                     # End-to-end smoke tests
├── .env                              # Environment configuration (active)
├── .env.example                      # Environment template
├── .gitignore                        # Git ignore patterns
│
├── app/                              # Main application
│   ├── __init__.py
│   ├── main.py                       # FastAPI app entry point
│   │
│   ├── core/                         # Core configuration
│   │   ├── __init__.py
│   │   └── config.py                 # Settings management
│   │
│   ├── models/                       # Data models
│   │   ├── __init__.py
│   │   └── schemas.py                # Pydantic models
│   │
│   ├── services/                     # Business logic
│   │   ├── __init__.py
│   │   ├── embeddings.py             # Embedding generation (bge-m3)
│   │   ├── qdrant_client.py          # Vector database client
│   │   ├── retriever.py              # Retrieval orchestration
│   │   ├── llm.py                    # Ollama LLM interface
│   │   └── prompt.py                 # Prompt templates
│   │
│   ├── routes/                       # API endpoints
│   │   ├── __init__.py
│   │   ├── ingest.py                 # Document ingestion
│   │   ├── query.py                  # Non-streaming queries
│   │   └── stream.py                 # Streaming + OpenAI endpoints
│   │
│   └── utils/                        # Utilities
│       ├── __init__.py
│       └── chunking.py               # Document loading & chunking
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── test_chunking.py              # Chunking tests
│   ├── test_embeddings.py            # Embedding tests
│   ├── test_qdrant.py                # Qdrant integration tests
│   └── test_llm.py                   # LLM service tests
│
└── docs/                             # Sample documents
    ├── machine_learning_intro.md     # ML concepts
    ├── vector_databases.md           # Vector DB guide
    └── architecture.txt              # RAG architecture
```

## File Descriptions

### Root Configuration Files

- **docker-compose.yml**: Orchestrates 4 services (Qdrant, Ollama, RAG-API, OpenWebUI) with health checks and volumes
- **Dockerfile**: Multi-stage Python 3.11 image for RAG-API service
- **Makefile**: Convenient targets (up, down, logs, ingest, test, etc.)
- **.env**: Active environment configuration (API keys, model names, parameters)
- **.env.example**: Template for environment variables
- **requirements.txt**: Production Python dependencies
- **requirements-dev.txt**: Development/testing dependencies
- **pytest.ini**: Pytest configuration and markers

### Application Structure

#### `app/main.py`

- FastAPI application initialization
- Route registration (ingest, query, stream)
- Startup event handlers
- Health check and stats endpoints
- Optional CORS configuration (disabled by default)

#### `app/core/config.py`

- Pydantic Settings for environment variables
- Cached settings singleton
- All configuration parameters (Qdrant, embeddings, Ollama, retrieval)

#### `app/models/schemas.py`

- Request/response models for all endpoints
- IngestRequest, IngestResponse
- QueryRequest, QueryResponse
- StreamRequest, ChatCompletionRequest
- RetrievedChunk, StatsResponse, HealthResponse

#### `app/services/embeddings.py`

- EmbeddingService class
- Loads BAAI/bge-m3 via sentence-transformers
- Normalizes embeddings (L2 norm for cosine similarity)
- Batch embedding with progress tracking
- Singleton pattern for model reuse
- Offline mode support

#### `app/services/qdrant_client.py`

- QdrantService class
- Collection management (create with cosine distance, 1024-dim)
- Idempotent upsert (hash-based deduplication)
- Vector search with filtering support
- Statistics aggregation
- Health check and retry logic

#### `app/services/retriever.py`

- RetrieverService class
- Orchestrates embedding + search
- Formats retrieved chunks as context
- Returns chunks with metadata and scores
- Tracks retrieval latency

#### `app/services/llm.py`

- OllamaService class
- Native Ollama API integration
- Non-streaming generation
- Streaming generation (native format)
- OpenAI-compatible streaming
- Model pulling and health checks
- Message-to-prompt conversion

#### `app/services/prompt.py`

- RAG-optimized system prompt
- Citation instruction templates
- Source extraction from chunks
- OpenAI-format system message

#### `app/routes/ingest.py`

- POST /ingest endpoint
- File upload support
- Directory recursive processing
- Batch embedding generation
- Qdrant upsert with metadata
- Bearer token authentication

#### `app/routes/query.py`

- POST /query endpoint
- Non-streaming RAG pipeline
- Retrieve → format → generate → respond
- Returns answer + sources + metrics
- Bearer token authentication

#### `app/routes/stream.py`

- POST /stream endpoint (SSE format)
- POST /v1/chat/completions endpoint (OpenAI-compatible)
- Streaming RAG pipeline
- Token-by-token delivery
- Final usage metrics
- Multi-turn conversation support

#### `app/utils/chunking.py`

- Document loading (PDF, Markdown, TXT)
- Recursive text splitting with overlap
- Sentence-aware chunking
- DocumentChunk class with hash-based deduplication
- Directory processing

### Tests

- **test_chunking.py**: Text splitting, overlap, hash consistency
- **test_embeddings.py**: Model loading, dimension validation, normalization
- **test_qdrant.py**: Connection, upsert, search, idempotency, stats
- **test_llm.py**: Generation, streaming, OpenAI format, message conversion

### Sample Documents

- **machine_learning_intro.md**: ML fundamentals, types, algorithms
- **vector_databases.md**: Vector DB concepts, metrics, use cases, best practices
- **architecture.txt**: RAG system design, data flow, performance characteristics

### Scripts & Tools

- **smoke_test.py**: End-to-end integration test
  - Health check
  - Ingestion
  - Non-streaming query
  - Streaming query
  - Statistics validation

## Key Design Patterns

### Singleton Services

All services (embeddings, Qdrant, LLM) use singleton pattern for resource efficiency.

### Dependency Injection

FastAPI's `Depends()` used for authentication and service access.

### Async/Await

Streaming endpoints use async generators for backpressure handling.

### Environment-Based Configuration

All settings configurable via `.env` file, no hard-coded values.

### Health Checks

All Docker services have health checks with retry logic.

### Observability

Every request has trace_id, latency tracking, and structured logging.

### Security

Bearer token authentication on all mutation endpoints, health/docs public.

## Data Flow Summary

### Ingestion

```
Files → Load → Chunk → Embed (bge-m3) → Qdrant Upsert
```

### Query

```
Question → Embed → Qdrant Search → Format Context → LLM Generate → Stream Response
```

## Technology Stack

| Component        | Technology     | Version  |
| ---------------- | -------------- | -------- |
| Vector DB        | Qdrant         | v1.7.4   |
| LLM Runtime      | Ollama         | latest   |
| Embeddings       | BAAI/bge-m3    | 1024-dim |
| API Framework    | FastAPI        | 0.109.0  |
| Frontend         | OpenWebUI      | main     |
| Language         | Python         | 3.11     |
| Containerization | Docker Compose | v2.x     |

## API Endpoints

| Endpoint               | Method | Auth | Description                |
| ---------------------- | ------ | ---- | -------------------------- |
| `/`                    | GET    | No   | Root info                  |
| `/health`              | GET    | No   | Health check               |
| `/stats`               | GET    | Yes  | Collection statistics      |
| `/ingest`              | POST   | Yes  | Ingest documents           |
| `/query`               | POST   | Yes  | Non-streaming query        |
| `/stream`              | POST   | Yes  | SSE streaming query        |
| `/v1/chat/completions` | POST   | Yes  | OpenAI-compatible endpoint |

## Performance Targets

- Retrieval: < 100ms (p95)
- Time to first token: < 500ms (p95)
- Token generation: > 20 tokens/sec
- Ingestion: > 50 chunks/min
- Memory: < 6GB total (all services)

## Future Enhancements

- [ ] Hybrid search (dense + sparse)
- [ ] Reranking pipeline
- [ ] Query cache
- [ ] Document versioning
- [ ] Multi-user support
- [ ] Conversation memory
- [ ] Fine-tuned embeddings
- [ ] GPU acceleration toggle
- [ ] Prometheus metrics export
- [ ] Grafana dashboards

---

**Project Status**: Production Ready ✅  
**Last Updated**: 2026-02-01  
**License**: MIT
