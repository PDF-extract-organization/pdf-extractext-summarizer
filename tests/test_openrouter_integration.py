"""Prueba contra OpenRouter real.

Marcada como `integration`: no corre por defecto (`uv run pytest`) y se salta sola
si no hay OPENROUTER_API_KEY. Ejecutar con `uv run pytest -m integration`.
"""

import pytest

from app.core import Settings
from app.infrastructure.openrouter_provider import OpenRouterAIProvider

settings = Settings()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not settings.openrouter_api_key.strip(), reason="sin OPENROUTER_API_KEY"
    ),
]


def provider() -> OpenRouterAIProvider:
    return OpenRouterAIProvider(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_api_url,
        timeout_seconds=settings.request_timeout_seconds,
    )


async def test_health_check_real():
    assert await provider().health_check() is True


async def test_completion_real_devuelve_texto():
    result = await provider().complete(
        "Responde solo con la palabra pedida.",
        "Escribe la palabra: hola",
        model=settings.openrouter_model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )

    assert result.content.strip()
