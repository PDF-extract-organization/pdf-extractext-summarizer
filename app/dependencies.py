"""Cableado de dependencias. Router y main lo importan; él no importa a ninguno."""

from functools import lru_cache

from app.application.parameters import SummaryParameters
from app.application.services.summary_service import SummaryService
from app.core import Settings
from app.infrastructure.config_parameters_source import ConfigServiceParametersSource
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
        timeout_seconds=settings.request_timeout_seconds,
    )
    # Los del .env: valen cuando config no tiene la clave, no responde o no está
    defaults = SummaryParameters(
        model=settings.openrouter_model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        max_prompt_chars=settings.max_prompt_chars,
    )
    source = (
        ConfigServiceParametersSource(settings.config_url, settings.config_timeout_seconds)
        if settings.config_url.strip()
        else None
    )
    return SummaryService(provider, defaults, source)
