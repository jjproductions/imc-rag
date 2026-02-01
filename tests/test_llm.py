import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.llm import OllamaService


@pytest.fixture
def mock_requests():
    """Mock requests library."""
    with patch('app.services.llm.requests') as mock:
        yield mock


def test_ollama_service_initialization():
    """Test service initialization."""
    service = OllamaService()
    
    assert service.base_url == "http://ollama:11434"
    assert service.model == "llama3.1:8b-instruct-q4_0"
    assert service.temperature == 0.2


def test_ollama_health_check_success(mock_requests):
    """Test successful health check."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'models': [{'name': 'llama3.1:8b-instruct-q4_0'}]
    }
    mock_requests.get.return_value = mock_response
    
    service = OllamaService()
    is_healthy = service.health_check()
    
    assert is_healthy is True


def test_ollama_health_check_model_missing(mock_requests):
    """Test health check when model is missing."""
    # Mock tags response without the model
    mock_tags_response = Mock()
    mock_tags_response.status_code = 200
    mock_tags_response.json.return_value = {'models': []}
    
    # Mock pull response
    mock_pull_response = Mock()
    mock_pull_response.iter_lines.return_value = [
        b'{"status": "pulling manifest"}',
        b'{"status": "success"}'
    ]
    
    mock_requests.get.return_value = mock_tags_response
    mock_requests.post.return_value = mock_pull_response
    
    service = OllamaService()
    
    # Should attempt to pull model
    is_healthy = service.health_check()
    
    assert mock_requests.post.called


def test_ollama_generate(mock_requests):
    """Test non-streaming generation."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'response': 'Generated answer text'
    }
    mock_requests.post.return_value = mock_response
    
    service = OllamaService()
    result = service.generate("Test prompt")
    
    assert result == 'Generated answer text'
    mock_requests.post.assert_called_once()


@pytest.mark.asyncio
async def test_ollama_generate_stream(mock_requests):
    """Test streaming generation."""
    # Mock streaming response
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        b'{"response": "Hello"}',
        b'{"response": " world"}',
        b'{"done": true, "eval_count": 2}'
    ]
    mock_requests.post.return_value = mock_response
    
    service = OllamaService()
    
    chunks = []
    async for chunk in service.generate_stream("Test prompt"):
        chunks.append(chunk)
    
    assert len(chunks) == 3
    assert chunks[0]['response'] == 'Hello'
    assert chunks[1]['response'] == ' world'
    assert chunks[2]['done'] is True


@pytest.mark.asyncio
async def test_ollama_chat_stream_openai_format(mock_requests):
    """Test OpenAI-compatible streaming."""
    # Mock streaming response
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        b'{"response": "Test"}',
        b'{"response": " response"}',
        b'{"done": true}'
    ]
    mock_requests.post.return_value = mock_response
    
    service = OllamaService()
    messages = [
        {"role": "user", "content": "Hello"}
    ]
    
    chunks = []
    async for chunk in service.chat_stream_openai(messages):
        chunks.append(chunk)
    
    # Should have token chunks + final [DONE]
    assert len(chunks) > 0
    assert any('[DONE]' in chunk for chunk in chunks)


def test_messages_to_prompt():
    """Test message list conversion to prompt."""
    service = OllamaService()
    
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"}
    ]
    
    prompt = service._messages_to_prompt(messages)
    
    assert "System: You are helpful" in prompt
    assert "User: Hello" in prompt
    assert "Assistant: Hi there" in prompt
    assert prompt.endswith("Assistant: ")
