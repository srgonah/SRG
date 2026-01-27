"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "SRG Invoice Processing API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")

    # API
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    RELOAD: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/srg.db"

    # Security
    SECRET_KEY: str = Field(default="change-me-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # LLM
    LLM_PROVIDER: str = Field(default="ollama", pattern="^(ollama|llama_cpp)$")
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    LLAMA_CPP_MODEL_PATH: str = ""

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # Search
    FAISS_INDEX_PATH: str = "./data/faiss_index"
    SEARCH_TOP_K: int = 5
    RERANKER_ENABLED: bool = True

    # Cache
    CACHE_DIR: str = "./data/cache"
    EMBEDDING_CACHE_SIZE: int = 10000
    SEARCH_CACHE_TTL: int = 3600

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return list(v)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
