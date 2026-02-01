from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json
import time
import uuid
import logging
from typing import AsyncGenerator

from app.models.schemas import StreamRequest, ChatCompletionRequest
from app.services.retriever import get_retriever_service
from app.services.llm import get_ollama_service
from app.services.prompt import build_rag_prompt, extract_sources, RAG_SYSTEM_MESSAGE
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


async def stream_rag_response(
    query: str,
    top_k: int,
    temperature: float,
    trace_id: str
) -> AsyncGenerator[str, None]:
    """
    Generate streaming RAG response with SSE format.
    
    Yields SSE-formatted events with deltas and final usage metadata.
    """
    start_time = time.time()
    
    logger.info(f"[{trace_id}] Streaming query: {query[:100]}...")
    
    # Retrieve relevant chunks
    retriever = get_retriever_service()
    chunks, retrieval_time_ms = retriever.retrieve(query, top_k)
    
    # Send retrieval metadata
    yield json.dumps({
        "event": "retrieval",
        "retrieval_time_ms": retrieval_time_ms,
        "chunks_found": len(chunks)
    }) + "\n\n"
    
    if not chunks:
        yield json.dumps({
            "delta": "I don't have any relevant information to answer this question."
        }) + "\n\n"
        
        yield json.dumps({
            "complete": True,
            "trace_id": trace_id,
            "usage": {
                "latency_ms": (time.time() - start_time) * 1000,
                "retrieval_time_ms": retrieval_time_ms,
                "tokens_generated": 0
            }
        }) + "\n\n"
        return
    
    # Build context and prompt
    context = retriever.format_context(chunks)
    prompt = build_rag_prompt(query, context)
    
    # Stream LLM response
    llm = get_ollama_service()
    token_count = 0
    first_token_time = None
    
    async for chunk_data in llm.generate_stream(prompt, temperature):
        if chunk_data.get('done'):
            # Send final usage metadata
            total_time = time.time() - start_time
            ttft = (first_token_time - start_time) * 1000 if first_token_time else 0
            
            sources = extract_sources(chunks)
            
            yield json.dumps({
                "complete": True,
                "trace_id": trace_id,
                "sources": sources,
                "usage": {
                    "latency_ms": total_time * 1000,
                    "retrieval_time_ms": retrieval_time_ms,
                    "tokens_generated": token_count,
                    "time_to_first_token_ms": ttft
                }
            }) + "\n\n"
        else:
            # Send token delta
            token = chunk_data.get('response', '')
            if token:
                if first_token_time is None:
                    first_token_time = time.time()
                
                token_count += 1
                yield json.dumps({"delta": token}) + "\n\n"


@router.post("/stream")
async def stream_query(
    request: StreamRequest,
    _: None = Depends(verify_api_key)
):
    """
    Stream RAG response using Server-Sent Events.
    
    Returns:
        SSE stream with:
        - {"delta": "..."} for each token
        - {"complete": true, "usage": {...}} at the end
    """
    trace_id = str(uuid.uuid4())
    top_k = request.top_k or settings.top_k
    temperature = request.temperature if request.temperature is not None else settings.llm_temperature
    
    return EventSourceResponse(
        stream_rag_response(
            query=request.query,
            top_k=top_k,
            temperature=temperature,
            trace_id=trace_id
        ),
        media_type="text/event-stream"
    )


@router.post("/v1/chat/completions")
async def openai_chat_completions(
    request: ChatCompletionRequest,
    _: None = Depends(verify_api_key)
):
    """
    OpenAI-compatible chat completions endpoint.
    
    Supports both streaming and non-streaming modes.
    Performs RAG retrieval on user messages.
    """
    trace_id = str(uuid.uuid4())
    
    # Extract user query from messages
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")
    
    query = user_messages[-1].content
    
    logger.info(f"[{trace_id}] OpenAI-compatible request: {query[:100]}...")
    
    # Retrieve context
    retriever = get_retriever_service()
    chunks, retrieval_time_ms = retriever.retrieve(query, settings.top_k)
    
    # Build augmented messages
    augmented_messages = [RAG_SYSTEM_MESSAGE]
    
    if chunks:
        context = retriever.format_context(chunks)
        augmented_messages.append({
            "role": "user",
            "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{query}"
        })
    else:
        augmented_messages.append({
            "role": "user",
            "content": query
        })
    
    # Get temperature
    temperature = request.temperature if request.temperature is not None else settings.llm_temperature
    
    llm = get_ollama_service()
    
    if request.stream:
        # Return streaming response
        async def openai_stream_generator():
            async for sse_line in llm.chat_stream_openai(augmented_messages, temperature):
                yield sse_line
        
        return StreamingResponse(
            openai_stream_generator(),
            media_type="text/event-stream"
        )
    else:
        # Non-streaming response
        prompt = llm._messages_to_prompt(augmented_messages)
        answer = llm.generate(prompt, temperature)
        
        response = {
            "id": f"chatcmpl-{trace_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": answer
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,  # Not tracked
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        
        return response
