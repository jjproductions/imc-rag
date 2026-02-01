from fastapi import APIRouter, Depends, HTTPException, Header
import time
import uuid
import logging

from app.models.schemas import QueryRequest, QueryResponse
from app.services.retriever import get_retriever_service
from app.services.llm import get_ollama_service
from app.services.prompt import build_rag_prompt, extract_sources
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def verify_api_key(authorization: str = Header(...)):
    """Verify API key from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    _: None = Depends(verify_api_key)
):
    """
    Query documents with RAG (non-streaming).
    
    Returns complete answer with citations and retrieved chunks.
    """
    trace_id = str(uuid.uuid4())
    start_time = time.time()
    
    logger.info(f"[{trace_id}] Query: {request.query[:100]}...")
    
    # Retrieve relevant chunks
    retriever = get_retriever_service()
    top_k = request.top_k or settings.top_k
    
    chunks, retrieval_time_ms = retriever.retrieve(request.query, top_k)
    
    if not chunks:
        return QueryResponse(
            answer="I don't have any relevant information to answer this question.",
            sources=[],
            retrieved_chunks=[],
            trace_id=trace_id,
            latency_ms=(time.time() - start_time) * 1000,
            retrieval_time_ms=retrieval_time_ms
        )
    
    # Build context
    context = retriever.format_context(chunks)
    
    # Build prompt
    prompt = build_rag_prompt(request.query, context)
    
    # Generate answer
    llm = get_ollama_service()
    temperature = request.temperature if request.temperature is not None else settings.llm_temperature
    
    answer = llm.generate(prompt, temperature=temperature)
    
    # Extract sources
    sources = extract_sources(chunks)
    
    total_time_ms = (time.time() - start_time) * 1000
    
    logger.info(f"[{trace_id}] Query complete in {total_time_ms:.2f}ms")
    
    return QueryResponse(
        answer=answer,
        sources=sources,
        retrieved_chunks=chunks,
        trace_id=trace_id,
        latency_ms=total_time_ms,
        retrieval_time_ms=retrieval_time_ms,
        tokens_generated=None  # Not available in non-streaming mode
    )
