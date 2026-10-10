"""Dobles de prueba compartidos por la suite."""

import pytest

from app.application.interfaces.ai_provider import AIProvider, AIResponse


class FakeAIProvider(AIProvider):
    """Proveedor que registra lo que recibe y responde lo que se le diga.

    Si `error` tiene una excepción, la lanza en vez de responder.
    """

    def __init__(
        self,
        content: str = "Resumen de prueba",
        healthy: bool = True,
        error: Exception | None = None,
    ):
        self._content = content
        self._healthy = healthy
        self._error = error
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system_prompt: str, user_prompt: str) -> AIResponse:
        self.calls.append((system_prompt, user_prompt))
        if self._error:
            raise self._error
        return AIResponse(content=self._content, model="modelo/fake", tokens_used=42)

    async def health_check(self) -> bool:
        return self._healthy


@pytest.fixture
def fake_provider() -> FakeAIProvider:
    return FakeAIProvider()
