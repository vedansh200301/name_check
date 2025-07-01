import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration pulled from environment variables or .env file."""
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "forbid",
    }

    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    openai_model_fast: str = Field(..., description="The 'fast' model for routine tasks.")
    openai_model_smart: str = Field(..., description="The 'smart' model for complex tasks.")
    cache_ttl_seconds: int = Field(60 * 60 * 24 * 7, description="Cache TTL in seconds.")  # default 7 days

    # Path to Jinja2 template that suggests alternative names.
    suggest_template_path: Optional[str] = Field(None, description="Path to Jinja2 template.")


@lru_cache()
def get_settings() -> Settings:
    return Settings() 