"""Puerto del proveedor de IA y sus errores.

Los errores son del puerto, no de httpx: la capa de aplicación no conoce el transporte.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class MissingAPIKeyError(Exception):
    """No hay API key configurada para el proveedor."""


class AIProviderError(Exception):
    """El proveedor falló, no respondió o devolvió algo inesperado."""


class AITimeoutError(Exception):
    """El proveedor tardó más de lo permitido."""


class AIRateLimitError(Exception):
    """El proveedor rechazó la petición por exceso de peticiones."""

    def __init__(self, retry_after: str | None = None):
        super().__init__("Se alcanzó el límite de peticiones del proveedor de IA.")
        self.retry_after = retry_after


@dataclass
class AIResponse:
    content: str
    model: str
    tokens_used: int | None


class AIProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AIResponse:
        """Envía los prompts al modelo y devuelve su respuesta.

        Los parámetros llegan en cada llamada: pueden cambiar entre un resumen y otro.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """True si el proveedor está configurado y responde."""
