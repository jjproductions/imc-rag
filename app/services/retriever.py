from typing import List, Dict, Any
from app.services.qdrant_client import get_qdrant_service
from app.services.embeddings import get_embedding_service
from app.models.schemas import RetrievedChunk
import logging
import time

logger = logging.getLogger(__name__)


class RetrieverService:
    """Service for retrieving relevant chunks from Qdrant."""
    
    def __init__(self):
        self.qdrant = get_qdrant_service()
        self.embeddings = get_embedding_service()
    
    def retrieve(self, query: str, top_k: int = 5) -> tuple[List[RetrievedChunk], float]:
        """
        Retrieve top-k most relevant chunks for a query.
        
        Args:
            query: User query
            top_k: Number of chunks to retrieve
            
        Returns:
            Tuple of (retrieved chunks, retrieval time in ms)
        """
        start_time = time.time()
        
        # Generate query embedding
        logger.info(f"Retrieving top-{top_k} chunks for query: {query[:100]}...")
        query_vector = self.embeddings.embed_text(query)
        
        # Search Qdrant
        results = self.qdrant.search(
            query_vector=query_vector,
            top_k=top_k
        )
        
        retrieval_time = (time.time() - start_time) * 1000
        
        # Convert to RetrievedChunk objects
        chunks = []
        for result in results:
            payload = result['payload']
            chunk = RetrievedChunk(
                doc_id=payload.get('doc_id', 'unknown'),
                chunk_id=payload.get('chunk_id', 0),
                text=payload.get('text', ''),
                source_path=payload.get('source_path', 'unknown'),
                page=payload.get('page'),
                score=result['score']
            )
            chunks.append(chunk)
        
        logger.info(f"✅ Retrieved {len(chunks)} chunks in {retrieval_time:.2f}ms")
        
        return chunks, retrieval_time
    
    def format_context(self, chunks: List[RetrievedChunk]) -> str:
        """
        Format retrieved chunks into a context string.
        
        Args:
            chunks: List of retrieved chunks
            
        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant context found."
        
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source_ref = f"{chunk.doc_id}#chunk{chunk.chunk_id}"
            if chunk.page is not None:
                source_ref += f" (page {chunk.page})"
            
            context_parts.append(
                f"[Source {i}: {source_ref}]\n{chunk.text}\n"
            )
        
        return "\n".join(context_parts)


def get_retriever_service() -> RetrieverService:
    """Get retriever service instance."""
    return RetrieverService()
