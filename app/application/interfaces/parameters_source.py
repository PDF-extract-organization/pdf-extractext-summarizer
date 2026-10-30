"""Puerto de la configuración centralizada de la que salen los parámetros del resumen."""

from abc import ABC, abstractmethod


class ParametersSource(ABC):
    @abstractmethod
    async def get_overrides(self) -> dict[str, str] | None:
        """Los valores configurados, por nombre (`max_tokens`, `model`...), como texto.

        None si la fuente no responde: quien llama usa entonces el .env. Nunca lanza.
        """
