import pytest
from unittest.mock import Mock, patch
from app.services.embeddings import EmbeddingService


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer to avoid loading real model."""
    with patch('app.services.embeddings.SentenceTransformer') as mock:
        # Mock encode method to return 1024-dim vector
        mock_model = Mock()
        mock_model.encode.return_value = [0.1] * 1024
        mock.return_value = mock_model
        yield mock


def test_embedding_service_initialization():
    """Test embedding service initialization."""
    service = EmbeddingService()
    
    assert service.model is None  # Not loaded yet
    assert service.dimension == 1024
    assert service.model_name == "BAAI/bge-m3"


def test_embedding_service_load_model(mock_sentence_transformer):
    """Test model loading."""
    service = EmbeddingService()
    service.load_model()
    
    assert service.model is not None
    mock_sentence_transformer.assert_called_once()


def test_embed_text_shape(mock_sentence_transformer):
    """Test that embeddings have correct shape (1024-dim)."""
    service = EmbeddingService()
    
    # Mock to return correct dimension
    mock_model = Mock()
    import numpy as np
    mock_model.encode.return_value = np.random.rand(1024)
    service.model = mock_model
    
    embedding = service.embed_text("Test text")
    
    assert len(embedding) == 1024
    assert isinstance(embedding, list)
    assert all(isinstance(x, float) for x in embedding)


def test_embed_text_normalization(mock_sentence_transformer):
    """Test that normalize_embeddings=True is used."""
    service = EmbeddingService()
    service.load_model()
    
    service.embed_text("Test text")
    
    # Verify normalize_embeddings was set
    call_kwargs = service.model.encode.call_args[1]
    assert call_kwargs.get('normalize_embeddings') is True


def test_embed_batch(mock_sentence_transformer):
    """Test batch embedding."""
    service = EmbeddingService()
    
    # Mock batch encoding
    mock_model = Mock()
    import numpy as np
    mock_model.encode.return_value = np.random.rand(3, 1024)  # 3 texts, 1024 dims
    service.model = mock_model
    
    texts = ["Text 1", "Text 2", "Text 3"]
    embeddings = service.embed_batch(texts, batch_size=32)
    
    assert len(embeddings) == 3
    assert all(len(emb) == 1024 for emb in embeddings)
    
    # Verify batch size was passed
    call_kwargs = service.model.encode.call_args[1]
    assert call_kwargs.get('batch_size') == 32


def test_embed_text_auto_loads_model(mock_sentence_transformer):
    """Test that embed_text loads model if not loaded."""
    service = EmbeddingService()
    assert service.model is None
    
    # Mock the encode to return proper dimension
    import numpy as np
    mock_model = Mock()
    mock_model.encode.return_value = np.random.rand(1024)
    mock_sentence_transformer.return_value = mock_model
    
    service.embed_text("Test")
    
    # Model should be loaded now
    assert service.model is not None


def test_embedding_dimension_validation():
    """Test that dimension is validated."""
    service = EmbeddingService()
    
    # Mock model that returns wrong dimension
    mock_model = Mock()
    mock_model.encode.return_value = [0.1] * 512  # Wrong dimension!
    service.model = mock_model
    
    with pytest.raises(AssertionError):
        service.embed_text("Test")
