from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import get_settings
from app.models.schemas import HealthResponse, StatsResponse
from app.services.qdrant_client import get_qdrant_service
from app.services.llm import get_ollama_service
from app.services.embeddings import get_embedding_service
from app.routes import ingest, query, stream

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG API",
    description="Local Retrieval-Augmented Generation API with Qdrant, bge-m3, and Ollama",
    version="1.0.0"
)

settings = get_settings()


# CORS middleware (disabled by default for security)
# Uncomment if you need CORS for web frontend access
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


def verify_api_key(authorization: str = Header(...)):
    """Verify API key from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


# Include routers
app.include_router(ingest.router, tags=["Ingestion"])
app.include_router(query.router, tags=["Query"])
app.include_router(stream.router, tags=["Streaming"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("🚀 Starting RAG API...")
    
    # Initialize services (will auto-connect/load)
    try:
        qdrant = get_qdrant_service()
        logger.info("✅ Qdrant connected")
        
        embeddings = get_embedding_service()
        logger.info("✅ Embedding model loaded")
        
        ollama = get_ollama_service()
        logger.info("✅ Ollama LLM ready")
        
        logger.info("🎉 RAG API ready to serve requests!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "RAG API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Verifies connectivity to Qdrant, Ollama, and embedding model.
    """
    qdrant = get_qdrant_service()
    ollama = get_ollama_service()
    embeddings = get_embedding_service()
    
    qdrant_ok = qdrant.health_check()
    ollama_ok = ollama.health_check()
    embeddings_ok = embeddings.model is not None
    
    all_healthy = qdrant_ok and ollama_ok and embeddings_ok
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        qdrant_connected=qdrant_ok,
        ollama_connected=ollama_ok,
        embedding_model_loaded=embeddings_ok
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats(_: None = Depends(verify_api_key)):
    """
    Get collection statistics.
    
    Requires API key authentication.
    """
    qdrant = get_qdrant_service()
    stats = qdrant.get_stats()
    
    return StatsResponse(
        collection_name=stats['collection_name'],
        total_points=stats['total_points'],
        vector_dim=stats['vector_dim'],
        distance=stats['distance'],
        documents=stats['documents'],
        indexed_at=stats.get('indexed_at', 'N/A')
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
