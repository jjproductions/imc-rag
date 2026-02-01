from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Qdrant Configuration
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "imc_corpus"
    
    # Embeddings
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    
    # Ollama LLM
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.1:8b-instruct-q4_0"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048
    
    # Retrieval
    top_k: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 100
    
    # Security
    api_key: str = "local-key"
    
    # Offline mode
    hf_datasets_offline: str = "0"
    transformers_offline: str = "0"
    hf_home: str = "/root/.cache/huggingface"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
