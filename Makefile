.PHONY: up down logs logs-api restart ps ingest test clean

# Default path for ingestion
path ?= ./docs

up:
	@echo "🚀 Starting RAG system..."
	docker compose up -d
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 5
	@echo "✅ Services started. Check status with: make ps"
	@echo "📊 OpenWebUI: http://localhost:3000"
	@echo "📡 RAG API: http://localhost:8000/docs"

down:
	@echo "🛑 Stopping RAG system..."
	docker compose down

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f rag-api

restart:
	@echo "🔄 Restarting services..."
	docker compose restart

ps:
	docker compose ps

ingest:
	@echo "📥 Ingesting documents from $(path)..."
	@if [ ! -d "$(path)" ]; then \
		echo "❌ Error: Directory $(path) does not exist"; \
		exit 1; \
	fi
	docker exec rag-system-rag-api python -c "import sys; sys.path.insert(0, '/app'); \
		from app.routes.ingest import ingest_directory; \
		from app.core.config import settings; \
		import asyncio; \
		asyncio.run(ingest_directory('$(path)'))"
	@echo "✅ Ingestion complete"

test:
	@echo "🧪 Running tests..."
	docker exec rag-system-rag-api pytest tests/ -v --tb=short

clean:
	@echo "🗑️  Removing all data and volumes..."
	@read -p "Are you sure? This will delete all ingested data (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker compose down -v; \
		echo "✅ Cleanup complete"; \
	else \
		echo "❌ Cleanup cancelled"; \
	fi

health:
	@echo "🏥 Checking service health..."
	@curl -s http://localhost:6333/health | jq . || echo "❌ Qdrant unhealthy"
	@curl -s http://localhost:11434/api/tags | jq . || echo "❌ Ollama unhealthy"
	@curl -s http://localhost:8000/health | jq . || echo "❌ RAG-API unhealthy"

stats:
	@echo "📊 Fetching collection statistics..."
	@curl -s -H "Authorization: Bearer local-key" http://localhost:8000/stats | jq .

pull-models:
	@echo "📦 Pulling Ollama model..."
	docker exec rag-system-ollama ollama pull $(OLLAMA_MODEL)
	@echo "✅ Model pulled successfully"
