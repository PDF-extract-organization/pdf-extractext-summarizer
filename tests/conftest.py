"""Dobles de prueba compartidos por la suite."""

from dataclasses import dataclass

import pytest

from app.application.interfaces.ai_provider import AIProvider, AIResponse
from app.application.interfaces.parameters_source import ParametersSource
from app.application.parameters import SummaryParameters

# Los valores del .env en los tests
DEFAULTS = SummaryParameters(
    model="modelo/env", max_tokens=1000, temperature=0.3, max_prompt_chars=100
)


@dataclass
class Call:
    system_prompt: str
    user_prompt: str
    model: str
    max_tokens: int
    temperature: float
    api_key: str | None


class FakeAIProvider(AIProvider):
    """Proveedor que registra lo que recibe y responde lo que se le diga.

    Si `error` tiene una excepción, la lanza en vez de responder.
    """

    def __init__(
        self,
        content: str = "Resumen de prueba",
        healthy: bool = True,
        error: Exception | None = None,
        truncated: bool = False,
    ):
        self._content = content
        self._healthy = healthy
        self._error = error
        self._truncated = truncated
        self.calls: list[Call] = []

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        api_key: str | None = None,
    ) -> AIResponse:
        self.calls.append(
            Call(system_prompt, user_prompt, model, max_tokens, temperature, api_key)
        )
        if self._error:
            raise self._error
        return AIResponse(
            content=self._content, model=model, tokens_used=42, truncated=self._truncated
        )

    async def health_check(self) -> bool:
        return self._healthy


class FakeParametersSource(ParametersSource):
    """Configuración centralizada en memoria. `None` simula que no responde."""

    def __init__(self, overrides: dict[str, str] | None = None):
        self.overrides = overrides

    async def get_overrides(self) -> dict[str, str] | None:
        return self.overrides


@pytest.fixture
def fake_provider() -> FakeAIProvider:
    return FakeAIProvider()
