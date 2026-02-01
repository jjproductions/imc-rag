import requests
import json
from typing import AsyncGenerator, Optional, Dict, Any
from app.core.config import get_settings
import logging
import time

logger = logging.getLogger(__name__)

settings = get_settings()


class OllamaService:
    """Service for interacting with Ollama LLM."""
    
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        
    def health_check(self) -> bool:
        """Check if Ollama is accessible and model is available."""
        try:
            # Check if service is up
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                return False
            
            # Check if model is available
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            
            # Extract base model name (before colon)
            base_model = self.model.split(':')[0]
            available = any(base_model in name for name in model_names)
            
            if not available:
                logger.warning(f"Model {self.model} not found. Available: {model_names}")
                logger.info(f"Attempting to pull model {self.model}...")
                self._pull_model()
            
            return True
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    def _pull_model(self):
        """Pull the model from Ollama registry."""
        try:
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model},
                stream=True,
                timeout=600
            )
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    status = data.get('status', '')
                    if 'pulling' in status.lower():
                        logger.info(f"Pulling model: {status}")
            
            logger.info(f"✅ Model {self.model} pulled successfully")
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            raise
    
    def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        """
        Generate a non-streaming response.
        
        Args:
            prompt: Input prompt
            temperature: Override default temperature
            
        Returns:
            Generated text
        """
        temp = temperature if temperature is not None else self.temperature
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": self.max_tokens
            }
        }
        
        logger.info(f"Generating response with {self.model} (temp={temp})")
        
        start_time = time.time()
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=120
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
        
        result = response.json()
        elapsed = time.time() - start_time
        
        logger.info(f"✅ Generated response in {elapsed:.2f}s")
        
        return result.get('response', '')
    
    async def generate_stream(
        self,
        prompt: str,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate a streaming response (native Ollama format).
        
        Args:
            prompt: Input prompt
            temperature: Override default temperature
            
        Yields:
            Dicts with 'response' field containing token deltas
        """
        temp = temperature if temperature is not None else self.temperature
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temp,
                "num_predict": self.max_tokens
            }
        }
        
        logger.info(f"Streaming response with {self.model} (temp={temp})")
        
        start_time = time.time()
        first_token_time = None
        token_count = 0
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=120
            )
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    
                    if first_token_time is None:
                        first_token_time = time.time()
                    
                    if 'response' in data:
                        token_count += 1
                        yield data
                    
                    if data.get('done', False):
                        total_time = time.time() - start_time
                        ttft = (first_token_time - start_time) * 1000 if first_token_time else 0
                        
                        logger.info(
                            f"✅ Stream complete: {token_count} tokens in {total_time:.2f}s "
                            f"(TTFT: {ttft:.2f}ms)"
                        )
                        
                        # Yield final metadata
                        yield {
                            'done': True,
                            'total_duration': total_time * 1e9,  # nanoseconds
                            'prompt_eval_count': data.get('prompt_eval_count', 0),
                            'eval_count': token_count
                        }
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise
    
    async def chat_stream_openai(
        self,
        messages: list,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response in OpenAI format.
        
        Args:
            messages: List of chat messages
            temperature: Override default temperature
            
        Yields:
            SSE-formatted strings compatible with OpenAI API
        """
        # Convert messages to prompt
        prompt = self._messages_to_prompt(messages)
        
        # Stream from Ollama
        async for chunk in self.generate_stream(prompt, temperature):
            if chunk.get('done'):
                # Send final message
                final_chunk = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": self.model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            else:
                # Send token delta
                token = chunk.get('response', '')
                if token:
                    delta_chunk = {
                        "id": f"chatcmpl-{int(time.time())}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": self.model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": token},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(delta_chunk)}\n\n"
    
    def _messages_to_prompt(self, messages: list) -> str:
        """Convert chat messages to a prompt string."""
        prompt_parts = []
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'system':
                prompt_parts.append(f"System: {content}\n")
            elif role == 'user':
                prompt_parts.append(f"User: {content}\n")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}\n")
        
        prompt_parts.append("Assistant: ")
        return "\n".join(prompt_parts)


# Global singleton
_ollama_service = None


def get_ollama_service() -> OllamaService:
    """Get or create the global Ollama service instance."""
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
        
        # Wait for Ollama to be ready
        max_retries = 10
        retry_delay = 3
        
        for attempt in range(max_retries):
            if _ollama_service.health_check():
                break
            if attempt < max_retries - 1:
                logger.warning(f"Ollama not ready, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
        
    return _ollama_service
