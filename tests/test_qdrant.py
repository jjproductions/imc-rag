import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.qdrant_client import QdrantService


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client."""
    with patch('app.services.qdrant_client.QdrantClient') as mock:
        client_instance = Mock()
        
        # Mock get_collections
        mock_collection = Mock()
        mock_collection.name = "test_collection"
        client_instance.get_collections.return_value = Mock(collections=[])
        
        # Mock create_collection
        client_instance.create_collection.return_value = None
        
        # Mock upsert
        client_instance.upsert.return_value = None
        
        # Mock search
        mock_result = Mock()
        mock_result.id = "test_id"
        mock_result.score = 0.95
        mock_result.payload = {"text": "test", "doc_id": "doc1"}
        client_instance.search.return_value = [mock_result]
        
        # Mock scroll for idempotency check
        client_instance.scroll.return_value = ([], None)
        
        # Mock get_collection
        mock_collection_info = Mock()
        mock_collection_info.points_count = 100
        client_instance.get_collection.return_value = mock_collection_info
        
        mock.return_value = client_instance
        yield client_instance


def test_qdrant_service_initialization():
    """Test service initialization."""
    service = QdrantService()
    
    assert service.client is None
    assert service.collection_name == "imc_corpus"
    assert service.vector_size == 1024


def test_qdrant_connect(mock_qdrant_client):
    """Test connection to Qdrant."""
    service = QdrantService()
    service.connect()
    
    assert service.client is not None
    mock_qdrant_client.create_collection.assert_called_once()


def test_qdrant_upsert_points(mock_qdrant_client):
    """Test upserting points."""
    service = QdrantService()
    service.client = mock_qdrant_client
    
    points = [
        {
            'id': 'test_1',
            'vector': [0.1] * 1024,
            'payload': {
                'text': 'Test text',
                'doc_id': 'doc1',
                'hash': 'abc123'
            }
        }
    ]
    
    inserted = service.upsert_points(points)
    
    assert inserted == 1
    mock_qdrant_client.upsert.assert_called_once()


def test_qdrant_search(mock_qdrant_client):
    """Test vector search."""
    service = QdrantService()
    service.client = mock_qdrant_client
    
    query_vector = [0.2] * 1024
    results = service.search(query_vector, top_k=5)
    
    assert len(results) == 1
    assert results[0]['score'] == 0.95
    assert 'payload' in results[0]
    
    mock_qdrant_client.search.assert_called_once()


def test_qdrant_health_check(mock_qdrant_client):
    """Test health check."""
    service = QdrantService()
    service.client = mock_qdrant_client
    
    is_healthy = service.health_check()
    
    assert is_healthy is True
    mock_qdrant_client.get_collections.assert_called()


def test_qdrant_get_stats(mock_qdrant_client):
    """Test statistics retrieval."""
    service = QdrantService()
    service.client = mock_qdrant_client
    
    # Mock scroll for document counting
    mock_point = Mock()
    mock_point.payload = {'source_path': '/docs/test.pdf'}
    mock_qdrant_client.scroll.return_value = ([mock_point], None)
    
    stats = service.get_stats()
    
    assert stats['collection_name'] == 'imc_corpus'
    assert stats['total_points'] == 100
    assert stats['vector_dim'] == 1024
    assert stats['distance'] == 'cosine'
    assert isinstance(stats['documents'], dict)


def test_qdrant_idempotent_upsert(mock_qdrant_client):
    """Test idempotent upsert skips duplicates."""
    service = QdrantService()
    service.client = mock_qdrant_client
    
    # Mock scroll to return existing point (duplicate)
    mock_existing = Mock()
    mock_qdrant_client.scroll.return_value = ([mock_existing], None)
    
    points = [
        {
            'id': 'test_1',
            'vector': [0.1] * 1024,
            'payload': {'text': 'Test', 'hash': 'duplicate_hash'}
        }
    ]
    
    inserted = service.upsert_points(points)
    
    # Should skip duplicate
    assert inserted == 0
    mock_qdrant_client.upsert.assert_not_called()
