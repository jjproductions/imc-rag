# Local RAG Chat System

A fully local, production-ready Retrieval-Augmented Generation (RAG) system with no cloud dependencies at runtime.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User / OpenWebUI                         │
│                      http://localhost:3000                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP/SSE
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         RAG-API (FastAPI)                        │
│                      http://localhost:8000                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   /ingest    │  │    /query    │  │  /stream | /v1/chat  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│         │                 └──────────┬───────────┘              │
│         ▼                            ▼                          │
│  ┌──────────────┐          ┌───────────────────┐               │
│  │  Embeddings  │◄─────────┤    Retriever      │               │
│  │  (bge-m3)    │          │  (Qdrant Query)   │               │
│  └──────┬───────┘          └─────────┬─────────┘               │
│         │                            │                          │
└─────────┼────────────────────────────┼──────────────────────────┘
          │                            │
          │ embed & upsert             │ search vectors
          ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Qdrant (Vector Database)                      │
│                      http://qdrant:6333                          │
│               Collection: cosine, 1024-dim, normalized           │
└─────────────────────────────────────────────────────────────────┘

          Query context + prompt → Ollama LLM ← stream tokens
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Ollama (Local LLM Runtime)                    │
│                      http://ollama:11434                         │
│               Model: llama3.1:8b-instruct-q4_0                   │
└─────────────────────────────────────────────────────────────────┘
```

## Components

- **Qdrant**: Vector database for semantic search (1024-dim cosine similarity)
- **Ollama**: Local LLM runtime (llama3.1:8b-instruct-q4_0)
- **RAG-API**: FastAPI backend orchestrating ingestion, retrieval, and generation
- **OpenWebUI**: Web frontend for chat interface

## Quick Start (Online Mode)

```bash
# 1. Clone and navigate
cd rag-system

# 2. Copy environment file
cp .env.example .env

# 3. Start all services (downloads models on first run)
make up

# 4. Wait for services to be healthy (~2-5 min for model downloads)
make logs

# 5. Ingest sample documents
make ingest path=./docs

# 6. Open OpenWebUI
open http://localhost:3000

# 7. Configure OpenWebUI to use RAG-API:
#    - Go to Settings → Connections
#    - Set OpenAI API Base URL: http://rag-api:8000/v1
#    - Set API Key: local-key
#    - Select model: llama3.1

# 8. Start chatting with your documents!
```

## Offline / Air-Gapped Setup

For environments without internet access at runtime:

### Step 1: Pre-download Models (on internet-connected machine)

```bash
# Create models directory
mkdir -p ./models/embeddings ./models/ollama

# Download bge-m3 embeddings model
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-m3', cache_folder='./models/embeddings')
print('✓ bge-m3 downloaded')
"

# Download Ollama model
docker run -v ./models/ollama:/root/.ollama ollama/ollama:latest \
  ollama pull llama3.1:8b-instruct-q4_0

# Package models directory
tar -czf models.tar.gz ./models
```

### Step 2: Transfer & Mount Models

Transfer `models.tar.gz` to air-gapped machine, then:

```bash
# Extract models
tar -xzf models.tar.gz

# Update docker-compose.yml to mount models:
# Under rag-api service, add:
#   volumes:
#     - ./models/embeddings:/models/embeddings:ro

# Under ollama service, update:
#   volumes:
#     - ./models/ollama:/root/.ollama

# Update .env for offline mode:
HF_DATASETS_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_HOME=/models/embeddings

# Start services
make up
```

### Step 3: Verify Offline Operation

```bash
# Check no external network calls
docker exec rag-api-rag-api-1 env | grep OFFLINE
# Should show: TRANSFORMERS_OFFLINE=1, HF_DATASETS_OFFLINE=1

# Test ingestion
make ingest path=./docs

# Test query
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer local-key" \
  -H "Content-Type: application/json" \
  -d '{"query":"What documents are available?"}'
```

## API Usage

### Ingest Documents

```bash
# Ingest a folder
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer local-key" \
  -F "path=./docs"

# Ingest single file
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer local-key" \
  -F "file=@document.pdf"
```

### Non-Streaming Query

```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer local-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic?",
    "top_k": 5
  }'
```

### Streaming Query (SSE)

```bash
curl -N -X POST http://localhost:8000/stream \
  -H "Authorization: Bearer local-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain the key concepts",
    "top_k": 5
  }'
```

### OpenAI-Compatible Streaming

```bash
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer local-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1",
    "messages": [{"role": "user", "content": "What are the main findings?"}],
    "stream": true
  }'
```

### Get Statistics

```bash
curl http://localhost:8000/stats \
  -H "Authorization: Bearer local-key"
```

## Configuration

Edit `.env` file:

```bash
# Qdrant Configuration
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=imc_corpus

# Embeddings
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024

# Ollama LLM
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_0
LLM_TEMPERATURE=0.2

# Retrieval
TOP_K=5
CHUNK_SIZE=800
CHUNK_OVERLAP=100

# Security
API_KEY=local-key

# Offline Mode (optional)
# HF_DATASETS_OFFLINE=1
# TRANSFORMERS_OFFLINE=1
# HF_HOME=/models/embeddings
```

## Swapping Models

### Change LLM Model

```bash
# 1. Pull new model in Ollama
docker exec -it rag-system-ollama-1 ollama pull mistral:7b-instruct

# 2. Update .env
OLLAMA_MODEL=mistral:7b-instruct

# 3. Restart rag-api
docker compose restart rag-api
```

### Change Embedding Model

⚠️ **Warning**: Changing embeddings requires re-ingesting all documents.

```bash
# 1. Update .env
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384

# 2. Delete existing collection
docker exec -it rag-system-qdrant-1 curl -X DELETE \
  http://localhost:6333/collections/imc_corpus

# 3. Restart rag-api (recreates collection)
docker compose restart rag-api

# 4. Re-ingest documents
make ingest path=./docs
```

## Adjusting Retrieval Parameters

```bash
# More context per query (may slow down LLM)
TOP_K=10

# Larger chunks (better context, fewer chunks)
CHUNK_SIZE=1200
CHUNK_OVERLAP=200

# Smaller chunks (more granular, more results)
CHUNK_SIZE=400
CHUNK_OVERLAP=50

# Restart after changes
docker compose restart rag-api
```

## Adding New Documents

```bash
# Add single file
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer local-key" \
  -F "file=@new-document.pdf"

# Add folder (recursive)
make ingest path=./new-docs

# Verify ingestion
curl http://localhost:8000/stats \
  -H "Authorization: Bearer local-key"
```

## Makefile Targets

```bash
make up           # Start all services
make down         # Stop all services
make logs         # Tail all logs
make logs-api     # Tail rag-api logs only
make restart      # Restart all services
make ps           # Show service status
make ingest       # Ingest docs (requires path=./docs)
make test         # Run pytest suite
make clean        # Remove volumes and data
```

## Observability

All requests include:

- `trace_id`: Unique identifier for request tracking
- `latency_ms`: Total request duration
- `retrieval_time_ms`: Time spent in Qdrant search
- `tokens_generated`: Number of LLM tokens
- `time_to_first_token_ms`: Latency before first token

Check logs:

```bash
docker logs -f rag-system-rag-api-1
```

## Testing

```bash
# Run all tests
make test

# Run specific test
docker exec rag-system-rag-api-1 pytest tests/test_chunking.py -v

# Test with coverage
docker exec rag-system-rag-api-1 pytest --cov=app tests/
```

## Troubleshooting

### Services not starting

```bash
# Check service health
make ps

# Check logs for specific service
docker logs rag-system-qdrant-1
docker logs rag-system-ollama-1
docker logs rag-system-rag-api-1

# Restart all
make down && make up
```

### Embeddings model not loading

```bash
# Check if model is cached
docker exec rag-system-rag-api-1 ls -la /root/.cache/huggingface/

# Force re-download (online mode)
docker exec rag-system-rag-api-1 rm -rf /root/.cache/huggingface/
docker compose restart rag-api
```

### Ollama model not found

```bash
# List available models
docker exec rag-system-ollama-1 ollama list

# Pull model manually
docker exec rag-system-ollama-1 ollama pull llama3.1:8b-instruct-q4_0

# Check model running
curl http://localhost:11434/api/tags
```

### OpenWebUI not connecting to RAG-API

1. Ensure API_KEY matches in `.env` and OpenWebUI settings
2. Use `http://rag-api:8000/v1` (internal Docker network)
3. Check CORS settings in `app/main.py` if needed

### 401 Unauthorized errors

```bash
# Verify API key
curl http://localhost:8000/stats \
  -H "Authorization: Bearer local-key"

# Update .env if needed
API_KEY=your-secure-key-here
```

## Security Considerations

- Change `API_KEY` in `.env` for production
- Do not expose ports outside localhost/internal network
- Use firewall rules to restrict access
- Consider adding rate limiting for production use

## Performance Tuning

```bash
# Increase workers for higher throughput
# In Dockerfile, update CMD:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Adjust Qdrant memory
# In docker-compose.yml:
qdrant:
  environment:
    - QDRANT__STORAGE__PERFORMANCE__MAX_SEARCH_THREADS=4
```

## License

MIT

## Support

For issues, check:

1. Docker logs: `make logs`
2. Service health: `make ps`
3. API docs: http://localhost:8000/docs
