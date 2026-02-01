from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)
from typing import List, Dict, Any, Optional
from app.core.config import get_settings
import logging
import time

logger = logging.getLogger(__name__)

settings = get_settings()


class QdrantService:
    """Service for interacting with Qdrant vector database."""
    
    def __init__(self):
        self.client = None
        self.collection_name = settings.qdrant_collection
        self.vector_size = settings.embedding_dim
        
    def connect(self):
        """Connect to Qdrant and create collection if needed."""
        if self.client is not None:
            return
        
        logger.info(f"Connecting to Qdrant at {settings.qdrant_url}")
        
        # Retry connection with exponential backoff
        max_retries = 10
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.client = QdrantClient(url=settings.qdrant_url)
                logger.info("✅ Connected to Qdrant")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Qdrant connection attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Failed to connect to Qdrant after {max_retries} attempts: {e}")
                    raise
        
        # Create collection if it doesn't exist
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection with cosine distance if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            logger.info(f"Creating collection '{self.collection_name}' (cosine, {self.vector_size}-dim)")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE  # Cosine similarity for normalized vectors
                )
            )
            logger.info("✅ Collection created")
        else:
            logger.info(f"Collection '{self.collection_name}' already exists")
    
    def upsert_points(self, points: List[Dict[str, Any]]) -> int:
        """
        Upsert points to collection with idempotency (skip if hash exists).
        
        Args:
            points: List of dicts with 'id', 'vector', and 'payload'
            
        Returns:
            Number of points actually inserted (excluding duplicates)
        """
        if self.client is None:
            self.connect()
        
        # Check for existing hashes to enable idempotency
        new_points = []
        for point in points:
            point_hash = point['payload'].get('hash')
            if point_hash:
                # Search for existing point with this hash
                search_result = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="hash",
                                match=MatchValue(value=point_hash)
                            )
                        ]
                    ),
                    limit=1
                )
                if not search_result[0]:  # No existing point found
                    new_points.append(point)
            else:
                new_points.append(point)
        
        if not new_points:
            logger.info("All points already exist (idempotent upsert)")
            return 0
        
        # Convert to PointStruct
        qdrant_points = [
            PointStruct(
                id=p['id'],
                vector=p['vector'],
                payload=p['payload']
            )
            for p in new_points
        ]
        
        # Batch upsert
        self.client.upsert(
            collection_name=self.collection_name,
            points=qdrant_points
        )
        
        logger.info(f"✅ Upserted {len(new_points)} points (skipped {len(points) - len(new_points)} duplicates)")
        return len(new_points)
    
    def search(self, query_vector: List[float], top_k: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding (normalized)
            top_k: Number of results to return
            filter_dict: Optional metadata filters
            
        Returns:
            List of results with score and payload
        """
        if self.client is None:
            self.connect()
        
        search_filter = None
        if filter_dict:
            # Build filter from dict (placeholder for future filtering)
            pass
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=search_filter
        )
        
        return [
            {
                'id': result.id,
                'score': result.score,
                'payload': result.payload
            }
            for result in results
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        if self.client is None:
            self.connect()
        
        collection_info = self.client.get_collection(self.collection_name)
        
        # Count documents by source_path
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )
        
        doc_counts = {}
        for point in scroll_result[0]:
            source = point.payload.get('source_path', 'unknown')
            doc_counts[source] = doc_counts.get(source, 0) + 1
        
        return {
            'collection_name': self.collection_name,
            'total_points': collection_info.points_count,
            'vector_dim': self.vector_size,
            'distance': 'cosine',
            'documents': doc_counts
        }
    
    def health_check(self) -> bool:
        """Check if Qdrant is accessible."""
        try:
            if self.client is None:
                self.connect()
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False


# Global singleton instance
_qdrant_service = None


def get_qdrant_service() -> QdrantService:
    """Get or create the global Qdrant service instance."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
        _qdrant_service.connect()
    return _qdrant_service
