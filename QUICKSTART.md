# Quick Start Guide

Get your RAG system running in under 5 minutes.

## Prerequisites

- Docker & Docker Compose installed
- 8GB+ RAM available
- 10GB+ disk space for models
- Internet connection (for initial setup)

## Step 1: Clone or Create Project

```bash
# If you have the code
cd rag-system

# Or create directory structure
mkdir rag-system && cd rag-system
# ... copy all files ...
```

## Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# (Optional) Edit API key
# nano .env
# Change: API_KEY=your-secret-key-here
```

## Step 3: Start Services

```bash
# Start all containers (downloads models on first run)
make up

# This will start:
# - Qdrant (vector database)
# - Ollama (LLM runtime)
# - RAG-API (backend)
# - OpenWebUI (frontend)
```

**⏳ First start takes 2-10 minutes to download models.**

Monitor progress:

```bash
# Watch logs
make logs

# Check when ready (all should show "healthy")
make ps
```

## Step 4: Ingest Documents

```bash
# Ingest sample documents
make ingest path=./docs

# Output should show:
# ✅ Ingested 3 documents
# 📄 Created XX chunks
```

## Step 5: Test the API

```bash
# Run smoke tests
python smoke_test.py
```

Or test manually:

```bash
# Query via API
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer local-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?"
  }' | jq .
```

## Step 6: Use OpenWebUI

1. Open browser: http://localhost:3000

2. Configure connection:
   - Click Settings (gear icon)
   - Go to "Connections" or "External Connections"
   - Set **OpenAI API Base URL**: `http://rag-api:8000/v1`
   - Set **API Key**: `local-key`
   - Save settings

3. Start chatting:
   - Select model: `llama3.1`
   - Ask: "What is machine learning?"
   - Responses will include citations from your documents!

## Verification Checklist

✅ All services healthy: `make ps`  
✅ Documents ingested: `curl -H "Authorization: Bearer local-key" http://localhost:8000/stats`  
✅ Query works: Try the curl example above  
✅ Streaming works: `python smoke_test.py`  
✅ OpenWebUI accessible: http://localhost:3000

## Troubleshooting

### Services not starting

```bash
# Check logs for errors
make logs

# Restart everything
make down
make up
```

### Ollama model not found

```bash
# Pull model manually
docker exec rag-system-ollama-1 ollama pull llama3.1:8b-instruct-q4_0

# Check available models
docker exec rag-system-ollama-1 ollama list
```

### Embeddings model not loading

```bash
# Check if model is downloading
docker logs rag-system-rag-api-1 | grep -i "embedding"

# May take 5-10 minutes on first run
# Model is ~2GB
```

### Out of memory

```bash
# Reduce Ollama model size in .env:
OLLAMA_MODEL=llama3.1:7b-instruct-q4_0

# Or use smaller embedding model (requires re-ingestion):
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
```

### Connection refused errors

```bash
# Wait for services to be fully ready
sleep 30

# Check health
curl http://localhost:8000/health
```

## Next Steps

### Add Your Documents

```bash
# Add your own documents to ./docs
cp /path/to/your/documents/*.pdf ./docs/

# Ingest them
make ingest path=./docs
```

### Change LLM Model

```bash
# Edit .env
OLLAMA_MODEL=mistral:7b-instruct

# Pull new model
docker exec rag-system-ollama-1 ollama pull mistral:7b-instruct

# Restart API
docker compose restart rag-api
```

### Test Streaming

```bash
# Stream a response
curl -N -X POST http://localhost:8000/stream \
  -H "Authorization: Bearer local-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain vector databases"}'
```

### View API Documentation

Open in browser: http://localhost:8000/docs

Interactive Swagger UI with all endpoints.

## Stopping the System

```bash
# Stop all services (keeps data)
make down

# Stop and remove all data
make clean
```

## Common Commands

```bash
make up          # Start services
make down        # Stop services
make logs        # View all logs
make logs-api    # View API logs only
make ps          # Service status
make health      # Check health
make stats       # Collection statistics
make test        # Run tests
make ingest      # Ingest documents
```

## Production Considerations

Before deploying to production:

1. **Change API key**: Edit `.env` and set strong `API_KEY`
2. **Resource limits**: Adjust Docker resource allocations
3. **Monitoring**: Export logs to monitoring system
4. **Backup**: Regularly backup Qdrant volume
5. **Security**: Use firewall rules, don't expose ports publicly
6. **SSL/TLS**: Put behind reverse proxy with HTTPS

## Support

- Check logs: `make logs`
- View health: `make health`
- API docs: http://localhost:8000/docs
- Test suite: `make test`

## Success!

If you've reached this point, your RAG system is ready! 🎉

Start asking questions about your documents through OpenWebUI or the API.
