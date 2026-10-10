"""Cableado de dependencias. Router y main lo importan; él no importa a ninguno."""

from functools import lru_cache

from app.application.services.summary_service import SummaryService
from app.core import Settings
from app.infrastructure.openrouter_provider import OpenRouterAIProvider


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_summary_service() -> SummaryService:
    settings = get_settings()
    provider = OpenRouterAIProvider(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_api_url,
        model=settings.openrouter_model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        timeout_seconds=settings.request_timeout_seconds,
    )
    return SummaryService(provider, max_prompt_chars=settings.max_prompt_chars)
