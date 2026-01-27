"""
Application settings with Pydantic v2 validation.

Loads configuration from environment variables with sensible defaults.
"""

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: Literal["ollama", "llama_cpp"] = "ollama"
    model_name: str = "llama3.1:8b"
    vision_model: str = "llava:13b"
    host: str = "http://localhost:11434"
    timeout: int = 120
    max_tokens: int = 4096
    temperature: float = 0.1

    # Circuit breaker settings
    failure_threshold: int = 3
    cooldown_seconds: int = 60

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_multiplier: float = 2.0

    # Startup settings
    warmup_on_start: bool = False  # Whether to warm up LLM on app start


class EmbeddingSettings(BaseSettings):
    """Embedding model configuration."""

    model_config = SettingsConfigDict(env_prefix="EMBED_")

    model_name: str = "BAAI/bge-m3"
    dimension: int = 1024
    batch_size: int = 32
    device: str = "cuda"  # "cuda" or "cpu"
    normalize: bool = True


class StorageSettings(BaseSettings):
    """Storage configuration."""

    model_config = SettingsConfigDict(env_prefix="STORAGE_")

    data_dir: Path = Path("data")
    db_name: str = "srg.db"
    faiss_chunks_index: str = "faiss_chunks.bin"
    faiss_items_index: str = "faiss_items.bin"

    # SQLite settings
    pool_size: int = 5
    busy_timeout: int = 30000  # ms

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    @property
    def chunks_index_path(self) -> Path:
        return self.data_dir / self.faiss_chunks_index

    @property
    def items_index_path(self) -> Path:
        return self.data_dir / self.faiss_items_index


class SearchSettings(BaseSettings):
    """Search and RAG configuration."""

    model_config = SettingsConfigDict(env_prefix="SEARCH_")

    # Hybrid search
    rrf_k: int = 60
    faiss_candidates: int = 60
    fts_candidates: int = 60

    # Reranker
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 10

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 50


class ParserSettings(BaseSettings):
    """Invoice parser configuration."""

    model_config = SettingsConfigDict(env_prefix="PARSER_")

    # Template matching
    template_dir: Path = Path("templates/companies")
    template_min_confidence: float = 0.7

    # Table parsing
    min_column_gap: int = 2
    header_search_lines: int = 50

    # Vision fallback
    vision_enabled: bool = True
    vision_min_confidence: float = 0.6


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="API_")

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # Upload limits
    max_upload_size: int = 50 * 1024 * 1024  # 50 MB
    allowed_extensions: list[str] = [".pdf", ".png", ".jpg", ".jpeg"]


class CacheSettings(BaseSettings):
    """Cache configuration."""

    model_config = SettingsConfigDict(env_prefix="CACHE_")

    # Memory cache
    embedding_cache_size: int = 10000
    search_cache_size: int = 1000
    search_cache_ttl: int = 300  # seconds

    # Disk cache
    vision_cache_enabled: bool = True
    vision_cache_dir: Path = Path("data/cache/vision")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SRG Invoice System"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Sub-settings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    parser: ParserSettings = Field(default_factory=ParserSettings)
    api: APISettings = Field(default_factory=APISettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)

    @field_validator("storage", mode="before")
    @classmethod
    def ensure_data_dir(cls, v: Any) -> StorageSettings:
        if isinstance(v, dict):
            settings = StorageSettings(**v)
        else:
            settings = v or StorageSettings()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        return settings


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _settings
    _settings = None
