import os
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()


class EmbeddingService:
    """Service for generating embeddings using BAAI/bge-m3."""
    
    def __init__(self):
        self.model = None
        self.model_name = settings.embedding_model
        self.dimension = settings.embedding_dim
        
    def load_model(self):
        """Load the embedding model."""
        if self.model is not None:
            return
        
        logger.info(f"Loading embedding model: {self.model_name}")
        
        # Set offline mode if configured
        if settings.transformers_offline == "1":
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_DATASETS_OFFLINE"] = "1"
            logger.info("Running in OFFLINE mode")
        
        try:
            self.model = SentenceTransformer(
                self.model_name,
                cache_folder=settings.hf_home
            )
            logger.info(f"✅ Model loaded successfully (dim={self.dimension})")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate normalized embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Normalized 1024-dim embedding vector
        """
        if self.model is None:
            self.load_model()
        
        # Generate embedding
        embedding = self.model.encode(
            text,
            normalize_embeddings=True,  # L2 normalization for cosine similarity
            show_progress_bar=False
        )
        
        # Validate dimension
        assert len(embedding) == self.dimension, \
            f"Expected {self.dimension}-dim vector, got {len(embedding)}"
        
        # `embedding` may be a numpy array, tensor, or plain list.
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return list(embedding)
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate normalized embeddings for a batch of texts.
        
        Args:
            texts: List of input texts
            batch_size: Batch size for encoding
            
        Returns:
            List of normalized embedding vectors
        """
        if self.model is None:
            self.load_model()
        
        logger.info(f"Embedding {len(texts)} texts in batches of {batch_size}")
        
        # Generate embeddings with normalization
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
            batch_size=batch_size
        )
        
        # Validate dimensions
        assert embeddings.shape[1] == self.dimension, \
            f"Expected {self.dimension}-dim vectors, got {embeddings.shape[1]}"
        
        logger.info(f"✅ Generated {len(embeddings)} embeddings")
        
        return embeddings.tolist()


# Global singleton instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
        _embedding_service.load_model()
    return _embedding_service
