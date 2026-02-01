from typing import List
from app.models.schemas import RetrievedChunk


def build_rag_prompt(query: str, context: str) -> str:
    """
    Build a RAG-optimized prompt with context and query.
    
    Args:
        query: User question
        context: Retrieved context chunks
        
    Returns:
        Formatted prompt for LLM
    """
    
    system_prompt = """You are a helpful AI assistant that answers questions based on provided context.

RULES:
1. Use ONLY the information from the provided context to answer questions.
2. Cite your sources using the format [Source X] where X is the source number.
3. If the context doesn't contain enough information to answer the question, say "I don't have enough information in the provided context to answer that question."
4. Be concise and factual. Do not add information not present in the context.
5. When making claims, always cite the specific source(s) that support them.
6. If multiple sources support a claim, cite all relevant sources.

CONTEXT:
{context}

QUESTION:
{query}

ANSWER:"""
    
    return system_prompt.format(context=context, query=query)


def extract_sources(chunks: List[RetrievedChunk]) -> List[dict]:
    """
    Extract unique sources from retrieved chunks.
    
    Args:
        chunks: List of retrieved chunks
        
    Returns:
        List of source dictionaries with metadata
    """
    sources = []
    seen = set()
    
    for chunk in chunks:
        source_id = f"{chunk.doc_id}#chunk{chunk.chunk_id}"
        if source_id not in seen:
            sources.append({
                'doc_id': chunk.doc_id,
                'chunk_id': chunk.chunk_id,
                'source_path': chunk.source_path,
                'page': chunk.page,
                'score': chunk.score,
                'reference': source_id
            })
            seen.add(source_id)
    
    return sources


RAG_SYSTEM_MESSAGE = {
    "role": "system",
    "content": """You are a helpful AI assistant that answers questions based on provided context.

RULES:
1. Use ONLY the information from the provided context to answer questions.
2. Cite your sources using the format [Source X] where X is the source number from the context.
3. If the context doesn't contain enough information, say "I don't have enough information in the provided context to answer that question."
4. Be concise and factual. Do not add information not present in the context.
5. When making claims, always cite the specific source(s) that support them.
6. If multiple sources support a claim, cite all relevant sources."""
}
