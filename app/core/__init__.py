"""Configuración leída de variables de entorno o del .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_api_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free"

    max_prompt_chars: int = 12000
    max_tokens: int = 1024
    temperature: float = 0.3
    request_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
